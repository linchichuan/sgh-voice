"""Tests for dashboard static asset routing."""


def test_dashboard_serves_index_and_static_assets(isolated_data_dir):
    import dashboard

    client = dashboard.app.test_client()

    assert client.get("/").status_code == 200
    assert client.get("/css/base.css").status_code == 200
    assert client.get("/css/tokens.css").status_code == 200
    assert client.get("/js/app.js").status_code == 200
    assert client.get("/js/lib/api.js").status_code == 200
