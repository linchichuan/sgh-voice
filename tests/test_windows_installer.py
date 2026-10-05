"""Static guards for the Windows-only installer smoke script.

These checks do not execute Inno Setup or constitute Windows acceptance.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "windows/install-test.ps1").read_text(encoding="utf-8")
INSTALLER = (ROOT / "windows/installer.iss").read_text(encoding="utf-8")


def test_installer_smoke_has_matching_identity_and_preexisting_install_guard():
    app_id = re.search(r"^AppId=\{(\{[^\r\n]+})$", INSTALLER, re.M).group(1)
    assert f"$AppId = '{app_id}_is1'" in SCRIPT
    guard = SCRIPT.index("Existing SGH Voice installation or shortcut found")
    install = SCRIPT.index("Invoke-SmokeProcess $Installer")
    assert guard < install
    assert "HKCU:" in SCRIPT and "HKLM:" in SCRIPT and "WOW6432Node" in SCRIPT


def test_installer_smoke_never_requests_elevation_security_bypass_or_cloud():
    for unsafe in ("-Verb RunAs", "Set-ExecutionPolicy", "Unblock-File", "Add-MpPreference",
                   "Set-MpPreference", "--api-key", "OPENAI_API_KEY", "GROQ_API_KEY"):
        assert unsafe not in SCRIPT
    assert "/NORESTART /RESTARTEXITCODE=3010" in SCRIPT
    assert "/VERYSILENT /SUPPRESSMSGBOXES" in SCRIPT
    assert "standardUserTested = $false" in SCRIPT
    assert "windowsDesktopAcceptance = 'not-run'" in SCRIPT
    assert "microphoneTested = $false; cloudTested = $false; inputDeliveryTested = $false" in SCRIPT


def test_installed_runtime_checked_outside_checkout_with_exact_bytes():
    assert "[Guid]::NewGuid()" in SCRIPT
    assert "'installed app with spaces'" in SCRIPT
    assert "Get-FileHash -LiteralPath $Installer -Algorithm SHA256" in SCRIPT
    assert "Get-ChildItem -LiteralPath $SourceApp -Recurse -File" in SCRIPT
    assert "Invoke-SmokeProcess $InstalledExe ('--self-test \"' + $SmokeReport + '\"') $TestRoot" in SCRIPT
    assert "--app $InstalledExe --smoke-report $SmokeReport --source-commit $Build.sourceCommit" in SCRIPT


def test_cleanup_is_in_finally_and_cannot_hide_uninstall_failure():
    cleanup = SCRIPT.index("Invoke-SmokeProcess $Uninstaller")
    assert "} finally {" in SCRIPT[:cleanup]
    assert "if ($TemporaryCreated -and $Report.ok) { Remove-Item -LiteralPath $TestRoot -Recurse -Force }" in SCRIPT
    assert "Assert-Smoke (-not (Test-Path -LiteralPath $InstallDirectory))" in SCRIPT
    assert "$Checks.externalSyntheticDataPreserved = $true" in SCRIPT
    assert "[Environment]::SetEnvironmentVariable('SGHVOICE_DATA_DIR', $PreviousDataDir, 'Process')" in SCRIPT


def test_uninstall_waits_for_inno_second_phase_process_tree():
    assert "-WorkingDirectory $WorkingDirectory -Wait -PassThru" in SCRIPT
    assert "$Process.WaitForExit(" not in SCRIPT


def test_installer_is_per_machine_and_silent_mode_skips_interactive_launch():
    assert "PrivilegesRequired=admin" in INSTALLER
    assert "{autoprograms}" in INSTALLER and "{autodesktop}" in INSTALLER
    assert "Flags: nowait postinstall skipifsilent" in INSTALLER
    assert "[UninstallDelete]" not in INSTALLER


def test_installer_smoke_checks_machine_registration_and_legacy_per_user_paths():
    assert '$UninstallKey = "HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\$AppId"' in SCRIPT
    assert "GetFolderPath('CommonPrograms')" in SCRIPT
    assert "GetFolderPath('CommonDesktopDirectory')" in SCRIPT
    assert "$LegacyInstall" in SCRIPT and "$LegacyDesktop" in SCRIPT
    assert "Assert-Smoke $Report.elevatedRunner" in SCRIPT
    assert "$Checks.machineRegistration = $true" in SCRIPT
