"""Local Japanese SOAP draft from a consultation transcript.

The bundled llama.cpp CPU build (llama-completion.exe) runs as a short-lived
child process: the prompt goes in through a private temporary file, the draft
comes back on stdout. No port is opened and nothing is downloaded; the model is
the pinned GGUF next to the executable (resources/windows/llm-ja-v1.json).

The draft is for a clinician to check. After generation, numbers and katakana
terms (drug names, tests) that do not occur in the transcript are listed as
"to check" so invented values stand out.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata

from windows_client.models import ModelIntegrityError, RESOURCE_ROOT, verified_model_dir

LLM_MANIFEST = json.loads((RESOURCE_ROOT / "llm-ja-v1.json").read_text(encoding="utf-8"))
LLM_VERIFIED_CACHE = "llm-verified.json"
LLM_INFO = {
    "name": LLM_MANIFEST["name"], "license": LLM_MANIFEST["license"],
    "runtime": f"llama.cpp {LLM_MANIFEST['runtime']['tag']} ({LLM_MANIFEST['runtime']['license']})",
    "size_label": f"{sum(f['size'] for f in LLM_MANIFEST['files']) / 1_000_000_000:.2f} GB",
}
TIMEOUT_SECONDS = 30 * 60
HEADINGS = ("S", "O", "A", "P")

SYSTEM_PROMPT = """あなたは日本の医療機関で使われる診療記録の下書き作成を補助します。
入力は、医師と患者の診察中の会話を音声認識で文字にしたものです。話者の区別はなく、誤認識を含むことがあります。話者は文脈から判断してください。
この会話から、医師が確認・修正するための SOAP 形式の下書きを日本語で作成してください。

