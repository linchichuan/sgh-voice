; Compile through windows/build.ps1. This installer intentionally has no signing key.
#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef SourceDir
  #error SourceDir is required
#endif
#ifndef OutputDir
  #error OutputDir is required
#endif

[Setup]
AppId={{FF155096-E838-4FF3-8AAE-23D89693E9A7}
AppName=SGH Voice
AppVersion={#AppVersion}
AppPublisher=Shingihou Co., Ltd.
AppPublisherURL=https://voice.shingihou.com
DefaultDirName={autopf}\SGHVoice
DefaultGroupName=SGH Voice
DisableProgramGroupPage=yes
; Per-machine: hospital IT installs once; every Windows account shares the
; read-only program and model. Each user's settings stay in their own profile.
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=SGHVoice-Windows-{#AppVersion}-x64-unsigned
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\SGH Voice.exe
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
; User profile/configuration data is deliberately outside the install directory.
; The ~1.5 GB model is stored uncompressed: FP16 weights barely compress and
; LZMA over them would only slow building and installation. Total stays
; below the 2 GB single-file setup limit, so no disk spanning is needed.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "\models,\models\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\models\*"; DestDir: "{app}\models"; Flags: ignoreversion recursesubdirs createallsubdirs nocompression

[Icons]
Name: "{autoprograms}\SGH Voice"; Filename: "{app}\SGH Voice.exe"
Name: "{autodesktop}\SGH Voice"; Filename: "{app}\SGH Voice.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SGH Voice.exe"; Description: "Open SGH Voice"; Flags: nowait postinstall skipifsilent
