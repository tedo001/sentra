; Inno Setup script for SENTRA (sentra.py) - the Windows setup wizard.
;
; It packages the folder PyInstaller produced; it does not compile Python:
;
;     pyinstaller packaging\sentra.spec --noconfirm --clean     -> dist\SENTRA\
;     iscc packaging\sentra_installer.iss                       -> dist\installer\SENTRA-<ver>-setup.exe
;
; packaging\build_sentra.bat runs both. /DAppVersion=x.y.z overrides the version.
;
; The setup flow: Welcome -> Licence notes -> Install folder -> Start menu ->
; Additional shortcuts -> Ready -> Installing -> What to do next (gemma2) -> Finish,
; with "Start SENTRA" ticked on the last page.

#ifndef AppVersion
  #define AppVersion "2.0.0"
#endif

#define AppName "SENTRA"
#define AppPublisher "Oil India Limited"
#define AppExeName "SENTRA.exe"
#define SourceDir "..\dist\SENTRA"

[Setup]
; A different AppId from the single-window console's, so both can be installed.
AppId={{8E2B6C41-3F7A-4D95-B1C2-7A6E0F4D9C58}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}
VersionInfoDescription=SENTRA - SIF precursor detection, Problem Statement 26165
DefaultDirName={autopf}\SENTRA
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=..\dist\installer
OutputBaseFilename=SENTRA-{#AppVersion}-setup
SetupIconFile=..\ui\assets\sentra.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Per-machine when elevated, per-user otherwise: a plant workstation is often locked down.
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExeName}
CloseApplications=yes
RestartApplications=no
; Before installing: the fonts' licences and the data note. After: gemma2.
InfoBeforeFile=sentra_before_install.txt
InfoAfterFile=sentra_after_install.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "sentra_after_install.txt"; DestDir: "{app}"; DestName: "README-after-install.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\{#AppName} (presentation size)"; Filename: "{app}\{#AppExeName}"; Parameters: "--present"
Name: "{group}\What to do after installing"; Filename: "{app}\README-after-install.txt"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent

; SENTRA keeps its accounts, audit trail, decisions, calendar, SQL database,
; sealed secrets and settings under %APPDATA%\SIF Insight Console - never in
; this folder. Uninstalling leaves them, on purpose: the audit trail and the
; decision trail are records, and a reinstall should find them.
