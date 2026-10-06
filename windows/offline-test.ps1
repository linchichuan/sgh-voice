[CmdletBinding()]
param([double]$MaxCer = 0.15)
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
    # Public, non-clinical Japanese test speech (FLEURS, CC-BY 4.0) is fetched
    # by CI tooling first. The application itself then runs with Python
    # network connections denied and uses only the model inside its bundle.
    $Fixture = Join-Path $TestRoot 'speech'
    & python scripts/prepare_windows_speech_fixture.py --out $Fixture --count 5 --skip 40 --phone-mp3
    if ($LASTEXITCODE -ne 0) { throw 'Public speech fixture preparation failed.' }
    $Clips = Join-Path $Fixture 'clips.json'
    $Arguments = @('--offline-self-test', 'bundled', "`"$ReportPath`"", '--speech-set', "`"$Clips`"",
                   '--max-cer', $MaxCer.ToString([Globalization.CultureInfo]::InvariantCulture),
                   '--soap-transcript', "`"$(Join-Path $RepoRoot 'scripts\fixtures\consultation-ja-fictional.txt')`"")
    $Process = Start-Process -FilePath $AppExe -ArgumentList $Arguments -WorkingDirectory $TestRoot -PassThru
    try {
        if (-not $Process.WaitForExit(900000)) {
            $Process.Kill($true)
            throw 'Offline inference exceeded the time limit.'
        }
        $ExitCode = $Process.ExitCode
    } finally { $Process.Dispose() }
    $Report = Get-Content -LiteralPath $ReportPath -Raw -Encoding utf8 | ConvertFrom-Json
    foreach ($Clip in @($Report.speech)) {
        $Kind = if ($Clip.imported) { 'IMPORTED ' + $Clip.format } else { 'WAV' }
        Write-Host ("[{4}] CER {0:P1} in {1}s`n  REF {2}`n  HYP {3}" -f $Clip.cer, $Clip.seconds, $Clip.reference, $Clip.hypothesis, $Kind)
    }
    Write-Host ("Model hash check {0}s; first inference {1}s; overall CER {2:P1} (ceiling {3:P0})" -f `
        $Report.model_hash_seconds, $Report.first_inference_seconds, $Report.cer, $MaxCer)
    if ($ExitCode -ne 0 -or $Report.ok -ne $true -or $Report.local_inference_tested -ne $true `
            -or $Report.accuracy_tested -ne $true -or $Report.python_network_attempts -ne 0 `
            -or $Report.platform -ne 'win32' -or -not $Report.model_verified -or $Report.soap_tested -ne $true `
            -or -not (@($Report.speech) | Where-Object { $_.imported -and $_.format -eq 'MP3' -and $_.cer -le $MaxCer }) `
            -or -not (@($Report.speech) | Where-Object { $_.imported -and $_.format -eq 'WAV' -and $_.cer -le $MaxCer })) {
        throw 'Offline runtime evidence is missing or failed.'
    }
    & python scripts/check_soap_report.py $ReportPath
    if ($LASTEXITCODE -ne 0) { throw 'Bundled SOAP draft check failed.' }
    Write-Host 'PASS bundled model: SHA-256 verified; Japanese WAV clips plus imported MP3 and WAV files (Japanese folder/file names) recognized under the CER ceiling; Python network denied.'
    Write-Host 'Public read speech only: microphone, medical dictation accuracy and target-input acceptance were not tested.'
} finally {
    Pop-Location
    # TestRoot is this invocation's random directory, never a user model folder.
    if (Test-Path -LiteralPath $TestRoot) { Remove-Item -LiteralPath $TestRoot -Recurse -Force }
}
