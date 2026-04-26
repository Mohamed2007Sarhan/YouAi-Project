#define MyAppName "YouAI"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Mohamed Sarhan"
#define MyAppExeName "YouAI.exe"

[Setup]
AppId={{3A9D98D8-5E26-48BC-8D67-96D77BF7A1A2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={commonappdata}\YouAI
DefaultGroupName=YouAI
DisableProgramGroupPage=yes
DisableDirPage=no
OutputDir=..\package
OutputBaseFilename=YouAI_v1_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Dirs]
Name: "{app}\logs"
Name: "{app}\Backend\data"
Name: "{app}\Backend\memory"

[Files]
Source: "dist\YouAI\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\YouAI"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\YouAI"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch YouAI now"; Flags: nowait postinstall skipifsilent
