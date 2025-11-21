# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-09-30-windows-native-installer/spec.md

> Created: 2025-09-30
> Version: 1.0.0

## Technical Requirements

### 1. PyInstaller Configuration

**Main Application Executable** (`FuturesTradingLog.exe`):
```python
# build_installer.py - PyInstaller configuration
spec_file_config = {
    'name': 'FuturesTradingLog',
    'entry_point': 'app.py',
    'hidden_imports': [
        'flask',
        'sqlalchemy',
        'celery',
        'redis',
        'cryptography',
        'jinja2',
        'werkzeug',
        'click',
        'itsdangerous',
        'models',
        'services',
        'routes',
        'repositories',
        'config',
        'middleware',
        'domain'
    ],
    'datas': [
        ('templates', 'templates'),
        ('static', 'static'),
        ('.env.example', '.'),
    ],
    'binaries': [],
    'excludes': ['tkinter', 'matplotlib'],
    'one_file': False,  # Use one-dir for better performance
    'console': False,   # Hide console window for GUI mode
    'icon': 'static/images/icon.ico'
}
```

**Celery Worker Executable** (`FuturesTradingLog-Worker.exe`):
```python
worker_spec_config = {
    'name': 'FuturesTradingLog-Worker',
    'entry_point': 'celery_app.py',
    'console': True,  # Keep console for worker logs
    'hidden_imports': ['celery', 'redis', 'services', 'tasks'],
}
```

**File Watcher Executable** (`FuturesTradingLog-FileWatcher.exe`):
```python
watcher_spec_config = {
    'name': 'FuturesTradingLog-FileWatcher',
    'entry_point': 'scripts/file_watcher.py',
    'console': True,
    'hidden_imports': ['watchdog', 'services'],
}
```

**Build Optimization**:
- Use `--onedir` mode for faster startup and easier debugging
- Expected bundle size: 150-200MB for main app with all dependencies
- Strip debug symbols in production builds
- Use UPX compression for smaller executable sizes (optional)

### 2. Inno Setup Script Structure

**Main Installer Script** (`installer.iss`):

