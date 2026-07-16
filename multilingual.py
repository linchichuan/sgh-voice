"""多語文字保護工具。

核心原則：中文可以做簡繁正規化，但日文的新字體、假名與英文技術詞必須原樣保留。
OpenCC 無法判斷文字所屬語言，直接對整段中日英混合文字執行 ``s2twp`` 會把
日文的「画像」「動画」「台風」錯轉成中文的「畫像」「動畫」「臺風」。
"""

from __future__ import annotations

import re
from typing import Callable


_HAN_RE = re.compile(r"[\u3400-\u9fff]")
_KANA_RE = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_HAN_RUN_RE = re.compile(r"([\u3400-\u9fff]+)")

# 以句讀／換行切 clause；含假名的 clause 再按 Han run 分析，保護日本語新字體，
# 同時允許「这是软件です」這種明確簡體中文片段被正常繁化。
_CLAUSE_SEPARATOR_RE = re.compile(r"([，,。！？!?；;\n]+)")

# 只列「以日本語新字體／詞形存在、繁中不會這樣寫」的高頻純漢字詞。
# 無假名的 Han 本質上無法靠 Unicode 完美判別中日語；先保護真實 log 與開發／醫療
# 工作流最常見的詞，再讓其餘文字走 OpenCC。避免把所有「参考」都當日文，破壞繁中。
JAPANESE_KANJI_TERMS = tuple(sorted({
    "来週", "画像", "動画", "台風", "国際", "会議", "会社", "大学",
    "開発", "実装", "検証", "仕様", "画面", "機能", "設定", "処理",
    "変換", "対応", "連絡", "電話", "予約", "病院", "医療", "薬品",
    "患者", "受付", "診療", "請求", "保険", "計画", "関係", "状態", "参考",
    "学習", "写真", "説明", "検索", "選択", "登録", "更新", "削除", "保存",
    "編集", "入力", "出力", "送信", "受信", "接続", "認証", "権限", "環境",
    "運用", "改善", "最適化", "自動化",
}, key=len, reverse=True))
_AMBIGUOUS_JAPANESE_KANJI_TERMS = {"参考"}
_JAPANESE_ASR_KANJI_CORRECTIONS = {
    "设置": "設定",
    "开发": "開発",
    "处理": "処理",
    "体验": "体験",
    "确认": "確認",
}

# 日文 clause 內仍可能混入明確簡體中文（例：「这是软件です」）。只對含下列
# 「日本語不使用的簡體字」的 Han run 做 OpenCC；国／会／画 等中日共用異體不列入。
_SIMPLIFIED_CHINESE_HINT_RE = re.compile(
    # 多字詞補足單字本身也可能是日文新字體的情況（例：数／体）。
    r"(?:数据|视频|软件|优化|设置|问题|确认|处理|开发|体验|云服务|"
    # 下列字不屬於現代日文常用新字體；刻意排除 体／点／万／与／数／会／画。
    r"[这们为发软网优个后关开问际图视频从还进过边门时产业东车书无验处确请])")


def script_profile(text: str) -> tuple[bool, bool, bool]:
    """回傳 ``(has_han, has_kana, has_latin)``。"""

    value = text or ""
    return (
        bool(_HAN_RE.search(value)),
        bool(_KANA_RE.search(value)),
        bool(_LATIN_RE.search(value)),
    )


def contains_kana(text: str) -> bool:
    return bool(_KANA_RE.search(text or ""))


def is_code_switched(text: str) -> bool:
    """是否有可可靠判斷的跨語系混用。

    Han + Kana 是一般日文，不算 code-switch；Japanese + English（Kana + Latin）或
    Chinese + English（Han + Latin，無 Kana）才算。中日混用若都只用 Han/Kana，
    Unicode 無法可靠拆分，交由 contains_kana 的日文路徑保護。
    """

    has_han, has_kana, has_latin = script_profile(text)
    if has_kana:
        return has_latin
    return has_han and has_latin


def script_bucket(text: str) -> str:
    """供 metadata telemetry 使用的 script bucket。"""

    has_han, has_kana, has_latin = script_profile(text)
    if has_kana:
        return "mixed" if has_latin else "ja"
    if has_han:
        return "mixed" if has_latin else "zh"
    if has_latin:
        return "en"
    return "other"


