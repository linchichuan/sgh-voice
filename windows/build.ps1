[CmdletBinding()]
# -LockUnpinnedModel: TEST BUILDS ONLY. While resources/windows/model-ja-v1.json
# is not yet pinned, pin it from what the Hub serves now and write the locked
# manifest into the bundle. A pinned manifest is always verified strictly.
param([switch]$PreflightOnly, [switch]$LockUnpinnedModel)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'Build requires Windows; macOS cannot cross-build this executable.' }
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot
try {
    foreach ($Command in @('python', 'git')) {
        if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) { throw "Missing required tool: $Command" }
    }
    & python -c "import sys,struct; assert sys.platform == 'win32' and sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8, 'Requires Windows x64 Python 3.12'; import PyInstaller, tkinter, keyring, sounddevice, soundfile, opencc, ctranslate2, tokenizers, onnxruntime; from windows_client._vendor import faster_whisper"
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
    # The pinned speech model ships inside the installer: users never download it.
    # Every file is checked against resources/windows/model-ja-v1.json (size + SHA-256).
    $FetchArguments = @('scripts/fetch_windows_model.py', '--dest', (Join-Path $AppDirectory 'models'))
    if ($LockUnpinnedModel) {
        $FetchArguments += @('--lock-unpinned', '--write-manifest', (Join-Path $AppDirectory '_internal\resources\windows\model-ja-v1.json'))
    }
    & python @FetchArguments
    if ($LASTEXITCODE -ne 0) { throw 'Pinned model fetch or verification failed.' }
    # The SOAP language model and the official llama.cpp CPU runtime, pinned by
    # resources/windows/llm-ja-v1.json (release zip SHA-256 + GGUF size/SHA-256).
    & python scripts/fetch_windows_llm.py --dest (Join-Path $AppDirectory 'llm')
    if ($LASTEXITCODE -ne 0) { throw 'Pinned SOAP model/runtime fetch or verification failed.' }
    $SmokeReport = Join-Path $DistRoot 'windows-smoke.json'
    $Smoke = Start-Process -FilePath $AppExe -ArgumentList @('--self-test', "`"$SmokeReport`"") -Wait -PassThru
    if ($Smoke.ExitCode -ne 0 -or -not (Test-Path $SmokeReport)) { throw 'Frozen application self-test failed.' }
    & $Iscc "/DAppVersion=$Version" "/DSourceDir=$AppDirectory" "/DOutputDir=$DistRoot" windows/installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation failed.' }
    # Companion setup with the SOAP model (kept separate: one setup must stay under ~4 GB).
    & $Iscc "/DAppVersion=$Version" "/DSourceDir=$(Join-Path $AppDirectory 'llm')" "/DOutputDir=$DistRoot" windows/installer-soap.iss
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation of the SOAP model setup failed.' }
    $Installer = Join-Path $DistRoot "SGHVoice-Windows-$Version-x64-unsigned.exe"
    & python scripts/verify_windows_release.py --installer $Installer --app $AppExe --smoke-report $SmokeReport --source-commit $SourceCommit --write-manifest "$DistRoot\windows-build.json"
    if ($LASTEXITCODE -ne 0) { throw 'Build verification failed.' }
    # Checksums for hospital IT: both setups and every bundled model/runtime file.
    $Sums = @((Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant() + '  ' + (Split-Path -Leaf $Installer))
    $SoapSetup = Join-Path $DistRoot "SGHVoice-Windows-$Version-x64-unsigned-soap-model.exe"
    $Sums += (Get-FileHash -LiteralPath $SoapSetup -Algorithm SHA256).Hash.ToLowerInvariant() + '  ' + (Split-Path -Leaf $SoapSetup)
    $Bundled = @(Get-ChildItem -LiteralPath (Join-Path $AppDirectory 'models') -Recurse -File) + @(Get-ChildItem -LiteralPath (Join-Path $AppDirectory 'llm') -Recurse -File)
    foreach ($ModelFile in $Bundled | Sort-Object FullName) {
        $Relative = [IO.Path]::GetRelativePath($AppDirectory, $ModelFile.FullName).Replace('\', '/')
        $Sums += (Get-FileHash -LiteralPath $ModelFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant() + '  ' + $Relative
    }
    [IO.File]::WriteAllLines((Join-Path $DistRoot 'SHA256SUMS.txt'), [string[]]$Sums, [Text.UTF8Encoding]::new($false))
    Get-Content -LiteralPath (Join-Path $DistRoot 'SHA256SUMS.txt') | Write-Host
    Write-Host "PASS unsigned build: $Installer"
    Write-Host 'Windows microphone/hotkey/target-paste acceptance remains NOT RUN. Nothing was published.'
} finally {
    Remove-Item Env:SGH_WINDOWS_BUILD_INFO -ErrorAction SilentlyContinue
    Pop-Location
}
