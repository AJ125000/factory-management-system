; Inno Setup script for the FMS Windows installer (built by CI; see .github/workflows/ci.yml).
;
;   iscc /DAppVersion=0.8.0 packaging\windows\fms.iss
;
; Installs for the current user only (no admin rights needed). The data lives separately
; in %LOCALAPPDATA%\FMS, so installing a new version or uninstalling never touches it.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{8F3C2B71-6A4E-4F3B-9C1D-5E2A7B9D4F10}
AppName=Factory Management System
AppVerName=Factory Management System {#AppVersion}
AppVersion={#AppVersion}
AppPublisher=FMS
DefaultDirName={localappdata}\Programs\FMS
DefaultGroupName=FMS
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist-installer
OutputBaseFilename=FMS-Setup-{#AppVersion}
SetupIconFile=..\..\..\assets\output_icon.ico
UninstallDisplayIcon={app}\FMS.exe
UninstallDisplayName=Factory Management System
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; FMS.exe holds this mutex while running: the installer asks to close it first.
AppMutex=FMSHubMutex
CloseApplications=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startup"; Description: "Start FMS automatically when Windows starts (recommended)"; GroupDescription: "Options:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Options:"

[Files]
Source: "..\..\dist\FMS\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\FMS"; Filename: "{app}\FMS.exe"
Name: "{group}\Reset FMS password"; Filename: "{app}\fms-admin.exe"; Parameters: "reset-password"
Name: "{group}\FMS data folder"; Filename: "{localappdata}\FMS"
Name: "{userdesktop}\FMS"; Filename: "{app}\FMS.exe"; Tasks: desktopicon
; At login FMS starts quietly in the tray (no window); the owner opens it from there.
Name: "{userstartup}\FMS"; Filename: "{app}\FMS.exe"; Parameters: "--no-window"; Tasks: startup

[Run]
Filename: "{app}\FMS.exe"; Description: "Open FMS now"; Flags: nowait postinstall skipifsilent

[Messages]
FinishedLabel=FMS is installed. It runs in the system tray (bottom-right, next to the clock).%n%nYour data is kept in the AppData\Local\FMS folder and is never removed by installing or uninstalling.
