"""Conservative extractive SOAP draft gate, not a clinical correctness checker.

An exact sentence multiset prevents changed doses, names, negations, omissions,
and invented diagnoses. Classification into S/O/A/P is still unverified, so even
a passing draft MUST be reviewed by a clinician and is never auto-pasted.
"""
from collections import Counter
import re

REVIEW_NOTICE = "SOAP 草稿：需醫師逐項核對原始逐字稿；尚未核對，不可直接作為病歷。"
FAILURE_NOTICE = "SOAP 整理未通過保留原文檢查或服務不可用；未自動輸入，請核對下方原始逐字稿。"
_HEADERS = re.compile(r"(?m)^\s*\[([SOAP])\]\s*$")
_SENTENCE_BOUNDARIES = re.compile(r"(?<=[。！？!?])|\n")


def sentences(text):
    # Preserve every lexical character, comma, minus sign, decimal and space
    # inside a sentence. No Unicode/case/OpenCC normalization for clinical data.
    # Split, rather than select matches: every non-whitespace character must
    # participate, including unpunctuated middle lines and isolated punctuation.
    return [part.strip() for part in _SENTENCE_BOUNDARIES.split(text or "")
            if part.strip()]


def validate_soap_draft(raw, draft):
    """Return (accepted draft or None, non-sensitive reason code)."""
    if not isinstance(draft, str) or not draft.strip():
        return None, "unavailable"
    draft = draft.strip()
    headers = list(_HEADERS.finditer(draft))
    if [m.group(1) for m in headers] != list("SOAP") or draft[:headers[0].start()].strip():
        return None, "invalid_sections"
    chunks = []
    for i, header in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(draft)
        body = draft[header.end():end].strip()
        # Empty sections express no assigned excerpt, NOT a clinical negative.
        if body:
            chunks.extend(sentences(body))
    original = sentences(raw)
    if not original or Counter(chunks) != Counter(original):
        return None, "source_sentences_changed"
    return draft, "review_required"


def result_message(result):
    if not result.get("source_recoverable"):
        return "SOAP 未自動輸入。歷史紀錄寫入失敗，請勿關閉 App；本次原文僅暫存記憶體，請先重試儲存。"
    if result.get("error") == "medical_soap_review_required":
        message = "SOAP 草稿已保留於歷史紀錄，請醫師對照原文核對後手動複製；未自動輸入。"
    else:
        message = "SOAP 整理未通過安全檢查或服務不可用，未自動輸入；原始逐字稿可於歷史紀錄查看。"
    return message
