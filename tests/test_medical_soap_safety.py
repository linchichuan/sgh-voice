"""Synthetic SOAP pipeline regressions; no provider/network or patient data."""
import pytest

RAW = "沒有藥物過敏。血壓 150/90。醫師評估高血壓。アムロジピン 5mg，每日一次。"
GOOD = "[S]\n沒有藥物過敏。\n[O]\n血壓 150/90。\n[A]\n醫師評估高血壓。\n[P]\nアムロジピン 5mg，每日一次。"


def prepare(t, monkeypatch, output, raw=RAW):
    import transcriber
    monkeypatch.setattr(transcriber, "detect_app_style", lambda config: {})
    t.config.update({"active_scene": "medical_consultation", "stt_engine": "mlx-whisper",
                     "enable_claude_polish": True, "llm_engine": "groq",
                     "groq_api_key": "synthetic", "enable_hybrid_mode": False})
    monkeypatch.setattr(t, "_local_stt", lambda *a, **k: raw)
    monkeypatch.setattr(t, "_groq_llm_process", lambda *a, **k: output)


@pytest.mark.parametrize("bad", [GOOD.replace("5mg", "50mg"),
    GOOD.replace("沒有藥物過敏", "有藥物過敏"),
    GOOD.replace("アムロジピン", "ワルファリン"),
    GOOD.replace("150/90", "120/80"),
    GOOD.replace("醫師評估高血壓", "醫師評估糖尿病"),
    GOOD.replace("每日一次", "每日兩次")])
def test_unsafe_soap_is_not_pasteable(mock_transcriber, monkeypatch, bad):
    prepare(mock_transcriber, monkeypatch, bad)
    result = mock_transcriber.transcribe("synthetic.wav", 1)
    assert result["final"] == ""
    assert result["error"] == "medical_soap_failed"
    assert result["raw"] == RAW
    entry = mock_transcriber.memory.history[-1]
    assert entry["whisper_raw"] == RAW
    assert entry["soap_status"] == "failed"
    assert bad not in entry.values()


def test_soap_draft_requires_manual_review(mock_transcriber, monkeypatch):
    prepare(mock_transcriber, monkeypatch, GOOD)
    result = mock_transcriber.transcribe("synthetic.wav", 1)
    assert result["final"] == ""
    assert result["error"] == "medical_soap_review_required"
    assert result["soap_draft"] == GOOD
    assert mock_transcriber.memory.history[-1]["mode"] == "medical_soap"


def test_soap_disabled_polish_does_not_silently_paste_raw(mock_transcriber, monkeypatch):
    prepare(mock_transcriber, monkeypatch, None)
    mock_transcriber.config["enable_claude_polish"] = False
    result = mock_transcriber.transcribe("synthetic.wav", 1)
    assert result["final"] == ""
    assert result["error"] == "medical_soap_failed"


def test_soap_retry_keeps_guard_after_scene_change(mock_transcriber, monkeypatch):
    prepare(mock_transcriber, monkeypatch, GOOD.replace("5mg", "50mg"))
    mock_transcriber.transcribe("synthetic.wav", 1)
    mock_transcriber.config["active_scene"] = "general"
    result = mock_transcriber.retry_last_llm()
    assert result["final"] == ""
    assert result["error"] == "medical_soap_failed"


def test_soap_bypasses_personal_replacements(mock_transcriber, monkeypatch):
    prepare(mock_transcriber, monkeypatch, GOOD)
    def forbidden(*args, **kwargs):
        pytest.fail("SOAP must use original STT, not personal replacements")
    monkeypatch.setattr(mock_transcriber.memory, "apply_corrections", forbidden)
    monkeypatch.setattr(mock_transcriber, "_apply_smart_replace", forbidden)
    mock_transcriber.transcribe("synthetic.wav", 1)


def test_soap_voice_command_cannot_bypass_guard(mock_transcriber, monkeypatch):
    prepare(mock_transcriber, monkeypatch, GOOD)
    monkeypatch.setattr(mock_transcriber, "_detect_voice_command", lambda raw: ("changed", "email"))
    result = mock_transcriber.transcribe("synthetic.wav", 1)
    assert result["raw"] == RAW
    assert result["final"] == ""


