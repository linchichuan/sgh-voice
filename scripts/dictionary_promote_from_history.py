"""
從歷史 whisper_raw → final_text 對比中，把高頻 token 級替換自動升級為 dictionary corrections。

設計：
- 不呼叫 LLM。完全本地、快、零成本。
- 用 difflib 做 token 級 diff（與 memory.learn_correction 同款 tokenize）。
- 套用 memory._is_meaningful_correction 守門員，與互動學習完全一致。
- 跳過 BASE_CORRECTIONS 已有的、dictionary 已有的。
- 預設只分析 edited=True 的使用者驗證資料，且 --dry-run 不寫入。
- auto / both 僅供 legacy 分析；不得搭配 --apply，避免模型輸出反餵污染詞庫。

用法：
  python3 scripts/dictionary_promote_from_history.py              # dry-run
  python3 scripts/dictionary_promote_from_history.py --apply      # 實際寫入
  python3 scripts/dictionary_promote_from_history.py --min-freq 5 # 提高門檻
"""
import argparse
import difflib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import DATA_DIR, BASE_CORRECTIONS, load_dictionary, save_dictionary
from memory import Memory

try:
    from opencc import OpenCC
    _opencc = OpenCC("s2twp")
except Exception:
    _opencc = None


HISTORY_FILE = os.path.join(DATA_DIR, "history.json")


def _is_substring_relation(a, b):
    """a 包含 b 或 b 包含 a — 通常是 LLM 多/少加東西的幻覺，不是 Whisper 錯誤。
    例：KusuriJapan ↔ KusuriJapanJapan、語音輸入 ↔ 語音 都會被擋。"""
    if not a or not b:
        return False
    if a == b:
        return False
    return a in b or b in a


def _is_opencc_handled(wrong, right):
    """如果簡繁轉換已經能修，就不該升級到 dictionary（OpenCC 是第 5 層自動處理）。"""
    if _opencc is None:
        return False
    try:
        return _opencc.convert(wrong) == right
    except Exception:
        return False


def _tokenize(text):
    """與 memory.learn_correction 相同的切分規則。"""
    return re.findall(r"[a-zA-Z0-9_'-]+|\s+|[^\sa-zA-Z0-9_'-]", text or "")


# ASCII 技術詞/品牌名 pattern：駝峰、含數字、連字、或含大寫字母的 ASCII token
# 例：Supabase, Ultravox, Zeabur, n8n, GPT-4o, Node.js, Claude Code
_TECH_TERM_RE = re.compile(r"^[A-Za-z][A-Za-z0-9.\-]*[A-Za-z0-9]$")

def _is_tech_term(s):
    """判斷 right 是否為 ASCII 技術詞 / 品牌名（值得降低 freq 門檻 + 同步進 custom_words）。
    條件：純 ASCII，長度 3+，且 (含大寫字母 OR 含數字 OR 含連字/點)。
    純小寫單字（如 'and'）不算 — 避免噪音。"""
    if not s or len(s) < 3 or not s.isascii():
        return False
    if " " in s:
        # 允許多字組合，但每段都要像技術詞（如 "LINE Bot", "Claude Code"）
        parts = s.split()
        return all(_is_tech_term(p) for p in parts)
    if not _TECH_TERM_RE.match(s):
        return False
    has_upper = any(c.isupper() for c in s)
    has_digit = any(c.isdigit() for c in s)
    has_sep = any(c in ".-" for c in s)
    return has_upper or has_digit or has_sep


