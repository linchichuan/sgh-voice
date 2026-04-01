#!/usr/bin/env python3
"""
test_prompt_quality.py — _DICTATE_SYSTEM prompt 品質自動測試

品質工程師自動化測試腳本：
- 5 個多語樣本（中文/日文/英文/混合/長文）送入 LLM
- 依據 7 條品質規則驗證輸出
- 支援所有 5 引擎（Groq/OpenRouter/Claude/OpenAI/Ollama）
- 輸出 Markdown 報告到 test/results/PROMPT_QUALITY.md

用法：
  python3 scripts/test_prompt_quality.py [--engine groq|openrouter|claude|openai|ollama]
"""

import json
import os
import re
import sys
import time
from datetime import datetime

# 加入專案根目錄
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import load_config

# ─── 測試樣本（模擬 Whisper STT 原始輸出）───

SAMPLES = [
    {
        "id": "zh_filler",
        "lang": "繁體中文",
        "description": "含填充詞的中文口語",
        "input": "那個就是說我們公司嗯最近在做一個新的那個產品然後就是需要跟日本的供應商聯繫一下就是看看他們的報價",
        "checks": ["no_filler", "no_translation", "output_only"],
    },
    {
        "id": "ja_keigo",
        "lang": "日本語",
        "description": "含口語的日文商務對話",
        "input": "えーとあのですね、山田さんに連絡したいんですけど、明日のミーティングの件で、何に宜しくお願いしますって伝えてもらえますか",
        "checks": ["no_filler", "no_translation", "keigo_upgrade", "output_only"],
    },
    {
        "id": "en_basic",
        "lang": "English",
        "description": "含 filler 的英文語音",
        "input": "um so basically I wanted to uh discuss the quarterly report with the team and um see if we can get the numbers by Friday",
        "checks": ["no_filler", "no_translation", "output_only"],
    },
    {
        "id": "mixed_trilingual",
        "lang": "中日英混合",
        "description": "三語混合的日常商務語音",
        "input": "えーと林さん、那個关于KusuriJapan的order、我想確認一下shipping date是不是下周的水曜日、麻煩你check一下",
        "checks": ["no_filler", "no_translation", "preserve_mixed", "output_only"],
    },
    {
        "id": "long_structured",
        "lang": "中日混合長文",
        "description": "需要結構化排版的多重點長文",
        "input": (
            "那個就是我整理一下今天會議的重點好了，第一個是新義豊的網站需要更新，"
            "包括首頁的banner跟產品頁面的價格，第二個是物流的部分冷蔵便的クールボックス要多訂20個，"
            "第三個是下個月的東京出差日程要確認，大概是15號到18號，"
            "然後最後一個是林さん提到的VIZZ的新包裝設計要在月底前完成，えーと大概就這些"
        ),
        "checks": ["no_filler", "no_translation", "structured", "output_only"],
    },
]

# ─── 品質檢查函數 ───

FILLER_PATTERNS = [
    r"那個",
    r"就是說",
    r"就是",
    r"嗯",
    r"えーと",
    r"あの(ですね)?",
    r"\bum\b",
    r"\buh\b",
    r"\bbasically\b",
    r"\bso\b(?=\s+(basically|I|we))",
]

HALLUCINATION_MARKERS = [
    "好的", "沒問題", "了解", "為您", "以下是", "I appreciate", "Sure",
    "以下は", "承知しました", "Here is", "Here's the",
    "我來幫您", "讓我", "根據您的",
]

EXPLANATION_PATTERNS = [
    r"(?:修正|修改|調整|翻譯|整理)(?:了|如下|結果|後)",
    r"(?:以下|下記)(?:為|は|is)",
    r"(?:I've|I have) (?:corrected|revised|edited)",
    r"※|注[：:]|備注",
]