@pytest.mark.parametrize("raw,draft", [
    ("No allergy. Dose 2.5 mg.", "[S]\nNo allergy. Dose 2.5 mg.\n[O]\n[A]\n[P]"),
    ("発熱なし。血圧 150/90。", "[S]\n発熱なし。\n[O]\n血圧 150/90。\n[A]\n[P]"),
    ("疼痛。疼痛。", "[S]\n疼痛。疼痛。\n[O]\n[A]\n[P]"),
])
def test_verbatim_multilingual_draft_and_empty_sections(raw, draft):
    from medical_soap import validate_soap_draft
    assert validate_soap_draft(raw, draft) == (draft, "review_required")


@pytest.mark.parametrize("draft", [GOOD + "\n建議住院。", GOOD.replace("沒有藥物過敏。", ""),
    GOOD.replace("[O]", "[P]"), GOOD.replace("[O]", "[O] 正常"),
    "以下是摘要：\n" + GOOD, GOOD.replace("沒有藥物過敏。", "沒有藥物過敏。沒有藥物過敏。")])
def test_structure_omission_duplication_and_invention_rejected(draft):
    from medical_soap import validate_soap_draft
    assert validate_soap_draft(RAW, draft)[0] is None


def test_history_failure_is_not_reported_as_persisted(mock_transcriber, monkeypatch):
    from medical_soap import result_message
    prepare(mock_transcriber, monkeypatch, GOOD)
    monkeypatch.setattr(mock_transcriber.memory, "add_to_history", lambda entry: False)
    result = mock_transcriber.transcribe("synthetic.wav", 1)
    assert result["source_recoverable"] is False
    assert result["final"] == ""
    assert "寫入失敗" in result_message(result)
    assert mock_transcriber._last_stt_cache["raw"] == RAW


def test_history_edit_does_not_train_personal_dictionary(empty_memory, monkeypatch):
    import dashboard
    entry = {"timestamp": "2026-10-09T00:00:00", "mode": "medical_soap",
             "pipeline_mode": "medical_soap", "whisper_raw": RAW, "final_text": GOOD}
    empty_memory.add_to_history(entry)
    monkeypatch.setattr(dashboard, "memory", empty_memory)
    monkeypatch.setattr(dashboard, "load_config", lambda: {"enable_auto_learn": True})
    monkeypatch.setattr(empty_memory, "learn_correction", lambda *a, **k: pytest.fail("medical draft learned"))
    response = dashboard.app.test_client().patch(
        "/api/history/2026-10-09T00:00:00", json={"final_text": GOOD.replace("5mg", "2.5mg")})
    assert response.status_code == 200
    assert response.get_json()["learned"] == []
    assert empty_memory.history[-1]["edited"] is False
    assert empty_memory.history[-1]["medical_review_edited"] is True


@pytest.mark.parametrize("error", ["medical_soap_failed", "medical_soap_review_required"])
def test_app_recording_path_never_pastes_medical_draft(monkeypatch, isolated_data_dir, error):
    import app
    from tests.test_paste_idempotency import _build_engine
    pasted, notices = [], []
    engine = _build_engine(monkeypatch, pasted)
    monkeypatch.setattr(app, "notify", lambda title, text: notices.append(text))
    engine.transcriber.transcribe = lambda *a, **k: {
        "error": error, "final": "", "raw": RAW, "soap_draft": GOOD, "source_recoverable": True}
    engine._transcribe_and_paste(None, None, 1.0, "dictate", "", 1000.0, None)
    assert pasted == []
    assert notices and "SOAP" in notices[0]


def test_app_retry_never_pastes_medical_draft(monkeypatch, isolated_data_dir):
    import app
    from tests.test_paste_idempotency import _build_engine
    pasted, notices = [], []
    engine = _build_engine(monkeypatch, pasted)
    monkeypatch.setattr(app, "notify", lambda title, text: notices.append(text))
    engine.transcriber._last_stt_cache = {"raw": RAW}
    engine.transcriber.retry_last_llm = lambda **k: {
        "error": "medical_soap_review_required", "final": "", "soap_draft": GOOD,
        "source_recoverable": True}
    engine.retry_last_transcription()
    assert pasted == []
    assert notices and "SOAP" in notices[0]
    assert engine._retry_in_progress is False


def test_soap_history_does_not_become_few_shot_even_after_review(mock_transcriber, monkeypatch):
    prepare(mock_transcriber, monkeypatch, GOOD)
    mock_transcriber.transcribe("synthetic.wav", 1)
    entry = mock_transcriber.memory.history[-1]
    mock_transcriber.memory.update_history_item(entry["timestamp"], GOOD)
    assert entry["edited"] is False
    assert entry["medical_review_edited"] is True
    examples = mock_transcriber.memory.get_few_shot_examples(n=20, verified_only=True)
    assert all(RAW not in str(example) for example in examples)


