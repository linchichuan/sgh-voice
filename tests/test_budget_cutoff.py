"""Hard monthly budget enforcement at cloud provider boundaries."""

import types
from datetime import date


def test_dashboard_rewrite_is_blocked_before_provider_when_budget_is_exhausted(
    isolated_data_dir, monkeypatch
):
    import config
    import dashboard

    config.save_stats(
        {
            "usage": {
                "2026-08": {
                    "anthropic_input_tokens": 0,
                    "anthropic_output_tokens": 1_000_000,
                }
            }
        }
    )
    monkeypatch.setattr(config, "date", type("FixedDate", (), {
        "today": staticmethod(lambda: __import__("datetime").date(2026, 8, 24))
    }))
    monkeypatch.setattr(
        dashboard,
        "load_config",
        lambda: {
            "anthropic_api_key": "synthetic-key",
            "monthly_budget_jpy": 1,
            "enable_budget_cutoff": True,
        },
    )
    monkeypatch.setattr(
        dashboard.anthropic,
        "Anthropic",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("provider must not be created after cutoff")
        ),
    )

    response = dashboard.app.test_client().post(
        "/api/rewrite",
        json={"text": "synthetic input", "style": "concise"},
    )

    assert response.status_code == 402
    assert response.get_json()["code"] == "monthly_budget_exceeded"


def test_dashboard_rewrite_usage_is_charged_to_anthropic_provider(
    isolated_data_dir, monkeypatch
):
    import config
    import dashboard

    config.save_stats({"usage": {}})
    response_object = types.SimpleNamespace(
        model="synthetic-claude",
        usage=types.SimpleNamespace(input_tokens=11, output_tokens=7),
        content=[types.SimpleNamespace(text="synthetic rewrite")],
    )
    client = types.SimpleNamespace(
        messages=types.SimpleNamespace(create=lambda **_kwargs: response_object)
    )
    monkeypatch.setattr(
        dashboard,
        "load_config",
        lambda: {
            "anthropic_api_key": "synthetic-key",
            "claude_model": "synthetic-claude",
            "monthly_budget_jpy": 0,
            "enable_budget_cutoff": False,
            "language": "en",
        },
    )
    monkeypatch.setattr(
        dashboard.anthropic, "Anthropic", lambda **_kwargs: client
    )

    response = dashboard.app.test_client().post(
        "/api/rewrite",
        json={"text": "synthetic input", "style": "concise"},
    )

    assert response.status_code == 200
    row = config.load_stats()["usage"][date.today().strftime("%Y-%m")]
    assert row["anthropic_input_tokens"] == 11
    assert row["anthropic_output_tokens"] == 7
    assert row["details"][-1]["type"] == "rewrite"


def test_dashboard_rewrite_applies_configured_provider_timeout(
    isolated_data_dir, monkeypatch
):
    import dashboard

    response_object = types.SimpleNamespace(
        model="synthetic-claude",
        usage=types.SimpleNamespace(input_tokens=1, output_tokens=1),
        content=[types.SimpleNamespace(text="synthetic rewrite")],
    )
    client = types.SimpleNamespace(
        messages=types.SimpleNamespace(create=lambda **_kwargs: response_object)
    )
    client_kwargs = []
    monkeypatch.setattr(
        dashboard,
        "load_config",
        lambda: {
            "anthropic_api_key": "synthetic-key",
            "claude_model": "synthetic-claude",
            "llm_timeout_sec": 3.5,
            "monthly_budget_jpy": 0,
            "enable_budget_cutoff": False,
            "language": "en",
        },
    )
    monkeypatch.setattr(
        dashboard.anthropic,
        "Anthropic",
        lambda **kwargs: client_kwargs.append(kwargs) or client,
    )

    response = dashboard.app.test_client().post(
        "/api/rewrite",
        json={"text": "synthetic input", "style": "concise"},
    )

    assert response.status_code == 200
    assert client_kwargs[0]["timeout"] == 3.5


