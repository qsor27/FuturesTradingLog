# Futures Trading Log - Windows Installer

This directory contains the Windows native installer build system for Futures Trading Log. The installer packages the Python application, Redis cache, and all dependencies into a single `.exe` file that installs everything as Windows Services.

## Overview

The installer uses:
- **PyInstaller**: Bundles Python application into standalone executable
- **Inno Setup**: Creates professional Windows installer with service management
- **NSSM**: Manages Windows Services for Flask app and Redis
- **Redis for Windows**: Bundled Redis cache server

## Prerequisites

### Required Software

1. **Python 3.8+** (for building, not required on target machines)
   - Already installed: Python 3.13.5

2. **PyInstaller** (for bundling)
   ```bash
   pip install pyinstaller
   ```

3. **Inno Setup 6.0+** (for creating installer)
   - Download from: https://jrsoftware.org/isdl.php
   - Install to default location: `C:\Program Files (x86)\Inno Setup 6\`

### Optional Software

- **Code signing certificate** (for production releases)
- **Inno Setup Preprocessor** (included with Inno Setup)

## Quick Start

### 1. Download Dependencies

Download Redis and NSSM (only needed once):

```bash
cd installer
python download_dependencies.py
```

This downloads:
- Redis 7.2.6 for Windows (~10 MB)
- NSSM 2.24 (Service Manager) (~300 KB)

### 2. Build the Installer

Run the automated build script:

```bash
cd installer
python build_installer.py
```

This will:
1. Clean previous build artifacts
2. Build executable with PyInstaller (~2 minutes)
3. Verify dependencies
4. Create installer with Inno Setup
5. Output: `installer/output/FuturesTradingLog-Setup-1.0.0.exe` (~160-215 MB)

### 3. Test the Installer

Run the generated installer on a test Windows machine:

```bash
installer/output/FuturesTradingLog-Setup-1.0.0.exe
```

The installer will:
- Install to `C:\Program Files\Futures Trading Log`
- Create data directory in `C:\ProgramData\Futures Trading Log`
- Install Redis as Windows Service
- Install Flask app as Windows Service
- Start both services automatically
- Open browser to `http://localhost:5000`

## Build Process Details

### Directory Structure

```
installer/
├── app.spec                      # PyInstaller config for main app
├── celery_worker.spec            # PyInstaller config for Celery (future)
├── file_watcher.spec             # PyInstaller config for file watcher (future)
├── FuturesTradingLog.iss         # Inno Setup installer script
├── build_installer.py            # Automated build script
├── download_dependencies.py      # Dependency downloader
├── README.md                     # This file
│
├── configs/
│   ├── redis.windows.conf        # Redis configuration template
│   └── .env.template             # Application config template
│
├── scripts/
│   ├── start_services.bat        # Start all services
│   ├── stop_services.bat         # Stop all services
│   ├── restart_services.bat      # Restart all services
│   └── check_services.bat        # Check service status
│
├── redis/                        # Redis binaries (downloaded)
│   ├── redis-server.exe
│   ├── redis-cli.exe
│   └── redis.conf
│
├── nssm/                         # NSSM service manager (downloaded)
│   └── nssm.exe
│
├── dist/                         # PyInstaller output (generated)
│   └── FuturesTradingLog/
│       ├── FuturesTradingLog.exe
│       ├── _internal/
│       └── ...
│
├── build/                        # PyInstaller build cache (generated)
└── output/                       # Inno Setup output (generated)
    └── FuturesTradingLog-Setup-1.0.0.exe
```

### PyInstaller Configuration

Three `.spec` files define how to bundle the application:

1. **app.spec** - Main Flask web application
   - Bundles Flask, SQLAlchemy, Redis client, Pandas
   - Includes `templates/` and `static/` directories
   - Output: `FuturesTradingLog.exe` (~21 MB)

2. **celery_worker.spec** - Background Celery worker (future)
   - Bundles Celery, Redis, task modules
   - Output: `CeleryWorker.exe`

3. **file_watcher.spec** - File monitoring service (future)
   - Bundles file watching and auto-import logic
   - Output: `FileWatcher.exe`

### Inno Setup Configuration

The `FuturesTradingLog.iss` script defines:

- **Installation directories**:
  - Application: `C:\Program Files\Futures Trading Log`
  - Data: `C:\ProgramData\Futures Trading Log`

- **Windows Services**:
  - `FuturesTradingLog-Redis` - Redis cache service
  - `FuturesTradingLog-Web` - Flask web server

- **Service configuration**:
  - Auto-start on system boot (optional)
  - Restart on failure
  - Dependency: Web service depends on Redis

- **Shortcuts**:
  - Start Menu folder with service management
  - Optional desktop shortcut
  - Links to logs and data directories

- **Uninstaller**:
  - Stops and removes all services
  - Removes application files
  - Optionally preserves or removes data directory

## Customization

### Version Number

Edit `FuturesTradingLog.iss`:

```pascal
#define MyAppVersion "1.0.0"
```

### Application Name

Edit `FuturesTradingLog.iss`:

```pascal
#define MyAppName "Futures Trading Log"
#define MyAppPublisher "Your Company Name"
#define MyAppURL "https://your-website.com"
```

### Hidden Imports

If PyInstaller misses dependencies, add them to `app.spec`:

```python
hiddenimports = [
    'flask',
    'sqlalchemy',
    # Add more modules here
]
```

### Installation Directory

Edit `FuturesTradingLog.iss`:

```pascal
DefaultDirName={autopf}\YourAppName
```

### Redis Configuration