```iss
#define AppName "Futures Trading Log"
#define AppVersion "1.0.0"
#define AppPublisher "Your Organization"
#define AppURL "https://github.com/yourusername/FuturesTradingLog"
#define AppExeName "FuturesTradingLog.exe"
#define ServiceBaseName "FuturesTradingLog"

[Setup]
AppId={{YOUR-GUID-HERE}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
LicenseFile=LICENSE.txt
OutputDir=dist\installer
OutputBaseFilename=FuturesTradingLog-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile=static\images\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startmenuicon"; Description: "Create Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startservices"; Description: "Start services after installation"; GroupDescription: "Service Configuration:"; Flags: checked

[Files]
; Main Application
Source: "dist\FuturesTradingLog\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\FuturesTradingLog-Worker\*"; DestDir: "{app}\worker"; Flags: ignoreversion recursesubdirs
Source: "dist\FuturesTradingLog-FileWatcher\*"; DestDir: "{app}\watcher"; Flags: ignoreversion recursesubdirs

; Redis Portable
Source: "vendor\redis\*"; DestDir: "{app}\redis"; Flags: ignoreversion recursesubdirs

; NSSM (Service Manager)
Source: "vendor\nssm\win64\nssm.exe"; DestDir: "{app}\bin"; Flags: ignoreversion

; Configuration Templates
Source: ".env.example"; DestDir: "{commonappdata}\{#AppName}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "config\*.example"; DestDir: "{commonappdata}\{#AppName}\config"; Flags: onlyifdoesntexist uninsneveruninstall

[Dirs]
Name: "{commonappdata}\{#AppName}"; Permissions: users-modify
Name: "{commonappdata}\{#AppName}\data"; Permissions: users-modify
Name: "{commonappdata}\{#AppName}\data\db"; Permissions: users-modify
Name: "{commonappdata}\{#AppName}\data\logs"; Permissions: users-modify
Name: "{commonappdata}\{#AppName}\data\charts"; Permissions: users-modify
Name: "{commonappdata}\{#AppName}\data\archive"; Permissions: users-modify
Name: "{commonappdata}\{#AppName}\config"; Permissions: users-modify

[Icons]
Name: "{group}\{#AppName}"; Filename: "http://localhost:5555"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\Stop Services"; Filename: "{app}\bin\stop-services.bat"
Name: "{group}\Start Services"; Filename: "{app}\bin\start-services.bat"
Name: "{group}\View Logs"; Filename: "{commonappdata}\{#AppName}\data\logs"
Name: "{autodesktop}\{#AppName}"; Filename: "http://localhost:5555"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Install Windows Services
Filename: "{app}\bin\nssm.exe"; Parameters: "install {#ServiceBaseName}-Redis ""{app}\redis\redis-server.exe"" ""{app}\redis\redis.conf"""; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "install {#ServiceBaseName}-Web ""{app}\{#AppExeName}"""; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "install {#ServiceBaseName}-Worker ""{app}\worker\FuturesTradingLog-Worker.exe"""; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "install {#ServiceBaseName}-FileWatcher ""{app}\watcher\FuturesTradingLog-FileWatcher.exe"""; Flags: runhidden

; Configure service parameters
Filename: "{app}\bin\nssm.exe"; Parameters: "set {#ServiceBaseName}-Web AppDirectory ""{app}"""; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set {#ServiceBaseName}-Web AppEnvironmentExtra ""DATA_DIR={commonappdata}\{#AppName}\data"""; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set {#ServiceBaseName}-Web Start SERVICE_AUTO_START"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set {#ServiceBaseName}-Web DependOnService {#ServiceBaseName}-Redis"; Flags: runhidden

Filename: "{app}\bin\nssm.exe"; Parameters: "set {#ServiceBaseName}-Worker AppDirectory ""{app}\worker"""; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set {#ServiceBaseName}-Worker AppEnvironmentExtra ""DATA_DIR={commonappdata}\{#AppName}\data"""; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set {#ServiceBaseName}-Worker DependOnService {#ServiceBaseName}-Redis"; Flags: runhidden

Filename: "{app}\bin\nssm.exe"; Parameters: "set {#ServiceBaseName}-FileWatcher AppDirectory ""{app}\watcher"""; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set {#ServiceBaseName}-FileWatcher AppEnvironmentExtra ""DATA_DIR={commonappdata}\{#AppName}\data"""; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "set {#ServiceBaseName}-FileWatcher DependOnService {#ServiceBaseName}-Web"; Flags: runhidden

; Start services if selected
Filename: "{app}\bin\nssm.exe"; Parameters: "start {#ServiceBaseName}-Redis"; Flags: runhidden; Tasks: startservices
Filename: "{app}\bin\nssm.exe"; Parameters: "start {#ServiceBaseName}-Web"; Flags: runhidden; Tasks: startservices
Filename: "{app}\bin\nssm.exe"; Parameters: "start {#ServiceBaseName}-Worker"; Flags: runhidden; Tasks: startservices
Filename: "{app}\bin\nssm.exe"; Parameters: "start {#ServiceBaseName}-FileWatcher"; Flags: runhidden; Tasks: startservices

; Open browser after installation
Filename: "http://localhost:5555"; Flags: shellexec postinstall skipifsilent; Description: "Open Futures Trading Log in browser"

[UninstallRun]
; Stop and remove services
Filename: "{app}\bin\nssm.exe"; Parameters: "stop {#ServiceBaseName}-FileWatcher"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "stop {#ServiceBaseName}-Worker"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "stop {#ServiceBaseName}-Web"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "stop {#ServiceBaseName}-Redis"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "remove {#ServiceBaseName}-FileWatcher confirm"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "remove {#ServiceBaseName}-Worker confirm"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "remove {#ServiceBaseName}-Web confirm"; Flags: runhidden
Filename: "{app}\bin\nssm.exe"; Parameters: "remove {#ServiceBaseName}-Redis confirm"; Flags: runhidden

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    DataDir := ExpandConstant('{commonappdata}\{#AppName}');
    if DirExists(DataDir) then
    begin
      if MsgBox('Do you want to remove all application data including your trading database and logs?' + #13#10#13#10 +
                'Select No to preserve your data for future reinstallation.',
                mbConfirmation, MB_YESNO) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
```

