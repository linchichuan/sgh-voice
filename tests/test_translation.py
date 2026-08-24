import time

import pytest

from translation import (
    TranslationError,
    build_translation_directive,
    format_translation_output,
    normalize_translation_targets,
    parse_translation_response,
    validate_translation_semantics,
)


def test_normalize_translation_targets_deduplicates_and_preserves_order():
    assert normalize_translation_targets(["日文", "ko", "ja", "英文"]) == (
        "ja",
        "ko",
        "en",
    )


@pytest.mark.parametrize(
    "targets",
    [
        [],
        ["ja", "ko", "en", "zh-Hant", "fr"],
        ["unsupported"],
        ["ja", object()],
    ],
)
def test_normalize_translation_targets_rejects_invalid_requests(targets):
    with pytest.raises(TranslationError):
        normalize_translation_targets(targets)


def test_translation_directive_requires_exact_json_and_preserves_terms():
    directive = build_translation_directive(["ja", "ko"])
    assert '["ja", "ko"]' in directive
    assert "exactly one JSON object" in directive
    assert "names, brands, medical terms, numbers, dates, URLs" in directive
    assert "questions must remain questions" in directive
    assert "requests or commands must remain requests or commands" in directive
    assert "Never turn a question or request into an answer" in directive
    assert "assistant-style prefaces" in directive


def test_parse_and_format_single_translation_without_label():
    parsed = parse_translation_response('{"ja":"明日、連絡します。"}', ["ja"])
    assert format_translation_output(parsed, ["ja"]) == "明日、連絡します。"


def test_parse_and_format_multiple_translations_in_target_order():
    parsed = parse_translation_response(
        '{"ko":"내일 연락하겠습니다.","ja":"明日、連絡します。"}',
        ["ja", "ko"],
    )
    assert format_translation_output(parsed, ["ja", "ko"]) == (
        "【日本語】\n明日、連絡します。\n\n"
        "【한국어】\n내일 연락하겠습니다."
    )


@pytest.mark.parametrize(
    "response",
    [
        "```json\n{\"ja\":\"ok\"}\n```",
        '{"ja":"ok","ko":"extra"}',
        '{"ko":"missing ja"}',
        '{"ja":""}',
        '["not", "an", "object"]',
    ],
)
def test_parse_translation_response_fails_closed(response):
    with pytest.raises(TranslationError):
        parse_translation_response(response, ["ja"])


def test_semantic_guard_accepts_questions_preserved_in_all_supported_languages():
    source = "請問明天幾點到？"
    translations = {
        "zh-Hant": "請問明天幾點到？",
        "ja": "明日は何時に到着しますか？",
        "en": "What time will you arrive tomorrow?",
        "ko": "내일 몇 시에 도착하나요?",
    }

    assert validate_translation_semantics(
        source,
        translations,
        ["zh-Hant", "ja", "en", "ko"],
    ) == translations


def test_semantic_guard_rejects_assistant_answer_inside_valid_json():
    source = "你今天好嗎？"
    parsed = parse_translation_response(
        '{"ja":"はい、元気です。"}',
        ["ja"],
    )

    with pytest.raises(TranslationError, match="assistant answer"):
        validate_translation_semantics(source, parsed, ["ja"])


@pytest.mark.parametrize(
    "answer",
    [
        "今日は元気です。",
        "今日は元気ですか？私は元気です。",
    ],
)
def test_semantic_guard_rejects_question_changed_into_direct_answer(answer):
    with pytest.raises(TranslationError, match="preserve the source question"):
        validate_translation_semantics(
            "你今天好嗎？",
            {"ja": answer},
            ["ja"],
        )


