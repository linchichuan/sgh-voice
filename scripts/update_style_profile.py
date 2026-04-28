"""
從 history 最近 N 筆 final_text 分析使用者語氣，產出 1-2 段描述寫回 dictionary.style_profile。
這是個人化後處理的「高層描述」，與 few-shot 的「具體範例」互補。

用法：
  python3 scripts/update_style_profile.py              # dry-run 印出
  python3 scripts/update_style_profile.py --apply      # 寫入 dictionary
  python3 scripts/update_style_profile.py --n 200      # 用最近 200 筆（預設 100）

排程（launchd 週日 02:00 自動更新）：見 scripts/launchd/com.shingihou.style-profile.plist
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import load_config, save_dictionary
from memory import Memory


_PROFILE_PROMPT = (
    "你是文體分析助理。以下是使用者最近的語音輸入轉寫結果（已經過後處理，"
    "代表使用者預期的書寫風格）。請輸出 1~2 段、總共不超過 200 字的「使用者語氣特徵描述」，"
    "供下游 LLM 在後處理時當 system prompt 提示。\n\n"
    "請涵蓋以下面向（有則寫，沒有跳過）：\n"
    "- 句子長短偏好（短切多 / 長句連綴）\n"
    "- 標點習慣（逗號密集？句號偏少？慣用問號/驚嘆號？）\n"
    "- 語氣（口語 / 書面 / 商務 / 技術）\n"
    "- 中英日混排習慣（是否常夾英文技術詞？英文是否半形？）\n"
    "- 慣用句式或口頭禪（「對吧」「就是說」之類）\n"
    "- 領域用詞特徵（醫療 / 技術 / 商務）\n\n"
    "嚴格要求：\n"
    "- 只輸出描述本身，不要任何前綴（不要『根據分析』『以下是』『使用者偏好』之類的開場）。\n"
    "- 用繁體中文。\n"
    "- 把這段描述當作後續 LLM 的 system prompt 一部分，所以要寫成「指令式」的風格指南，例：\n"
    "  「偏好短句、常夾英文技術詞（如 prompt、API），中文用全形標點、英文用半形空格分隔。」\n"
)


def _call_llm(config, prompt, content):
    """以主管線同樣的 fallback 鏈呼叫 LLM。"""
    full = f"{prompt}\n\n=== 使用者最近輸入樣本 ===\n{content}"

    # Groq（最快、便宜）
    if config.get("groq_api_key"):
        try:
            import openai
            client = openai.OpenAI(base_url="https://api.groq.com/openai/v1",
                                    api_key=config["groq_api_key"], timeout=30)
            resp = client.chat.completions.create(
                model=config.get("groq_model", "llama-3.3-70b-versatile"),
                messages=[{"role": "user", "content": full}],
                temperature=0.2, max_tokens=400,
            )
            return resp.choices[0].message.content.strip(), "groq"
        except Exception as e:
            print(f"⚠️  Groq 失敗: {e}")

    if config.get("anthropic_api_key"):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=config["anthropic_api_key"], timeout=30)
            resp = client.messages.create(
                model=config.get("claude_model", "claude-haiku-4-5-20251001"),
                max_tokens=400, temperature=0.2,
                messages=[{"role": "user", "content": full}],
            )
            return resp.content[0].text.strip(), "claude"
        except Exception as e:
            print(f"⚠️  Claude 失敗: {e}")

    if config.get("openai_api_key"):
        try:
            import openai
            client = openai.OpenAI(api_key=config["openai_api_key"], timeout=30)
            resp = client.chat.completions.create(
                model=config.get("openai_model", "gpt-4o-mini"),
                messages=[{"role": "user", "content": full}],
                temperature=0.2, max_tokens=400,
            )
            return resp.choices[0].message.content.strip(), "openai"
        except Exception as e:
            print(f"⚠️  OpenAI 失敗: {e}")

    return None, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="實際寫入 dictionary.style_profile")
    parser.add_argument("--n", type=int, default=100, help="採樣最近 N 筆（預設 100）")
    parser.add_argument("--min-chars", type=int, default=15, help="單筆最少字元（過濾極短紀錄）")
    args = parser.parse_args()

    config = load_config()
    mem = Memory()

    samples = []
    for h in reversed(mem.history):
        text = (h.get("final_text") or "").strip()
        if len(text) < args.min_chars:
            continue
        samples.append(text)
        if len(samples) >= args.n:
            break

    if len(samples) < 10:
        print(f"❌ 樣本不足（{len(samples)} 筆，需 ≥10）")
        return 1

    sample_text = "\n".join(f"- {s}" for s in samples)
    print(f"📊 採樣 {len(samples)} 筆（總長 {len(sample_text)} 字）")
    print("⏳ 呼叫 LLM 分析...")

    profile, engine = _call_llm(config, _PROFILE_PROMPT, sample_text)
    if not profile:
        print("❌ 所有 LLM 都失敗")
        return 1

    profile = profile.strip().strip('"').strip("'")
    print(f"\n=== 新 Profile（by {engine}）===\n{profile}\n")
    print(f"=== 舊 Profile ===\n{mem.get_style_profile()}\n")

    if not args.apply:
        print("💡 dry-run。確認無誤加 --apply 寫入。")
        return 0

    mem.update_style_profile(profile)
    print(f"✅ 已寫入 dictionary.style_profile（{len(profile)} 字）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
