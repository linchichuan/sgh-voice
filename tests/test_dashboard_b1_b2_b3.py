"""Tests for the three Typeless-inspired dashboard features:

B1 — dictionary batch import (.txt / .csv), two-step preview/apply.
B2 — usage insights (streaks + heatmap) surfaced via /api/insights.
B3 — in-app feedback entry point, local-only persistence.

All fixtures are isolated_data_dir / empty_memory based (tmp_path), matching the
rest of this suite's convention — never touches the real ~/.voice-input/.
"""
import io
import json
from datetime import date, timedelta
from pathlib import Path

import pytest


# ─── B1: dictionary batch import ──────────────────────────────────────────

def _upload(client, content_bytes, filename, **form):
    data = {"file": (io.BytesIO(content_bytes), filename)}
    data.update(form)
    return client.post(
        "/api/dictionary/import",
        data=data,
        content_type="multipart/form-data",
    )


def test_dictionary_import_txt_preview_then_apply_reuses_add_custom_word(
    empty_memory, monkeypatch
):
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()

    # "Claude" appears twice (in-file duplicate); one blank + one whitespace-only line.
    txt = "Claude\nHaiku\n\nClaude\n   \nOpus\n".encode("utf-8")

    preview = _upload(client, txt, "words.txt", apply="false")
    assert preview.status_code == 200
    payload = preview.get_json()
    assert payload["applied"] is False
    assert payload["counts"] == {"importable": 3, "duplicates": 1, "invalid": 2}
    assert set(payload["importable"]) == {"Claude", "Haiku", "Opus"}
    # Preview must not write anything.
    assert empty_memory.get_dictionary_words()["manual_added"] == []

    # apply=true with no `excluded` (or excluded=[]) imports every importable word.
    applied = _upload(client, txt, "words.txt", apply="true", excluded=json.dumps([]))
    assert applied.status_code == 200
    applied_payload = applied.get_json()
    assert applied_payload["applied"] is True
    assert set(applied_payload["imported"]) == {"Claude", "Haiku", "Opus"}

    listing = client.get("/api/dictionary").get_json()
    assert set(listing["custom_words"]["manual_added"]) == {"Claude", "Haiku", "Opus"}

    # Re-running the same import must not create duplicates — every previously
    # imported word must now show up as "duplicate", not "importable".
    rerun = _upload(client, txt, "words.txt", apply="false")
    rerun_payload = rerun.get_json()
    assert rerun_payload["counts"]["importable"] == 0
    assert set(rerun_payload["duplicates"]) == {"Claude", "Haiku", "Opus"}

    rerun_apply = _upload(client, txt, "words.txt", apply="true")
    assert rerun_apply.get_json()["imported"] == []
    listing2 = client.get("/api/dictionary").get_json()
    manual = listing2["custom_words"]["manual_added"]
    assert sorted(manual) == sorted(set(manual))  # still no duplicates


def test_dictionary_import_csv_first_column_only(empty_memory, monkeypatch):
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()

    csv_bytes = "Aloha,greeting\nAloha,dup\n,note\nMahalo,thanks\n".encode("utf-8")
    preview = _upload(client, csv_bytes, "words.csv", apply="false")
    payload = preview.get_json()
    assert payload["counts"] == {"importable": 2, "duplicates": 1, "invalid": 1}
    assert set(payload["importable"]) == {"Aloha", "Mahalo"}

    applied = _upload(client, csv_bytes, "words.csv", apply="true")  # no excluded → import all
    assert set(applied.get_json()["imported"]) == {"Aloha", "Mahalo"}
    listing = client.get("/api/dictionary").get_json()
    assert set(listing["custom_words"]["manual_added"]) == {"Aloha", "Mahalo"}


@pytest.mark.parametrize(
    "filename,content,form,expected_code,expected_status",
    [
        ("words.pdf", b"Claude\n", {}, "unsupported_type", 400),
        ("empty.txt", b"", {}, "empty_file", 400),
        ("blank.txt", b"   \n\n", {}, "empty_file", 400),
    ],
)
def test_dictionary_import_rejects_bad_input(
    empty_memory, monkeypatch, filename, content, form, expected_code, expected_status
):
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()
    res = _upload(client, content, filename, **form)
    assert res.status_code == expected_status
    assert res.get_json()["code"] == expected_code


def test_dictionary_import_rejects_bad_encoding(empty_memory, monkeypatch):
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()
    bad = b"\xc3\x28\xff\xfe"  # not valid UTF-8
    res = _upload(client, bad, "bad.txt")
    assert res.status_code == 400
    assert res.get_json()["code"] == "bad_encoding"


