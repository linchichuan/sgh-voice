#!/usr/bin/env python3
"""Build an aggregate writing-style profile without exporting history text.

The analyzer is deliberately deterministic and local-only. It reports broad
formatting traits, never sample text, names, or provider-generated inferences.
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory import Memory


_ASCII_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.+/-]*")
_KANA_RE = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff]")
_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_TECH_TERMS = {
    "api",
    "sdk",
    "llm",
    "prompt",
    "server",
    "deploy",
    "git",
    "cloud",
    "websocket",
}
_MEDICAL_MARKERS = (
    "醫療",
    "診所",
    "患者",
    "病院",
    "医療",
    "薬",
    "處方",
    "診療",
)
_BUSINESS_MARKERS = (
    "客戶",
    "合作",
    "提案",
    "契約",
    "運用",
    "業務",
    "確認",
    "schedule",
)


def generate_local_style_profile(samples: list[str]) -> str:
    """Return aggregate style instructions without echoing any sample text."""
    cleaned = [
        sample.strip()
        for sample in samples
        if isinstance(sample, str) and sample.strip()
    ]
    if not cleaned:
        raise ValueError("at least one non-empty sample is required")

    lengths = [len(sample) for sample in cleaned]
    average_length = statistics.fmean(lengths)
    combined = "\n".join(cleaned)
    lowered = combined.lower()

    if average_length < 35:
        sentence_trait = "偏好精簡短句，避免不必要的長篇鋪陳"
    elif average_length > 90:
        sentence_trait = "偏好資訊完整的長句，但應維持清楚分段"
    else:
        sentence_trait = "偏好中等長度、資訊密度適中的句子"

    comma_count = sum(combined.count(mark) for mark in ("，", ",", "、"))
    stop_count = sum(
        combined.count(mark) for mark in ("。", ".", "！", "!", "？", "?")
    )
    if comma_count > max(stop_count * 2, 4):
        punctuation_trait = "常以逗號串接資訊，輸出時保留節奏並適度斷句"
    elif stop_count == 0:
        punctuation_trait = "原始輸入較少句末標點，輸出時補齊自然標點"
    else:
        punctuation_trait = "標點使用均衡，維持自然完整的句末標點"

    ascii_words = _ASCII_WORD_RE.findall(combined)
    cjk_chars = _CJK_RE.findall(combined)
    language_traits: list[str] = []
    if ascii_words and cjk_chars:
        language_traits.append("保留中英文混排與半形英文技術詞")
    if _KANA_RE.search(combined) and cjk_chars:
        language_traits.append("保留中文與日文混排，不任意翻譯專有內容")
    if not language_traits:
        language_traits.append("維持原輸入語言，不自行增加其他語言")

    domains: list[str] = []
    ascii_terms = {word.lower() for word in ascii_words}
    if ascii_terms & _TECH_TERMS:
        domains.append("技術")
    if any(marker in combined for marker in _MEDICAL_MARKERS):
        domains.append("醫療")
    if any(marker.lower() in lowered for marker in _BUSINESS_MARKERS):
        domains.append("商務")
    domain_trait = (
        f"保留{'、'.join(domains)}領域的正式專有名詞"
        if domains
        else "保留原有專有名詞，不推測或擴寫未提供的內容"
    )

    return "；".join(
        [sentence_trait, punctuation_trait, *language_traits, domain_trait]
    ) + "。"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="在本機從近期紀錄產生不含原文的寫作風格摘要"
    )
    parser.add_argument("--apply", action="store_true", help="寫入 dictionary.style_profile")
    parser.add_argument("--n", type=int, default=100, help="最近樣本數（10-100）")
    parser.add_argument("--min-chars", type=int, default=15, help="單筆最少字元")
    args = parser.parse_args()

    if not 10 <= args.n <= 100:
        parser.error("--n must be between 10 and 100")
    if args.min_chars < 1:
        parser.error("--min-chars must be positive")

    memory = Memory()
    samples: list[str] = []
    for entry in reversed(memory.history):
        text = (entry.get("final_text") or "").strip()
        if len(text) < args.min_chars:
            continue
        samples.append(text)
        if len(samples) >= args.n:
            break

    if len(samples) < 10:
        print(f"❌ 樣本不足（{len(samples)} 筆，需 ≥10）")
        return 1

    profile = generate_local_style_profile(samples)
    print(f"📊 已在本機彙整 {len(samples)} 筆；未傳送或輸出逐字稿內容")
    print(f"\n=== 新 Profile（local）===\n{profile}\n")
    print(f"=== 舊 Profile ===\n{memory.get_style_profile()}\n")

    if not args.apply:
        print("💡 dry-run。確認無誤後加 --apply 寫入。")
        return 0

    memory.update_style_profile(profile)
    print(f"✅ 已寫入 dictionary.style_profile（{len(profile)} 字）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
