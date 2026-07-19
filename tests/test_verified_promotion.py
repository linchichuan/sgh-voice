"""Verified-only dictionary promotion and history-learning safety tests.

All fixtures are in-memory or tmp_path based; these tests never inspect real history.
"""
import json
import sys
from pathlib import Path

import pytest


def _history(raw, final, *, edited):
    return {
        "timestamp": "2026-07-20T00:00:00",
        "whisper_raw": raw,
        "final_text": final,
        "edited": edited,
    }


def test_promote_api_defaults_to_verified_history_and_applies_only_selection(
    empty_memory, monkeypatch
):
    import config
    import dashboard

    empty_memory.history = [
        _history("clod code", "Claude code", edited=True),
        _history("clod desktop", "Claude desktop", edited=True),
        _history("type less app", "Typeless app", edited=True),
        _history("type less tool", "Typeless tool", edited=True),
        # More frequent, but not user verified: this must not enter default candidates.
        *[_history("lime bot", "LINE bot", edited=False) for _ in range(5)],
    ]
    monkeypatch.setattr(dashboard, "memory", empty_memory)
    monkeypatch.setattr(config, "save_dictionary", lambda value: None)
    client = dashboard.app.test_client()

    preview = client.post(
        "/api/dictionary/promote_from_history",
        json={"min_freq": 2, "apply": False},
    )
    assert preview.status_code == 200
    payload = preview.get_json()
    assert payload["source"] == "edited"
    pairs = {(p["wrong"], p["right"]) for p in payload["promoted"]}
    assert ("clod", "Claude") in pairs
    assert ("lime", "LINE") not in pairs

    applied = client.post(
        "/api/dictionary/promote_from_history",
        json={
            "min_freq": 2,
            "source": "edited",
            "apply": True,
            "selected": [{"wrong": "clod", "right": "Claude"}],
        },
    )
    assert applied.status_code == 200
    assert applied.get_json()["promoted"] == [
        {"wrong": "clod", "right": "Claude", "freq": 2}
    ]
    assert empty_memory.dictionary["corrections"] == {"clod": "Claude"}


@pytest.mark.parametrize("source", ["auto", "both"])
def test_promote_api_rejects_legacy_sources_for_apply(
    source, empty_memory, monkeypatch
):
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    response = dashboard.app.test_client().post(
        "/api/dictionary/promote_from_history",
        json={
            "source": source,
            "apply": True,
            "selected": [{"wrong": "clod", "right": "Claude"}],
        },
    )
    assert response.status_code == 400
    assert "preview-only" in response.get_json()["error"]


def test_history_patch_persists_edit_but_respects_disabled_auto_learn(monkeypatch):
    import dashboard

    calls = {"updated": [], "learned": []}

    class FakeMemory:
        def update_history_item(self, timestamp, new_text):
            calls["updated"].append((timestamp, new_text))
            return "clod code"

        def learn_correction(self, old_text, new_text, source):
            calls["learned"].append((old_text, new_text, source))
            return [{"wrong": "clod", "right": "Claude"}]

    monkeypatch.setattr(dashboard, "memory", FakeMemory())
    monkeypatch.setattr(
        dashboard, "load_config", lambda: {"enable_auto_learn": False}
    )
    response = dashboard.app.test_client().patch(
        "/api/history/2026-07-20T00:00:00",
        json={"final_text": "Claude code"},
    )
    assert response.status_code == 200
    assert calls["updated"] == [
        ("2026-07-20T00:00:00", "Claude code")
    ]
    assert calls["learned"] == []
    assert response.get_json()["learned"] == []


def test_pipeline_error_mining_uses_only_verified_history_and_guardian():
    from scripts import pipeline_health

    history = [
        *[_history("clod code", "Claude code", edited=True) for _ in range(3)],
        *[_history("alpha code", "omega code", edited=True) for _ in range(3)],
        *[_history("lime bot", "LINE bot", edited=False) for _ in range(6)],
    ]
    result = pipeline_health.mine_error_patterns(history, {"corrections": {}})

    assert result["verified_records"] == 6
    assert [(x["wrong"], x["right"]) for x in result["uncovered"]] == [
        ("clod", "Claude")
    ]


def test_pipeline_auto_fix_rechecks_guardian(tmp_path, monkeypatch):
    from scripts import pipeline_health

    dictionary = {"corrections": {}}
    monkeypatch.setattr(pipeline_health, "DICT_FILE", tmp_path / "dictionary.json")
    added = pipeline_health.auto_apply_corrections(
        {
            "uncovered": [
                {"wrong": "clod", "right": "Claude", "count": 3},
                {"wrong": "alpha", "right": "omega", "count": 5},
            ]
        },
        dictionary,
    )

    assert added == 1
    assert dictionary["corrections"] == {"clod": "Claude"}
    assert json.loads((tmp_path / "dictionary.json").read_text())["corrections"] == {
        "clod": "Claude"
    }


def test_dictionary_promote_cli_refuses_legacy_apply(monkeypatch):
    from scripts import dictionary_promote_from_history as promote

    monkeypatch.setattr(
        sys, "argv", ["dictionary_promote_from_history.py", "--apply", "--source", "both"]
    )
    with pytest.raises(SystemExit) as exc:
        promote.main()
    assert exc.value.code == 2


def test_promote_modal_defaults_verified_and_sends_selected_pairs():
    source = (
        Path(__file__).parents[1]
        / "static/js/pages/dictionary/promote-modal.js"
    ).read_text(encoding="utf-8")

    assert "value: 'edited', selected: ''" in source
    assert "selected: items.map(({ wrong, right }) => ({ wrong, right }))" in source
    assert "sourceSel.value !== 'edited'" in source


def test_model_status_uses_hf_cache_for_non_absolute_alias(tmp_path, monkeypatch):
    import dashboard

    hf_home = tmp_path / "huggingface"
    snapshot = (
        hf_home
        / "hub/models--mlx-community--whisper-turbo/snapshots/revision"
    )
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("HF_HOME", str(hf_home))

    response = dashboard.app.test_client().get("/api/model/status/whisper-turbo")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["repo"] == "mlx-community/whisper-turbo"
    assert payload["downloaded"] is True
