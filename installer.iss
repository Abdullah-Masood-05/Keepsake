; =====================================================================
;  Inno Setup Script - Satchel
;  Packages the Nuitka single-file exe + ffmpeg into a Windows installer.
;  Build with: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; =====================================================================

#define MyAppName "Satchel"
#define MyAppVersion "2.1.1"
#define MyAppPublisher "Abdullah Masood"
#define MyAppURL "https://github.com/Abdullah-Masood-05/Satchel"
#define MyAppExeName "Satchel.exe"
#define MySourceDir "build_dist"
#define MyFFmpegDir "ffmpeg"

[Setup]
; AppId uniquely identifies this application; do not change between versions.
AppId={{A351DA37-959C-4480-A2E1-3B2E74FA8BDD}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
VersionInfoVersion=2.1.1.0
VersionInfoProductName={#MyAppName}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; The Start menu folder was renamed with the app; do not reuse the old one.
UsePreviousGroup=no
; Admin install to Program Files by default; the user may choose a
; per-user install instead.
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=installer_output
OutputBaseFilename=Satchel-Setup-{#MyAppVersion}
SetupIconFile=resources\icons\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MySourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; ffmpeg must sit next to the exe; the app looks there first.
Source: "{#MyFFmpegDir}\ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#MyFFmpegDir}\ffprobe.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[InstallDelete]
; Leftovers from earlier names ("YouTube Video Downloader", then "Fetchly").
; Same AppId, so upgrades land in the old install folder.
Type: files; Name: "{app}\Fetchly.exe"
Type: filesandordirs; Name: "{autoprograms}\Fetchly"
Type: files; Name: "{autodesktop}\Fetchly.lnk"
Type: files; Name: "{app}\YouTubeVideoDownloader.exe"
Type: filesandordirs; Name: "{autoprograms}\YouTube Video Downloader"
Type: files; Name: "{autoprograms}\YouTube Video Downloader.lnk"
Type: files; Name: "{autodesktop}\YouTube Video Downloader.lnk"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