def test_transcriber_blocks_cloud_stt_after_budget_cutoff(
    mock_transcriber, isolated_data_dir, tmp_path, monkeypatch
):
    import config

    month = date.today().strftime("%Y-%m")
    config.save_stats(
        {
            "usage": {
                month: {
                    "openai_output_tokens": 1_000_000,
                }
            }
        }
    )
    mock_transcriber.config.update(
        {
            "stt_engine": "cloud-only",
            "openai_api_key": "synthetic-key",
            "enable_hybrid_mode": False,
            "enable_budget_cutoff": True,
            "monthly_budget_jpy": 1,
        }
    )
    calls = []
    response = types.SimpleNamespace(text="synthetic source", language="en")
    client = types.SimpleNamespace(
        audio=types.SimpleNamespace(
            transcriptions=types.SimpleNamespace(
                create=lambda **kwargs: calls.append(kwargs) or response
            )
        )
    )
    monkeypatch.setattr(
        mock_transcriber,
        "_get_openai_client",
        lambda *_args, **_kwargs: client,
    )
    audio_file = tmp_path / "synthetic.wav"
    audio_file.write_bytes(b"synthetic")

    result = mock_transcriber.transcribe(str(audio_file), audio_duration=1.0)

    assert result is None
    assert calls == []


def test_dashboard_test_llm_respects_the_same_cloud_budget_boundary(
    isolated_data_dir, monkeypatch
):
    import config
    import dashboard
    import openai

    month = date.today().strftime("%Y-%m")
    config.save_stats(
        {"usage": {month: {"openai_output_tokens": 1_000_000}}}
    )
    monkeypatch.setattr(
        dashboard,
        "load_config",
        lambda: {
            "openai_api_key": "synthetic-key",
            "openai_model": "synthetic-model",
            "enable_budget_cutoff": True,
            "monthly_budget_jpy": 1,
        },
    )
    monkeypatch.setattr(
        openai,
        "OpenAI",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("test request must be blocked before client creation")
        ),
    )

    response = dashboard.app.test_client().post(
        "/api/test-llm", json={"engine": "openai"}
    )

    assert response.status_code == 402
    assert response.get_json()["code"] == "monthly_budget_exceeded"


def test_transcriber_blocks_cloud_llm_but_keeps_local_fallback(
    mock_transcriber, isolated_data_dir, monkeypatch
):
    import config

    month = date.today().strftime("%Y-%m")
    config.save_stats(
        {"usage": {month: {"anthropic_output_tokens": 1_000_000}}}
    )
    mock_transcriber.config.update(
        {
            "stt_engine": "mlx-whisper",
            "enable_hybrid_mode": False,
            "enable_claude_polish": True,
            "llm_engine": "claude",
            "anthropic_api_key": "synthetic-key",
            "enable_budget_cutoff": True,
            "monthly_budget_jpy": 1,
        }
    )
    monkeypatch.setattr(
        mock_transcriber,
        "_local_stt",
        lambda _audio: {
            "text": "um this is a sufficiently long synthetic source sentence",
            "language": "en",
        },
    )
    calls = []
    client = types.SimpleNamespace(
        messages=types.SimpleNamespace(
            create=lambda **kwargs: calls.append(kwargs)
        )
    )
    monkeypatch.setattr(
        mock_transcriber,
        "_get_anthropic_client",
        lambda *_args, **_kwargs: client,
    )

    result = mock_transcriber.transcribe("synthetic.wav", audio_duration=1.0)

    assert calls == []
    assert result is not None
    assert mock_transcriber.memory.history[-1]["llm_source"] == "regex"


def test_budget_cutoff_fails_closed_for_unpriced_paid_openrouter_model(
    mock_transcriber, isolated_data_dir, monkeypatch
):
    import config

    config.save_stats({"usage": {}})
    mock_transcriber.config.update(
        {
            "openrouter_api_key": "synthetic-key",
            "openrouter_model": "vendor/synthetic-paid-model",
            "enable_budget_cutoff": True,
            "monthly_budget_jpy": 1000,
        }
    )
    calls = []
    response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(
            message=types.SimpleNamespace(content="synthetic output")
        )],
        usage=types.SimpleNamespace(prompt_tokens=3, completion_tokens=2),
    )
    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(
                create=lambda **kwargs: calls.append(kwargs) or response
            )
        )
    )
    monkeypatch.setattr(
        mock_transcriber,
        "_get_openai_client",
        lambda *_args, **_kwargs: client,
    )

    result = mock_transcriber._openrouter_process(
        "synthetic source sentence", "dictate", ""
    )

    assert result is None
    assert calls == []
