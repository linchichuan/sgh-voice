"""End-to-end tests for the approval-gated LLM post-processing fallback chain.

transcriber.py:671-736 builds `routes_map` keyed by `llm_engine` and walks the
route list (e.g. groq -> openrouter -> claude -> openai -> ollama) until one
provider returns a validated result. Cross-provider fallback is opt-in because
it sends the same transcript to another data processor. Without consent,
failures must degrade locally instead of crossing a second cloud boundary.

No real network or Ollama calls are made. `Transcriber._get_openai_client`
and `Transcriber._get_anthropic_client` are monkeypatched per-test to return
fake clients whose `.chat.completions.create()` / `.messages.create()`
either raise (simulating a dead key / timeout / network drop) or return a
canned response object shaped like the real SDK response, so the *real*
`_groq_llm_process` / `_openrouter_process` / `_claude_process` /
`_openai_process` bodies run untouched -- including `_validate_llm_result`
and the hallucination detector.

`_local_llm_process` (ollama) is exercised through the real detector-status
short-circuit: `mock_transcriber`'s `get_detector()` returns a fresh
MagicMock() each call, whose `.status` never equals `OllamaStatus.CONNECTED`,
so the real function's own "not connected -> return None" branch runs
without needing a fake HTTP client.
"""

from types import SimpleNamespace

import event_ledger


# A neutral, keyword-free Chinese sentence, deliberately > 60 chars so
# `_should_skip_llm` takes neither the "<=20 chars" nor the "<=60 chars +
# CJK-only + action word" skip branch, guaranteeing every test actually
# reaches the enable_claude_polish / routes_map block under test.
RAW_TEXT = (
    "今天下午的產品會議討論了新版本上線的時程規劃，包含測試排程、跨部門溝通、"
    "風險評估與上線後的監控作業安排，另外也提到教育訓練與客服支援的準備進度"
)
assert len(RAW_TEXT) > 60, "sample text too short, would hit _should_skip_llm"
assert not RAW_TEXT.startswith(("好的", "以下是")), "sample must not collide with _CONV_MARKERS"


