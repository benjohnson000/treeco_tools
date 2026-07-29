; Spruce Reorder Tool installer

#define MyAppName "Spruce Reorder Tool"
#define MyAppVersion "0.1.2"
#define MyAppPublisher "Treeco"
#define MyAppURL "https://github.com/benjohnson000/treeco_tools"
#define MyAppExeName "Spruce Reorder Tool.exe"

[Setup]
AppId={{2E84F09F-67F6-4807-A5E1-DA6DB769B6CF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

DefaultDirName={localappdata}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=C:\Users\ConorKarperien\Documents\GitHub\treeco-stuff\inventory projection testing\icon.ico

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

DisableProgramGroupPage=yes
OutputDir=C:\Users\ConorKarperien\Documents\GitHub\treeco-stuff\inventory projection testing\installer
OutputBaseFilename=SpruceReorderToolSetup
SolidCompression=yes
WizardStyle=modern dynamic

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "C:\Users\ConorKarperien\Documents\GitHub\treeco-stuff\inventory projection testing\dist\Spruce Reorder Tool.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\ConorKarperien\Documents\GitHub\treeco-stuff\inventory projection testing\dist\data\settings.json"; DestDir: "{app}\data"; Flags: onlyifdoesntexist
Source: "C:\Users\ConorKarperien\Documents\GitHub\treeco-stuff\inventory projection testing\dist\data\branches.json"; DestDir: "{app}\data"; Flags: ignoreversion
Source: "C:\Users\ConorKarperien\Documents\GitHub\treeco-stuff\inventory projection testing\dist\data\flooring_vendors.csv"; DestDir: "{app}\data"; Flags: ignoreversion
Source: "C:\Users\ConorKarperien\Documents\GitHub\treeco-stuff\inventory projection testing\dist\data\vendors.csv"; DestDir: "{app}\data"; Flags: ignoreversion
Source: "C:\Users\ConorKarperien\Documents\GitHub\treeco-stuff\inventory projection testing\dist\data\treeco-horizontal-logo-white.png"; DestDir: "{app}\data"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