### 3. Redis for Windows Bundling

**Redis Portable Setup**:
- Source: Redis for Windows (Microsoft fork or Memurai)
- Version: Redis 5.0.14 or compatible
- Location: `vendor/redis/` directory
- Size: Approximately 5-10MB

**Redis Configuration** (`redis.conf`):
```conf
# Redis configuration for Futures Trading Log
port 6379
bind 127.0.0.1
protected-mode yes
timeout 300
tcp-keepalive 300

# Persistence
save 900 1
save 300 10
save 60 10000
dir {COMMONAPPDATA}/FuturesTradingLog/data/redis

# Logging
loglevel notice
logfile {COMMONAPPDATA}/FuturesTradingLog/data/logs/redis.log

# Memory
maxmemory 256mb
maxmemory-policy allkeys-lru
```

**Dynamic Configuration**:
- Installer script replaces `{COMMONAPPDATA}` with actual path during installation
- Pre-configured for localhost-only access for security

### 4. NSSM Integration for Service Management

**NSSM (Non-Sucking Service Manager)**:
- Version: 2.24 or later
- Architecture: x64
- Location: `vendor/nssm/win64/nssm.exe`
- Size: ~350KB

**Service Configuration Strategy**:

**Service 1: FuturesTradingLog-Redis**
```batch
nssm install FuturesTradingLog-Redis "C:\Program Files\Futures Trading Log\redis\redis-server.exe" "C:\Program Files\Futures Trading Log\redis\redis.conf"
nssm set FuturesTradingLog-Redis DisplayName "Futures Trading Log - Redis Cache"
nssm set FuturesTradingLog-Redis Description "Redis cache server for Futures Trading Log application"
nssm set FuturesTradingLog-Redis Start SERVICE_AUTO_START
nssm set FuturesTradingLog-Redis AppStdout "C:\ProgramData\Futures Trading Log\data\logs\redis-stdout.log"
nssm set FuturesTradingLog-Redis AppStderr "C:\ProgramData\Futures Trading Log\data\logs\redis-stderr.log"
nssm set FuturesTradingLog-Redis AppRotateFiles 1
nssm set FuturesTradingLog-Redis AppRotateSeconds 86400
```

**Service 2: FuturesTradingLog-Web**
```batch
nssm install FuturesTradingLog-Web "C:\Program Files\Futures Trading Log\FuturesTradingLog.exe"
nssm set FuturesTradingLog-Web DisplayName "Futures Trading Log - Web Application"
nssm set FuturesTradingLog-Web Description "Flask web application for Futures Trading Log"
nssm set FuturesTradingLog-Web Start SERVICE_AUTO_START
nssm set FuturesTradingLog-Web DependOnService FuturesTradingLog-Redis
nssm set FuturesTradingLog-Web AppDirectory "C:\Program Files\Futures Trading Log"
nssm set FuturesTradingLog-Web AppEnvironmentExtra "DATA_DIR=C:\ProgramData\Futures Trading Log\data" "FLASK_ENV=production" "PORT=5555"
nssm set FuturesTradingLog-Web AppStdout "C:\ProgramData\Futures Trading Log\data\logs\web-stdout.log"
nssm set FuturesTradingLog-Web AppStderr "C:\ProgramData\Futures Trading Log\data\logs\web-stderr.log"
nssm set FuturesTradingLog-Web AppRotateFiles 1
nssm set FuturesTradingLog-Web AppRotateSeconds 86400
```

