; Companion setup: the SOAP language model and llama.cpp CPU runtime for SGH Voice.
; Built by windows/build.ps1 and normally run silently by the main setup with
; /DIR="{app}\llm". It registers no separate uninstaller: the main uninstaller
; removes {app}\llm.
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
AppId={{2D1D5B7C-6A3E-4C55-9C61-0B7F3E8D9A41}
AppName=SGH Voice SOAP model
AppVersion={#AppVersion}
AppPublisher=Shingihou Co., Ltd.
DefaultDirName={autopf}\SGHVoice\llm
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=SGHVoice-Windows-{#AppVersion}-x64-unsigned-soap-model
; GGUF weights are already quantized; compression would only slow setup.
Compression=none
Uninstallable=no
CreateUninstallRegKey=no
UpdateUninstallLogAppName=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
