[CmdletBinding()]
param()

# Install only the exact artifact produced by build.ps1, into a script-owned
# temporary directory. This proves CI packaging behavior, not microphone or
# interactive Windows 10/11 acceptance. No credentials or network calls are used.
# The installer is per-machine (administrator install, shared by all accounts).
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitProcess -or $PSVersionTable.PSVersion.Major -lt 7) {
    throw 'Installer smoke test requires Windows and 64-bit PowerShell 7.'
}
$RepoRoot = Split-Path -Parent $PSScriptRoot
$DistRoot = Join-Path $RepoRoot 'dist\windows'
$BuildManifest = Join-Path $DistRoot 'windows-build.json'
$ReportPath = Join-Path $DistRoot 'windows-install-test.json'
$SmokeReport = Join-Path $DistRoot 'windows-installed-smoke.json'
$InstallLog = Join-Path $DistRoot 'windows-install.log'
$UninstallLog = Join-Path $DistRoot 'windows-uninstall.log'
$AppId = '{FF155096-E838-4FF3-8AAE-23D89693E9A7}_is1'
$UninstallKey = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppId"
$ExistingKeys = @(
    $UninstallKey,
    "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\$AppId",
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppId",
    "HKCU:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\$AppId"
)
$StartShortcut = Join-Path ([Environment]::GetFolderPath('CommonPrograms')) 'SGH Voice.lnk'
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath('CommonDesktopDirectory')) 'SGH Voice.lnk'
# Earlier per-user preview locations must not be overwritten either.
$LegacyGroup = Join-Path ([Environment]::GetFolderPath('Programs')) 'SGH Voice'
$LegacyDesktop = Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'SGH Voice.lnk'
$DefaultInstall = Join-Path $env:ProgramFiles 'SGHVoice'
$LegacyInstall = Join-Path $env:LOCALAPPDATA 'Programs\SGHVoice'

function Invoke-SmokeProcess {
    param([string]$Executable, [string]$Arguments, [string]$WorkingDirectory)
    # -Wait follows the process tree on Windows. Inno's first uninstall process
    # exits before its second phase finishes; Process.WaitForExit alone can race.
    # The calling CI step supplies a timeout for the complete smoke sequence.
    $Process = Start-Process -FilePath $Executable -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory -Wait -PassThru
    try {
        $Process.Refresh()
        if ($Process.ExitCode -ne 0) {
            throw "A test-owned process failed with exit code $($Process.ExitCode)."
        }
    } finally {
        $Process.Dispose()
    }
}

