# SGH Voice Windows build and acceptance

## Current status

This branch prepares a Windows desktop client and an **unsigned, per-user installer**.
Source tests on macOS do **not** establish Windows compatibility. No Windows installer
has been built, installed, recorded audio, or passed target-paste acceptance in this
task. There is no public Windows download until the checks below pass.

The original `voiceinput.spec` / `build.sh` remain the macOS build. Windows uses
`windows_launcher.py`, the `windows_client` package, shared recording/transcription/
configuration modules, and `windows/sghvoice.spec`. Windows does not package rumps,
PyObjC, MLX, or the macOS dashboard. The installer does not enable paid providers or
install an offline model. Preserve the client's actual engine availability and privacy
policy; do not describe the Windows build as fully offline without an implemented and
tested local recognizer.

## Verified build resources (2026-10-04)

- Repository `linchichuan/sgh-voice` is public. GitHub Actions is enabled. Its registered
  self-hosted runner count is **0**. The existing workflows are CI, Firebase Hosting,
  and dynamic Pages deployment; none builds Windows.
- Latest audited public main was `e096d3c977d9b9cdc98c17639ceaf6e39ebc5822`.
  [Its CI run passed](https://github.com/linchichuan/sgh-voice/actions/runs/37163389339).
- Current execution host is Darwin arm64. Local PyInstaller 6.19.0 is installed in
  a Python 3.14 macOS environment, not a supported Windows build environment.
- Parallels is installed, but `prlctl list --all --output name,status` reported its
  `Windows 11` VM as **invalid**. It was not started, repaired, or replaced.
- The official [`windows-2022` runner image inventory](https://github.com/actions/runner-images/blob/main/images/windows/Windows2022-Readme.md)
  lists Python 3.12 and Inno Setup 6. A job still checks actual installed tools.
  Image contents can change.
- [PyInstaller requires a Windows host for Windows output](https://pyinstaller.org/en/stable/).
  A renamed macOS file, a cross-built bootloader alone, or a macOS unit-test run is
  not a Windows release.

## Cost and authorization boundary

[GitHub's current billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
states that standard hosted runners are free for public repositories. Larger runners
are always charged. Artifact storage is subject to the account's included storage
and billing settings. This workflow uses one standard `windows-2022` job, a 25-minute
timeout, no build matrix, no cache, and one-day artifact retention. Account-wide
storage usage/budget was not audited; do not promise zero total billing.

The workflow is **manual only** and has `contents: read`; it never creates a GitHub
Release, changes main, or deploys the download site. No workflow was dispatched in
this task. A new `workflow_dispatch` file must exist on the default branch before it
can be dispatched, even when selecting another branch. See
[GitHub's manual workflow documentation](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).
Do not push unreviewed application changes to main merely to enable a build.

Before activating a new builder, installing missing software, changing a workflow
on main, or accepting any paid service/license, report the exact action and obtain
any approval still required by the session. No new credential, VM, runner subscription,
code-signing certificate, or security exception is part of this implementation.

[Inno Setup's license](https://jrsoftware.org/files/is/license.txt) currently permits
commercial applications under its stated conditions; its
[website requests commercial users to purchase a license](https://jrsoftware.org/isinfo.php).
No purchase is made by these scripts. Preserve its notices. If policy requires a
commercial license, settle that before building in a new environment.

## Build on an approved Windows environment

Prerequisites: a reviewed, clean commit; Windows x64; official Python 3.12 x64 with
Tcl/Tk; Git; Inno Setup 6; the pinned dependencies below. An existing approved
environment can use the commands directly. On a new environment, dependency
installation is a separate explicit setup step; `build.ps1` never installs software.

```powershell
py -3.12 -m venv .venv-windows
.\.venv-windows\Scripts\Activate.ps1
python -m pip install --require-hashes --only-binary=:all: -r requirements-windows-build.txt
.\windows\build.ps1 -PreflightOnly
.\windows\build.ps1
```

Do not disable PowerShell execution policy or OS security to make these commands
work. Use the machine's approved execution method or resolve the policy with its owner.

`requirements-windows.txt` and `requirements-windows-build.txt` pin the applicable
packages and SHA256 hashes from the existing `requirements-dev.lock`. Windows-only
`pefile==2023.2.7` uses the [PyPI release hashes](https://pypi.org/project/pefile/2023.2.7/).
The newer 2024.8.26 pefile is explicitly excluded by PyInstaller. These pins have not
yet been installed together on Windows; the first real job must confirm resolution.
Read-only published PyPI metadata checks confirmed all 42 pinned packages' dependency
constraints and compatible Windows x64 CPython 3.12 wheels with matching lock hashes.
No macOS requirements file is installed on Windows, and no unbounded dependency
upgrade occurs. A missing compatible wheel causes a failure for review.

`build.ps1` refuses non-Windows, non-x64 Python, a non-3.12 interpreter, missing tools,
an unidentifiable version, or a dirty checkout. It cleans only `build/windows` and
`dist/windows`, embeds the exact Git source commit and `config.APP_VERSION`, builds
an onedir bundle, executes the frozen app's offline self-test, and runs Inno Setup.
The application installs into `%LOCALAPPDATA%\Programs\SGHVoice` without elevation.
It provides a Start menu shortcut, optional desktop shortcut, and uninstaller.
Uninstall does not remove the user's profile or credentials.

Outputs (after a successful real Windows build):

```text
dist/windows/SGHVoice/SGH Voice.exe
dist/windows/SGHVoice-Windows-<version>-x64-unsigned.exe
dist/windows/windows-build.json
dist/windows/windows-smoke.json
```

The manifest records the source commit, version, installer size/SHA256, app SHA256,
and frozen self-test. Its `windowsAcceptance` remains `not-run`, `published` remains
`false`. SHA256 and valid PE headers establish artifact identity and structure,
not safety, successful audio capture, or correct behavior in another application.

## What the manual job proves

The workflow installs the hashed Python dependencies, runs Windows-specific tests,
builds the application and installer, and checks the frozen application with:

```powershell
& '.\dist\windows\SGHVoice\SGH Voice.exe' --self-test '.\dist\windows\windows-smoke.json'
```

The self-test uses an isolated temporary profile and no external API or microphone.
It checks Windows architecture, required imports, native Windows bindings, Tcl/Tk
startup, audio libraries, OpenCC, and the credential backend class without reading
user credentials. Hardware recording, actual credential persistence, app focus,
global hotkeys, and insertion remain separate acceptance requirements.

A successful job uploads an unsigned test artifact with one-day retention. It is
not a permanent public download. Download the artifact before expiration and
preserve the original installer and manifests unchanged for acceptance.

## Real Windows acceptance before opening downloads

Use an authorized Windows 11 x64 session with a working microphone and an interactive
desktop. A hosted build runner's library self-test does not replace this session.
Record the OS/build, tester/date, app version, exact source commit, installer SHA256,
observed results, and any failure. Use synthetic, non-sensitive dictation only.

1. Install from the exact `.exe` as a standard user. Confirm Start menu launch, no
   admin requirement, correct version and configuration directory. Observe normal
   Windows security behavior. The build is unsigned; do not disable SmartScreen,
   Defender, or organizational policy. If the OS blocks it, record `BLOCKED` and
   leave public download disabled until there is an approved resolution.
2. Select the real microphone and record short synthetic Chinese, Japanese, and
   English samples; verify sound level, start/stop, repeated recording, permissions
   denied, missing device, and recovery. Verify only the offered/available recognizer
   modes; provider calls require approved existing credentials and usage scope.
3. Verify recognition and cleanup choices, language selection, saved settings across
   restart, and error handling. Confirm privacy mode never silently falls back to
   a cloud provider. If the available Windows recognizer cannot run privately, show
   that limitation and refuse the request rather than upload audio.
4. Test the configured global hotkey with Notepad and a browser input. Confirm the
   original intended input receives text once, Unicode remains correct, and changing
   foreground app during recording does not paste into a different target. Test
   normal versus elevated target applications; use clipboard fallback where Windows
   privilege boundaries prevent injection rather than escalating the app.
5. Test clipboard fallback, user changes to clipboard while processing, no selection,
   closed targets, locked clipboard, and focus refusal. Confirm text remains
   recoverable without overwriting unrelated clipboard changes or pasting elsewhere.
6. Restart, repeat, and uninstall. Confirm removal of application and shortcuts while
   preserving the user's profile; reinstall and verify expected settings behavior.

Save the evidence to `docs/windows-acceptance-<version>-<date>.md`. The publication
gate requires the exact source commit and installer SHA256 plus these explicit
results (do not prefill `PASS` before observing them):

```text
- installation: PASS
- microphone: PASS
- hotkey: PASS
- target-paste: PASS
- clipboard-fallback: PASS
- privacy: PASS
- uninstall: PASS
```

After independent review and real acceptance, the public
`sgh-voice-web/downloads/windows-release.json` may be updated with matching installer
metadata, passed build evidence, and a passed acceptance record bound to that SHA256.
Place the original installer at the website's own `/downloads/<fileName>` path.
Run `python -m pytest tests/test_windows_download.py -q -o addopts=` before staging
or publishing; it verifies available-state metadata against the actual local installer
and acceptance record. Leave the public manifest `pending` until exact-byte acceptance.
The validator supports a final read-only check:

```powershell
python scripts/verify_windows_release.py `
  --installer 'dist/windows/SGHVoice-Windows-<version>-x64-unsigned.exe' `
  --app 'dist/windows/SGHVoice/SGH Voice.exe' `
  --smoke-report 'dist/windows/windows-smoke.json' `
  --source-commit '<40-character-commit>' `
  --public-manifest 'sgh-voice-web/downloads/windows-release.json'
```

This validator never writes the public manifest, uploads a binary, or deploys the
site. Review the exact destination and artifact, then use the existing approved
publication path. Provide a real downloadable URL only after verified publication.

## Remaining blocker

An approved, working Windows builder and an interactive Windows acceptance session
are still required. Options are an explicitly authorized single standard hosted
build plus a separate real Windows tester, or an approved existing Windows machine.
Repairing the invalid VM, adding a new VM, or buying infrastructure is not automatic.
Until those steps succeed, report **source prepared / build NOT RUN / Windows
acceptance NOT RUN / publication NOT DONE**.