def test_app_continuous_path_never_pastes_medical_draft(monkeypatch, isolated_data_dir):
    import app
    from tests.test_paste_idempotency import _build_engine
    pasted, notices, callbacks = [], [], {}
    engine = _build_engine(monkeypatch, pasted)
    engine._recorder_transition_lock = app.threading.RLock()
    engine.recorder = type("Recorder", (), {
        "start_continuous": lambda self, **kwargs: callbacks.update(kwargs) or True})()
    monkeypatch.setattr(app, "notify", lambda title, text: notices.append(text))
    engine.transcriber.transcribe = lambda *a, **k: {
        "error": "medical_soap_review_required", "final": "", "soap_draft": GOOD,
        "source_recoverable": True}
    assert engine.start_continuous_mode() is True
    callbacks["on_segment"]([0.1], 1.0)
    assert pasted == []
    assert notices and "SOAP" in notices[0]


@pytest.mark.parametrize("mode,pipeline_mode,should_learn", [
    ("medical_soap", "medical_soap", False),
    ("retry(medical_soap)", "medical_soap", False),
    ("edit", "medical_soap", False),
    ("dictate", "dictate", True),
    ("continuous", "dictate", True),
])
def test_actual_clipboard_observer_excludes_medical_drafts(
        monkeypatch, isolated_data_dir, mode, pipeline_mode, should_learn):
    """Drive one real observer iteration; no actual macOS clipboard or thread."""
    import sys
    import types
    from datetime import datetime
    import app

    original = "[S] 病患沒有藥物過敏。\n[O] 血壓 150/90。\n[A] 高血壓。\n[P] アムロジピン 5mg，每日一次。"
    copied = original.replace("高血壓。", "疑似原發性高血壓。")
    updated, learned, targets = [], [], []
    counts = iter([1, 2])
    pb = types.SimpleNamespace(changeCount=lambda: next(counts),
        pasteboardItems=lambda: [object()], stringForType_=lambda kind: copied)
    monkeypatch.setitem(sys.modules, "AppKit", types.SimpleNamespace(
        NSPasteboard=types.SimpleNamespace(generalPasteboard=lambda: pb)))
    class FakeThread:
        def __init__(self, target, **kwargs):
            targets.append(target)
        def start(self):
            pass
    monkeypatch.setattr(app.threading, "Thread", FakeThread)
    monkeypatch.setattr(app, "_consume_internal_pasteboard_generation", lambda count: False)
    class EndIteration(Exception):
        pass
    sleeps = []
    def tick(seconds):
        if sleeps:
            raise EndIteration
        sleeps.append(seconds)
    monkeypatch.setattr(app.time, "sleep", tick)
    entry = {"timestamp": datetime.now().isoformat(), "final_text": original,
             "mode": mode, "pipeline_mode": pipeline_mode}
    engine = types.SimpleNamespace(config={"enable_auto_learn": True}, is_recording=False,
        memory=types.SimpleNamespace(get_history=lambda **k: [entry],
            update_history_item=lambda *a, **k: updated.append((a, k)) or original,
            learn_correction=lambda *a, **k: learned.append((a, k)) or []))
    app.start_clipboard_observer(engine)
    with pytest.raises(EndIteration):
        targets[0]()
    assert bool(updated) is should_learn
    assert bool(learned) is should_learn


@pytest.mark.parametrize("raw,draft", [
    ("沒有藥物過敏。血壓 150/90。", "[S]\n沒有藥物過敏。\n改用藥物 50mg 每日兩次\n血壓 150/90。\n[O]\n[A]\n[P]"),
    ("沒有藥物過敏\n血壓 150/90。", "[S]\n血壓 150/90。\n[O]\n[A]\n[P]"),
])
def test_unpunctuated_middle_lines_cannot_be_invented_or_omitted(raw, draft):
    from medical_soap import validate_soap_draft
    assert validate_soap_draft(raw, draft)[0] is None


def test_every_non_whitespace_character_participates_in_soap_comparison():
    from medical_soap import sentences, validate_soap_draft
    raw = "沒有過敏\n血壓 150/90。\n2.5mg 每日一次\n!"
    parts = sentences(raw)
    assert "沒有過敏" in parts
    assert "2.5mg 每日一次" in parts
    assert "!" in parts
    assert "".join("".join(parts).split()) == "".join(raw.split())
    draft = "[S]\n沒有過敏\n[O]\n血壓 150/90。\n[A]\n!\n[P]\n2.5mg 每日一次"
    assert validate_soap_draft(raw, draft)[0] == draft