def extract_diff_pairs(raw, fin):
    """回傳 [(wrong, right), ...] 從一筆 raw→fin 的差異。"""
    pairs = []
    a = _tokenize(raw)
    b = _tokenize(fin)
    matcher = difflib.SequenceMatcher(None, a, b)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op != "replace":
            continue
        wrong = "".join(a[i1:i2]).strip()
        right = "".join(b[j1:j2]).strip()
        if wrong and right and wrong != right:
            pairs.append((wrong, right))
    return pairs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="實際寫入 dictionary.json（預設僅 dry-run）")
    parser.add_argument("--min-freq", type=int, default=5, help="最低頻次（一般詞，預設 5）")
    parser.add_argument("--tech-min-freq", type=int, default=2,
                        help="ASCII 技術詞/品牌名最低頻次（預設 2，因為這類錯誤通常少量出現但必須抓）")
    parser.add_argument("--source", choices=["auto", "edited", "both"], default="edited",
                        help="edited=使用者驗證資料（預設）；auto/both 僅供 legacy dry-run 分析")
    parser.add_argument("--top", type=int, default=50, help="最多列印 N 條（預設 50）")
    args = parser.parse_args()

    if args.apply and args.source != "edited":
        parser.error("--apply 只允許 --source edited；auto/both 僅供 legacy dry-run 分析")

    if not os.path.exists(HISTORY_FILE):
        print(f"❌ 找不到 {HISTORY_FILE}")
        return 1

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)

    print(f"📚 歷史總筆數：{len(history)}")

    # 統計差異對（依 --source 過濾）
    counter = Counter()
    valid_records = 0
    n_edited = sum(1 for h in history if h.get("edited"))
    print(f"   其中 edited=True：{n_edited} 筆")

    for h in history:
        if args.source == "edited" and not h.get("edited"):
            continue
        if args.source == "auto" and h.get("edited"):
            continue
        raw = (h.get("whisper_raw") or "").strip()
        fin = (h.get("final_text") or "").strip()
        if not raw or not fin or raw == fin:
            continue
        valid_records += 1
        for pair in extract_diff_pairs(raw, fin):
            counter[pair] += 1

    print(f"   依 --source={args.source} 採用樣本：{valid_records}")
    print(f"   抽出差異對總數：{sum(counter.values())} 個 / 去重 {len(counter)} 種")

    # 套守門員
    mem = Memory()
    base_keys = {k.lower() for k in BASE_CORRECTIONS.keys()}
    existing = set(mem.dictionary.get("corrections", {}).keys())

    promoted = []        # (wrong, right, freq, is_tech) 通過所有守門
    skipped_base = []    # 已存在於 BASE 或 dictionary
    skipped_substr = []  # 子字串關係（LLM 加減字幻覺）
    skipped_opencc = []  # OpenCC 已自動處理
    skipped_filter = []  # 既有守門員拒絕
    skipped_lowfreq = [] # 頻次未達門檻（依 tech / 一般 分層）

    # 既有 custom_words（用於去重，避免重複加入）
    existing_words_lower = {
        w.lower() for w in mem.dictionary.get("manual_added", [])
        if isinstance(w, str)
    }

    for (wrong, right), freq in counter.most_common():
        is_tech = _is_tech_term(right)
        threshold = args.tech_min_freq if is_tech else args.min_freq
        if freq < threshold:
            # 注意：most_common 是按 freq 排序，但 tech / 非 tech 的門檻不同，
            # 不能一律 break。低於一般門檻但屬技術詞可能仍要收。
            skipped_lowfreq.append((wrong, right, freq, is_tech))
            continue
        if wrong.lower() in base_keys or wrong in existing:
            skipped_base.append((wrong, right, freq))
            continue
        if _is_substring_relation(wrong, right):
            skipped_substr.append((wrong, right, freq))
            continue
        if _is_opencc_handled(wrong, right):
            skipped_opencc.append((wrong, right, freq))
            continue
        if not mem._is_meaningful_correction(wrong, right, source="auto-promote"):
            skipped_filter.append((wrong, right, freq))
            continue
        promoted.append((wrong, right, freq, is_tech))

    n_tech = sum(1 for *_, is_tech in promoted if is_tech)
    print()
    print(f"✅ 通過守門員可升級：{len(promoted)} 條"
          f"（一般 min_freq={args.min_freq} / 技術詞 min_freq={args.tech_min_freq}，"
          f"其中技術詞 {n_tech} 條會同步進 custom_words）")
    print(f"⏭️  跳過（已存在）：{len(skipped_base)} 條")
    print(f"♻️  跳過（OpenCC 已修）：{len(skipped_opencc)} 條")
    print(f"🌀 跳過（子字串關係）：{len(skipped_substr)} 條")
    print(f"🚫 跳過（守門員拒絕）：{len(skipped_filter)} 條")
    print(f"📉 跳過（頻次不足）：{len(skipped_lowfreq)} 條")

    if promoted:
        print("\n=== 待升級規則（freq desc）===")
        for w, r, f, is_tech in promoted[: args.top]:
            tag = "🔧" if is_tech else "  "
            print(f"  {tag} [{f:3d}×] {w!r:30s} → {r!r}")

    if skipped_filter:
        print(f"\n=== 守門員拒絕的 top {min(20, len(skipped_filter))} 範例（供檢視）===")
        for w, r, f in skipped_filter[:20]:
            print(f"  [{f:3d}×] {w!r:40s} → {r!r}")
    if skipped_base:
        print(f"\n=== 已存在規則 top {min(10, len(skipped_base))} 範例 ===")
        for w, r, f in skipped_base[:10]:
            print(f"  [{f:3d}×] {w!r:40s} → {r!r}")

    if not args.apply:
        print("\n💡 dry-run 結束。確認無誤後加 --apply 實際寫入。")
        return 0

    if not promoted:
        print("\nℹ️  無可升級規則。")
        return 0

    # 寫入
    corr = mem.dictionary.setdefault("corrections", {})
    freq_dict = mem.dictionary.setdefault("frequency", {})
    # Runtime/UI/STT share the flat manual_added list.  The old script wrote a
    # separate dictionary.custom_words list that no runtime path ever consumed.
    words = mem.dictionary.setdefault("manual_added", [])
    n_words_added = 0
    for w, r, f, is_tech in promoted:
        corr[w] = r
        freq_dict[w] = freq_dict.get(w, 0) + f
        # 技術詞同步寫進 custom_words → 下次 Whisper prompt 直接認得（治本）
        if is_tech and r.lower() not in existing_words_lower:
            words.append(r)
            existing_words_lower.add(r.lower())
            n_words_added += 1
    save_dictionary(mem.dictionary)
    print(f"\n✅ 已寫入 {len(promoted)} 條 corrections 到 dictionary.json")
    if n_words_added > 0:
        print(f"   + {n_words_added} 個技術詞同步加入 custom_words（下次 Whisper prompt 將認得）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
