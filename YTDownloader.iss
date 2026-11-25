#define MyAppName "YT Downloader Pro"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.8"
#endif
#define MyAppPublisher "Jackson Quequi"
#define MyAppExeName "YT Downloader Pro.exe"

[Setup]
AppId={{A4D6D7A5-9C0F-4A8E-B4D2-1E2F12345678}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

AppPublisherURL=https://github.com/
AppSupportURL=https://github.com/
AppUpdatesURL=https://github.com/

DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}

OutputDir=Output
OutputBaseFilename=YTDownloaderPro_Setup

Compression=lzma2
SolidCompression=yes

WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

SetupIconFile=icone.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

DisableProgramGroupPage=yes

[Languages]
Name: "portuguesebrazil"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]

Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

Source: "ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "ffprobe.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "deno.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]

Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]

Filename: "{app}\{#MyAppExeName}"; Description: "Executar {#MyAppName}"; Flags: nowait postinstall

[Code]
// Fecha o programa (e o processo pai do onefile) antes de copiar os arquivos,
// para o instalador nao falhar com "DeleteFile falhou; codigo 5".
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM "{#MyAppExeName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(1500);
  Result := '';
end;