def check_no_filler(output, sample):
    """檢查輸出不含填充詞"""
    found = []
    for pat in FILLER_PATTERNS:
        matches = re.findall(pat, output, re.IGNORECASE)
        if matches:
            found.extend(matches)
    return (len(found) == 0, f"殘留填充詞: {found}" if found else "✓ 無填充詞")


def check_no_translation(output, sample):
    """檢查 LLM 沒有翻譯原文（語言應保持一致）"""
    input_text = sample["input"]
    lang = sample["lang"]

    # 中文輸入不應被翻成日文/英文
    if lang == "繁體中文":
        ja_ratio = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF]', output)) / max(len(output), 1)
        if ja_ratio > 0.3:
            return (False, f"中文被翻成日文 (假名比例 {ja_ratio:.0%})")

    # 日文輸入不應被翻成中文
    if lang == "日本語":
        zh_chars = len(re.findall(r'[\u4e00-\u9fff]', output))
        ja_chars = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF]', output))
        if zh_chars > 0 and ja_chars == 0:
            return (False, "日文被翻成中文")

    # 英文不應被翻
    if lang == "English":
        non_ascii = len(re.findall(r'[^\x00-\x7F]', output))
        if non_ascii > len(output) * 0.1:
            return (False, f"英文被翻譯 (非 ASCII 比例 {non_ascii/len(output):.0%})")

    return (True, "✓ 語言一致")


def check_output_only(output, sample):
    """檢查輸出只有修正後文字，無解釋、無前言"""
    # 檢查幻覺開頭
    for marker in HALLUCINATION_MARKERS:
        if output.startswith(marker):
            return (False, f"含幻覺前綴: '{marker}...'")

    # 檢查解釋性文字
    for pat in EXPLANATION_PATTERNS:
        if re.search(pat, output):
            return (False, f"含解釋文字: {re.search(pat, output).group()}")

    return (True, "✓ 純淨輸出")


def check_keigo_upgrade(output, sample):
    """檢查日文敬語是否提升"""
    # 口語殘留檢查
    casual_patterns = [r"んですけど", r"もらえますか"]
    has_casual = any(re.search(p, output) for p in casual_patterns)
    # 敬語標記檢查
    keigo_patterns = [r"いただ[きけ]", r"くださ[いる]", r"ございます", r"承ります", r"何卒"]
    has_keigo = any(re.search(p, output) for p in keigo_patterns)

    if has_keigo:
        return (True, "✓ 敬語提升")
    elif not has_casual:
        return (True, "✓ 口語已改善（非正式敬語）")
    else:
        return (False, "口語未改善為商務敬語")


def check_preserve_mixed(output, sample):
    """檢查三語混合是否保持"""
    has_zh = bool(re.search(r'[\u4e00-\u9fff]', output))
    has_ja = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF]', output))
    has_en = bool(re.search(r'[A-Za-z]{2,}', output))

    preserved = []
    if has_zh: preserved.append("中")
    if has_ja: preserved.append("日")
    if has_en: preserved.append("英")

    if len(preserved) >= 2:
        return (True, f"✓ 保留 {'/'.join(preserved)} 混合")
    else:
        return (False, f"語言被統一化，僅剩: {'/'.join(preserved)}")


def check_structured(output, sample):
    """檢查長文是否有結構化排版"""
    has_bullets = bool(re.search(r'[•\-\d][\.、）)]?\s', output))
    has_headers = bool(re.search(r'【.+】|#{1,3}\s', output))
    has_newlines = output.count('\n') >= 2

    if has_bullets or has_headers:
        return (True, "✓ 有結構化排版（條列/標題）")
    elif has_newlines:
        return (True, "✓ 有段落分隔")
    else:
        return (False, "長文未結構化")


CHECK_FUNCTIONS = {
    "no_filler": check_no_filler,
    "no_translation": check_no_translation,
    "output_only": check_output_only,
    "keigo_upgrade": check_keigo_upgrade,
    "preserve_mixed": check_preserve_mixed,
    "structured": check_structured,
}

# ─── LLM 呼叫 ───

