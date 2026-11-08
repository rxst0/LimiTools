; Inno Setup script: builds dist\LimiToolsSetup.exe
; Per-user install (no admin prompt) to %LOCALAPPDATA%\Programs\LimiTools (updates keep the folder the
; app is already in, e.g. ...\Programs\Rolimons Ad Poster from before the rename: same AppId),
; with a Start Menu entry (so Windows Search finds it), optional desktop icon and an uninstaller.

#define AppName "LimiTools"
#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif

[Setup]
AppId={{7C1E5B2A-4F3D-4C8E-9A61-2B7D0E5F3A91}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=rxst0
AppPublisherURL=https://github.com/rxst0/limitools
AppSupportURL=https://github.com/rxst0/limitools/issues
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=LimiToolsSetup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\LimiTools.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "dist\LimiTools.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\LimiTools.exe"; Comment: "Roblox limiteds toolkit: Rolimons ads, trades, values"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\LimiTools.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LimiTools.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Registry]
; Remove the app's "Start with Windows" entry (created from Settings) on uninstall.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "LimiTools"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "RolimonsAdPoster"; Flags: uninsdeletevalue

[InstallDelete]
; Renamed from Rolimons Ad Poster: remove the old program file and shortcuts.
Type: files; Name: "{app}\RoliAdPoster.exe"
Type: files; Name: "{autoprograms}\Rolimons Ad Poster.lnk"
Type: files; Name: "{autodesktop}\Rolimons Ad Poster.lnk"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\cache"
; The view-only Roblox trades window's browser profile (its Roblox sign-in).
Type: filesandordirs; Name: "{app}\roblox-session"
; The bundled RoValra extension, copied next to the app.
Type: filesandordirs; Name: "{app}\extensions"
; Files the app creates at runtime (including the saved cookie).
Type: files; Name: "{app}\.env"
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\config.json.tmp"
Type: files; Name: "{app}\state.json"
Type: filesandordirs; Name: "{app}\logs"