@pytest.mark.parametrize(
    ("source", "answer", "target"),
    [
        ("What time will you arrive tomorrow", "我明天上午十點到。", "zh-Hant"),
        ("幾點開始", "午前十時に始まります。", "ja"),
        ("何時に始まる", "오전 열 시에 시작합니다.", "ko"),
        ("Can I change the appointment", "予約を変更しました。", "ja"),
    ],
)
def test_semantic_guard_detects_question_without_terminal_question_mark(
    source, answer, target
):
    with pytest.raises(TranslationError, match="preserve the source question"):
        validate_translation_semantics(
            source,
            {target: answer},
            [target],
        )


def test_semantic_guard_accepts_requests_preserved_in_all_supported_languages():
    source = "請確認明天的預約。"
    translations = {
        "zh-Hant": "請確認明天的預約。",
        "ja": "明日の予約をご確認ください。",
        "en": "Please confirm tomorrow's appointment.",
        "ko": "내일 예약을 확인해 주세요.",
    }

    assert validate_translation_semantics(
        source,
        translations,
        ["zh-Hant", "ja", "en", "ko"],
    ) == translations


def test_semantic_guard_rejects_request_changed_into_completed_action():
    with pytest.raises(TranslationError, match="preserve the source request"):
        validate_translation_semantics(
            "請確認明天的預約。",
            {"ja": "明日の予約を確認しました。"},
            ["ja"],
        )


def test_semantic_guard_allows_polite_request_question_to_become_imperative():
    translations = {"ja": "明日の予約をご確認ください。"}

    assert validate_translation_semantics(
        "Could you confirm tomorrow's appointment?",
        translations,
        ["ja"],
    ) == translations


def test_semantic_guard_allows_formal_japanese_request_expansion():
    translations = {
        "ja": "明日、クリニックへご連絡くださいますようお願いいたします。",
    }

    assert validate_translation_semantics(
        "Please contact the clinic tomorrow.",
        translations,
        ["ja"],
    ) == translations


def test_semantic_guard_rejects_unsolicited_assistant_preface():
    with pytest.raises(TranslationError, match="assistant answer"):
        validate_translation_semantics(
            "明天會更新版本。",
            {"en": "Sure, the version will be updated tomorrow."},
            ["en"],
        )


def test_semantic_guard_rejects_exact_source_echo_for_different_target_language():
    with pytest.raises(TranslationError, match="unchanged source"):
        validate_translation_semantics(
            "明天會更新版本。",
            {"en": "明天會更新版本。"},
            ["en"],
        )


def test_semantic_guard_rejects_wrong_language_paraphrase():
    with pytest.raises(TranslationError, match="target language"):
        validate_translation_semantics(
            "明天會更新版本。",
            {"en": "明天將更新系統版本。"},
            ["en"],
        )


def test_semantic_guard_allows_preface_when_it_exists_in_the_source():
    translations = {
        "en": "Of course, the version will be updated tomorrow.",
    }

    assert validate_translation_semantics(
        "當然，明天會更新版本。",
        translations,
        ["en"],
    ) == translations


def test_semantic_guard_rejects_extreme_expansion_without_another_model_call():
    expanded = (
        "Please confirm this request, review every available option, explain all "
        "possible consequences, and provide a detailed implementation plan for "
        "the entire team, including costs, timelines, risks, owners, and every "
        "required follow-up action."
    )

    with pytest.raises(TranslationError, match="expanded far beyond"):
        validate_translation_semantics(
            "請確認。",
            {"en": expanded},
            ["en"],
        )


def test_semantic_guard_keeps_short_cross_script_translations_practical():
    translations = {"ja": "磁気共鳴画像法"}

    assert validate_translation_semantics(
        "MRI",
        translations,
        ["ja"],
    ) == translations


@pytest.mark.parametrize(
    ("source", "translations", "targets"),
    [
        ("", {"ja": "テスト"}, ["ja"]),
        ("測試", ["テスト"], ["ja"]),
        ("測試", {"ko": "테스트"}, ["ja"]),
    ],
)
def test_semantic_guard_rejects_invalid_inputs(source, translations, targets):
    with pytest.raises(TranslationError):
        validate_translation_semantics(source, translations, targets)


