#!/usr/bin/env python3
"""
dict-update.py — 業界辭書自動擴充（本機版）
定期從公開資料源（PMDA 新藥頁面）抓新術語，寫入 ~/.voice-input/dictionary.json。

用法：
    # 手動執行
    python3 scripts/dict-update.py

    # launchd 排程（每週日 03:00）
    launchctl load ~/Library/LaunchAgents/com.shingihou.dict-update.plist

    # 乾跑（只顯示結果，不寫入）
    python3 scripts/dict-update.py --dry-run
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

# 確保專案 root 在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = Path.home() / ".voice-input"
DICT_FILE = DATA_DIR / "dictionary.json"
LOG_FILE = DATA_DIR / "dict-update.log"


def log(msg: str):
    """寫 log 到 ~/.voice-input/dict-update.log"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} | {msg}\n")
    print(f"  {msg}")


def notify(title: str, body: str):
    """macOS 原生通知"""
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{body}" with title "{title}"'],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass


def load_dictionary() -> dict:
    """載入現有辭書"""
    if DICT_FILE.exists():
        with open(DICT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"corrections": {}, "frequency": {}, "auto_added": []}


def save_dictionary(d: dict):
    """儲存辭書"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DICT_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def fetch_pmda_terms() -> list[str]:
    """
    從 PMDA（醫藥品醫療器械綜合機構）公開頁面擷取藥品名
    抓取新藥核准資訊中的日文藥品名（カタカナ為主）
    """
    urls = [
        "https://www.pmda.go.jp/safety/info-services/drugs/0001.html",
        "https://www.pmda.go.jp/review-services/drug-reviews/review-information/p-drugs/0028.html",
    ]

    terms = set()
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")

            # 擷取カタカナ藥名 + 常見劑型後綴
            patterns = re.findall(
                r"([ァ-ヶー]{3,}(?:錠|カプセル|注射液|点眼液|軟膏|顆粒|細粒|散|シロップ|テープ|パッチ|吸入|坐剤))",
                html,
            )
            terms.update(patterns)

            # 也擷取英文藥品名（全大寫或首字母大寫的連續英文單字）
            eng_patterns = re.findall(r"\b([A-Z][a-z]{3,}(?:mab|nib|tide|zumab|tinib))\b", html)
            terms.update(eng_patterns)

        except Exception as e:
            log(f"PMDA 擷取失敗 ({url}): {e}")

    return list(terms)


def fetch_mhlw_terms() -> list[str]:
    """
    從厚生勞動省公開頁面擷取醫療相關術語
    """
    terms = set()
    url = "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/index.html"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")

        # 擷取醫療制度相關術語（漢字 3 字以上）
        patterns = re.findall(r"((?:[一-龥]{2,}(?:制度|保険|医療|診療|調剤|薬局|検査)))", html)
        terms.update(patterns)
    except Exception as e:
        log(f"MHLW 擷取失敗: {e}")

    return list(terms)


def extract_terms_with_claude(text: str, category: str) -> list[dict]:
    """呼叫 Claude API 從文本擷取專業術語（可選）"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return []

    try:
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 500,
            "messages": [{
                "role": "user",
                "content": (
                    f"以下文本中擷取所有{category}專業術語。"
                    f"只輸出 JSON 陣列，格式：[{{\"reading\":\"讀音\",\"display\":\"顯示文字\"}}]\n"
                    f"不要輸出其他文字。\n\n文本：{text[:2000]}"
                ),
            }],
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        text_content = result["content"][0]["text"]
        return json.loads(text_content)
    except Exception as e:
        log(f"Claude 術語擷取失敗: {e}")
        return []


def main():
    import argparse
    parser = argparse.ArgumentParser(description="SGH Voice 業界辭書自動擴充")
    parser.add_argument("--dry-run", action="store_true", help="只顯示結果，不寫入辭書")
    args = parser.parse_args()

    print("📚 SGH Voice 辭書自動擴充")
    print(f"   辭書檔案：{DICT_FILE}")
    print()

    dictionary = load_dictionary()
    existing_words = set(dictionary.get("auto_added", []))
    existing_corrections = dictionary.get("corrections", {})
    new_terms = []

    # 1. PMDA 新藥名
    print("[1/2] 擷取 PMDA 新藥名...")
    pmda_terms = fetch_pmda_terms()
    for term in pmda_terms:
        if term not in existing_words and term not in existing_corrections:
            new_terms.append(("pmda", term))
    print(f"  擷取到 {len(pmda_terms)} 個術語，新增 {len(new_terms)} 個")

    # 2. MHLW 醫療術語
    print("[2/2] 擷取 MHLW 醫療術語...")
    mhlw_terms = fetch_mhlw_terms()
    mhlw_new = 0
    for term in mhlw_terms:
        if term not in existing_words and term not in existing_corrections:
            new_terms.append(("mhlw", term))
            mhlw_new += 1
    print(f"  擷取到 {len(mhlw_terms)} 個術語，新增 {mhlw_new} 個")

    # 結果
    print()
    if not new_terms:
        log("無新術語")
        print("✅ 辭書已是最新，無新術語")
        return

    print(f"📋 共發現 {len(new_terms)} 個新術語：")
    for source, term in new_terms[:20]:
        print(f"  [{source}] {term}")
    if len(new_terms) > 20:
        print(f"  ... 還有 {len(new_terms) - 20} 個")

    if args.dry_run:
        print("\n⏭️  乾跑模式，未寫入辭書")
        return

    # 寫入辭書
    auto_added = dictionary.get("auto_added", [])
    for source, term in new_terms:
        auto_added.append(term)
    dictionary["auto_added"] = auto_added
    save_dictionary(dictionary)

    log(f"新增 {len(new_terms)} 個術語（PMDA: {len(pmda_terms)}, MHLW: {mhlw_new}）")
    notify("📚 SGH Voice 辭書更新", f"新增 {len(new_terms)} 個術語")
    print(f"\n✅ 已寫入 {len(new_terms)} 個新術語到辭書")


if __name__ == "__main__":
    main()
