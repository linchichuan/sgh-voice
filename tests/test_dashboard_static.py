"""Tests for dashboard static asset routing."""


def test_dashboard_serves_index_and_static_assets(isolated_data_dir):
    import dashboard

    client = dashboard.app.test_client()

    assert client.get("/").status_code == 200
    assert client.get("/css/base.css").status_code == 200
    assert client.get("/css/tokens.css").status_code == 200
    assert client.get("/js/app.js").status_code == 200
    assert client.get("/js/lib/api.js").status_code == 200


def test_dashboard_router_keeps_hash_query_on_settings_route():
    from pathlib import Path

    source = (Path(__file__).parents[1] / "static/js/app.js").read_text(
        encoding="utf-8"
    )

    assert "(location.hash || '#/').split('?')[0]" in source


def test_dashboard_record_hint_reads_actual_hotkey():
    from pathlib import Path

    source = (
        Path(__file__).parents[1] / "static/js/pages/dashboard.js"
    ).read_text(encoding="utf-8")

    assert "api.getConfig()" in source
    assert "formatHotkey(hotkey)" in source
    assert "Right Option キーで起動" not in source
