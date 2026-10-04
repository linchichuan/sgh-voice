# Vendored faster-whisper for SGHVoice Windows

Upstream: https://github.com/SYSTRAN/faster-whisper

Tag: `v1.2.1`

Commit: `65882eee9f5cdbeeb2d877f1131d48cf241b327d`

The upstream source and `assets/silero_vad_v6.onnx` were fetched from the exact
commit above. Every download was checked against its Git blob hash and size from
the official GitHub tree API. `PROVENANCE.json` records the upstream URL, Git blob
SHA-1, byte size, SHA-256 and final vendored SHA-256 for each file. No PyPI package,
installer or compiled decoder was installed or executed to obtain these files.

## License and attribution

`LICENSE` is the complete, unchanged upstream MIT license, copyright SYSTRAN.
The upstream VAD code identifies its derivation from Silero VAD;
`LICENSE.silero-vad` retains the complete Silero Team MIT attribution from the
official Silero VAD `v6.0` tag, commit
`fba061dc5559f696e62171e9a0741782b0fdc23c`. The ONNX asset here is the one distributed
by faster-whisper at the pinned commit, not a substituted or generated model.

These notices cover the vendored component. They do not change SGHVoice's license
or replace the separate notices required for CTranslate2, NumPy, tokenizers,
ONNX Runtime, Hugging Face Hub and other packaged dependencies.

## Local patches

1. `__init__.py`, `transcribe.py` and `vad.py`: absolute internal imports were
   relocated from `faster_whisper.*` to
   `windows_client._vendor.faster_whisper.*`. Feature extraction, tokenization,
   CTranslate2 calls and transcription/decoding algorithms are unchanged.
2. `audio.py`: replace the PyAV/FFmpeg frontend with a real PCM WAV decoder using
   Python `wave` and NumPy. It only accepts complete, nonempty, 16 kHz, mono,
   signed PCM16 WAV recordings. Other rates, compressed formats, channels and
   stereo splitting are explicitly unsupported; no resampling or alternative
   backend is attempted. The upstream `pad_or_trim` implementation is retained.
3. `utils.py`: `download_model` retains its function signature but unconditionally
   raises `RuntimeError("SGHVoice model setup required")`. Remove the now-unused
   Hugging Face Hub and `re` imports. Model acquisition is an explicit separate
   SGHVoice setup action, never an inference-time fallback.
4. `transcribe.py`: a missing local `tokenizer.json` raises an error instead of
   invoking `tokenizers.Tokenizer.from_pretrained`. Together with the disabled
   download helper, this remains offline even if a validated model file disappears
   between readiness checking and engine construction.
5. No other upstream source or asset is patched. `PROVENANCE.md` and
   `PROVENANCE.json` are local provenance records.

The surrounding `local_stt.py` validates a complete absolute local model bundle,
enforces Hugging Face offline/telemetry flags before import, disables ONNX Runtime
telemetry before importing this package, selects CPU/int8 and
`local_files_only=True`, and passes `vad_filter=False`. The Windows controller
forces the recorder to 16 kHz. This vendored package is an internal implementation
detail, not a replacement general-purpose faster-whisper distribution.

No `av` package, PyAV extension, FFmpeg library/executable, CUDA library, Torch or
Transformers component is part of this vendored directory. Native runtime DLL
selection and third-party notices are verified separately by the Windows build.
