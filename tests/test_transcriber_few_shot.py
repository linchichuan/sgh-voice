"""Tests for transcriber._few_shot_pairs and _echoes_fewshot.
Few-shot 是 LLM 個人化的核心，degenerate-input gate 是 v2.1.1 後關鍵安全網。"""
import pytest


def test_few_shot_returns_empty_when_disabled(mock_transcriber):
    """enable_fewshot=False → 永不注入。"""
    mock_transcriber.config["enable_fewshot"] = False
    pairs = mock_transcriber._few_shot_pairs(mode="dictate", current_text="今天天氣很好我們去走走")
    assert pairs == []


def test_few_shot_returns_empty_for_short_input(mock_transcriber):
    """current_text < fewshot_min_input_chars (預設 8) → 跳過，防 LLM 退化複誦。"""
    mock_transcriber.config["enable_fewshot"] = True
    mock_transcriber.config["fewshot_min_input_chars"] = 8
    pairs = mock_transcriber._few_shot_pairs(mode="dictate", current_text="hi")
    assert pairs == []


def test_few_shot_returns_empty_for_edit_mode(mock_transcriber):
    """mode='edit'（rewrite API）一律不注入 few-shot。"""
    mock_transcriber.config["enable_fewshot"] = True
    pairs = mock_transcriber._few_shot_pairs(mode="edit", current_text="some longer text here for testing")
    assert pairs == []


def test_echoes_fewshot_detects_exact_replay(mock_transcriber):
    """LLM 輸出 == 某筆 few-shot example 的 final，且不等於當前 raw → 視為複誦幻覺。"""
    mock_transcriber.config["enable_fewshot"] = True
    # populated_memory 的 edited 範例之一：final="Claude Code 真的很強。"
    leaked_final = "Claude Code 真的很強。"
    current_raw = "今天有點累想休息"
    assert mock_transcriber._echoes_fewshot(leaked_final, current_raw) is True


def test_echoes_fewshot_passes_legit_repeat(mock_transcriber):
    """若 result == final == raw → 使用者真的講了同樣一句，不算複誦。"""
    mock_transcriber.config["enable_fewshot"] = True
    same = "Claude Code 真的很強。"
    assert mock_transcriber._echoes_fewshot(same, same) is False
