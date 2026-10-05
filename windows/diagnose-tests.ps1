$ErrorActionPreference = 'Stop'
$Evidence = Join-Path $env:RUNNER_TEMP 'sghvoice-test-diagnostics'
New-Item -ItemType Directory -Force -Path $Evidence | Out-Null
$Start = [Diagnostics.ProcessStartInfo]::new()
$Start.FileName = (Get-Command python).Source
$Start.WorkingDirectory = (Get-Location).Path
$Start.UseShellExecute = $false
$Start.RedirectStandardInput = $true
$Start.RedirectStandardOutput = $true
$Start.RedirectStandardError = $true
$Start.Environment['PYTHONUNBUFFERED'] = '1'
$Start.Environment['PYTHONIOENCODING'] = 'utf-8'
$Start.Environment['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
$Start.Environment.Remove('GH_TOKEN') | Out-Null
foreach ($Arg in @('-u', 'scripts/diagnose_windows_tests.py', '--evidence-dir', $Evidence,
                   '--startup-timeout', '30', '--case-timeout', '30', '-vv', '--durations=20')) {
    $Start.ArgumentList.Add($Arg)
}
foreach ($Test in (Get-ChildItem tests/test_windows*.py | Sort-Object Name)) {
    $Start.ArgumentList.Add($Test.FullName)
}
$Process = [Diagnostics.Process]::new()
$Process.StartInfo = $Start
if (-not $Process.Start()) { throw 'Could not start diagnostic test process.' }
$Process.StandardInput.Close()
# Drain both pipes asynchronously, so verbose output cannot fill a child pipe.
$Stdout = $Process.StandardOutput.ReadToEndAsync()
$Stderr = $Process.StandardError.ReadToEndAsync()
$Clock = [Diagnostics.Stopwatch]::StartNew()
$TimedOut = $false
$NextHeartbeat = 0
while (-not $Process.WaitForExit(1000)) {
    if ($Clock.Elapsed.TotalSeconds -ge $NextHeartbeat) {
        Write-Output "Diagnostic child active: $([int]$Clock.Elapsed.TotalSeconds)s"
        $Progress = Join-Path $Evidence 'progress.jsonl'
        if (Test-Path -LiteralPath $Progress) { Get-Content -LiteralPath $Progress -Tail 1 }
        $NextHeartbeat += 15
    }
    if ($Clock.Elapsed.TotalSeconds -ge 120) {
        $TimedOut = $true
        $Process.Kill($true)
        break
    }
}
$Exited = $Process.WaitForExit(10000)
$OutputClosed = $Stdout.Wait(10000)
$ErrorClosed = $Stderr.Wait(10000)
if ($OutputClosed) {
    $Stdout.Result | Set-Content -LiteralPath (Join-Path $Evidence 'pytest-stdout.txt') -Encoding utf8
    Write-Output $Stdout.Result
}
if ($ErrorClosed) {
    $Stderr.Result | Set-Content -LiteralPath (Join-Path $Evidence 'pytest-stderr.txt') -Encoding utf8
    Write-Output $Stderr.Result
}
$Trace = Join-Path $Evidence 'hang-trace.txt'
if (Test-Path -LiteralPath $Trace) { Get-Content -LiteralPath $Trace }
$Code = if ($Exited) { $Process.ExitCode } else { -1 }
@{ timedOut = $TimedOut; exited = $Exited; stdoutClosed = $OutputClosed;
   stderrClosed = $ErrorClosed; exitCode = $Code; elapsedSeconds = $Clock.Elapsed.TotalSeconds } |
    ConvertTo-Json -Compress | Write-Output
if ($TimedOut -or -not $Exited -or -not $OutputClosed -or -not $ErrorClosed -or $Code -ne 0) {
    exit 1
}
exit 0