**Service 3: FuturesTradingLog-Worker**
```batch
nssm install FuturesTradingLog-Worker "C:\Program Files\Futures Trading Log\worker\FuturesTradingLog-Worker.exe"
nssm set FuturesTradingLog-Worker DisplayName "Futures Trading Log - Background Worker"
nssm set FuturesTradingLog-Worker Description "Celery background worker for async task processing"
nssm set FuturesTradingLog-Worker Start SERVICE_AUTO_START
nssm set FuturesTradingLog-Worker DependOnService FuturesTradingLog-Redis
nssm set FuturesTradingLog-Worker AppDirectory "C:\Program Files\Futures Trading Log\worker"
nssm set FuturesTradingLog-Worker AppEnvironmentExtra "DATA_DIR=C:\ProgramData\Futures Trading Log\data"
nssm set FuturesTradingLog-Worker AppStdout "C:\ProgramData\Futures Trading Log\data\logs\worker-stdout.log"
nssm set FuturesTradingLog-Worker AppStderr "C:\ProgramData\Futures Trading Log\data\logs\worker-stderr.log"
nssm set FuturesTradingLog-Worker AppRotateFiles 1
```

**Service 4: FuturesTradingLog-FileWatcher**
```batch
nssm install FuturesTradingLog-FileWatcher "C:\Program Files\Futures Trading Log\watcher\FuturesTradingLog-FileWatcher.exe"
nssm set FuturesTradingLog-FileWatcher DisplayName "Futures Trading Log - File Watcher"
nssm set FuturesTradingLog-FileWatcher Description "Monitors NinjaTrader CSV files for automatic import"
nssm set FuturesTradingLog-FileWatcher Start SERVICE_AUTO_START
nssm set FuturesTradingLog-FileWatcher DependOnService FuturesTradingLog-Web
nssm set FuturesTradingLog-FileWatcher AppDirectory "C:\Program Files\Futures Trading Log\watcher"
nssm set FuturesTradingLog-FileWatcher AppEnvironmentExtra "DATA_DIR=C:\ProgramData\Futures Trading Log\data"
nssm set FuturesTradingLog-FileWatcher AppStdout "C:\ProgramData\Futures Trading Log\data\logs\watcher-stdout.log"
nssm set FuturesTradingLog-FileWatcher AppStderr "C:\ProgramData\Futures Trading Log\data\logs\watcher-stderr.log"
```

**Failure Recovery Configuration**:
```batch
# Restart services on failure
nssm set <ServiceName> AppExit Default Restart
nssm set <ServiceName> AppRestartDelay 5000
nssm set <ServiceName> AppThrottle 10000
```

### 5. Directory Structure and File Deployment