function Assert-Smoke {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

# Fail before installation if an existing user/machine installation or shortcut
# could be replaced. This script never removes another installation's resources.
foreach ($Path in @($ExistingKeys) + @($StartShortcut, $DesktopShortcut, $DefaultInstall, $LegacyGroup, $LegacyDesktop, $LegacyInstall)) {
    if (Test-Path -LiteralPath $Path) { throw 'Existing SGH Voice installation or shortcut found; use a clean test account.' }
}
Assert-Smoke (Test-Path -LiteralPath $BuildManifest) 'Run build.ps1 before the installer smoke test.'
$Build = Get-Content -LiteralPath $BuildManifest -Raw -Encoding utf8 | ConvertFrom-Json
Assert-Smoke ($Build.version -match '^\d+\.\d+\.\d+$') 'Invalid build version.'
Assert-Smoke ($Build.sourceCommit -match '^[a-f0-9]{40}$') 'Invalid source commit.'
$InstallerName = "SGHVoice-Windows-$($Build.version)-x64-unsigned.exe"
Assert-Smoke ($Build.installer.name -eq $InstallerName) 'Unexpected installer filename.'
$Installer = Join-Path $DistRoot $InstallerName
Assert-Smoke (Test-Path -LiteralPath $Installer) 'Installer is missing.'
Assert-Smoke (((Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant()) -eq $Build.installer.sha256) 'Installer hash differs from the build record.'
$SourceApp = Join-Path $DistRoot 'SGHVoice'
Assert-Smoke (Test-Path -LiteralPath (Join-Path $SourceApp 'SGH Voice.exe')) 'Built application is missing.'

$TemporaryParent = [Environment]::GetEnvironmentVariable('RUNNER_TEMP', 'Process')
if ([string]::IsNullOrWhiteSpace($TemporaryParent)) { $TemporaryParent = [IO.Path]::GetTempPath() }
$TestRoot = Join-Path $TemporaryParent ('SGHVoice-install-smoke-' + [Guid]::NewGuid().ToString('N'))
$InstallDirectory = Join-Path $TestRoot 'installed app with spaces'
$InstalledExe = Join-Path $InstallDirectory 'SGH Voice.exe'
$Sentinel = Join-Path $TestRoot 'external-synthetic-data.txt'
$SentinelText = [Guid]::NewGuid().ToString('N')
$Uninstaller = Join-Path $InstallDirectory 'unins000.exe'
$Failure = $null
$Phase = 'prepare'
$UninstallAttempted = $false
$TemporaryCreated = $false
$PreviousDataDir = [Environment]::GetEnvironmentVariable('SGHVOICE_DATA_DIR', 'Process')
$Checks = [ordered]@{
    installation = $false; installedFiles = $false; machineRegistration = $false
    shortcuts = $false; installedSelfTest = $false; uninstall = $false
    externalSyntheticDataPreserved = $false
}
$Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
$Report = [ordered]@{
    schemaVersion = 1; kind = 'windows-ci-installer-smoke'; ok = $false
    sourceCommit = $Build.sourceCommit; version = $Build.version
    installerSha256 = $Build.installer.sha256; platform = 'windows'
    osVersion = [Environment]::OSVersion.VersionString
    elevatedRunner = $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    checks = $Checks; failedPhase = $null
    microphoneTested = $false; cloudTested = $false; inputDeliveryTested = $false
    standardUserTested = $false; windowsDesktopAcceptance = 'not-run'; published = $false
}
$Identity.Dispose()
Assert-Smoke $Report.elevatedRunner 'The per-machine installer test needs an elevated (administrator) runner.'

try {
    New-Item -ItemType Directory -Path $TestRoot | Out-Null
    $TemporaryCreated = $true
    Set-Content -LiteralPath $Sentinel -Value $SentinelText -NoNewline -Encoding utf8
    $env:SGHVOICE_DATA_DIR = Join-Path $TestRoot 'isolated-profile'
    # --self-test creates its own further isolated profile and never loads keys.
    foreach ($StaleReport in @($SmokeReport, $InstallLog, $UninstallLog)) {
        if (Test-Path -LiteralPath $StaleReport) { Remove-Item -LiteralPath $StaleReport -Force }
    }
    $Phase = 'install'
    $InstallArguments = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /RESTARTEXITCODE=3010 /SP- /LANG=english /TASKS=desktopicon /DIR="' + $InstallDirectory + '" /LOG="' + $InstallLog + '"'
    Invoke-SmokeProcess $Installer $InstallArguments $TestRoot
    Assert-Smoke ((Test-Path -LiteralPath $InstalledExe) -and (Test-Path -LiteralPath $Uninstaller)) 'Installed application or uninstaller is missing.'
    $Checks.installation = $true

    $Phase = 'installed-files'
    foreach ($SourceFile in Get-ChildItem -LiteralPath $SourceApp -Recurse -File) {
        $Relative = [IO.Path]::GetRelativePath($SourceApp, $SourceFile.FullName)
        $InstalledFile = Join-Path $InstallDirectory $Relative
        Assert-Smoke (Test-Path -LiteralPath $InstalledFile) 'An installed bundle file is missing.'
        Assert-Smoke ((Get-FileHash -LiteralPath $SourceFile.FullName -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $InstalledFile -Algorithm SHA256).Hash) 'Installed bundle file differs from built bytes.'
    }
    $Checks.installedFiles = $true
    $Phase = 'registration'
    Assert-Smoke (Test-Path -LiteralPath $UninstallKey) 'Per-machine uninstall registration is missing.'
    $Registration = Get-ItemProperty -LiteralPath $UninstallKey
    Assert-Smoke ($Registration.InstallLocation.TrimEnd('\') -eq $InstallDirectory.TrimEnd('\')) 'Per-machine registration points outside the test installation.'
    Assert-Smoke ($Registration.DisplayVersion -eq $Build.version) 'Installed version differs from built version.'
    foreach ($OtherKey in $ExistingKeys | Where-Object { $_ -ne $UninstallKey }) {
        Assert-Smoke (-not (Test-Path -LiteralPath $OtherKey)) 'Installer unexpectedly registered outside the 64-bit machine hive.'
    }
    $Checks.machineRegistration = $true
    $Phase = 'shortcuts'
    $ShortcutShell = New-Object -ComObject WScript.Shell
    try {
        foreach ($ShortcutPath in @($StartShortcut, $DesktopShortcut)) {
            Assert-Smoke (Test-Path -LiteralPath $ShortcutPath) 'Installed shortcut is missing.'
            $Shortcut = $ShortcutShell.CreateShortcut($ShortcutPath)
            try {
                Assert-Smoke ($Shortcut.TargetPath -eq $InstalledExe) 'Shortcut target differs from the test installation.'
            } finally {
                [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($Shortcut)
            }
        }
    } finally {
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($ShortcutShell)
    }
    $Checks.shortcuts = $true

    $Phase = 'installed-self-test'
    # Working outside both source and original bundle catches accidental reliance
    # on checkout files or build-machine Python imports.
    Invoke-SmokeProcess $InstalledExe ('--self-test "' + $SmokeReport + '"') $TestRoot
    Assert-Smoke (Test-Path -LiteralPath $SmokeReport) 'Installed self-test report is missing.'
    & python (Join-Path $RepoRoot 'scripts\verify_windows_release.py') --installer $Installer `
        --app $InstalledExe --smoke-report $SmokeReport --source-commit $Build.sourceCommit
    if ($LASTEXITCODE -ne 0) { throw 'Installed executable self-test validation failed.' }
    $Checks.installedSelfTest = $true
} catch {
    $Failure = $_
    $Report.failedPhase = $Phase
} finally {
    try {
        if (Test-Path -LiteralPath $Uninstaller) {
            $UninstallAttempted = $true
            Invoke-SmokeProcess $Uninstaller ('/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG="' + $UninstallLog + '"') $TestRoot
            # Inno's uninstaller can remove its own directory just after exit.
            $Deadline = [DateTime]::UtcNow.AddSeconds(10)
            while ((Test-Path -LiteralPath $InstallDirectory) -and [DateTime]::UtcNow -lt $Deadline) {
                Start-Sleep -Milliseconds 100
            }
            Assert-Smoke (-not (Test-Path -LiteralPath $InstallDirectory)) 'Uninstall left application files behind.'
            foreach ($OwnedResource in @($UninstallKey, $StartShortcut, $DesktopShortcut)) {
                Assert-Smoke (-not (Test-Path -LiteralPath $OwnedResource)) 'Uninstall left registration or shortcuts behind.'
            }
            $Checks.uninstall = $true
        }
        if ($TemporaryCreated) {
            Assert-Smoke ((Get-Content -LiteralPath $Sentinel -Raw -Encoding utf8) -eq $SentinelText) 'Uninstall changed external synthetic data.'
            $Checks.externalSyntheticDataPreserved = $true
        }
    } catch {
        if ($null -eq $Failure) { $Failure = $_; $Report.failedPhase = 'uninstall' }
    } finally {
        [Environment]::SetEnvironmentVariable('SGHVOICE_DATA_DIR', $PreviousDataDir, 'Process')
        $Report.ok = ($null -eq $Failure) -and ($Checks.Values -notcontains $false)
        $Report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding utf8
        # Never use manual deletion to turn a failed uninstall into a passing one.
        # Cleanup is limited to the unique directory created above, after success.
        if ($TemporaryCreated -and $Report.ok) { Remove-Item -LiteralPath $TestRoot -Recurse -Force }
    }
}
if ($null -ne $Failure) { throw $Failure }
Assert-Smoke ($Report.ok -and $UninstallAttempted) 'Installer test did not complete every required check.'
Write-Host 'PASS Windows CI install / installed runtime self-test / uninstall.'
Write-Host 'Microphone, cloud, target input, standard-user rights and Windows desktop acceptance remain NOT RUN.'
