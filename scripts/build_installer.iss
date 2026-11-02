; Inno Setup 7 supports deep dependency paths without user registry changes.
#if VER < EncodeVer(7, 0, 0)
  #error Inno Setup 7 or newer is required for long-path installation support.
#endif
#ifndef AppVersion
  #define AppVersion "0.2.3"
#endif
#ifndef DistDir
  #define DistDir "..\dist\NaNoBO"
#endif

[Setup]
SetupArchitecture=x64
AppId={{B04C2468-D93F-4641-8D6F-CB7A78600EB1}
AppName=NaNoBO
AppVersion={#AppVersion}
AppPublisher=NaNoBO contributors
AppPublisherURL=https://github.com/wei-rui499/NaNoBO
AppSupportURL=https://github.com/wei-rui499/NaNoBO/issues
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
Name: "chinesesimp"; MessagesFile: "localizations\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\NaNoBO"; Filename: "{app}\NaNoBO.exe"; WorkingDir: "{localappdata}"
Name: "{group}\NaNoBO Tutorials"; Filename: "{app}\_internal\docs\html\index.html"
Name: "{autodesktop}\NaNoBO"; Filename: "{app}\NaNoBO.exe"; WorkingDir: "{localappdata}"; Tasks: desktopicon
Name: "{group}\Uninstall NaNoBO"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\NaNoBO.exe"; Description: "{cm:LaunchProgram,NaNoBO}"; Flags: nowait postinstall skipifsilent

; Project files are user-owned. The uninstaller removes only the installed app.
