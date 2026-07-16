"""繁中／日文／English code-switch 的回歸測試。"""

import numpy as np
from opencc import OpenCC

from multilingual import (
    convert_traditional_preserving_japanese,
    is_code_switched,
    language_profile,
    resolve_output_language_hint,
    script_bucket,
    script_profile,
)


def test_opencc_converts_chinese_only():
    text = "这是软件，网络和数据都要优化。"
    out = convert_traditional_preserving_japanese(text, OpenCC("s2twp"))
    assert out == "這是軟體，網路和資料都要最佳化。"


def test_opencc_preserves_japanese_shinjitai_with_spaces():
    text = "来週 supplier と画像、動画を確認します。台風の参考資料です。"
    out = convert_traditional_preserving_japanese(text, OpenCC("s2twp"))
    assert out == text
    assert "來週" not in out
    assert "畫像" not in out
    assert "動畫" not in out


def test_opencc_preserves_high_confidence_kanji_only_japanese():
    text = "来週、画像、国際会議、開発"
    assert convert_traditional_preserving_japanese(text, OpenCC("s2twp")) == text


def test_opencc_handles_mixed_clauses_independently():
    text = "这是软件，画像と動画を確認します。网络也要优化。"
    out = convert_traditional_preserving_japanese(text, OpenCC("s2twp"))
    assert out == "這是軟體，画像と動画を確認します。網路也要最佳化。"


def test_opencc_preserves_leading_punctuation():
    text = "。来週確認します。网络"
    out = convert_traditional_preserving_japanese(text, OpenCC("s2twp"))
    assert out == "。来週確認します。網路"


def test_opencc_converts_explicit_simplified_chinese_inside_japanese_clause():
    text = "这是软件です。これは画像です。"
    out = convert_traditional_preserving_japanese(text, OpenCC("s2twp"))
    assert out == "這是軟體です。これは画像です。"


def test_opencc_protects_japanese_suffix_inside_mixed_han_run():
    converter = OpenCC("s2twp")
    assert convert_traditional_preserving_japanese("设置画面です", converter) == "設定画面です"
    assert convert_traditional_preserving_japanese("开发環境を確認します", converter) == "開發環境を確認します"
    assert convert_traditional_preserving_japanese("体验学習を改善します", converter) == "體驗学習を改善します"


def test_opencc_ja_hint_repairs_common_japanese_asr_kanji():
    converter = OpenCC("s2twp")
    assert convert_traditional_preserving_japanese(
        "设置画面です。开发環境を確認します。体验学習を改善します。",
        converter,
        language_hint="ja",
    ) == "設定画面です。開発環境を確認します。体験学習を改善します。"


def test_opencc_does_not_treat_common_japanese_shinjitai_as_simplified_chinese():
    text = "全体と問題点と一万円と給与を確認します。具体的です。云々と説明します。"
    assert convert_traditional_preserving_japanese(text, OpenCC("s2twp")) == text


def test_opencc_uses_stt_language_hint_for_ambiguous_kanji_only_text():
    converter = OpenCC("s2twp")
    assert convert_traditional_preserving_japanese("参考", converter) == "参考"
    assert convert_traditional_preserving_japanese("参考", converter, language_hint="ja") == "参考"
    assert convert_traditional_preserving_japanese("参考", converter, language_hint="zh") == "參考"
    assert convert_traditional_preserving_japanese("请参考", converter) == "請參考"


def test_opencc_ja_hint_still_converts_explicit_chinese_clause():
    text = "这是软件。来週確認します。"
    out = convert_traditional_preserving_japanese(
        text, OpenCC("s2twp"), language_hint="ja",
    )
    assert out == "這是軟體。来週確認します。"


def test_output_language_hint_prefers_translation_target():
    assert resolve_output_language_hint("translate_ja", "zh") == "ja"
    assert resolve_output_language_hint("translate_zh", "ja") == "zh"
    assert resolve_output_language_hint("formal", "ja") == "ja"


def test_opencc_preserves_common_kanji_only_japanese_in_auto_mode():
    text = "学習、写真、検索、編集、自動化"
    assert convert_traditional_preserving_japanese(text, OpenCC("s2twp")) == text


