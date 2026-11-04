#define AppVersion "1.0.0"
[Setup]
AppId={{F685C7B3-F98D-4235-B381-C0AF0E1A67BA}
AppName=QR Live Scanner
AppVersion={#AppVersion}
AppPublisher=QR Live Scanner
AppPublisherURL=https://github.com/huybitvvt/qr-live-scanner
DefaultDirName={localappdata}\Programs\QRLiveScanner
DefaultGroupName=QR Live Scanner
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\dist\installer
OutputBaseFilename=QRLiveScanner-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\QRLiveScanner.exe
LicenseFile=..\LICENSE
CloseApplications=yes
RestartApplications=no
WizardStyle=modern

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: startup; Description: "Start scanner when signing in to Windows"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "..\dist\QRLiveScanner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\HUONG-DAN.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\QR Live Scanner"; Filename: "{app}\QRLiveScanner.exe"
Name: "{autodesktop}\QR Live Scanner"; Filename: "{app}\QRLiveScanner.exe"; Tasks: desktopicon
Name: "{userstartup}\QR Live Scanner"; Filename: "{app}\QRLiveScanner.exe"; Tasks: startup

[Run]
Filename: "{app}\QRLiveScanner.exe"; Description: "Open QR Live Scanner"; Flags: nowait postinstall skipifsilent
