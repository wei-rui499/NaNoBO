; Build on native Windows with Inno Setup 6. No WSL or user Python is required.
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef DistDir
  #define DistDir "..\dist\NaNoBO"
#endif

[Setup]
AppId={{B04C2468-D93F-4641-8D6F-CB7A78600EB1}
AppName=NaNoBO
AppVersion={#AppVersion}
AppPublisher=NaNoBO contributors
AppComments=Independent desktop interface for local chemical experiment planning
DefaultDirName={localappdata}\Programs\NaNoBO
DefaultGroupName=NaNoBO
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\installers
OutputBaseFilename=NaNoBO-{#AppVersion}-windows-x64-setup-unsigned
Compression=lzma2/fast
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern
UninstallDisplayIcon={app}\NaNoBO.exe
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\NaNoBO"; Filename: "{app}\NaNoBO.exe"; WorkingDir: "{localappdata}"
Name: "{autodesktop}\NaNoBO"; Filename: "{app}\NaNoBO.exe"; WorkingDir: "{localappdata}"; Tasks: desktopicon
Name: "{group}\Uninstall NaNoBO"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\NaNoBO.exe"; Description: "Launch NaNoBO"; Flags: nowait postinstall skipifsilent

; Project files are user-owned. The uninstaller removes only the installed app.
