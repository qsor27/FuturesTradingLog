; Inno Setup Script for Futures Trading Log
; Creates a professional Windows installer with service integration

#define MyAppName "Futures Trading Log"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Futures Trading Log"
#define MyAppURL "https://github.com/yourusername/FuturesTradingLog"
#define MyAppExeName "FuturesTradingLog.exe"

[Setup]
; Basic application information
AppId={{A5B8C3D4-E6F7-4A8B-9C0D-1E2F3A4B5C6D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=LICENSE
OutputDir=Output
OutputBaseFilename=FuturesTradingLog-Setup-v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Main application executables
Source: "dist\FuturesTradingLog\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\FuturesTradingLog-Worker\*"; DestDir: "{app}\worker"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\FuturesTradingLog-FileWatcher\*"; DestDir: "{app}\filewatcher"; Flags: ignoreversion recursesubdirs createallsubdirs

; Redis binaries and config
Source: "vendor\redis\*"; DestDir: "{app}\redis"; Flags: ignoreversion recursesubdirs createallsubdirs

; NSSM for service management
Source: "vendor\nssm\win64\nssm.exe"; DestDir: "{app}\bin"; Flags: ignoreversion

; Helper scripts
Source: "dist\bin\*.bat"; DestDir: "{app}\bin"; Flags: ignoreversion

; Configuration templates
Source: ".env.example"; DestDir: "{commonappdata}\{#MyAppName}\config"; Flags: onlyifdoesntexist uninsneveruninstall

[Dirs]
; Create data directories in ProgramData with user-modify permissions
Name: "{commonappdata}\{#MyAppName}"; Permissions: users-modify
Name: "{commonappdata}\{#MyAppName}\db"; Permissions: users-modify
Name: "{commonappdata}\{#MyAppName}\logs"; Permissions: users-modify
Name: "{commonappdata}\{#MyAppName}\charts"; Permissions: users-modify
Name: "{commonappdata}\{#MyAppName}\archive"; Permissions: users-modify
Name: "{commonappdata}\{#MyAppName}\config"; Permissions: users-modify
Name: "{commonappdata}\{#MyAppName}\redis"; Permissions: users-modify

[Icons]
; Start menu shortcuts
Name: "{group}\{#MyAppName}"; Filename: "http://localhost:5555"; Comment: "Open Futures Trading Log"
Name: "{group}\Start Services"; Filename: "{app}\bin\start-services.bat"; Comment: "Start all services"
Name: "{group}\Stop Services"; Filename: "{app}\bin\stop-services.bat"; Comment: "Stop all services"
Name: "{group}\View Logs"; Filename: "{commonappdata}\{#MyAppName}\logs"; Comment: "Open logs folder"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Optional desktop shortcut
Name: "{autodesktop}\{#MyAppName}"; Filename: "http://localhost:5555"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Run]
; Install Redis service
Filename: "{app}\bin\nssm.exe"; Parameters: "install FuturesTradingLog-Redis ""{app}\redis\redis-server.exe"" ""{app}\redis\redis.conf"""; StatusMsg: "Installing Redis service..."; Flags: runhidden

; Install Web service
Filename: "{app}\bin\nssm.exe"; Parameters: "install FuturesTradingLog-Web ""{app}\{#MyAppExeName}"""; StatusMsg: "Installing Web service..."; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set FuturesTradingLog-Web AppDirectory ""{app}"""; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set FuturesTradingLog-Web DependOnService FuturesTradingLog-Redis"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set FuturesTradingLog-Web AppEnvironmentExtra DATA_DIR=""{commonappdata}\{#MyAppName}"" FLASK_ENV=production PORT=5555"; Flags: runhidden

; Install Celery worker service
Filename: "{app}\bin\nssm.exe"; Parameters: "install FuturesTradingLog-Worker ""{app}\worker\FuturesTradingLog-Worker.exe"""; StatusMsg: "Installing Worker service..."; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set FuturesTradingLog-Worker AppDirectory ""{app}\worker"""; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set FuturesTradingLog-Worker DependOnService FuturesTradingLog-Redis"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set FuturesTradingLog-Worker AppEnvironmentExtra DATA_DIR=""{commonappdata}\{#MyAppName}"" FLASK_ENV=production"; Flags: runhidden

; Install File Watcher service
Filename: "{app}\bin\nssm.exe"; Parameters: "install FuturesTradingLog-FileWatcher ""{app}\filewatcher\FuturesTradingLog-FileWatcher.exe"""; StatusMsg: "Installing File Watcher service..."; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set FuturesTradingLog-FileWatcher AppDirectory ""{app}\filewatcher"""; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set FuturesTradingLog-FileWatcher DependOnService FuturesTradingLog-Redis"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set FuturesTradingLog-FileWatcher AppEnvironmentExtra DATA_DIR=""{commonappdata}\{#MyAppName}"" FLASK_ENV=production"; Flags: runhidden

; Start all services
Filename: "{app}\bin\nssm.exe"; Parameters: "start FuturesTradingLog-Redis"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "start FuturesTradingLog-Web"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "start FuturesTradingLog-Worker"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "start FuturesTradingLog-FileWatcher"; Flags: runhidden

; Open browser after installation
Filename: "http://localhost:5555"; Description: "Open Futures Trading Log"; Flags: postinstall shellexec skipifsilent nowait

[UninstallRun]
; Stop all services in reverse order
Filename: "{app}\bin\nssm.exe"; Parameters: "stop FuturesTradingLog-FileWatcher"; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c timeout /t 2 /nobreak"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "stop FuturesTradingLog-Worker"; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c timeout /t 2 /nobreak"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "stop FuturesTradingLog-Web"; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c timeout /t 2 /nobreak"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "stop FuturesTradingLog-Redis"; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c timeout /t 5 /nobreak"; Flags: runhidden

; Remove all services
Filename: "{app}\bin\nssm.exe"; Parameters: "remove FuturesTradingLog-FileWatcher confirm"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "remove FuturesTradingLog-Worker confirm"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "remove FuturesTradingLog-Web confirm"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "remove FuturesTradingLog-Redis confirm"; Flags: runhidden

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataPath: string;
  ResultCode: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataPath := ExpandConstant('{commonappdata}\{#MyAppName}');

    if DirExists(DataPath) then
    begin
      if MsgBox('Do you want to delete all data files (database, logs, charts)?' + #13#10 +
                'If you plan to reinstall, select No to preserve your data.',
                mbConfirmation, MB_YESNO) = IDYES then
      begin
        DelTree(DataPath, True, True, True);
      end;
    end;
  end;
end;