def call_llm(engine, config, system_prompt, user_text):
    """呼叫指定引擎的 LLM"""
    import openai as openai_lib

    t0 = time.time()

    if engine == "groq":
        client = openai_lib.OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=config.get("groq_api_key"),
            timeout=15.0,
        )
        model = config.get("groq_model", "llama-3.3-70b-versatile")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
            temperature=0.3,
            max_tokens=2048,
        )
        result = resp.choices[0].message.content.strip()

    elif engine == "openrouter":
        client = openai_lib.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=config.get("openrouter_api_key"),
            timeout=20.0,
        )
        model = config.get("openrouter_model", "qwen/qwen3-30b-a3b:free")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
            temperature=0.3,
            max_tokens=2048,
            extra_headers={"HTTP-Referer": "https://shingihou.com", "X-Title": "SGH Voice"},
        )
        result = resp.choices[0].message.content.strip()

    elif engine == "claude":
        import anthropic
        client = anthropic.Anthropic(api_key=config.get("anthropic_api_key"), timeout=15.0)
        model = config.get("claude_model", "claude-3-5-haiku-20241022")
        resp = client.messages.create(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_text}],
            max_tokens=2048,
            temperature=0.3,
        )
        result = resp.content[0].text.strip()

    elif engine == "openai":
        client = openai_lib.OpenAI(api_key=config.get("openai_api_key"), timeout=15.0)
        model = config.get("openai_model", "gpt-4o")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
            temperature=0.3,
            max_tokens=2048,
        )
        result = resp.choices[0].message.content.strip()

    elif engine == "ollama":
        client = openai_lib.OpenAI(
            base_url="http://127.0.0.1:11434/v1",
            api_key="ollama",
            timeout=15.0,
        )
        model = config.get("local_llm_model", "qwen3.5:latest")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
            temperature=0.1,
            max_tokens=1024,
        )
        result = resp.choices[0].message.content.strip()

    else:
        raise ValueError(f"未知引擎: {engine}")

    # 清除 <think> 標籤（reasoning models）
    result = re.sub(r'<think>[\s\S]*?</think>|<think>[\s\S]*$', '', result).strip()

    latency = time.time() - t0
    return result, latency, model


def detect_available_engine(config):
    """偵測可用引擎，優先順序: groq → openrouter → claude → openai → ollama"""
    preferred = config.get("preferred_llm_engine", "groq")
    order = [preferred] + [e for e in ["groq", "openrouter", "claude", "openai", "ollama"] if e != preferred]
    key_map = {
        "groq": "groq_api_key",
        "openrouter": "openrouter_api_key",
        "claude": "anthropic_api_key",
        "openai": "openai_api_key",
        "ollama": None,
    }
    for eng in order:
        key_field = key_map.get(eng)
        if key_field is None:
            return eng  # ollama 不需要 key
        if config.get(key_field):
            return eng
    return None


def get_system_prompt(config):
    """取得 _DICTATE_SYSTEM（從 transcriber.py 匯入）"""
    from transcriber import Transcriber
    return Transcriber._DICTATE_SYSTEM


# ─── 主測試流程 ───