規則:
- 会話の中で明示された情報だけを書く。推測、一般論、会話にない診断名・検査・薬剤・注意事項を追加しない。
- 数値、薬剤名、用量、回数は会話のとおりに書く。会話で言われていない単位や基準値は付け加えない。
- 患者が否定した症状（例：「胸の痛みはない」）も、否定であることがわかるように S に書く。
- 会話に該当する情報がない項目は「記載なし」と書く。
- 日本語で書く。中国語の字体や表現を使わない。
- 出力は次の 4 つの見出しと箇条書きのみ。前置きや結びの文は書かない。
S（主観的情報）:
O（客観的情報）:
A（評価）:
P（計画）:"""


class SoapError(RuntimeError):
    """A stable UI error code; never carries transcript text or paths."""

    def __init__(self, code="soap_failed"):
        self.code = code
        super().__init__(code)


def bundled_llm_root():
    """<app>\\llm. SGHVOICE_LLM_DIR is for source checkouts and tests only."""
    override = os.environ.get("SGHVOICE_LLM_DIR")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parents[1] / "build" / "windows"
    return base / "llm"


def build_prompt(transcript):
    """Qwen chat format with thinking disabled (empty think block)."""
    return ("<|im_start|>system\n" + SYSTEM_PROMPT + "<|im_end|>\n"
            "<|im_start|>user\n" + transcript.strip() + "<|im_end|>\n"
            "<|im_start|>assistant\n<think>\n\n</think>\n\n")


def context_size(transcript, manifest=None):
    """Conservative token budget (about one token per Japanese character)."""
    generation = (manifest or LLM_MANIFEST)["generation"]
    needed = len(transcript) + len(SYSTEM_PROMPT) + generation["max_tokens"] + 256
    if needed > generation["max_context"]:
        raise SoapError("soap_transcript_too_long")
    return max(4096, -(-needed // 1024) * 1024)


def clean_output(text):
    text = text.replace("\r\n", "\n")
    marker = "<|im_start|>assistant"
    if marker in text:  # tolerate a runtime that echoes the prompt
        text = text.rsplit(marker, 1)[1]
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    for token in ("<|im_end|>", "<|endoftext|>", "[end of text]"):
        text = text.split(token, 1)[0]
    return text.strip()


def has_soap_headings(text):
    return all(re.search(rf"(?m)^[\s#*【\[]*{h}\s*[（(:：】\]]", text) for h in HEADINGS)


def _numbers(text):
    return re.findall(r"\d+(?:\.\d+)?", unicodedata.normalize("NFKC", text))


def _katakana_terms(text):
    return re.findall(r"[ァ-ヺー]{3,}", unicodedata.normalize("NFKC", text))


def unverified_terms(draft, transcript):
    """Numbers and katakana terms in the draft that the transcript never contains."""
    source = unicodedata.normalize("NFKC", transcript)
    source_numbers = set(_numbers(source))
    found = []
    for number in _numbers(draft):
        if number not in source_numbers and number not in found:
            found.append(number)
    for term in _katakana_terms(draft):
        if term not in source and term not in found:
            found.append(term)
    return found


def physical_memory_bytes():
    if sys.platform != "win32":
        return None
    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullTotalPhys)


class SoapDrafter:
    def __init__(self, root=None, *, cache_dir=None, manifest=None, popen=subprocess.Popen):
        self.manifest = manifest or LLM_MANIFEST
        self.root = Path(root) if root is not None else bundled_llm_root()
        self._cache_dir = cache_dir
        self._popen = popen
        self._model = None

    def locate(self):
        """Verify the pinned GGUF (cached) and the runtime; raise SoapError."""
        executable = self.root / "runtime" / self.manifest["runtime"]["executable"]
        if executable.is_symlink() or not executable.is_file():
            raise SoapError("soap_unavailable")
        try:
            folder = verified_model_dir(self.root / self.manifest["id"], cache_dir=self._cache_dir,
                                        manifest={**self.manifest, "revision": self.manifest["runtime"]["tag"]
                                                  + "/" + self.manifest["files"][0]["sha256"]},
                                        cache_name=LLM_VERIFIED_CACHE)
        except ModelIntegrityError as exc:
            raise SoapError("soap_unavailable" if exc.code == "model_missing" else "soap_model_invalid") from None
        self._model = folder / self.manifest["files"][0]["name"]
        return executable

    @property
    def available(self):
        try:
            self.locate()
            return True
        except SoapError:
            return False

    def draft(self, transcript, *, should_cancel=lambda: False, on_progress=lambda seconds: None):
        """Return {"text", "unverified", "seconds"}; raise SoapError."""
        transcript = (transcript or "").strip()
        if not transcript:
            raise SoapError("soap_empty")
        executable = self.locate()
        generation = self.manifest["generation"]
        context = context_size(transcript, self.manifest)
        folder = Path(tempfile.mkdtemp(prefix="sghvoice-soap-"))
        started = time.monotonic()
        process = None
        try:
            prompt = folder / "prompt.txt"
            prompt.write_text(build_prompt(transcript), encoding="utf-8")
            command = [str(executable), "-m", str(self._model), "-f", str(prompt),
                       "-n", str(generation["max_tokens"]), "-c", str(context),
                       "--temp", str(generation["temperature"]), "--top-p", str(generation["top_p"]),
                       "-no-cnv", "--no-display-prompt"]
            flags = 0
            if sys.platform == "win32":
                flags = subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS
            environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH")
                           if key in os.environ}
            process = self._popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, cwd=str(folder), env=environment,
                                  creationflags=flags)
            chunks = []
            reader = threading.Thread(target=lambda: chunks.append(process.stdout.read()), daemon=True)
            reader.start()
            while process.poll() is None:
                if should_cancel():
                    raise SoapError("cancelled")
                elapsed = time.monotonic() - started
                if elapsed > TIMEOUT_SECONDS:
                    raise SoapError("soap_timeout")
                on_progress(elapsed)
                time.sleep(0.25)
            reader.join(10)
            if should_cancel():
                raise SoapError("cancelled")
            if process.returncode != 0:
                raise SoapError("soap_failed")
            text = clean_output(b"".join(c for c in chunks if c).decode("utf-8", errors="replace"))
            if not has_soap_headings(text):
                raise SoapError("soap_failed")
            return {"text": text, "unverified": unverified_terms(text, transcript),
                    "seconds": round(time.monotonic() - started, 1)}
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                try:
                    process.wait(10)
                except Exception:
                    pass
            shutil.rmtree(folder, ignore_errors=True)


def compose_result(soap, transcript, labels):
    """The text shown in the result box: draft first, transcript kept below."""
    parts = [labels["soap_heading"], soap["text"]]
    if soap.get("unverified"):
        parts += ["", labels["soap_unverified"] + "、".join(soap["unverified"])]
    parts += ["", "――――――――――", labels["transcript_heading"], transcript.strip()]
    return "\n".join(parts)
