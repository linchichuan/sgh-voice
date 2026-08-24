"""macOS notification boundary tests.

Notification data must travel as process arguments, never as AppleScript source.
"""


def test_notify_passes_legitimate_unicode_as_osascript_arguments(monkeypatch):
    import app

    calls = []
    monkeypatch.setattr(
        app.subprocess,
        "Popen",
        lambda argv, **kwargs: calls.append((argv, kwargs)),
    )

    title = '-e SGH Voice — "安全"'
    message = "翻譯完成：明日の予約を確認しました。"
    app.notify(title, message)

    argv, _kwargs = calls[0]
    assert argv[:2] == ["osascript", "-e"]
    assert argv[-3] == "--"
    assert argv[-2:] == [title, message]


def test_notify_never_interpolates_untrusted_text_into_applescript(monkeypatch):
    import app

    calls = []
    monkeypatch.setattr(
        app.subprocess,
        "Popen",
        lambda argv, **kwargs: calls.append((argv, kwargs)),
    )

    payload = '\\" & do shell script "touch /tmp/should-not-run" & "'
    app.notify("Voice Input", payload)

    argv, _kwargs = calls[0]
    script_source = argv[2]
    assert payload not in script_source
    assert argv[-1] == payload
    assert "on run argv" in script_source