def _configure_offline_translation(mock_transcriber):
    mock_transcriber.config.update({
        "stt_engine": "mlx-whisper",
        "enable_hybrid_mode": False,
        "enable_audio_gate": False,
        "enable_claude_polish": True,
        "llm_engine": "groq",
        "groq_api_key": "test-only",
        "openrouter_api_key": "",
        "anthropic_api_key": "",
        "openai_api_key": "",
        "translation_target_languages": ["ja", "ko"],
    })


def test_translation_pipeline_uses_one_stt_and_one_llm_for_multiple_targets(
    mock_transcriber, monkeypatch
):
    import transcriber as transcriber_module

    _configure_offline_translation(mock_transcriber)
    calls = {"stt": 0, "llm": 0}
    monkeypatch.setattr(transcriber_module, "detect_app_style", lambda _cfg: {
        "bundle_id": "",
        "app_name": "",
        "style": "default",
        "prompt": "",
    })

    def fake_stt(_audio):
        calls["stt"] += 1
        return "明天請聯絡我"

    def fake_llm(text, mode, directive, system_prompt=None):
        calls["llm"] += 1
        assert text == "明天請聯絡我"
        assert mode == "translate"
        assert '["ja", "ko"]' in directive
        assert "Do not add, omit, summarize, answer" in directive
        return '{"ja":"明日、連絡してください。","ko":"내일 연락해 주세요."}'

    monkeypatch.setattr(mock_transcriber, "_local_stt", fake_stt)
    monkeypatch.setattr(mock_transcriber, "_groq_llm_process", fake_llm)

    result = mock_transcriber._transcribe_impl(
        "offline.wav", 1.0, "translate", "", None, None, ["ja", "ko"],
    )

    assert calls == {"stt": 1, "llm": 1}
    assert result["translations"] == {
        "ja": "明日、連絡してください。",
        "ko": "내일 연락해 주세요.",
    }
    assert result["final"] == (
        "【日本語】\n明日、連絡してください。\n\n"
        "【한국어】\n내일 연락해 주세요."
    )


def test_translation_pipeline_rejects_malformed_provider_and_uses_next(
    mock_transcriber, monkeypatch
):
    import transcriber as transcriber_module

    _configure_offline_translation(mock_transcriber)
    mock_transcriber.config["openrouter_api_key"] = "test-only"
    mock_transcriber.config["allow_cross_provider_llm_fallback"] = True
    calls = []
    monkeypatch.setattr(transcriber_module, "detect_app_style", lambda _cfg: {
        "bundle_id": "",
        "app_name": "",
        "style": "default",
        "prompt": "",
    })
    monkeypatch.setattr(mock_transcriber, "_local_stt", lambda _audio: "測試")
    monkeypatch.setattr(
        mock_transcriber,
        "_groq_llm_process",
        lambda *_args, **_kwargs: calls.append("groq") or "not-json",
    )
    monkeypatch.setattr(
        mock_transcriber,
        "_openrouter_process",
        lambda *_args, **_kwargs: calls.append("openrouter")
        or '{"ja":"テスト","ko":"테스트"}',
    )

    result = mock_transcriber._transcribe_impl(
        "offline.wav", 1.0, "translate", "", None, None, ["ja", "ko"],
    )

    assert calls == ["groq", "openrouter"]
    assert result["translations"] == {"ja": "テスト", "ko": "테스트"}


