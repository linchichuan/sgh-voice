[CmdletBinding()]
param([switch]$PreflightOnly)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'Build requires Windows; macOS cannot cross-build this executable.' }
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot
try {
    foreach ($Command in @('python', 'git')) {
        if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) { throw "Missing required tool: $Command" }
    }
    & python -c "import sys,struct; assert sys.platform == 'win32' and sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8, 'Requires Windows x64 Python 3.12'; import PyInstaller, tkinter, keyring, sounddevice, soundfile, opencc, openai, anthropic"
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency/platform preflight failed. See docs/WINDOWS_BUILD.md.' }
    $Compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    $Iscc = if ($Compiler) { $Compiler.Source } else { Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe' }
    if (-not (Test-Path $Iscc)) { throw 'Inno Setup 6 is required. No software was installed automatically.' }
    $SourceCommit = (& git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $SourceCommit -notmatch '^[a-f0-9]{40}$') { throw 'Unable to identify source commit.' }
    $Dirty = & git status --porcelain --untracked-files=normal
    if ($LASTEXITCODE -ne 0 -or $Dirty) { throw 'Build requires a clean reviewed Git commit (including untracked source).' }
    $Version = (& python -c "import ast,pathlib; tree=ast.parse(pathlib.Path('config.py').read_text(encoding='utf-8')); print(next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='APP_VERSION' for t in n.targets)))").Trim()
    if ($LASTEXITCODE -ne 0 -or $Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid config.py APP_VERSION.' }
    if ($PreflightOnly) { Write-Host "PASS Windows x64 build preflight: $Version @ $SourceCommit"; return }

    $BuildRoot = Join-Path $RepoRoot 'build\windows'
    $DistRoot = Join-Path $RepoRoot 'dist\windows'
    # Never remove shared macOS or Android build directories.
    foreach ($Directory in @($BuildRoot, $DistRoot)) {
        if (Test-Path $Directory) { Remove-Item -Recurse -Force $Directory }
        New-Item -ItemType Directory -Path $Directory | Out-Null
    }
    $BuildInfo = Join-Path $BuildRoot 'windows-build-info.json'
    @{ schemaVersion=1; version=$Version; sourceCommit=$SourceCommit; platform='windows'; architecture='x64'; signing='unsigned' } |
        ConvertTo-Json | Set-Content -Encoding utf8 $BuildInfo
    $env:SGH_WINDOWS_BUILD_INFO = $BuildInfo
    & python -m PyInstaller --noconfirm --clean --workpath "$BuildRoot\pyinstaller" --distpath $DistRoot windows/sghvoice.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
    $AppDirectory = Join-Path $DistRoot 'SGHVoice'
    $AppExe = Join-Path $AppDirectory 'SGH Voice.exe'
    if (-not (Test-Path $AppExe)) { throw 'Application executable missing.' }
    $SmokeReport = Join-Path $DistRoot 'windows-smoke.json'
    $Smoke = Start-Process -FilePath $AppExe -ArgumentList @('--self-test', "`"$SmokeReport`"") -Wait -PassThru
    if ($Smoke.ExitCode -ne 0 -or -not (Test-Path $SmokeReport)) { throw 'Frozen application self-test failed.' }
    & $Iscc "/DAppVersion=$Version" "/DSourceDir=$AppDirectory" "/DOutputDir=$DistRoot" windows/installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation failed.' }
    $Installer = Join-Path $DistRoot "SGHVoice-Windows-$Version-x64-unsigned.exe"
    & python scripts/verify_windows_release.py --installer $Installer --app $AppExe --smoke-report $SmokeReport --source-commit $SourceCommit --write-manifest "$DistRoot\windows-build.json"
    if ($LASTEXITCODE -ne 0) { throw 'Build verification failed.' }
    Write-Host "PASS unsigned build: $Installer"
    Write-Host 'Windows microphone/hotkey/target-paste acceptance remains NOT RUN. Nothing was published.'
} finally {
    Remove-Item Env:SGH_WINDOWS_BUILD_INFO -ErrorAction SilentlyContinue
    Pop-Location
}
