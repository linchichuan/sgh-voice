[CmdletBinding()]
param([double]$MaxCer = 0.15, [int]$BenchmarkSeconds = 0)

# CI entry point for the Windows offline (Japanese, medical) edition, called by
# .github/workflows/windows-medical.yml. Keeping the steps here lets the build
# evolve without editing the workflow. The model benchmark is opt-in
# (-BenchmarkSeconds 2100); the 2026-10-05 comparison is in docs/WINDOWS_MEDICAL_EDITION.md. Public data only; nothing is uploaded.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'Windows CI only.' }
$RepoRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
Push-Location $RepoRoot
try {
    function Step([string]$Name, [scriptblock]$Body) {
        Write-Host "::group::$Name"
        $Started = Get-Date
        try { & $Body } finally {
            Write-Host "::endgroup::"
            Write-Host ("{0}: {1:N0}s" -f $Name, ((Get-Date) - $Started).TotalSeconds)
        }
    }
    Step 'Install hash-pinned dependencies' {
        & python -m pip install --require-hashes --only-binary=:all: -r requirements-windows-build.txt
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    }
    Step 'Windows source tests' {
        $Tests = @(Get-ChildItem tests/test_windows*.py | Sort-Object Name | ForEach-Object FullName)
        & python -m ruff check windows_launcher.py windows_client scripts/verify_windows_release.py scripts/fetch_windows_model.py @Tests --select E9,F63,F7,F82
        if ($LASTEXITCODE -ne 0) { throw 'Ruff failed.' }
        & python -m pytest @Tests -q -o addopts=
        if ($LASTEXITCODE -ne 0) { throw 'Windows tests failed.' }
    }
    $Unpinned = (& python -c "import json;m=json.load(open('resources/windows/model-ja-v1.json',encoding='utf-8'));print(m['revision']=='PENDING_REVISION')").Trim() -eq 'True'
    Step 'Build installer with bundled model' {
        if ($Unpinned) {
            Write-Host '::warning::Model manifest not pinned yet: this is a locked TEST build.'
            & ./windows/build.ps1 -LockUnpinnedModel
        } else {
            & ./windows/build.ps1
        }
    }
    Step 'Offline Japanese recognition with the bundled model' { & ./windows/offline-test.ps1 -MaxCer $MaxCer }
    Step 'Per-machine install, installed self-test, uninstall' { & ./windows/install-test.ps1 }
    if ($BenchmarkSeconds -gt 0) {
        Step 'Model selection benchmark (public FLEURS ja_jp)' {
            & python -m pip install --only-binary=:all: psutil==7.0.0 | Out-Null
            Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors | Format-List | Out-String | Write-Host
            & python scripts/benchmark_windows_ja_stt.py --work-dir (Join-Path $env:RUNNER_TEMP 'ja-stt-bench') --clips 15 --deadline $BenchmarkSeconds --long-form
            if ($LASTEXITCODE -ne 0) { Write-Host "::warning::benchmark exited with $LASTEXITCODE" }
        }
    }
    $Installer = Get-ChildItem dist/windows -Filter 'SGHVoice-Windows-*-x64-unsigned.exe' | Select-Object -First 1
    "## SGH Voice Windows offline edition`n" +
    "Installer: $($Installer.Name) ($([Math]::Round($Installer.Length / 1GB, 2)) GB)`n`n" +
    '```' + "`n" + (Get-Content dist/windows/SHA256SUMS.txt -Raw) + '```' + "`n" +
    'Not tested here: physical microphone, global hotkeys, target-app input, standard-user rights, LTSC/VDI, medical dictation accuracy. Unsigned; nothing published.' |
        Out-File -Append -Encoding utf8 $env:GITHUB_STEP_SUMMARY
    Write-Host 'PASS Windows offline edition CI.'
    # The optional benchmark may leave a non-zero native exit code behind.
    $global:LASTEXITCODE = 0
} finally {
    Pop-Location
}