def test_translation_pipeline_rejects_answer_and_uses_next_provider(
    mock_transcriber, monkeypatch
):
    import transcriber as transcriber_module

    _configure_offline_translation(mock_transcriber)
    mock_transcriber.config["openrouter_api_key"] = "test-only"
    mock_transcriber.config["allow_cross_provider_llm_fallback"] = True
    calls = []
    monkeypatch.setattr(transcriber_module, "detect_app_style", lambda _cfg: {
        "bundle_id": "",
        "app_name": "",
        "style": "default",
        "prompt": "",
    })
    monkeypatch.setattr(
        mock_transcriber,
        "_local_stt",
        lambda _audio: "請問明天的門診幾點開始？",
    )
    monkeypatch.setattr(
        mock_transcriber,
        "_groq_llm_process",
        lambda *_args, **_kwargs: calls.append("groq")
        or '{"ja":"明日の外来診療は午前9時に始まります。",'
        '"ko":"내일 외래 진료는 오전 9시에 시작합니다."}',
    )
    monkeypatch.setattr(
        mock_transcriber,
        "_openrouter_process",
        lambda *_args, **_kwargs: calls.append("openrouter")
        or '{"ja":"明日の外来診療は何時に始まりますか？",'
        '"ko":"내일 외래 진료는 몇 시에 시작하나요?"}',
    )

    result = mock_transcriber._transcribe_impl(
        "offline.wav", 1.0, "translate", "", None, None, ["ja", "ko"],
    )

    assert calls == ["groq", "openrouter"]
    assert result["translations"] == {
        "ja": "明日の外来診療は何時に始まりますか？",
        "ko": "내일 외래 진료는 몇 시에 시작하나요?",
    }


def test_translation_retry_rejects_answer_and_uses_next_provider(
    mock_transcriber, monkeypatch
):
    _configure_offline_translation(mock_transcriber)
    mock_transcriber.config["openrouter_api_key"] = "test-only"
    mock_transcriber.config["allow_cross_provider_llm_fallback"] = True
    mock_transcriber._last_stt_cache = {
        "raw": "請問明天的門診幾點開始？",
        "mode": "translate",
        "edit_context": "",
        "translation_targets": ["ja", "ko"],
        "timestamp": time.time(),
        "app_info": {},
        "app_id": "",
        "detected_language": "zh",
        "stt_source": "local",
        "audio_duration": 1.0,
    }
    calls = []
    monkeypatch.setattr(
        mock_transcriber,
        "_groq_llm_process",
        lambda *_args, **_kwargs: calls.append("groq")
        or '{"ja":"明日の外来診療は午前9時に始まります。",'
        '"ko":"내일 외래 진료는 오전 9시에 시작합니다."}',
    )
    monkeypatch.setattr(
        mock_transcriber,
        "_openrouter_process",
        lambda *_args, **_kwargs: calls.append("openrouter")
        or '{"ja":"明日の外来診療は何時に始まりますか？",'
        '"ko":"내일 외래 진료는 몇 시에 시작하나요?"}',
    )

    result = mock_transcriber._retry_last_llm_inner(None)

    assert calls == ["groq", "openrouter"]
    assert result["translations"]["ja"].endswith("ますか？")
    assert result["translations"]["ko"].endswith("나요?")


def test_translation_pipeline_without_configured_llm_fails_closed(
    mock_transcriber, monkeypatch
):
    import transcriber as transcriber_module

    _configure_offline_translation(mock_transcriber)
    mock_transcriber.config.update({
        "groq_api_key": "",
        "openrouter_api_key": "",
        "anthropic_api_key": "",
        "openai_api_key": "",
    })
    monkeypatch.setattr(transcriber_module, "detect_app_style", lambda _cfg: {
        "bundle_id": "",
        "app_name": "",
        "style": "default",
        "prompt": "",
    })
    monkeypatch.setattr(mock_transcriber, "_local_stt", lambda _audio: "測試")

    result = mock_transcriber._transcribe_impl(
        "offline.wav", 1.0, "translate", "", None, None, ["ja"],
    )

    assert result["error"] == "translation_failed"
    assert result["final"] == ""
    recovery = mock_transcriber.memory.history[-1]
    assert recovery["translation_status"] == "failed"
    assert recovery["source_text"] == "測試"
    assert recovery["final_text"] == ""
