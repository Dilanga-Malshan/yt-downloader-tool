[Setup]
AppId={{68D846C2-27E6-41BD-8128-EF323434BD39}
AppName=YT Downloader Pro
AppVersion=1.2.1
AppPublisher=Dilanga Malshan
DefaultDirName={localappdata}\Programs\YT Downloader Pro
DefaultGroupName=YT Downloader Pro
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\installer
OutputBaseFilename=YT-Downloader-Pro-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\product-icon.ico
UninstallDisplayIcon={app}\YT-Downloader-Pro.exe

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\YT-Downloader-Pro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\YT Downloader Pro"; Filename: "{app}\YT-Downloader-Pro.exe"
Name: "{autodesktop}\YT Downloader Pro"; Filename: "{app}\YT-Downloader-Pro.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\YT-Downloader-Pro.exe"; Description: "Launch YT Downloader Pro"; Flags: nowait postinstall skipifsilent