def language_profile(text: str) -> tuple[str, bool]:
    """Few-shot 用的語言 profile：``(primary_language, has_latin)``。

    日文的 Han 與 Kana 是同一語言，允許 verified 範例把「といあわせ」校正為
    「問い合わせ」；但 Japanese+English 與 Chinese+English 仍分開。
    """

    has_han, has_kana, has_latin = script_profile(text)
    if has_kana:
        return ("ja", has_latin)
    if has_han:
        return ("zh", has_latin)
    if has_latin:
        return ("en", True)
    return ("other", False)


def resolve_output_language_hint(operation: str | None, source_hint: str | None) -> str | None:
    """翻譯類 edit operation 以輸出語言為準，其餘沿用 STT/source hint。"""

    return {
        "translate_ja": "ja",
        "translate_zh": "zh",
        "translate_en": "en",
    }.get(operation or "", source_hint)


def _convert_with_japanese_term_placeholders(
    text: str,
    convert: Callable[[str], str],
    *,
    chinese_hint: bool = False,
) -> str:
    """在無假名 clause 中保護高可信日文漢字詞，再繁化其餘內容。"""

    protected: dict[str, str] = {}
    masked = text
    for term in JAPANESE_KANJI_TERMS:
        if (term in _AMBIGUOUS_JAPANESE_KANJI_TERMS
                and (chinese_hint or _SIMPLIFIED_CHINESE_HINT_RE.search(text))):
            continue
        if term not in masked:
            continue
        placeholder = f"ZXQJAPANESE{len(protected)}QXZ"
        protected[placeholder] = term
        masked = masked.replace(term, placeholder)
    converted = convert(masked)
    for placeholder, term in protected.items():
        converted = converted.replace(placeholder, term)
    return converted


def convert_traditional_preserving_japanese(
    text: str,
    converter: object | Callable[[str], str] | None,
    language_hint: str | None = None,
) -> str:
    """只轉換非日文 run，保留日文新字體與 code-switched Latin/kana span。

    ``converter`` 可傳 OpenCC instance（具 ``convert`` method）或一般 callable。
    若 converter 不可用或轉換失敗，安全地回傳原文。
    """

    if not text or converter is None:
        return text

    convert = getattr(converter, "convert", converter)
    if not callable(convert):
        return text

    hint = (language_hint or "").strip().lower()
    japanese_hint = hint == "ja" or hint.startswith("ja-") or hint in {"japanese", "日本語"}
    chinese_hint = hint == "zh" or hint.startswith("zh-") or hint in {"chinese", "中文"}

    output: list[str] = []
    try:
        for part in _CLAUSE_SEPARATOR_RE.split(text):
            if not part:
                continue
            if _CLAUSE_SEPARATOR_RE.fullmatch(part):
                output.append(part)
            elif contains_kana(part):
                # 日文 clause：保留一般 Han／Kana；只有明確含非日文簡體字的 Han run
                # 才做繁中轉換，兼顧「これは画像です」與「这是软件です」。
                for run in _HAN_RUN_RE.split(part):
                    if run and _HAN_RUN_RE.fullmatch(run):
                        normalized_run = run
                        if japanese_hint:
                            for wrong, right in _JAPANESE_ASR_KANJI_CORRECTIONS.items():
                                normalized_run = normalized_run.replace(wrong, right)
                        if _SIMPLIFIED_CHINESE_HINT_RE.search(normalized_run):
                            output.append(_convert_with_japanese_term_placeholders(
                                normalized_run, convert, chinese_hint=True,
                            ))
                        else:
                            output.append(normalized_run)
                    else:
                        output.append(run)
            else:
                # STT verbose response 明確判定為日文時，純漢字 clause 也保持原樣；
                # auto/zh 無法判斷時才走高可信日文詞 placeholder + OpenCC。
                if japanese_hint and not _SIMPLIFIED_CHINESE_HINT_RE.search(part):
                    output.append(part)
                else:
                    output.append(_convert_with_japanese_term_placeholders(
                        part, convert, chinese_hint=chinese_hint,
                    ))
    except Exception:
        return text
    return "".join(output)