def test_script_profile_distinguishes_code_switch_types():
    assert script_profile("純中文內容") == (True, False, False)
    assert script_profile("来週supplierと確認") == (True, True, True)
    assert is_code_switched("SEO 跟 GEO") is True
    assert is_code_switched("来週確認します") is False
    assert script_bucket("来週確認します") == "ja"
    assert script_bucket("来週 supplier と確認します") == "mixed"
    assert language_profile("といあわせフォーム") == language_profile("問い合わせフォーム")


def test_canonical_aliases_are_deterministic(empty_memory):
    raw = "content form、Cata-cana，還有 SEO、GO"
    out = empty_memory.apply_corrections(raw)
    assert "contact form" in out
    assert "カタカナ" in out
    assert "SEO、GEO" in out


def test_protected_terms_block_stale_runtime_rules(empty_memory):
    empty_memory.dictionary["corrections"] = {
        "LINE": "line",
        "Cloud": "Claude",
    }
    out = empty_memory.apply_corrections("LINE Bot 部署到 Cloud Run")
    assert out == "LINE Bot 部署到 Cloud Run"


def test_phrase_level_claude_correction_still_works(empty_memory):
    assert empty_memory.apply_corrections("打開 cloud code") == "打開 Claude Code"


def test_whitelisted_multilingual_spelling_corrections(empty_memory):
    assert empty_memory.apply_corrections("SEO 跟 GO") == "SEO 跟 GEO"
    assert empty_memory.apply_corrections("Twilo API") == "Twilio API"
    assert empty_memory.apply_corrections("といあわせフォーム") == "問い合わせフォーム"


def test_verified_fewshot_filters_unedited_and_script_mismatch(populated_memory):
    mixed = populated_memory.get_few_shot_examples(
        n=10,
        current_text="今天用 GitHub 寫程式",
        verified_only=True,
    )
    assert mixed
    assert all("今天天氣很好" not in raw for raw, _ in mixed)
    assert all(script_profile(raw) == (True, False, True) for raw, _ in mixed)

    japanese = populated_memory.get_few_shot_examples(
        n=10,
        current_text="来週supplierと確認します",
        verified_only=True,
    )
    assert japanese == []


def test_verified_fewshot_allows_japanese_kana_to_kanji_correction(populated_memory):
    populated_memory.history.append({
        "whisper_raw": "といあわせフォームについて確認します",
        "final_text": "問い合わせフォームについて確認します。",
        "mode": "dictate",
        "edited": True,
    })
    examples = populated_memory.get_few_shot_examples(
        n=10,
        current_text="来週問い合わせフォームを確認します",
        verified_only=True,
    )
    assert any(raw.startswith("といあわせ") for raw, _ in examples)


def test_short_japanese_and_code_switch_do_not_skip_llm(mock_transcriber):
    assert mock_transcriber._should_skip_llm("来週確認します") is False
    assert mock_transcriber._should_skip_llm("SEO 跟 GEO") is False
    assert mock_transcriber._should_skip_llm("純中文短句") is True


def test_validator_preserves_latin_and_kana_spans(mock_transcriber):
    assert mock_transcriber._code_switch_spans_preserved(
        "来週 supplier と確認します", "来週 supplier と確認します。"
    ) is True
    assert mock_transcriber._code_switch_spans_preserved(
        "来週 supplier と確認します", "来週サプライヤーと確認します。"
    ) is False
    assert mock_transcriber._code_switch_spans_preserved(
        "mini 版を確認します", "迷你版を確認します。"
    ) is False
    assert mock_transcriber._code_switch_spans_preserved(
        "GitHub を確認します", "github を確認します。"
    ) is True
    assert mock_transcriber._code_switch_spans_preserved(
        "Use Node.js", "Use Node.js."
    ) is True
    assert mock_transcriber._code_switch_spans_preserved(
        "これはとてもいいです", "これは、とてもいいです。"
    ) is True
    assert mock_transcriber._code_switch_spans_preserved(
        "えーとそれで確認します", "それで確認します。"
    ) is True
    assert mock_transcriber._code_switch_spans_preserved(
        "SEO 跟 GO", "SEO 跟 GEO"
    ) is True
    assert mock_transcriber._code_switch_spans_preserved(
        "Twilo API", "Twilio API"
    ) is True
    assert mock_transcriber._code_switch_spans_preserved(
        "といあわせフォーム", "問い合わせフォーム"
    ) is True
    assert mock_transcriber._code_switch_spans_preserved(
        "カタカナを確認します", "確認內容。"
    ) is False
    assert mock_transcriber._code_switch_spans_preserved(
        "カタカナを確認します", "かたかなを確認します。"
    ) is False