Edit `configs/redis.windows.conf`:

```conf
maxmemory 256mb
port 6379
bind 127.0.0.1
```

### Environment Variables

Edit `configs/.env.template`:

```ini
FLASK_PORT=5000
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=INFO
```

## Troubleshooting

### Build Issues

**Problem**: PyInstaller fails with "module not found"
- **Solution**: Add missing module to `hiddenimports` in `.spec` file

**Problem**: Inno Setup compiler not found
- **Solution**: Install Inno Setup from https://jrsoftware.org/isdl.php
- Verify installation: `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`

**Problem**: Redis or NSSM missing
- **Solution**: Run `python download_dependencies.py`

### Installation Issues

**Problem**: Services fail to start
- **Solution**: Check logs in `C:\ProgramData\Futures Trading Log\logs\`
- Verify Redis port 6379 is not in use
- Check Windows Event Viewer for service errors

**Problem**: Port 5000 already in use
- **Solution**: Stop other applications using port 5000
- Or change port in service configuration

**Problem**: Permission denied errors
- **Solution**: Run installer as Administrator
- Check folder permissions in `C:\ProgramData\`

### Runtime Issues

**Problem**: Application won't start
- **Solution**: Check service status with `check_services.bat`
- Review logs in data directory
- Verify Redis is running

**Problem**: Cannot access http://localhost:5000
- **Solution**: Check Windows Firewall settings
- Verify Web service is running
- Check `web_stdout.log` and `web_stderr.log`

## Service Management

### Using Batch Files

Located in installation directory's `tools/` folder:

```batch
# Start all services
start_services.bat

# Stop all services
stop_services.bat

# Restart all services
restart_services.bat

# Check service status
check_services.bat
```

### Using Windows Services Manager

1. Press `Win + R`, type `services.msc`, press Enter
2. Find services starting with "Futures Trading Log"
3. Right-click → Start/Stop/Restart

### Using NSSM Command Line

```powershell
# Check status
nssm status FuturesTradingLog-Web
nssm status FuturesTradingLog-Redis

# Start service
nssm start FuturesTradingLog-Web

# Stop service
nssm stop FuturesTradingLog-Web

# Restart service
nssm restart FuturesTradingLog-Web
```

### Using Command Line

```powershell
# Check status
sc query FuturesTradingLog-Web

# Start service
net start FuturesTradingLog-Web

# Stop service
net stop FuturesTradingLog-Web
```

## Uninstallation

### Complete Uninstall (Removes Everything)

1. Run uninstaller from Start Menu or Add/Remove Programs
2. When prompted, choose **YES** to remove data directory
3. This removes:
   - Application files
   - Windows Services
   - Database and logs
   - Configuration files

### Partial Uninstall (Preserve Data)

1. Run uninstaller
2. When prompted, choose **NO** to keep data directory
3. This preserves:
   - Database (`futures_trades_clean.db`)
   - Logs
   - Configuration (`.env` file)
   - Charts and backups

Data directory location: `C:\ProgramData\Futures Trading Log`

## Building for Distribution

### Development Build

For testing:

```bash
python build_installer.py
```

### Production Build

For public release:

1. **Update version number** in `FuturesTradingLog.iss`
2. **Code sign executables** (optional but recommended):
   ```bash
   signtool sign /f certificate.pfx /p password FuturesTradingLog.exe
   ```
3. **Build installer**:
   ```bash
   python build_installer.py
   ```
4. **Code sign installer** (optional but recommended):
   ```bash
   signtool sign /f certificate.pfx /p password FuturesTradingLog-Setup-1.0.0.exe
   ```
5. **Test on clean Windows VM**
6. **Create release notes**
7. **Upload to distribution server**

### CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Build Windows Installer

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install pyinstaller
      - name: Download dependencies
        run: python installer/download_dependencies.py
      - name: Build installer
        run: python installer/build_installer.py
      - name: Upload artifact
        uses: actions/upload-artifact@v3
        with:
          name: installer
          path: installer/output/*.exe
```

## Maintenance

### Updating Application

When you update the core application:

1. Update Python code, requirements, etc.
2. Rebuild installer: `python build_installer.py`
3. Test on clean machine
4. Distribute new installer

**No code duplication** - same codebase for Docker and Windows!

### Updating Dependencies

When updating Python packages:

1. Update `requirements.txt`
2. Test application locally
3. Rebuild installer (PyInstaller picks up new dependencies automatically)

### Updating Redis

1. Download new Redis version
2. Extract to `installer/redis/`
3. Update `redis.windows.conf` if needed
4. Rebuild installer

### Updating NSSM

1. Download new NSSM version
2. Extract `nssm.exe` to `installer/nssm/`
3. Rebuild installer

## Support

### Logs Location

After installation, logs are located in:

```
C:\ProgramData\Futures Trading Log\logs\
├── web_stdout.log          # Flask application output
├── web_stderr.log          # Flask application errors
├── redis_stdout.log        # Redis output
├── redis_stderr.log        # Redis errors
└── app.log                 # Application-level logs
```

### Health Check

Check application health:

```
http://localhost:5000/health
http://localhost:5000/health/detailed
```

### Metrics

View application metrics:

```
http://localhost:5000/metrics
```

## License

See the LICENSE file in the root directory of the project.

## Resources

- **Inno Setup Documentation**: https://jrsoftware.org/ishelp/
- **PyInstaller Documentation**: https://pyinstaller.org/
- **NSSM Documentation**: https://nssm.cc/usage
- **Redis Documentation**: https://redis.io/documentation