def _oai_response(text, prompt_tokens=5, completion_tokens=5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def _claude_response(text, stop_reason="end_turn", input_tokens=5, output_tokens=5):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class _FakeChatClient:
    """Stands in for the cached openai.OpenAI-shaped client."""

    def __init__(self, behavior):
        self._behavior = behavior
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        return self._behavior(**kwargs)

    def with_options(self, timeout=None):
        return self


class _FakeAnthropicClient:
    def __init__(self, behavior):
        self._behavior = behavior
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        return self._behavior(**kwargs)

    def with_options(self, timeout=None):
        return self


def _behavior(tag, calls, *, raise_exc=None, text=None, claude=False):
    def _run(**kwargs):
        calls.append(tag)
        if raise_exc is not None:
            raise raise_exc
        return _claude_response(text) if claude else _oai_response(text)
    return _run


def _prepare(monkeypatch, transcriber, *, openai_clients=None, anthropic_client=None, **overrides):
    """Shared setup: isolate config, kill unrelated variance, wire fake clients."""
    import transcriber as tr_mod

    transcriber.config.update({
        "enable_audio_gate": False,
        "enable_claude_polish": True,
        "enable_voice_commands": False,  # keep RAW_TEXT from tripping voice-command detection
        "enable_filler_removal": False,  # regex-fallback path must equal `corrected` verbatim
        "active_scene": "general",
        "llm_engine": "groq",
        "allow_cross_provider_llm_fallback": False,
        "groq_api_key": "",
        "openrouter_api_key": "",
        "anthropic_api_key": "",
        "openai_api_key": "",
        "enable_hybrid_mode": False,
        **overrides,
    })
    monkeypatch.setattr(tr_mod, "detect_app_style", lambda config: {
        "bundle_id": "", "app_name": "", "style": "default", "prompt": "",
    })
    monkeypatch.setattr(transcriber, "_local_stt", lambda source: {"text": RAW_TEXT, "language": "zh"})
    # Deterministic corrected==raw: BASE_CORRECTIONS / smart_replace content is out of
    # scope for this fallback-chain test and must not silently perturb assertions.
    monkeypatch.setattr(transcriber.memory, "apply_corrections", lambda text, **kw: text)
    transcriber._opencc = None  # remove OpenCC as a source of nondeterminism

    openai_clients = openai_clients or {}
    monkeypatch.setattr(transcriber, "_get_openai_client", lambda key, **kw: openai_clients[key])
    if anthropic_client is not None:
        monkeypatch.setattr(transcriber, "_get_anthropic_client", lambda api_key, **kw: anthropic_client)


def _run(transcriber):
    return transcriber._transcribe_impl("fake.wav", 5.0, "dictate", "", None)


# ── 1. Primary engine succeeds -> no other engine is ever touched ──────────

def test_primary_engine_success_short_circuits_chain(mock_transcriber, monkeypatch):
    calls = []
    groq_client = _FakeChatClient(_behavior("groq", calls, text=RAW_TEXT))
    _prepare(
        monkeypatch, mock_transcriber,
        openai_clients={"groq_llm": groq_client},
        groq_api_key="k-groq",
    )

    def _boom(*a, **kw):
        raise AssertionError("fallback engine must not be called when primary succeeds")

    monkeypatch.setattr(mock_transcriber, "_openrouter_process", _boom)
    monkeypatch.setattr(mock_transcriber, "_claude_process", _boom)
    monkeypatch.setattr(mock_transcriber, "_openai_process", _boom)
    monkeypatch.setattr(mock_transcriber, "_local_llm_process", _boom)

    result = _run(mock_transcriber)

    assert result["final"] == RAW_TEXT
    assert calls == ["groq"]


# ── 2. Primary failure stays inside selected provider by default ──────────

def test_primary_failure_does_not_cross_provider_boundary_without_opt_in(
    mock_transcriber, monkeypatch
):
    calls = []
    groq_client = _FakeChatClient(
        _behavior("groq", calls, raise_exc=TimeoutError("simulated timeout"))
    )
    _prepare(
        monkeypatch,
        mock_transcriber,
        openai_clients={"groq_llm": groq_client},
        groq_api_key="k-groq",
        openrouter_api_key="k-or",
    )

    def _cross_provider_call(*args, **kwargs):
        raise AssertionError("cross-provider fallback requires explicit consent")

    monkeypatch.setattr(mock_transcriber, "_openrouter_process", _cross_provider_call)
    result = _run(mock_transcriber)

    assert result["final"] == RAW_TEXT
    assert calls == ["groq"]


# ── 3. Opted-in primary failure cascades to the next engine ───────────────

def test_primary_exception_cascades_to_next_engine(mock_transcriber, monkeypatch):
    calls = []
    groq_client = _FakeChatClient(_behavior("groq", calls, raise_exc=TimeoutError("simulated network timeout")))
    openrouter_client = _FakeChatClient(_behavior("openrouter", calls, text=RAW_TEXT))
    _prepare(
        monkeypatch, mock_transcriber,
        openai_clients={"groq_llm": groq_client, "openrouter_llm": openrouter_client},
        groq_api_key="k-groq",
        openrouter_api_key="k-or",
        allow_cross_provider_llm_fallback=True,
    )

    def _boom(*a, **kw):
        raise AssertionError("claude/openai/ollama must not be reached once openrouter succeeds")

    monkeypatch.setattr(mock_transcriber, "_claude_process", _boom)
    monkeypatch.setattr(mock_transcriber, "_openai_process", _boom)
    monkeypatch.setattr(mock_transcriber, "_local_llm_process", _boom)

    result = _run(mock_transcriber)

    assert result["final"] == RAW_TEXT
    assert calls == ["groq", "openrouter"]  # real cascade order, groq attempted first


# ── 4. Every opted-in engine fails -> regex fallback ─────────────────────

def test_all_engines_fail_falls_back_to_regex(mock_transcriber, monkeypatch):
    calls = []
    groq_client = _FakeChatClient(_behavior("groq", calls, raise_exc=ConnectionError("dns fail")))
    openrouter_client = _FakeChatClient(_behavior("openrouter", calls, raise_exc=TimeoutError("timeout")))
    openai_client = _FakeChatClient(_behavior("openai", calls, raise_exc=ConnectionError("key revoked")))
    claude_client = _FakeAnthropicClient(_behavior("claude", calls, raise_exc=TimeoutError("timeout"), claude=True))

    ledger_events = []
    monkeypatch.setattr(
        event_ledger, "log",
        lambda event_type, **fields: ledger_events.append((event_type, fields)),
    )

    _prepare(
        monkeypatch, mock_transcriber,
        openai_clients={
            "groq_llm": groq_client,
            "openrouter_llm": openrouter_client,
            "openai_llm": openai_client,
        },
        anthropic_client=claude_client,
        groq_api_key="k-groq",
        openrouter_api_key="k-or",
        anthropic_api_key="k-claude",
        openai_api_key="k-openai",
        allow_cross_provider_llm_fallback=True,
        enable_hybrid_mode=True,  # required for try_ollama() to actually attempt (and fail)
    )

    result = _run(mock_transcriber)

    assert result["final"] == RAW_TEXT  # regex fallback == corrected (filler removal disabled)
    assert calls == ["groq", "openrouter", "claude", "openai"]  # ollama fails via detector, no client call
    assert ("llm_all_failed_fell_to_regex", {"mode": "dictate"}) in ledger_events


# ── 5. Hallucinated output is discarded by the validator -> reverts to source text ──

def test_hallucination_detection_reverts_to_original_text(mock_transcriber, monkeypatch):
    calls = []
    hallucinated = "以下是整理後的逐字稿內容：" + RAW_TEXT  # starts with a _CONV_MARKERS phrase
    groq_client = _FakeChatClient(_behavior("groq", calls, text=hallucinated))

    validator_events = []
    monkeypatch.setattr(
        event_ledger, "validator_action",
        lambda action, validator, engine, **kw: validator_events.append((action, validator, engine, kw)),
    )

    _prepare(
        monkeypatch, mock_transcriber,
        openai_clients={"groq_llm": groq_client},
        groq_api_key="k-groq",
    )

    result = _run(mock_transcriber)

    assert result["final"] == RAW_TEXT  # hallucinated text discarded, reverted to source
    assert calls == ["groq"]
    assert any(
        action == "discard" and kw.get("reason") == "full_segment_hallucination"
        for action, validator, engine, kw in validator_events
    ), f"expected a full_segment_hallucination discard event, got {validator_events}"
