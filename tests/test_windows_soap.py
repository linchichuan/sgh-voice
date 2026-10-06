"""Local SOAP drafting: prompt, parsing, integrity and the child process contract.

No model is run here; a fake process stands in for llama-completion.exe. The
real runtime and model are exercised on Windows CI (windows/offline-test.ps1).
"""
import hashlib
import io
import json
from pathlib import Path

import pytest

from windows_client import soap
from windows_client.soap import SoapDrafter, SoapError

DRAFT = ("S（主観的情報）:\n- 胸痛なし\nO（客観的情報）:\n- 血圧 148/92 mmHg\n- eGFR 68 mL/min/1.73m2\n"
         "A（評価）:\n- 血糖コントロール悪化\nP（計画）:\n- メトホルミン 750mg 1日2回\n- インスリン検討")
TRANSCRIPT = "胸の痛みはないです。148の92ですね。eGFRは68です。メトホルミンを1回750ミリ、1日2回に増やしましょう。"


def test_prompt_disables_thinking_and_keeps_rules():
    prompt = soap.build_prompt("  会話  ")
    assert prompt.startswith("<|im_start|>system\n")
    assert "<|im_start|>user\n会話<|im_end|>" in prompt
    assert prompt.endswith("<|im_start|>assistant\n<think>\n\n</think>\n\n")
    for rule in ("推測", "否定", "記載なし", "単位", "指示"):
        assert rule in soap.SYSTEM_PROMPT


def test_context_budget_and_limit():
    assert soap.context_size("あ" * 100) == 4096
    size = soap.context_size("あ" * 9000)
    assert size % 1024 == 0 and size >= 9000 + 1500
    with pytest.raises(SoapError) as error:
        soap.context_size("あ" * 30000)
    assert error.value.code == "soap_transcript_too_long"


def test_output_cleanup_and_headings():
    echoed = soap.build_prompt("x") + DRAFT + "<|im_end|>\n [end of text]"
    assert soap.clean_output(echoed) == DRAFT
    assert soap.clean_output("<think>考え中</think>\n" + DRAFT + " [end of text]") == DRAFT
    assert soap.has_soap_headings(DRAFT)
    assert soap.has_soap_headings("## S:\n- a\n## O:\n- b\n## A:\n- c\n## P:\n- d")
    assert not soap.has_soap_headings("S（主観的情報）:\n- a\nO（客観的情報）:\n- b")


def test_terms_missing_from_transcript_are_flagged():
    flagged = soap.unverified_terms(DRAFT, TRANSCRIPT)
    assert "インスリン" in flagged and "1.73" in flagged
    for said in ("148", "92", "68", "750", "メトホルミン"):
        assert said not in flagged


class FakeProcess:
    def __init__(self, output=b"", returncode=0, polls_before_exit=1):
        self.stdout = io.BytesIO(output)
        self.returncode = None
        self._final = returncode
        self._polls = polls_before_exit
        self.killed = False

    def poll(self):
        if self.killed:
            self.returncode = -9
        elif self._polls <= 0:
            self.returncode = self._final
        else:
            self._polls -= 1
        return self.returncode

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return self.returncode


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "llm"
    (root / "runtime").mkdir(parents=True)
    (root / "runtime" / "llama-completion.exe").write_bytes(b"MZ fake")
    model = root / "fake-model"
    model.mkdir()
    weights = b"synthetic gguf"
    (model / "fake.gguf").write_bytes(weights)
    manifest = json.loads(json.dumps(soap.LLM_MANIFEST))
    manifest["id"] = "fake-model"
    manifest["files"] = [{"name": "fake.gguf", "size": len(weights),
                          "sha256": hashlib.sha256(weights).hexdigest()}]
    return root, manifest, tmp_path / "cache"


def drafter(bundle, process, calls):
    root, manifest, cache = bundle

    def popen(command, **kwargs):
        prompt = Path(command[command.index("-f") + 1])
        calls.append({"command": command, "kwargs": kwargs, "prompt": prompt,
                      "prompt_text": prompt.read_text(encoding="utf-8")})
        return process
    return SoapDrafter(root, cache_dir=cache, manifest=manifest, popen=popen)


