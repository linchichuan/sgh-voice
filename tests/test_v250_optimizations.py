"""v2.5.0 最佳化回歸測試：
- edit 模式 validator 不再誤殺翻譯/改寫輸出
- _CONV_MARKERS 不誤殺「原文本來就以該詞開頭」的真實口述
- apply_corrections ASCII 規則 word boundary（Cloudflare 不再變 Claudeflare）
- _wrap_edit_text <command>/<text> 結構化包裝
- recorder._save 每段唯一檔名（並行轉寫不互踩）
- SOAP 場景 edit_directive 自動切換 edit 模式
"""
import numpy as np
import pytest


# ───── edit 模式 validator ──────────────────────────────────

def test_validate_edit_mode_passes_translation(mock_transcriber):
    """翻譯輸出 bigram overlap ≈ 0，dictate 規則必殺；edit 模式必須放行。"""
    raw = "今天天氣很好我們決定一起去公園散步順便買了一些飲料和點心回家"
    translated = "The weather was great today, so we decided to take a walk in the park together."
    status, res = mock_transcriber._validate_llm_result(raw, translated, "Test", mode="edit")
    assert status == "ok"
    assert res == translated


def test_validate_edit_mode_passes_email_expansion(mock_transcriber):
    """Email 草稿擴寫 >2.5x 長度，dictate 規則必殺；edit 模式必須放行。"""
    raw = "跟田中說明天會議改到三點"
    email = (
        "田中様\n\nお世話になっております。\n明日の会議についてご連絡いたします。"
        "開始時間が15時に変更となりましたので、ご確認のほどよろしくお願いいたします。\n\n敬具"
    )
    status, res = mock_transcriber._validate_llm_result(raw, email, "Test", mode="edit")
    assert status == "ok"


def test_validate_edit_mode_discards_preamble(mock_transcriber):
    """edit 模式仍要擋 meta-commentary 前言（「以下是」起手）。"""
    raw = "把這段翻成英文"
    bad = "以下是您要求的英文翻譯：Please translate this."
    status, res = mock_transcriber._validate_llm_result(raw, bad, "Test", mode="edit")
    assert status == "discard"
    assert res is None


def test_validate_edit_mode_discards_empty(mock_transcriber):
    status, res = mock_transcriber._validate_llm_result("原文", "   ", "Test", mode="edit")
    assert status == "discard"


# ───── _CONV_MARKERS 原文開頭豁免 ───────────────────────────

def test_hallucination_allows_legit_okay_opening(mock_transcriber):
    """使用者真的口述「好的，沒問題…」→ LLM 保留原句不是幻覺。"""
    raw = "好的沒問題我明天十點到會議室跟大家討論這個案子的後續安排"
    out = "好的，沒問題，我明天十點到會議室，跟大家討論這個案子的後續安排。"
    assert mock_transcriber._is_llm_hallucination(out, raw) is False


def test_hallucination_still_flags_added_marker(mock_transcriber):
    """原文沒有助理起手詞、LLM 無中生有加上 → 仍是幻覺。"""
    raw = "幫我把這段話翻成英文"
    bad = "I cannot help with that request because of policy."
    assert mock_transcriber._is_llm_hallucination(bad, raw) is True


# ───── apply_corrections word boundary ──────────────────────

def test_corrections_word_boundary_protects_cloudflare(populated_memory):
    """ASCII 規則 "cloud"→"Claude" 不得波及 Cloudflare / Google Cloud Platform 的子字串。"""
    out = populated_memory.apply_corrections("我們用 Cloudflare 來擋 DDoS")
    assert "Cloudflare" in out
    assert "Claudeflare" not in out


def test_corrections_word_boundary_still_fixes_standalone(populated_memory):
    out = populated_memory.apply_corrections("我請 cloud 幫我寫程式")
    assert "Claude" in out


def test_corrections_long_rule_still_applies(populated_memory):
    out = populated_memory.apply_corrections("打開 cloud code 來開發")
    assert "Claude Code" in out


# ───── _wrap_edit_text 結構化 ───────────────────────────────

def test_wrap_edit_text_uses_command_text_tags(mock_transcriber):
    wrapped = mock_transcriber._wrap_edit_text("hello world", "concise")
    assert wrapped.startswith("<command>")
    assert "<text>hello world</text>" in wrapped


def test_wrap_edit_text_custom_directive(mock_transcriber):
    wrapped = mock_transcriber._wrap_edit_text("body", "把這段改成五言絕句")
    assert "<command>把這段改成五言絕句</command>" in wrapped
    assert "<text>body</text>" in wrapped


def test_wrap_edit_text_no_context_still_wraps_text(mock_transcriber):
    """無指令時也要包 <text>，維持與 _EDIT_SYSTEM 的結構契約。"""
    wrapped = mock_transcriber._wrap_edit_text("plain", "")
    assert wrapped == "<text>plain</text>"


# ───── recorder._save 唯一檔名 ──────────────────────────────

def test_recorder_save_unique_filenames(monkeypatch):
    import recorder as rec_mod
    if rec_mod.sf is None:
        pytest.skip("soundfile not installed")
    r = rec_mod.Recorder({"sample_rate": 16000})
    audio = np.zeros(16000, dtype=np.float32)  # 1s，超過 0.3s 下限
    fp1 = r._save(audio)
    fp2 = r._save(audio)
    assert fp1 and fp2 and fp1 != fp2
    import os
    for fp in (fp1, fp2):
        if fp and os.path.exists(fp):
            os.remove(fp)


# ───── SOAP 場景 edit_directive 切換 ────────────────────────

def test_scene_edit_directive_switches_to_edit_mode(mock_transcriber, monkeypatch):
    """active_scene 含 edit_directive 時，dictate 自動切換為 edit 模式
    （送進 LLM 的 user 訊息應為 <command>/<text> 結構）。"""
    import transcriber as tr_mod

    mock_transcriber.config.update({
        "enable_audio_gate": False,
        "enable_claude_polish": True,
        "enable_hybrid_mode": False,
        "llm_engine": "groq",
        "groq_api_key": "gsk_test",
        "active_scene": "medical_consultation",
    })
    monkeypatch.setattr(tr_mod, "detect_app_style", lambda config: {
        "bundle_id": "", "app_name": "", "style": "default", "prompt": "",
    })
    monkeypatch.setattr(
        mock_transcriber, "_local_stt",
        lambda src: "病人說最近血壓比較高早上量是一百五醫生說先調整藥量兩週後回診",
    )

    captured = {}

    def fake_groq(text, mode, edit_context, system_prompt=None):
        captured["mode"] = mode
        captured["edit_context"] = edit_context
        return "[S] 病患自述血壓偏高（晨間 150）\n[P] 調整藥量，兩週後回診"

    monkeypatch.setattr(mock_transcriber, "_groq_llm_process", fake_groq)
    # 強制走 local STT 路徑
    mock_transcriber.config["stt_engine"] = "mlx-whisper"
    mock_transcriber.config["enable_hybrid_mode"] = True

    result = mock_transcriber._transcribe_impl(
        np.ones(16000, dtype=np.float32), 1.0, "dictate", "", None
    )
    assert captured["mode"] == "edit"
    assert "SOAP" in captured["edit_context"] or "[S]" in captured["edit_context"]
    assert result["final"].startswith("[S]")
