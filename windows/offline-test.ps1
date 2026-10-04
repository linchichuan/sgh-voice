[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'Offline frozen-runtime test requires Windows.' }
$RepoRoot = Split-Path -Parent $PSScriptRoot
$DistRoot = Join-Path $RepoRoot 'dist\windows'
$TestRoot = Join-Path $env:RUNNER_TEMP ('SGHVoice-offline-smoke-' + [Guid]::NewGuid().ToString('N'))
$ReportPath = Join-Path $DistRoot 'windows-offline-test.json'
$AppExe = Join-Path $DistRoot 'SGHVoice\SGH Voice.exe'
New-Item -ItemType Directory -Path $TestRoot | Out-Null
Push-Location $RepoRoot
try {
    # Explicit public-model acquisition for this one synthetic CI test only.
    # Pinned manifest is <150 MB; no clinical data, API account, or paid inference.
    $ModelPath = (& python -c "import sys; from windows_client.models import prepare_model,TOTAL_BYTES; assert TOTAL_BYTES < 150_000_000; print(prepare_model(sys.argv[1]))" $TestRoot).Trim()
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $ModelPath)) { throw 'Pinned test-model preparation failed.' }
    $Process = Start-Process -FilePath $AppExe -ArgumentList @('--offline-self-test', "`"$ModelPath`"", "`"$ReportPath`"") -WorkingDirectory $TestRoot -PassThru
    try {
        if (-not $Process.WaitForExit(180000)) {
            $Process.Kill($true)
            throw 'Synthetic inference exceeded three minutes.'
        }
        if ($Process.ExitCode -ne 0) { throw 'Bundled offline inference failed.' }
    } finally { $Process.Dispose() }
    $Report = Get-Content -LiteralPath $ReportPath -Raw -Encoding utf8 | ConvertFrom-Json
    if ($Report.ok -ne $true -or $Report.local_inference_tested -ne $true -or $Report.python_network_attempts -ne 0 -or $Report.platform -ne 'win32') {
        throw 'Offline runtime evidence is missing or failed.'
    }
    Write-Host 'PASS bundled CPU inference on synthetic silence with Python socket connections denied.'
    Write-Host 'Speech accuracy and physical microphone/target-input acceptance were not tested.'
} finally {
    Pop-Location
    # TestRoot is this invocation's random directory, never a user model folder.
    if (Test-Path -LiteralPath $TestRoot) { Remove-Item -LiteralPath $TestRoot -Recurse -Force }
}