def test_draft_runs_child_process_without_network_settings(bundle, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid")
    calls, progress = [], []
    output = (DRAFT + "\n [end of text]").encode("utf-8")
    result = drafter(bundle, FakeProcess(output), calls).draft(TRANSCRIPT, on_progress=progress.append)
    assert result["text"] == DRAFT
    assert "インスリン" in result["unverified"]
    call = calls[0]
    command = call["command"]
    assert Path(command[0]).name == "llama-completion.exe"
    for flag in ("-no-cnv", "--no-display-prompt", "-n", "-c", "--temp", "--seed"):
        assert flag in command
    assert not any(part.startswith(("-hf", "--hf", "-mu", "--model-url")) for part in command)
    assert TRANSCRIPT in call["prompt_text"]
    assert not call["prompt"].exists() and not call["prompt"].parent.exists()  # temp prompt removed
    assert "HTTPS_PROXY" not in call["kwargs"]["env"]
    assert call["kwargs"]["stdin"] is soap.subprocess.DEVNULL
    assert progress


def test_cancel_kills_process_and_removes_prompt(bundle):
    calls = []
    process = FakeProcess(polls_before_exit=10_000)
    with pytest.raises(SoapError) as error:
        drafter(bundle, process, calls).draft(TRANSCRIPT, should_cancel=lambda: True)
    assert error.value.code == "cancelled"
    assert process.killed and not calls[0]["prompt"].exists()


@pytest.mark.parametrize("output,returncode", [(b"no headings here", 0), (DRAFT.encode(), 1)])
def test_bad_output_or_exit_code_is_a_stable_error(bundle, output, returncode):
    with pytest.raises(SoapError) as error:
        drafter(bundle, FakeProcess(output, returncode), []).draft(TRANSCRIPT)
    assert error.value.code == "soap_failed"


def test_missing_runtime_or_modified_model_is_refused(bundle):
    root, manifest, cache = bundle
    (root / "fake-model" / "fake.gguf").write_bytes(b"synthetic GGUF")  # same size, changed
    with pytest.raises(SoapError) as error:
        SoapDrafter(root, cache_dir=cache, manifest=manifest).locate()
    assert error.value.code == "soap_model_invalid"
    (root / "runtime" / "llama-completion.exe").unlink()
    with pytest.raises(SoapError) as error:
        SoapDrafter(root, cache_dir=cache, manifest=manifest).locate()
    assert error.value.code == "soap_unavailable"
    assert SoapDrafter(root, cache_dir=cache, manifest=manifest).available is False


def test_empty_transcript_is_refused(bundle):
    with pytest.raises(SoapError) as error:
        drafter(bundle, FakeProcess(), []).draft("   ")
    assert error.value.code == "soap_empty"


def test_pinned_manifest_matches_ci_benchmark():
    manifest = soap.LLM_MANIFEST
    assert manifest["runtime"]["executable"] == "llama-completion.exe"
    assert manifest["runtime"]["asset"].endswith("-bin-win-cpu-x64.zip")
    assert len(manifest["runtime"]["sha256"]) == 64 and len(manifest["files"][0]["sha256"]) == 64
    assert manifest["license"].startswith("Apache-2.0")


def test_result_composition_keeps_transcript():
    labels = {"soap_heading": "[SOAP]", "soap_unverified": "[check] ", "transcript_heading": "[T]"}
    text = soap.compose_result({"text": DRAFT, "unverified": ["インスリン", "1.73"]}, TRANSCRIPT, labels)
    assert text.startswith("[SOAP]\n" + DRAFT)
    assert "[check] インスリン、1.73" in text
    assert text.endswith("[T]\n" + TRANSCRIPT)


def test_runtime_layout_file_locates_nested_executable(bundle):
    root, manifest, cache = bundle
    (root / "runtime" / "llama-completion.exe").unlink()
    nested = root / "runtime" / "build" / "bin"
    nested.mkdir(parents=True)
    (nested / "llama-completion.exe").write_bytes(b"MZ")
    (root / "runtime" / "runtime.json").write_text(json.dumps({"executable": "build/bin/llama-completion.exe"}))
    assert SoapDrafter(root, cache_dir=cache, manifest=manifest).locate() == nested / "llama-completion.exe"
    (root / "runtime" / "runtime.json").write_text(json.dumps({"executable": "../outside"}))
    with pytest.raises(SoapError):
        SoapDrafter(root, cache_dir=cache, manifest=manifest).locate()


def test_runtime_spec_per_platform():
    assert soap.runtime_spec(platform="win32")["executable"] == "llama-completion.exe"
    assert soap.runtime_spec(platform="darwin")["executable"] == "llama-completion"
