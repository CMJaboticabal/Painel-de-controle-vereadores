; Script gerado para Inno Setup
; Instala o Painel de Controle e o Driver USB CH340

#define MyAppName "Painel de Controle Tribuna"
#define MyAppVersion "1.6.0"
#define MyAppPublisher "Camara Municipal"
#define MyAppExeName "PainelControle.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application. Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{A8F9D831-2856-4D2B-9874-1234567890AB}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
; Uncomment the following line to run in non administrative install mode (install for current user only.)
;PrivilegesRequired=lowest
OutputBaseFilename=Instalador_PainelTribuna_v1.6.0
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=fotos\icon.ico

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Iniciar automaticamente com o Windows"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; O driver USB deve ser copiado explicitamente para garantir que esteja disponivel
Source: "CH34x_Install_Windows_v3_4.EXE"; DestDir: "{app}"; Flags: ignoreversion

; Copiar o icone para a raiz para facilitar o acesso dos atalhos
Source: "fotos\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

; O executavel principal e todos os arquivos gerados pelo PyInstaller
Source: "dist\PainelControle\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\icon.ico"
Name: "{autostartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon; IconFilename: "{app}\icon.ico"

[Run]
; Executa o instalador do driver SILENCIOSAMENTE ou INTERATIVAMENTE
Filename: "{app}\CH34x_Install_Windows_v3_4.EXE"; Description: "Instalar Driver USB (Necessario para Arduino)"; Flags: postinstall waituntilterminated runascurrentuser

; Opção para iniciar o sistema logo após instalar
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