def test_validator_discards_code_switch_translation(mock_transcriber):
    raw = "来週 supplier と確認します"
    status, result = mock_transcriber._validate_llm_result(
        raw, "来週サプライヤーと確認します。", "Test", mode="dictate"
    )
    assert status == "discard"
    assert result is None


def test_validator_returns_canonicalized_provider_output(mock_transcriber):
    status, result = mock_transcriber._validate_llm_result(
        "Twilio API を使います", "Twilo API を使います。", "Test", mode="dictate"
    )
    assert status == "ok"
    assert result == "Twilio API を使います。"

    status, result = mock_transcriber._validate_llm_result(
        "SEO 跟 GEO", "SEO 跟 GO", "Test", mode="dictate"
    )
    assert status == "ok"
    assert result == "SEO 跟 GEO"

    status, result = mock_transcriber._validate_llm_result(
        "contact form", "content form", "Test", mode="dictate"
    )
    assert status == "ok"
    assert result == "contact form"


def test_trailing_truncation_never_delivers_opencc_corrupted_japanese(mock_transcriber):
    raw = "学生学校科学学会図書館確認"
    llm = raw + "追加説明内容"
    truncated = mock_transcriber._truncate_trailing_hallucination(raw, llm)
    assert truncated == raw + "。"
    assert "學生" not in truncated and "學校" not in truncated and "學會" not in truncated


def test_pipeline_uses_stt_language_hint_for_kanji_only_japanese(
    mock_transcriber, monkeypatch,
):
    import transcriber as tr_mod

    mock_transcriber.config.update({
        "enable_audio_gate": False,
        "enable_hybrid_mode": True,
        "enable_claude_polish": False,
        "stt_engine": "mlx-whisper",
    })
    monkeypatch.setattr(tr_mod, "detect_app_style", lambda config: {
        "bundle_id": "", "app_name": "", "style": "default", "prompt": "",
    })
    monkeypatch.setattr(
        mock_transcriber,
        "_local_stt",
        lambda source: {"text": "参考", "language": "ja"},
    )
    result = mock_transcriber._transcribe_impl(
        np.ones(16000, dtype=np.float32), 1.0, "dictate", "", None,
    )
    assert result["final"] == "参考"
    assert mock_transcriber.memory.history[-1]["detected_language"] == "ja"


def test_pipeline_translation_target_overrides_stt_source_language(
    mock_transcriber, monkeypatch,
):
    import transcriber as tr_mod

    mock_transcriber.config.update({
        "enable_audio_gate": False,
        "enable_hybrid_mode": True,
        "enable_claude_polish": True,
        "stt_engine": "mlx-whisper",
        "llm_engine": "groq",
        "groq_api_key": "test-only",
    })
    monkeypatch.setattr(tr_mod, "detect_app_style", lambda config: {
        "bundle_id": "", "app_name": "", "style": "default", "prompt": "",
    })
    monkeypatch.setattr(
        mock_transcriber,
        "_local_stt",
        lambda source: {"text": "這是一段中文內容", "language": "zh"},
    )
    monkeypatch.setattr(
        mock_transcriber,
        "_groq_llm_process",
        lambda *args, **kwargs: "参考",
    )
    result = mock_transcriber._transcribe_impl(
        np.ones(16000, dtype=np.float32), 1.0, "edit", "translate_ja", None,
    )
    assert result["final"] == "参考"

    monkeypatch.setattr(
        mock_transcriber,
        "_local_stt",
        lambda source: {"text": "日本語の内容です", "language": "ja"},
    )
    result = mock_transcriber._transcribe_impl(
        np.ones(16000, dtype=np.float32), 1.0, "edit", "translate_zh", None,
    )
    assert result["final"] == "參考"


def test_dictate_prompt_contains_multilingual_contract(mock_transcriber):
    prompt = mock_transcriber._get_system_prompt(
        {"bundle_id": "com.openai.codex", "app_name": "Codex"}
    )
    assert "supplier stays supplier" in prompt
    assert "画像" in prompt and "来週" in prompt
    for term in (
        "SEO", "AEO", "GEO", "contact form", "お問い合わせフォーム",
        "問い合わせフォーム", "カタカナ", "ひらがな", "JSON-LD", "hreflang",
    ):
        assert term in prompt