def test_dictionary_import_rejects_oversized_file(empty_memory, monkeypatch):
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()
    huge = (b"word\n" * (dashboard._DICTIONARY_IMPORT_MAX_BYTES // 5 + 10))
    assert len(huge) > dashboard._DICTIONARY_IMPORT_MAX_BYTES
    res = _upload(client, huge, "huge.txt")
    assert res.status_code == 400
    assert res.get_json()["code"] == "too_large"


def test_dictionary_import_requires_file_field(empty_memory, monkeypatch):
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()
    res = client.post("/api/dictionary/import", data={}, content_type="multipart/form-data")
    assert res.status_code == 400
    assert res.get_json()["code"] == "missing_file"


def test_dictionary_import_size_check_is_off_by_one_safe(empty_memory, monkeypatch):
    """讀取上限改成 MAX+1 bytes 才判定超限（不整檔讀入才檢查）；這裡鎖住
    邊界：剛好等於上限必須被接受，多 1 byte 就必須被拒絕。若實作誤用
    read(MAX) 而非 read(MAX+1)，MAX+1 bytes 的檔案會被少讀 1 byte、
    len(raw) 算出來剛好等於 MAX，就會被誤判為沒有超限。"""
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()
    max_bytes = dashboard._DICTIONARY_IMPORT_MAX_BYTES
    first_line = b"word\n"
    at_limit = first_line + b"a" * (max_bytes - len(first_line))
    assert len(at_limit) == max_bytes

    res_at_limit = _upload(client, at_limit, "at_limit.txt")
    assert res_at_limit.status_code == 200

    over_limit = at_limit + b"\n"
    assert len(over_limit) == max_bytes + 1
    res_over_limit = _upload(client, over_limit, "over_limit.txt")
    assert res_over_limit.status_code == 400
    assert res_over_limit.get_json()["code"] == "too_large"


def test_dictionary_import_csv_strict_rejects_unterminated_quoted_field(
    empty_memory, monkeypatch
):
    """strict=True：CSV 語法本身壞掉（未終止的引號欄位）要直接回錯誤，不要
    讓 csv 模組用寬鬆規則默默吞掉整個檔案剩餘部分當成一個欄位。"""
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()
    bad_csv = b'"unterminated,foo\nbar,baz\n'
    res = _upload(client, bad_csv, "malformed.csv")
    assert res.status_code == 400
    assert res.get_json()["code"] == "bad_csv"


def test_dictionary_import_rejects_words_with_embedded_control_characters(
    empty_memory, monkeypatch
):
    """CSV 允許用引號包住合法內嵌換行的欄位（"foo\\nbar"），.strip() 清不掉
    字串「中間」的控制字元；這種詞彙必須被歸類 invalid，不能混進詞庫。"""
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()
    csv_bytes = 'Good,ok\n"foo\nbar",note\n'.encode("utf-8")
    res = _upload(client, csv_bytes, "embedded_newline.csv")
    assert res.status_code == 200
    payload = res.get_json()
    assert set(payload["importable"]) == {"Good"}
    assert payload["counts"]["invalid"] == 1


def test_dictionary_import_txt_rejects_words_with_embedded_nul(empty_memory, monkeypatch):
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()
    content = "Good\nbad\x00word\nAlsoGood\n".encode("utf-8")
    res = _upload(client, content, "nul.txt")
    assert res.status_code == 200
    payload = res.get_json()
    assert set(payload["importable"]) == {"Good", "AlsoGood"}
    assert payload["counts"]["invalid"] == 1


def test_dictionary_import_apply_with_no_excluded_imports_everything(empty_memory, monkeypatch):
    """apply=true 沒有 excluded（或 excluded=[]）→ 全部 importable 都要匯入，
    包含超過預覽截斷上限（500）的部分——這是前端「排除清單」設計依賴的
    後端合約：預設全部匯入，使用者取消勾選才是例外。用 600 個詞（> 500 的
    preview 截斷上限）驗證第 501–600 個詞不會因為從未出現在 preview 裡而
    被漏掉。"""
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()
    words = [f"word{i}" for i in range(600)]
    txt = ("\n".join(words) + "\n").encode("utf-8")

    preview = _upload(client, txt, "many.txt", apply="false")
    preview_payload = preview.get_json()
    assert preview_payload["counts"]["importable"] == 600
    assert len(preview_payload["importable"]) == 500  # preview 截斷顯示

    applied = _upload(client, txt, "many.txt", apply="true", excluded=json.dumps([]))
    payload = applied.get_json()
    assert payload["ok"] is True
    assert len(payload["imported"]) == 600
    assert set(payload["imported"]) == set(words)
    listing = client.get("/api/dictionary").get_json()
    assert set(listing["custom_words"]["manual_added"]) == set(words)


def test_dictionary_import_apply_excludes_only_the_named_word(empty_memory, monkeypatch):
    """Second-pass fix：舊版用『selected=使用者勾選的詞』，即使只取消勾選
    preview 顯示的 1 個詞，也會讓第 501–600 個（從未顯示、無從勾選）的詞
    整批被排除清單邏輯排除掉（599 個裡只匯入到「有被勾選」的那部分，實際
    只剩 499 個，不是使用者預期的 599 個）。改成『excluded=使用者取消勾選
    的詞』後，取消勾選第 1 個詞只排除那 1 個，其餘 599 個（含從未顯示過的
    第 501–600 個）必須全部匯入。"""
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()
    words = [f"word{i}" for i in range(600)]
    txt = ("\n".join(words) + "\n").encode("utf-8")

    excluded_word = "word0"  # 在 preview 前 500 筆之內，使用者看得到也勾得到
    applied = _upload(
        client, txt, "many.txt", apply="true",
        excluded=json.dumps([excluded_word]),
    )
    payload = applied.get_json()
    assert payload["ok"] is True
    assert len(payload["imported"]) == 599
    assert excluded_word not in payload["imported"]
    assert set(payload["imported"]) == set(words) - {excluded_word}
    listing = client.get("/api/dictionary").get_json()
    assert set(listing["custom_words"]["manual_added"]) == set(words) - {excluded_word}


def test_dictionary_import_excluded_word_not_in_file_is_silently_ignored(
    empty_memory, monkeypatch
):
    """excluded 內若有檔案裡根本不存在的詞，不視為錯誤、也不影響其餘詞的
    匯入——只是單純沒有效果。"""
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()
    txt = "Claude\nHaiku\n".encode("utf-8")

    applied = _upload(
        client, txt, "words.txt", apply="true",
        excluded=json.dumps(["NeverInFile", "AlsoNotInFile"]),
    )
    assert applied.status_code == 200
    payload = applied.get_json()
    assert payload["ok"] is True
    assert set(payload["imported"]) == {"Claude", "Haiku"}


@pytest.mark.parametrize(
    "excluded_raw,expected_code",
    [
        ("not-json", "invalid_excluded"),
        (json.dumps({"not": "a list"}), "invalid_excluded"),
        (json.dumps([1, 2, 3]), "invalid_excluded"),
    ],
)
def test_dictionary_import_rejects_malformed_excluded(
    empty_memory, monkeypatch, excluded_raw, expected_code
):
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()
    txt = "Claude\nHaiku\n".encode("utf-8")
    res = _upload(client, txt, "words.txt", apply="true", excluded=excluded_raw)
    assert res.status_code == 400
    assert res.get_json()["code"] == expected_code


def test_dictionary_import_apply_reports_failure_when_write_is_blocked(
    empty_memory, monkeypatch
):
    """匯入 apply 階段若 save_dictionary() 被 wipe_all 擋下（記憶體寫入被
    memory.add_custom_word() 復原、回傳 False），這裡不能回報「已匯入
    成功」——必須回 503 + ok:False，讓前端能顯示失敗，而不是靜默吞掉。"""
    import config as config_store
    import dashboard

    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()
    txt = "Claude\nHaiku\n".encode("utf-8")

    config_store.block_runtime_data_writes()
    try:
        res = _upload(client, txt, "blocked.txt", apply="true")
    finally:
        config_store.resume_runtime_data_writes()

    assert res.status_code == 503
    payload = res.get_json()
    assert payload["ok"] is False
    assert payload["code"] == "wipe_not_quiescent"
    assert payload["imported"] == []
    assert empty_memory.get_dictionary_words()["manual_added"] == []


# ─── B2: usage insights (streaks + heatmap) ───────────────────────────────

def _history_entry(d, i):
    return {
        "timestamp": f"{d.isoformat()}T{10 + i:02d}:00:00",
        "whisper_raw": "raw",
        "final_text": "final",
        "mode": "dictate",
    }


def test_get_activity_summary_computes_streaks_and_window(empty_memory):
    today = date.today()
    active_offsets = [0, 0, 1, 3, 4, 5]  # today has 2 entries; gap at day 2; run at 3-4-5
    empty_memory.history = [
        _history_entry(today - timedelta(days=off), i)
        for i, off in enumerate(active_offsets)
    ]

    summary = empty_memory.get_activity_summary(weeks=26)

    assert summary["current_streak_days"] == 2  # today + yesterday
    assert summary["longest_streak_days"] == 3  # day-3, day-4, day-5
    assert summary["total_active_days"] == 5  # today, day-1, day-3, day-4, day-5
    assert summary["weeks"] == 26
    assert len(summary["daily_counts"]) == 26 * 7

    by_date = {row["date"]: row["count"] for row in summary["daily_counts"]}
    assert by_date[today.isoformat()] == 2
    assert by_date[(today - timedelta(days=1)).isoformat()] == 1
    assert by_date[(today - timedelta(days=2)).isoformat()] == 0


def test_get_activity_summary_heatmap_window_is_week_aligned(empty_memory):
    """熱點圖視窗必須是完整的週日→週六網格，且今天之後的格子一律
    future=True、count=0；今天（含）以前一律 future=False。2026-09 修正：
    舊版後端固定回溯 182 天（不對齊週界）、前端自己再算一次『補到本週六』
    的日期範圍——只有今天剛好是週六時，兩邊起訖點才會一致；其餘 6/7 的
    日子，前端算出的範圍會比後端晚，導致後端這裡算出的最舊幾天被前端
    悄悄漏掉。現在改成這裡把週對齊算好、直接回傳整個網格，前端不再自己
    重算日期範圍。"""
    today = date.today()
    empty_memory.history = []
    summary = empty_memory.get_activity_summary(weeks=12)
    daily = summary["daily_counts"]
    assert len(daily) == 12 * 7

    first_date = date.fromisoformat(daily[0]["date"])
    last_date = date.fromisoformat(daily[-1]["date"])
    assert first_date.weekday() == 6  # Python: Monday=0 … Sunday=6
    assert last_date.weekday() == 5  # Saturday
    assert last_date >= today
    assert (last_date - first_date).days == 12 * 7 - 1

    for row in daily:
        d = date.fromisoformat(row["date"])
        if d > today:
            assert row["future"] is True
            assert row["count"] == 0
        else:
            assert row["future"] is False


def test_get_activity_summary_heatmap_includes_all_history_within_aligned_window(empty_memory):
    """對齊到週之後，視窗起點可能比舊版『今天往回 weeks*7-1 天』更晚（當
    今天不是週六時，視窗整體往未來偏移了幾天）——這裡直接在新視窗的最舊
    一天放一筆紀錄，確認它確實出現在回傳結果裡、count 正確，不會因為對齊
    運算而被排除在視窗之外。"""
    today = date.today()
    days_since_sunday = (today.weekday() + 1) % 7
    end_of_week = today + timedelta(days=6 - days_since_sunday)
    window_start = end_of_week - timedelta(days=12 * 7 - 1)

    empty_memory.history = [_history_entry(window_start, 0)]
    summary = empty_memory.get_activity_summary(weeks=12)
    by_date = {row["date"]: row for row in summary["daily_counts"]}
    assert by_date[window_start.isoformat()]["count"] == 1
    assert by_date[window_start.isoformat()]["future"] is False


def test_get_activity_summary_clamps_weeks_range(empty_memory):
    empty_memory.history = []
    assert empty_memory.get_activity_summary(weeks=1)["weeks"] == 12
    assert empty_memory.get_activity_summary(weeks=999)["weeks"] == 26
    assert empty_memory.get_activity_summary(weeks="not-a-number")["weeks"] == 26


def test_get_activity_summary_no_current_streak_when_gap_since_yesterday(empty_memory):
    today = date.today()
    empty_memory.history = [_history_entry(today - timedelta(days=3), 0)]
    summary = empty_memory.get_activity_summary()
    assert summary["current_streak_days"] == 0
    assert summary["longest_streak_days"] == 1
    assert summary["total_active_days"] == 1


def test_insights_endpoint_wires_to_memory(empty_memory, monkeypatch):
    import dashboard

    today = date.today()
    empty_memory.history = [_history_entry(today, 0)]
    monkeypatch.setattr(dashboard, "memory", empty_memory)
    client = dashboard.app.test_client()

    res = client.get("/api/insights")
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["current_streak_days"] == 1
    assert payload["total_active_days"] == 1
    assert isinstance(payload["daily_counts"], list)


# ─── B3: in-app feedback ───────────────────────────────────────────────────

def test_feedback_post_appends_local_jsonl_and_never_calls_network(
    isolated_data_dir, monkeypatch
):
    import dashboard

    client = dashboard.app.test_client()
    res = client.post(
        "/api/feedback",
        json={"category": "bug", "message": "The hotkey stopped working after sleep."},
    )
    assert res.status_code == 200
    assert res.get_json() == {"ok": True}

    feedback_file = isolated_data_dir / "feedback.jsonl"
    assert feedback_file.exists()
    lines = feedback_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["category"] == "bug"
    assert entry["message"] == "The hotkey stopped working after sleep."
    assert entry["app_version"] == dashboard.APP_VERSION
    assert "ts" in entry

    # Fail-closed contract: no outbound network call symbols anywhere in the
    # feedback write path. Mailing is a plain mailto link the user clicks
    # themselves (see static/js/pages/dashboard.js FeedbackCard).
    source = Path(dashboard.__file__).read_text(encoding="utf-8")
    start = source.index("_FEEDBACK_LOCK")
    end = source.index("def api_feedback_meta")
    feedback_block = source[start:end]
    for forbidden in ("requests.", "urlopen", "smtplib", "socket.", "http.client"):
        assert forbidden not in feedback_block


def test_feedback_write_fails_closed_when_path_is_a_symlink(isolated_data_dir):
    """feedback_path 若被換成指向別處的 symlink，O_NOFOLLOW 必須讓 open()
    失敗（ELOOP），而不是乖乖跟著連結寫到使用者未預期的目的地；呼叫端因此
    收到 500，不是靜默假裝寫入成功。"""
    import dashboard

    target = isolated_data_dir.parent / "attacker_target.jsonl"
    feedback_path = isolated_data_dir / "feedback.jsonl"
    feedback_path.symlink_to(target)

    client = dashboard.app.test_client()
    res = client.post("/api/feedback", json={"category": "bug", "message": "hi"})
    assert res.status_code == 500
    assert not target.exists()


def test_feedback_write_fails_closed_when_fchmod_fails(isolated_data_dir, monkeypatch):
    """fchmod() 收緊檔案權限失敗時必須整段放棄寫入（傳出例外→500），不能
    吞掉錯誤後繼續把使用者填寫的內容寫進權限沒收緊的檔案。"""
    import dashboard

    def boom(fd, mode):
        raise OSError("fchmod not permitted")

    monkeypatch.setattr(dashboard.os, "fchmod", boom)
    client = dashboard.app.test_client()
    res = client.post("/api/feedback", json={"category": "bug", "message": "hi"})
    assert res.status_code == 500

    feedback_path = isolated_data_dir / "feedback.jsonl"
    # os.open(..., O_CREAT) 可能已經建立了空檔案；重點是內容絕不能被寫入。
    if feedback_path.exists():
        assert feedback_path.read_text(encoding="utf-8") == ""


@pytest.mark.parametrize(
    "body,expected_code",
    [
        ({"category": "not-a-real-category", "message": "hi"}, "invalid_category"),
        ({"category": "bug", "message": ""}, "empty_message"),
        ({"category": "bug", "message": "   "}, "empty_message"),
        ({"category": "bug", "message": "x" * 4001}, "message_too_long"),
    ],
)
def test_feedback_post_validates(isolated_data_dir, body, expected_code):
    import dashboard

    client = dashboard.app.test_client()
    res = client.post("/api/feedback", json=body)
    assert res.status_code == 400
    assert res.get_json()["code"] == expected_code
    assert not (isolated_data_dir / "feedback.jsonl").exists()


def test_feedback_meta_returns_app_version(isolated_data_dir):
    import dashboard

    client = dashboard.app.test_client()
    res = client.get("/api/feedback/meta")
    assert res.status_code == 200
    assert res.get_json() == {"app_version": dashboard.APP_VERSION}


# ─── App version: single source of truth ───────────────────────────────────

def test_app_version_is_single_sourced_from_config():
    """app.py（CLI banner）與 dashboard.py（/api/feedback 的 mailto 版本號）
    曾經各自硬編一份版本字串、彼此矛盾（app.py 停在 "2.7.0"，dashboard.py
    已經是 "2.7.4"）。兩邊現在都必須是同一個 config.APP_VERSION 物件，不是
    兩份湊巧相等的字串常數。"""
    import app
    import config
    import dashboard

    assert app.APP_VERSION is config.APP_VERSION
    assert dashboard.APP_VERSION is config.APP_VERSION