**Installation Directory** (`C:\Program Files\Futures Trading Log\`):
```
C:\Program Files\Futures Trading Log\
├── FuturesTradingLog.exe           # Main Flask application
├── _internal\                       # PyInstaller bundled dependencies
│   ├── Python runtime files
│   ├── DLL dependencies
│   └── Package libraries
├── templates\                       # Flask templates
├── static\                          # Static assets (CSS, JS, images)
├── bin\
│   ├── nssm.exe                    # Service manager
│   ├── start-services.bat          # Helper script
│   └── stop-services.bat           # Helper script
├── redis\
│   ├── redis-server.exe
│   ├── redis-cli.exe
│   └── redis.conf                  # Pre-configured
├── worker\
│   ├── FuturesTradingLog-Worker.exe
│   └── _internal\
└── watcher\
    ├── FuturesTradingLog-FileWatcher.exe
    └── _internal\
```

**Data Directory** (`C:\ProgramData\Futures Trading Log\`):
```
C:\ProgramData\Futures Trading Log\
├── data\
│   ├── db\
│   │   └── trading_log.db         # SQLite database
│   ├── logs\
│   │   ├── app.log
│   │   ├── web-stdout.log
│   │   ├── worker-stdout.log
│   │   ├── watcher-stdout.log
│   │   └── redis.log
│   ├── charts\                     # Generated chart images
│   ├── archive\                    # Archived CSV files
│   └── redis\                      # Redis persistence files
├── config\
│   └── settings.json               # Application configuration
└── .env                            # Environment variables (created on first run)
```

**File Permissions**:
- Program Files directory: Read-only for standard users, full control for SYSTEM and Administrators
- ProgramData directory: Modify permissions for all users to allow data writes

### 6. Environment Variable Configuration

**System Environment Variables** (Set via installer):
```
FUTURES_TRADING_LOG_HOME=C:\Program Files\Futures Trading Log
FUTURES_TRADING_LOG_DATA=C:\ProgramData\Futures Trading Log\data
```

**Service-Specific Environment Variables** (Set via NSSM):
```
DATA_DIR=C:\ProgramData\Futures Trading Log\data
FLASK_ENV=production
PORT=5555
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=sqlite:///C:\ProgramData\Futures Trading Log\data\db\trading_log.db
LOG_LEVEL=INFO
```

**Environment File Template** (`.env.example` → `.env`):
```env
# Application Configuration
FLASK_ENV=production
SECRET_KEY=<auto-generated-on-install>
PORT=5555

# Database
DATABASE_URL=sqlite:///C:\ProgramData\Futures Trading Log\data\db\trading_log.db
SQLITE_WAL_MODE=1

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Paths
DATA_DIR=C:\ProgramData\Futures Trading Log\data
LOG_DIR=C:\ProgramData\Futures Trading Log\data\logs
CHART_DIR=C:\ProgramData\Futures Trading Log\data\charts
ARCHIVE_DIR=C:\ProgramData\Futures Trading Log\data\archive

# File Watcher
NINJASCRIPT_OUTPUT_DIR=C:\Users\<USERNAME>\Documents\NinjaTrader 8\export
WATCH_INTERVAL=5

# Logging
LOG_LEVEL=INFO
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
```

### 7. Uninstaller Requirements

**Pre-Uninstall Tasks**:
1. Stop all Windows Services in reverse dependency order:
   - FuturesTradingLog-FileWatcher
   - FuturesTradingLog-Worker
   - FuturesTradingLog-Web
   - FuturesTradingLog-Redis

2. Wait for graceful shutdown (10-second timeout per service)

3. Terminate any remaining processes forcefully if needed

**Service Removal**:
```batch
nssm stop FuturesTradingLog-FileWatcher
nssm stop FuturesTradingLog-Worker
nssm stop FuturesTradingLog-Web
nssm stop FuturesTradingLog-Redis

nssm remove FuturesTradingLog-FileWatcher confirm
nssm remove FuturesTradingLog-Worker confirm
nssm remove FuturesTradingLog-Web confirm
nssm remove FuturesTradingLog-Redis confirm
```

**File Cleanup**:
1. **Always Delete**:
   - All files in `C:\Program Files\Futures Trading Log\`
   - Start menu shortcuts
   - Desktop shortcuts
   - Registry entries under `HKLM\Software\Futures Trading Log`

2. **Optional User Data Deletion** (Prompt user):
   - Database: `C:\ProgramData\Futures Trading Log\data\db\`
   - Logs: `C:\ProgramData\Futures Trading Log\data\logs\`
   - Charts: `C:\ProgramData\Futures Trading Log\data\charts\`
   - Archive: `C:\ProgramData\Futures Trading Log\data\archive\`
   - Config: `C:\ProgramData\Futures Trading Log\config\`

3. **User Prompt Dialog**:
```
"Do you want to remove all application data including your trading database and logs?

Select No to preserve your data for future reinstallation."

[Yes] [No]
```

**Registry Cleanup**:
- Remove `HKLM\Software\Futures Trading Log`
- Remove uninstaller entry from `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\`
- Clean up any service-related registry entries

**Verification**:
- Check for remaining processes via tasklist
- Verify all services removed via `sc query`
- Confirm file deletion completed
- Log uninstallation to Windows Event Log

### 8. Build Automation Scripts

**Main Build Script** (`build_installer.py`):
```python
#!/usr/bin/env python3
"""
Build script for creating Windows installer
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

VERSION = "1.0.0"
BUILD_DIR = Path("build")
DIST_DIR = Path("dist")
VENDOR_DIR = Path("vendor")

def clean_build():
    """Remove previous build artifacts"""
    print("Cleaning build directories...")
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    shutil.rmtree(DIST_DIR / "FuturesTradingLog", ignore_errors=True)
    shutil.rmtree(DIST_DIR / "FuturesTradingLog-Worker", ignore_errors=True)
    shutil.rmtree(DIST_DIR / "FuturesTradingLog-FileWatcher", ignore_errors=True)

def build_executables():
    """Build all executables using PyInstaller"""
    print("Building main application...")
    subprocess.run([
        "pyinstaller",
        "--name=FuturesTradingLog",
        "--onedir",
        "--windowed",
        "--icon=static/images/icon.ico",
        "--add-data=templates;templates",
        "--add-data=static;static",
        "--add-data=.env.example;.",
        "--hidden-import=flask",
        "--hidden-import=sqlalchemy",
        "--hidden-import=celery",
        "--hidden-import=redis",
        "app.py"
    ], check=True)

    print("Building Celery worker...")
    subprocess.run([
        "pyinstaller",
        "--name=FuturesTradingLog-Worker",
        "--onedir",
        "--console",
        "--hidden-import=celery",
        "--hidden-import=redis",
        "celery_app.py"
    ], check=True)

    print("Building file watcher...")
    subprocess.run([
        "pyinstaller",
        "--name=FuturesTradingLog-FileWatcher",
        "--onedir",
        "--console",
        "--hidden-import=watchdog",
        "scripts/file_watcher.py"
    ], check=True)

def download_dependencies():
    """Download Redis and NSSM if not present"""
    print("Checking vendor dependencies...")

    # Check Redis
    redis_dir = VENDOR_DIR / "redis"
    if not redis_dir.exists():
        print("Redis binaries not found in vendor/redis/")
        print("Please download Redis for Windows and extract to vendor/redis/")
        return False

    # Check NSSM
    nssm_path = VENDOR_DIR / "nssm" / "win64" / "nssm.exe"
    if not nssm_path.exists():
        print("NSSM not found in vendor/nssm/win64/")
        print("Please download NSSM and extract to vendor/nssm/")
        return False

    return True

def create_helper_scripts():
    """Create helper batch scripts"""
    print("Creating helper scripts...")

    scripts_dir = DIST_DIR / "FuturesTradingLog" / "bin"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    # Start services script
    with open(scripts_dir / "start-services.bat", "w") as f:
        f.write("""@echo off
echo Starting Futures Trading Log services...
nssm start FuturesTradingLog-Redis
nssm start FuturesTradingLog-Web
nssm start FuturesTradingLog-Worker
nssm start FuturesTradingLog-FileWatcher
echo Services started.
pause
""")

    # Stop services script
    with open(scripts_dir / "stop-services.bat", "w") as f:
        f.write("""@echo off
echo Stopping Futures Trading Log services...
nssm stop FuturesTradingLog-FileWatcher
nssm stop FuturesTradingLog-Worker
nssm stop FuturesTradingLog-Web
nssm stop FuturesTradingLog-Redis
echo Services stopped.
pause
""")

def build_installer():
    """Compile Inno Setup installer"""
    print("Building installer with Inno Setup...")

    # Find Inno Setup compiler
    iscc_path = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if not Path(iscc_path).exists():
        print(f"Inno Setup compiler not found at {iscc_path}")
        print("Please install Inno Setup 6 or update the path in build script")
        return False

    subprocess.run([iscc_path, "installer.iss"], check=True)
    print(f"Installer created: dist/installer/FuturesTradingLog-Setup-{VERSION}.exe")
    return True

def main():
    """Main build process"""
    print(f"Building Futures Trading Log Installer v{VERSION}")
    print("=" * 60)

    # Step 1: Clean
    clean_build()

    # Step 2: Check dependencies
    if not download_dependencies():
        print("\nBuild failed: Missing vendor dependencies")
        return 1

    # Step 3: Build executables
    try:
        build_executables()
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed during PyInstaller: {e}")
        return 1

    # Step 4: Create helper scripts
    create_helper_scripts()

    # Step 5: Build installer
    try:
        if not build_installer():
            return 1
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed during Inno Setup compilation: {e}")
        return 1

    print("\n" + "=" * 60)
    print("Build completed successfully!")
    print(f"Installer: dist/installer/FuturesTradingLog-Setup-{VERSION}.exe")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**Testing Script** (`scripts/test_installer.py`):
```python
#!/usr/bin/env python3
"""
Automated installer testing script
"""
import subprocess
import time
import requests

def test_services_running():
    """Check if all services are running"""
    services = [
        "FuturesTradingLog-Redis",
        "FuturesTradingLog-Web",
        "FuturesTradingLog-Worker",
        "FuturesTradingLog-FileWatcher"
    ]

    for service in services:
        result = subprocess.run(
            ["sc", "query", service],
            capture_output=True,
            text=True
        )
        if "RUNNING" not in result.stdout:
            print(f"FAIL: Service {service} is not running")
            return False
        print(f"PASS: Service {service} is running")

    return True

def test_web_application():
    """Test if web application is accessible"""
    try:
        response = requests.get("http://localhost:5555", timeout=10)
        if response.status_code == 200:
            print("PASS: Web application is accessible")
            return True
        else:
            print(f"FAIL: Web application returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"FAIL: Could not connect to web application: {e}")
        return False

def test_redis_connection():
    """Test Redis connectivity"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        print("PASS: Redis is accessible")
        return True
    except Exception as e:
        print(f"FAIL: Could not connect to Redis: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing Futures Trading Log Installation")
    print("=" * 60)

    # Wait for services to start
    print("Waiting 30 seconds for services to initialize...")
    time.sleep(30)

    tests = [
        test_services_running,
        test_redis_connection,
        test_web_application
    ]

    results = [test() for test in tests]

    print("\n" + "=" * 60)
    if all(results):
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed!")
        return 1

if __name__ == "__main__":
    exit(main())
```

## Approach

### Phase 1: Development Environment Setup
1. Install PyInstaller, Inno Setup, and development dependencies
2. Download Redis for Windows binaries to `vendor/redis/`
3. Download NSSM to `vendor/nssm/`
4. Create icon file for application branding

### Phase 2: PyInstaller Configuration
1. Create PyInstaller spec files for main app, worker, and watcher
2. Test builds locally with `--onedir` mode
3. Optimize hidden imports and excluded modules
4. Verify all templates, static files, and data files are included
5. Test executables run correctly outside development environment

### Phase 3: Inno Setup Script Development
1. Create initial `installer.iss` with basic file deployment
2. Add directory creation for ProgramData structure
3. Implement NSSM service installation commands
4. Add service configuration and dependency setup
5. Create uninstaller service removal logic
6. Implement data preservation prompt

### Phase 4: Build Automation
1. Create `build_installer.py` master build script
2. Implement clean build process
3. Add vendor dependency validation
4. Create helper batch scripts
5. Integrate Inno Setup compilation

### Phase 5: Testing and Validation
1. Test installation on clean Windows 10/11 VM
2. Verify all services start correctly
3. Test web application accessibility
4. Test file watcher functionality
5. Test uninstallation with data preservation
6. Test uninstallation with data removal
7. Verify no orphaned processes or services remain

### Phase 6: Documentation and Release
1. Create installation guide for end users
2. Document troubleshooting steps
3. Create release notes template
4. Tag release version in git
5. Build and publish installer to GitHub releases

## External Dependencies

### Build Tools
- **PyInstaller 6.0+**: Application bundling
- **Inno Setup 6.0+**: Windows installer creation
- **Python 3.13.5**: Development environment

### Runtime Dependencies (Bundled)
- **Redis for Windows 5.0.14+**: Cache server (5-10MB)
- **NSSM 2.24+**: Service manager (350KB)
- **Python 3.13.5 Runtime**: Bundled by PyInstaller (~50-60MB)
- **Flask 3.0.0 + Dependencies**: Web framework (~40-50MB)
- **SQLite**: Database (included with Python)
- **Celery + Redis client**: Background tasks (~20-30MB)

### Testing Dependencies
- **Windows 10/11 VM**: Clean installation testing
- **requests library**: HTTP testing
- **redis-py**: Redis connectivity testing

### Distribution Requirements
- **Code signing certificate**: Optional but recommended for production
- **GitHub repository**: Release hosting
- **Documentation**: Installation and troubleshooting guides

### Size Estimates
- Main application bundle: 150-200MB
- Redis binaries: 5-10MB
- NSSM: <1MB
- Total installer size: ~160-220MB compressed with LZMA2
