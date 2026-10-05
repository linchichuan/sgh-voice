# SGH Voice Windows build and acceptance

## Current status

The 2.7.6 source adds an explicitly selected OpenAI cloud mode alongside the
default local CPU mode. See [WINDOWS_CLOUD_MODE.md](WINDOWS_CLOUD_MODE.md) for the
data route, user-key requirements and test boundaries. It requires a new,
versioned installer; the following build evidence applies to 2.7.5 only until a
new source-specific report is published.

The Windows 2.7.5 local-only CPU preview has been built, tested and published as an
**unsigned test prerelease**. [Download and reports](https://github.com/linchichuan/sgh-voice/releases/tag/windows-offline-preview-20261004)
are tied to source `4750f47dbb86efd11db77292f8f03d10a8068b2d`.
The [Windows Server 2022 run](https://github.com/linchichuan/sgh-voice/actions/runs/37202178595)
passed 239 tests and 65 subtests, packaging, local CPU inference on synthetic silence,
installation, installed-runtime checks and uninstallation. See
[WINDOWS_HANDOFF.md](WINDOWS_HANDOFF.md) for exact installer size/hash and scope.

Physical microphone, interactive hotkey/target-paste and standard-user Windows 10/11
acceptance remain **NOT VERIFIED**. The main website's stable Windows manifest stays
`pending`; its separate [preview download page](https://voice.shingihou.com/windows-preview.html)
is deployed. Synthetic-silence inference is not an accuracy benchmark.

Windows uses `windows_launcher.py`, `windows_client`, shared recording/configuration
modules and `windows/sghvoice.spec`. The macOS `voiceinput.spec` / `build.sh` remain
separate. Default local recognition uses faster-whisper/CTranslate2 on CPU with
`compute_type="int8"`, without an API key or cloud fallback. Optional cloud
recognition uses the user's OpenAI key only after explicit mode selection and
consent. LLM rewriting and
translation are disabled in this preview; users review and edit the recognizer's
text themselves. MLX, rumps, PyObjC and the macOS dashboard are not Windows engines.

## Local model and setup

The selected model is [Systran/faster-whisper-base](https://huggingface.co/Systran/faster-whisper-base),
a CTranslate2 conversion of OpenAI Whisper base multilingual, published under MIT.
The pinned source revision is
[`ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66`](https://huggingface.co/Systran/faster-whisper-base/tree/ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66).
`resources/windows/model-base-v1.json` records sizes and SHA256 for `model.bin`,
`config.json`, `tokenizer.json` and `vocabulary.txt`: **147,882,941 bytes, about 148 MB**
in total. The distributed weights are FP16; CPU int8 is the application's loading
and computation choice. Preserve the applicable license notices.

Model weights are not included in the installer. Choose a prepared local model
folder or explicitly confirm **Download local model** after reviewing source and
size. Startup and recording do not automatically download models. Setup downloads
public model data from Hugging Face without an account/token; it does not upload
recordings or transcript text. Files become active only after size and SHA256 checks.
Cancellation or failure leaves recognition unavailable, never cloud fallback. Once
prepared, the complete model runs locally. Network paths and incomplete model or
tokenizer folders are refused.

The target is Windows x64 with a CPU supporting at least **SSE 4.1**, as required by
[CTranslate2's prebuilt x86-64 binaries](https://opennmt.net/CTranslate2/hardware_support.html).
No GPU or CUDA setup is part of this path. **8 GB RAM and at least 1 GB free disk
space are provisional engineering recommendations, not measured minimums.** The
final app bundle, model staging and temporary audio also require space. A clean
Windows installation must verify whether any Visual C++ runtime dependency is
missing; report that instead of silently installing software. See
[CTranslate2 installation requirements](https://opennmt.net/CTranslate2/installation.html).
Latency depends on CPU, available memory and audio length. Real-time speed has
not been measured or promised.

The optional local Japanese psychiatry lexicon shows sourced spelling candidates
for manual review. It does not automatically replace transcript text, inject a
default recognition prompt or establish clinical meaning. It is **not evidence
of improved recognition accuracy**. Medical dictation requires human review against
the original speech, especially exact drug names, doses, units and negations. Text
and term candidates are transcription aids, not medical advice.

## Audited resources and cost

The 2026-10-04 audit found public repository `linchichuan/sgh-voice`, Actions enabled
and **0** registered self-hosted runners. Audited main was
`e096d3c977d9b9cdc98c17639ceaf6e39ebc5822`. Existing CI/Firebase/Pages workflows do
not build Windows. The current host is Darwin arm64; macOS PyInstaller cannot
produce a supported Windows executable. Parallels reports its Windows 11 VM as
**invalid**; it was not started, repaired or replaced.

The [standard windows-2022 image](https://github.com/actions/runner-images/blob/main/images/windows/Windows2022-Readme.md)
lists Python 3.12 and Inno Setup 6; preflight must check the actual image. GitHub
states [standard public-repository runner use is free](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
Larger runners are paid. The account's Actions artifact allowance/billing summary
is not visible with existing authorization. Do not depend on an unknown storage
allowance or add billing access.

The recommended path uses one standard Windows job, a 25-minute timeout, no matrix,
no Actions artifact upload, no cache upload and no custom-image snapshot. GitHub
Free includes [full-featured public repositories](https://docs.github.com/en/get-started/learning-about-github/githubs-plans#github-free-for-personal-accounts).
[Release assets](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases#storage-and-bandwidth-quotas)
have no total release-size or bandwidth quota; each asset must be under 2 GiB, with
at most 1000 per release. These rules support an included Release distribution path
with no additional runner/storage purchase. No separate Release-asset price is
listed there. This is an assessment of published policy, not an account-bill audit
or a guarantee about unrelated existing charges.

The existing `.github/workflows/windows-build.yml` is a manual-only preparation
with `contents: read` and no artifact/cache upload; it includes install and offline-runtime gates. It has not run and is
not the recommended Release-only path. A new
[workflow_dispatch file must exist on the default branch](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
before dispatch. A narrowly scoped
[push event](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#push)
can run from its feature branch without a main merge. Review the final workflow
before pushing; do not create an unnecessary PR that also starts the existing CI matrix.

## Test-prerelease delivery procedure

1. Finish integration and independent review, then record the new source SHA.
   Push that source to a feature branch whose workflow filters do not start a job.
2. Using the already authorized local GitHub credential, create an unpublished draft
   prerelease targeting that exact SHA. The source must exist remotely first. Use a
   new tag; do not overwrite existing releases or assets.
3. Push a reviewed, exact-branch, one-time trigger. Its single Windows job checks out
   the fixed source SHA with persisted Git credentials disabled, runs source tests,
   packages the app, performs frozen-runtime, cloud-adapter mock and local-inference checks, then tests
   installation, installed-runtime launch and uninstallation. Failed or absent gates
   cannot be reported as passing.
4. Only after those gates pass, upload the named installer, SHA256/build manifest and
   limited test reports to the existing draft. Use the job's ephemeral GITHUB_TOKEN
   with `contents: write`; do not export the local credential, add credentials, use
   `--clobber`, or upload Actions artifacts/caches.
5. Download locally and verify exact bytes, source SHA and test reports. Publish only
   as an unsigned **test prerelease**, `make_latest=false`, with physical microphone,
   standard-user installation, live cloud API and interactive desktop limits visible. Keep the stable
   website manifest pending until its separate full acceptance passes.

The [Release API](https://docs.github.com/en/rest/releases/releases#create-a-release)
requires workflow write authorization when the target changes `.github/workflows/`
relative to main, for creation and update. GITHUB_TOKEN cannot receive that permission.
The existing authorized local credential handles draft creation and final publication;
the runner only uploads assets. [GitHub CLI supports pending draft tags](https://github.com/cli/cli/blob/trunk/pkg/cmd/release/shared/fetch.go),
and [gh release upload](https://cli.github.com/manual/gh_release_upload) does not need
to create or publish the release. This procedure was completed for the preview listed above.

Any new host software, VM repair, paid runner/license, code-signing purchase or
credential change still requires the applicable session authorization. Do not change
main or deploy the website merely to enable a test build. Inno Setup's
[license](https://jrsoftware.org/files/is/license.txt) and
[commercial-use request](https://jrsoftware.org/isinfo.php) remain applicable; these
scripts make no purchase and must preserve notices.

## Build on the approved Windows environment

Use a clean reviewed commit, Windows x64, Python 3.12 x64 with Tcl/Tk, Git, Inno Setup
6 and the pinned dependencies. Dependency installation is an explicit setup step;
`build.ps1` does not install software itself.

```powershell
py -3.12 -m venv .venv-windows
.\.venv-windows\Scripts\Activate.ps1
python -m pip install --require-hashes --only-binary=:all: -r requirements-windows-build.txt
.\windows\build.ps1 -PreflightOnly
.\windows\build.ps1
.\windows\install-test.ps1
```

Use an approved PowerShell execution method; do not disable OS security or execution
policy. The offline dependency closure is separately pinned to official Windows
CPython 3.12 wheels and hashes in requirements-windows*.txt. The vendored MIT
faster-whisper frontend reads only our PCM16 mono 16 kHz WAV recordings, with no
PyAV/FFmpeg. See its PROVENANCE records and packaged third-party notices. The
spec excludes cloud SDKs, GPU DLLs and media codecs, and requires the CPU/VC runtime
DLLs. Missing compatible wheels or runtime DLLs fail visibly.

`build.ps1` refuses non-Windows, non-x64/non-3.12 Python, missing tools, invalid version
or a dirty checkout. It cleans only `build/windows` and `dist/windows`, embeds the
exact source SHA and app version, builds an onedir bundle and unsigned Inno installer,
and checks PE structure plus the frozen self-test. The default per-user installation
is `%LOCALAPPDATA%\Programs\SGHVoice`, without requested elevation. Uninstall preserves
the user's profile; this still needs actual standard-user verification.

After a successful real build, expected outputs include:

```text
dist/windows/SGHVoice/SGH Voice.exe
dist/windows/SGHVoice-Windows-<version>-x64-unsigned.exe
dist/windows/windows-build.json
dist/windows/windows-smoke.json
dist/windows/windows-install-test.json
dist/windows/windows-installed-smoke.json
```

`windows-build.json` binds installer/app hashes, size, version and source SHA.
Its full-desktop `windowsAcceptance` remains `not-run`; a build manifest with
`published: false` is a build-time record, not proof of current hosting state.
Hashes and PE structure establish identity, not dictation accuracy or microphone use.

## Automated checks and their limits

The frozen `--self-test <report-path>` uses an isolated temporary profile, no network
and no microphone. It checks Win32/Tk startup, audio file handling, OpenCC, local
runtime imports and the credential backend without reading user secrets. An import
check is not model inference. The separate frozen local-inference/synthetic-silence
check passed for the release above
with the pinned model and Python socket connections guarded; no Python network attempts
were observed. This is not whole-OS/native-library network monitoring. Silence tests
are not a clinical accuracy benchmark or proof of correct names, doses and negations.

`windows/install-test.ps1` passed in the Windows Server 2022 runner. It refuses an existing SGH
Voice installation, installs into an isolated directory, verifies installed bytes,
per-user registration and shortcuts, launches the installed self-test from outside
the checkout, and uninstalls. It records whether the runner is elevated. That
pass on an elevated Windows Server 2022 runner does not prove Windows 11 behavior,
standard-user rights,
physical microphone capture, hotkeys, target insertion or downloaded-file security
acceptance. Keep these limitations in the report and test-prerelease notes.

## Interactive acceptance before the stable website download

Use an authorized Windows 11 x64 desktop and real microphone, with synthetic,
non-sensitive samples. Record OS/build, tester/date, version, source SHA and the exact
installer SHA256. A hosted library/inference/installer check cannot replace this.

1. Install and launch as a standard user; verify version, settings directory and
   shortcuts. The build is unsigned. Observe normal SmartScreen/Defender/organization
   policy; do not disable it. If blocked, record BLOCKED and keep the stable gate closed.
2. Explicitly prepare/select the model. Test real microphone selection, levels,
   repeated recording, permission denial, device removal and recovery with Chinese,
   Japanese and English samples. Disconnect networking after setup and repeat.
3. Check local recognition, manual editing, language/settings persistence, cancellation,
   incomplete model files and errors. Verify no cloud fallback/API-key request/LLM
   rewrite. Check optional lexicon candidates leave the transcript unchanged. Manually
   inspect synthetic drug names, doses, units and negations; do not claim clinical validation.
4. Test hotkeys with Notepad and browser inputs, IME/Unicode, exactly-once insertion,
   closed targets and focus changes during recording. An unintended foreground app
   must not receive text. Respect normal/elevated application boundaries.
5. Test explicit Copy, locked clipboard, user clipboard changes and failed insertion.
   Text must remain recoverable; do not overwrite unrelated changes or retry partial
   insertion automatically. Clipboard exclusions do not control every third-party tool.
6. Restart, repeat, uninstall and reinstall. Verify application/shortcut removal and
   expected profile preservation.

Save `docs/windows-acceptance-<version>-<date>.md` with the exact source SHA and
installer SHA256. Record these only after observing them:

```text
- installation: PASS
- microphone: PASS
- hotkey: PASS
- target-paste: PASS
- clipboard-fallback: PASS
- privacy: PASS
- uninstall: PASS
```

After review and acceptance, update `sgh-voice-web/downloads/windows-release.json`
with matching metadata and the hash-bound record, placing the unchanged installer at
the website's own `/downloads/<fileName>`. Run
`python -m pytest tests/test_windows_download.py -q -o addopts=` before staging or
publishing. `scripts/verify_windows_release.py --public-manifest <path>` can validate
the exact installer/app/smoke/source identity with its other required arguments; it
never publishes or changes the public manifest. Provide a download URL only after
verifying publication. A test prerelease does not satisfy this stable-download gate.

Current outcome: **offline source PUSHED / Windows build PASS / test prerelease
PUBLISHED / interactive Windows acceptance NOT VERIFIED / own-site deployment PENDING**.
The exact installer and evidence are linked in [WINDOWS_HANDOFF.md](WINDOWS_HANDOFF.md).
The public preview does not satisfy the stable website acceptance gate.