def run_tests(engine=None):
    config = load_config()

    if engine is None:
        engine = detect_available_engine(config)
    if engine is None:
        print("❌ 沒有可用的 LLM 引擎（請設定至少一個 API Key）")
        sys.exit(1)

    system_prompt = get_system_prompt(config)
    print(f"🧪 Prompt 品質測試")
    print(f"   引擎: {engine}")
    print(f"   Prompt 長度: {len(system_prompt)} 字元")
    print(f"   測試樣本: {len(SAMPLES)} 個")
    print("=" * 60)

    results = []

    for sample in SAMPLES:
        print(f"\n📝 [{sample['id']}] {sample['description']}")
        print(f"   輸入: {sample['input'][:60]}...")

        try:
            output, latency, model = call_llm(engine, config, system_prompt, sample["input"])
            print(f"   輸出: {output[:80]}...")
            print(f"   延遲: {latency:.2f}s | 模型: {model}")

            # 執行品質檢查
            check_results = []
            for check_name in sample["checks"]:
                fn = CHECK_FUNCTIONS.get(check_name)
                if fn:
                    passed, msg = fn(output, sample)
                    check_results.append({"name": check_name, "passed": passed, "message": msg})
                    status = "✅" if passed else "❌"
                    print(f"   {status} {msg}")

            all_passed = all(c["passed"] for c in check_results)
            results.append({
                "sample": sample,
                "output": output,
                "latency": latency,
                "model": model,
                "checks": check_results,
                "passed": all_passed,
            })

        except Exception as e:
            print(f"   ❌ LLM 呼叫失敗: {e}")
            results.append({
                "sample": sample,
                "output": None,
                "latency": 0,
                "model": "N/A",
                "checks": [],
                "passed": False,
                "error": str(e),
            })

    # ─── 產生報告 ───
    generate_report(engine, system_prompt, results)
    return results


def generate_report(engine, system_prompt, results):
    """產生 Markdown 報告"""
    report_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test", "results")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "PROMPT_QUALITY.md")

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    total_checks = sum(len(r["checks"]) for r in results)
    passed_checks = sum(sum(1 for c in r["checks"] if c["passed"]) for r in results)
    avg_latency = sum(r["latency"] for r in results) / max(total, 1)

    lines = [
        f"# _DICTATE_SYSTEM Prompt 品質測試報告",
        f"",
        f"- **測試時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **LLM 引擎**: {engine}",
        f"- **模型**: {results[0]['model'] if results else 'N/A'}",
        f"- **Prompt 長度**: {len(system_prompt)} 字元",
        f"- **平均延遲**: {avg_latency:.2f}s",
        f"",
        f"## 總覽",
        f"",
        f"| 指標 | 結果 |",
        f"|------|------|",
        f"| 樣本通過率 | {passed}/{total} ({passed/total*100:.0f}%) |",
        f"| 檢查通過率 | {passed_checks}/{total_checks} ({passed_checks/total_checks*100:.0f}%) |",
        f"| 平均延遲 | {avg_latency:.2f}s |",
        f"",
        f"## 測試明細",
        f"",
    ]

    for r in results:
        s = r["sample"]
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        lines.append(f"### [{s['id']}] {s['description']} — {status}")
        lines.append(f"")
        lines.append(f"**語言**: {s['lang']} | **延遲**: {r['latency']:.2f}s")
        lines.append(f"")
        lines.append(f"**輸入**:")
        lines.append(f"```")
        lines.append(s["input"])
        lines.append(f"```")
        lines.append(f"")

        if r.get("error"):
            lines.append(f"**錯誤**: {r['error']}")
        else:
            lines.append(f"**輸出**:")
            lines.append(f"```")
            lines.append(r["output"])
            lines.append(f"```")
            lines.append(f"")
            lines.append(f"| 檢查項目 | 結果 |")
            lines.append(f"|----------|------|")
            for c in r["checks"]:
                icon = "✅" if c["passed"] else "❌"
                lines.append(f"| {c['name']} | {icon} {c['message']} |")

        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    # 寫入報告
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n{'='*60}")
    print(f"📊 報告已產生: {report_path}")
    print(f"   樣本通過: {passed}/{total} | 檢查通過: {passed_checks}/{total_checks}")
    print(f"   平均延遲: {avg_latency:.2f}s")

    if passed < total:
        print(f"   ⚠️ 有 {total - passed} 個樣本未通過！")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="測試 _DICTATE_SYSTEM prompt 品質")
    parser.add_argument("--engine", choices=["groq", "openrouter", "claude", "openai", "ollama"],
                        help="指定 LLM 引擎（預設自動偵測）")
    args = parser.parse_args()
    run_tests(engine=args.engine)
