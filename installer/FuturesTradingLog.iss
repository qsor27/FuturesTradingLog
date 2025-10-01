; Inno Setup Script for Futures Trading Log
; Creates a professional Windows installer with service management
; Requires Inno Setup 6.0 or later: https://jrsoftware.org/isdl.php

#define MyAppName "Futures Trading Log"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Trading Analytics"
#define MyAppURL "https://github.com/yourusername/FuturesTradingLog"
#define MyAppExeName "FuturesTradingLog.exe"
#define MyAppIcon "icon.ico"

[Setup]
; Basic Information
AppId={{FDB6E4F1-8C3D-4E9A-9B2A-5F7E3D6C8A9B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation Directories
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output Configuration
OutputDir=output
OutputBaseFilename=FuturesTradingLog-Setup-{#MyAppVersion}
SetupIconFile=icon.ico
Compression=lzma2/max
SolidCompression=yes

; Windows Version Requirements
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Privileges
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Wizard Configuration
WizardStyle=modern
DisableWelcomePage=no
LicenseFile=..\LICENSE

; Uninstall Configuration
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "full"; Description: "Full installation"
Name: "compact"; Description: "Compact installation (no sample data)"
Name: "custom"; Description: "Custom installation"; Flags: iscustom

[Components]
Name: "core"; Description: "Core Application Files"; Types: full compact custom; Flags: fixed
Name: "services"; Description: "Windows Services (Redis, Web Server, Workers)"; Types: full compact custom; Flags: fixed
Name: "shortcuts"; Description: "Desktop and Start Menu Shortcuts"; Types: full compact

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Components: shortcuts
Name: "startmenuicon"; Description: "Create a Start Menu shortcut"; GroupDescription: "Additional icons:"; Components: shortcuts; Flags: unchecked
Name: "autostart"; Description: "Start services automatically on system boot"; GroupDescription: "Service Configuration:"; Flags: unchecked

[Dirs]
; Application directories
Name: "{app}\logs"; Permissions: users-full
Name: "{app}\redis"; Permissions: users-full

; Data directories in ProgramData
Name: "{commonappdata}\{#MyAppName}"; Permissions: users-full
Name: "{commonappdata}\{#MyAppName}\db"; Permissions: users-full
Name: "{commonappdata}\{#MyAppName}\logs"; Permissions: users-full
Name: "{commonappdata}\{#MyAppName}\config"; Permissions: users-full
Name: "{commonappdata}\{#MyAppName}\charts"; Permissions: users-full
Name: "{commonappdata}\{#MyAppName}\archive"; Permissions: users-full
Name: "{commonappdata}\{#MyAppName}\backups"; Permissions: users-full

[Files]
; Main Application
Source: "dist\FuturesTradingLog\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: core

; Redis
Source: "redis\*"; DestDir: "{app}\redis"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: services

; NSSM (Service Manager)
Source: "nssm\nssm.exe"; DestDir: "{app}\tools"; Flags: ignoreversion; Components: services

; Configuration Templates
Source: "configs\redis.windows.conf"; DestDir: "{app}\redis"; DestName: "redis.conf"; Flags: ignoreversion; Components: services
Source: "configs\.env.template"; DestDir: "{commonappdata}\{#MyAppName}\config"; DestName: ".env"; Flags: onlyifdoesntexist; Components: core

; Documentation
Source: "..\README.md"; DestDir: "{app}\docs"; Flags: ignoreversion isreadme; Components: core
Source: "README.md"; DestDir: "{app}\docs"; DestName: "INSTALLER_README.md"; Flags: ignoreversion; Components: core

; Helper Scripts
Source: "scripts\start_services.bat"; DestDir: "{app}\tools"; Flags: ignoreversion; Components: services
Source: "scripts\stop_services.bat"; DestDir: "{app}\tools"; Flags: ignoreversion; Components: services
Source: "scripts\restart_services.bat"; DestDir: "{app}\tools"; Flags: ignoreversion; Components: services
Source: "scripts\check_services.bat"; DestDir: "{app}\tools"; Flags: ignoreversion; Components: services

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "http://localhost:5000"; Comment: "Open Futures Trading Log"; Tasks: startmenuicon
Name: "{group}\Stop Services"; Filename: "{app}\tools\stop_services.bat"; Comment: "Stop all services"; Tasks: startmenuicon
Name: "{group}\Start Services"; Filename: "{app}\tools\start_services.bat"; Comment: "Start all services"; Tasks: startmenuicon
Name: "{group}\View Logs"; Filename: "{commonappdata}\{#MyAppName}\logs"; Comment: "View application logs"; Tasks: startmenuicon
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"; Tasks: startmenuicon
Name: "{autodesktop}\{#MyAppName}"; Filename: "http://localhost:5000"; Comment: "Open Futures Trading Log"; Tasks: desktopicon

[Run]
; Install Redis as Windows Service
Filename: "{app}\tools\nssm.exe"; Parameters: "install FuturesTradingLog-Redis ""{app}\redis\redis-server.exe"" ""{app}\redis\redis.conf"""; Flags: runhidden; StatusMsg: "Installing Redis service..."; Components: services

; Configure Redis service
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Redis AppDirectory ""{app}\redis"""; Flags: runhidden; Components: services
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Redis DisplayName ""Futures Trading Log - Redis Cache"""; Flags: runhidden; Components: services
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Redis Description ""Redis cache service for Futures Trading Log application"""; Flags: runhidden; Components: services
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Redis Start SERVICE_AUTO_START"; Flags: runhidden; Components: services
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Redis AppStdout ""{commonappdata}\{#MyAppName}\logs\redis_stdout.log"""; Flags: runhidden; Components: services
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Redis AppStderr ""{commonappdata}\{#MyAppName}\logs\redis_stderr.log"""; Flags: runhidden; Components: services

; Install Web Application as Windows Service
Filename: "{app}\tools\nssm.exe"; Parameters: "install FuturesTradingLog-Web ""{app}\{#MyAppExeName}"""; Flags: runhidden; StatusMsg: "Installing Web service..."; Components: services

; Configure Web service
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Web AppDirectory ""{app}"""; Flags: runhidden; Components: services
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Web DisplayName ""Futures Trading Log - Web Server"""; Flags: runhidden; Components: services
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Web Description ""Flask web server for Futures Trading Log application"""; Flags: runhidden; Components: services
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Web Start SERVICE_AUTO_START"; Flags: runhidden; Components: services
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Web DependOnService FuturesTradingLog-Redis"; Flags: runhidden; Components: services
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Web AppEnvironmentExtra DATA_DIR={commonappdata}\{#MyAppName} FLASK_ENV=production REDIS_URL=redis://localhost:6379/0"; Flags: runhidden; Components: services
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Web AppStdout ""{commonappdata}\{#MyAppName}\logs\web_stdout.log"""; Flags: runhidden; Components: services
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Web AppStderr ""{commonappdata}\{#MyAppName}\logs\web_stderr.log"""; Flags: runhidden; Components: services

; Configure service failure recovery
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Redis AppExit Default Restart"; Flags: runhidden; Components: services
Filename: "{app}\tools\nssm.exe"; Parameters: "set FuturesTradingLog-Web AppExit Default Restart"; Flags: runhidden; Components: services

; Start services
Filename: "{app}\tools\nssm.exe"; Parameters: "start FuturesTradingLog-Redis"; Flags: runhidden; StatusMsg: "Starting Redis service..."; Components: services
Filename: "{app}\tools\nssm.exe"; Parameters: "start FuturesTradingLog-Web"; Flags: runhidden; StatusMsg: "Starting Web service..."; Components: services

; Open browser after installation
Filename: "http://localhost:5000"; Description: "Open Futures Trading Log"; Flags: postinstall shellexec skipifsilent

[UninstallRun]
; Stop all services before uninstall
Filename: "{app}\tools\nssm.exe"; Parameters: "stop FuturesTradingLog-Web"; Flags: runhidden; RunOnceId: "StopWebService"
Filename: "{app}\tools\nssm.exe"; Parameters: "stop FuturesTradingLog-Redis"; Flags: runhidden; RunOnceId: "StopRedisService"

; Wait for services to stop
Filename: "cmd.exe"; Parameters: "/c timeout /t 5 /nobreak"; Flags: runhidden; RunOnceId: "WaitForStop"

; Remove services
Filename: "{app}\tools\nssm.exe"; Parameters: "remove FuturesTradingLog-Web confirm"; Flags: runhidden; RunOnceId: "RemoveWebService"
Filename: "{app}\tools\nssm.exe"; Parameters: "remove FuturesTradingLog-Redis confirm"; Flags: runhidden; RunOnceId: "RemoveRedisService"

[UninstallDelete]
; Clean up log files
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\redis\dump.rdb"

; Ask user about data directory
; Note: User data in {commonappdata} is preserved by default

[Code]
var
  DataDirPage: TInputDirWizardPage;
  PreserveDataCheckbox: TNewCheckBox;

procedure InitializeWizard;
begin
  { Create custom page for data directory selection }
  DataDirPage := CreateInputDirPage(wpSelectDir,
    'Select Data Directory', 'Where should application data be stored?',
    'Select the folder where trading data, logs, and configuration will be stored, then click Next.',
    False, '');
  DataDirPage.Add('');
  DataDirPage.Values[0] := ExpandConstant('{commonappdata}\{#MyAppName}');
end;

function GetDataDir(Param: String): String;
begin
  Result := DataDirPage.Values[0];
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if MsgBox('Do you want to remove the application data directory (database, logs, configuration)?' + #13#10 +
              'This will delete all your trading data!' + #13#10#13#10 +
              'Data directory: ' + ExpandConstant('{commonappdata}\{#MyAppName}'),
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      DelTree(ExpandConstant('{commonappdata}\{#MyAppName}'), True, True, True);
      MsgBox('Application data has been removed.', mbInformation, MB_OK);
    end
    else
    begin
      MsgBox('Application data has been preserved at:' + #13#10 +
             ExpandConstant('{commonappdata}\{#MyAppName}'),
             mbInformation, MB_OK);
    end;
  end;
end;

function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  { Check if services are already installed and offer to stop them }
  if Exec(ExpandConstant('{sys}\sc.exe'), 'query FuturesTradingLog-Web', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      if MsgBox('Futures Trading Log services are currently running. Do you want to stop them before installation?',
                mbConfirmation, MB_YESNO) = IDYES then
      begin
        Exec(ExpandConstant('{sys}\sc.exe'), 'stop FuturesTradingLog-Web', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
        Exec(ExpandConstant('{sys}\sc.exe'), 'stop FuturesTradingLog-Redis', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
        Sleep(3000);
      end;
    end;
  end;
  Result := True;
end;

[Messages]
SetupAppTitle=Setup - {#MyAppName}
SetupWindowTitle=Setup - {#MyAppName} {#MyAppVersion}
WelcomeLabel1=Welcome to {#MyAppName} Setup
WelcomeLabel2=This will install [name/ver] on your computer.%n%nThis application provides automated futures trading performance analysis with NinjaTrader integration.%n%nIt is recommended that you close all other applications before continuing.
