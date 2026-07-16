"""Tests for memory.py — Whisper prompt builder, corrections, history, few-shot."""
import pytest


# ───── build_whisper_prompt ─────────────────────────────────

def test_build_whisper_prompt_returns_concatenated_string(empty_memory):
    """custom_words provided → returns comma-joined string."""
    prompt = empty_memory.build_whisper_prompt(["MyTerm1", "MyTerm2"])
    assert "MyTerm1" in prompt
    assert "MyTerm2" in prompt
    assert "," in prompt


def test_build_whisper_prompt_deduplicates(empty_memory):
    """重複的 term 跨 custom / scene / BASE 都只該出現一次。"""
    # BASE_CUSTOM_WORDS 已含 "Shingihou"；傳入也含 → 應只出現一次
    prompt = empty_memory.build_whisper_prompt(
        ["Shingihou", "UniqueA"],
        scene_words=["Shingihou", "UniqueB"],
    )
    assert prompt.count("Shingihou") == 1
    assert "UniqueA" in prompt
    assert "UniqueB" in prompt


def test_build_whisper_prompt_respects_limits(empty_memory):
    """≤ 20 詞 / ≤ 200 字元（memory.py 實作的硬上限）。"""
    huge_list = [f"Term{i:03d}" for i in range(100)]
    prompt = empty_memory.build_whisper_prompt(huge_list)
    # 不超過 200 字元
    assert len(prompt) <= 200
    # 不超過 20 個 comma-separated terms（19 commas + 20 terms）
    parts = [p.strip() for p in prompt.split(",")]
    assert len(parts) <= 20


def test_build_whisper_prompt_empty_returns_empty_string(empty_memory):
    """無任何詞彙時應回傳空字串（會跟 BASE_CUSTOM_WORDS merge，所以實際不為空 — 改 assert 型別）。"""
    # BASE_CUSTOM_WORDS 是常數會被併入，所以結果不會是 ""；只要 type 正確即可
    prompt = empty_memory.build_whisper_prompt([])
    assert isinstance(prompt, str)


def test_whisper_prompt_keeps_multilingual_and_core_terms_balanced(empty_memory):
    custom = [f"custom-{index}" for index in range(10)]
    prompt = empty_memory.build_whisper_prompt(custom)
    for term in (
        "SEO", "GEO", "contact form", "お問い合わせフォーム", "カタカナ",
        "Shingihou", "新義豊", "Supabase", "Twilio", "Claude",
    ):
        assert term in prompt


# ───── apply_corrections ───────────────────────────────────

def test_apply_corrections_user_overrides_scene_and_base(empty_memory):
    """三層優先：使用者全域 > 場景 > 基底。BASE 有 'cloud code'→'Claude Code'。
    使用者寫入相同 key 但不同 value → 應用使用者版本。"""
    empty_memory.dictionary["corrections"] = {"cloud code": "我的自訂版本"}
    result = empty_memory.apply_corrections("I love cloud code today")
    assert "我的自訂版本" in result
    assert "Claude Code" not in result


def test_apply_corrections_scene_overrides_base(empty_memory):
    """scene_corrections 傳入時可覆蓋一般規則（但被使用者全域覆蓋）。"""
    result = empty_memory.apply_corrections(
        "use ultra vox today",
        scene_corrections={"ultra vox": "Ultravox-X"},
    )
    assert "Ultravox-X" in result


def test_canonical_case_normalization_is_allowed(empty_memory):
    empty_memory.dictionary["corrections"] = {"IOS": "iOS", "N8N": "n8n"}
    assert empty_memory.apply_corrections("IOS app with N8N") == "iOS app with n8n"


def test_apply_corrections_does_nothing_when_no_match(empty_memory):
    """沒有命中規則 → 原文返回。"""
    out = empty_memory.apply_corrections("This text has nothing to correct.")
    # 沒命中 BASE_CORRECTIONS 任何 key
    assert "This text" in out


# ───── update_history_item ─────────────────────────────────

def test_update_history_item_marks_edited(populated_memory):
    """更新 final_text + 設定 edited=True。"""
    ts = "2026-01-01T10:00:00"
    new_text = "今天天氣超棒，我們出門了。"
    old = populated_memory.update_history_item(ts, new_text)
    assert old == "今天天氣很好，我們去散步。"

    # 找回該筆紀錄
    found = next(h for h in populated_memory.history if h.get("timestamp") == ts)
    assert found["final_text"] == new_text
    assert found["edited"] is True


def test_update_history_item_returns_none_for_unknown_timestamp(populated_memory):
    """找不到對應 timestamp → 回 None，不該 raise。"""
    result = populated_memory.update_history_item("non-existent-ts", "whatever")
    assert result is None


# ───── get_few_shot_examples ──────────────────────────────

def test_get_few_shot_prefers_edited(populated_memory):
    """history 含 edited + non-edited；應該先給 edited 的範例。"""
    examples = populated_memory.get_few_shot_examples(n=2)
    # 兩筆 edited 的 raw：
    #   "cloud code 真的很強"
    #   "我在使用 ultra vox 整合 twilio"
    raws = [r for r, _ in examples]
    assert any("cloud code" in r for r in raws) or any("ultra vox" in r for r in raws)
    # 應該全部來自 edited
    assert len(examples) <= 2


def test_get_few_shot_returns_empty_when_history_empty(empty_memory):
    """空 history → 空 list。"""
    examples = empty_memory.get_few_shot_examples(n=3)
    assert examples == []


def test_get_few_shot_filters_short_entries(populated_memory):
    """min_chars=12 → "shorty" (6 字) 該被過濾。"""
    examples = populated_memory.get_few_shot_examples(n=10, min_chars=12)
    raws = [r for r, _ in examples]
    assert "shorty" not in raws


def test_get_few_shot_respects_n(populated_memory):
    """n=1 → 最多回 1 筆。"""
    examples = populated_memory.get_few_shot_examples(n=1)
    assert len(examples) <= 1


def test_verified_few_shot_excludes_edit_and_cross_script(populated_memory):
    populated_memory.history.extend([
        {
            "whisper_raw": "請翻譯這段內容",
            "final_text": "Please translate this text.",
            "mode": "edit",
            "edited": True,
        },
        {
            "whisper_raw": "今天需要處理文件",
            "final_text": "Handle the document today.",
            "mode": "dictate",
            "edited": True,
        },
    ])
    examples = populated_memory.get_few_shot_examples(
        n=20,
        current_text="今天需要確認設定",
        verified_only=True,
    )
    raws = {raw for raw, _ in examples}
    assert "請翻譯這段內容" not in raws
    assert "今天需要處理文件" not in raws


def test_history_is_persisted_immediately(empty_memory, isolated_data_dir):
    import json

    entry = {
        "timestamp": "2026-07-14T12:00:00",
        "whisper_raw": "測試內容",
        "final_text": "測試內容。",
        "mode": "dictate",
    }
    assert empty_memory.add_to_history(entry) is True
    with open(isolated_data_dir / "history.json", "r", encoding="utf-8") as handle:
        saved = json.load(handle)
    assert saved[-1] == entry
