# Futures Trading Log - Installation Guide

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [First-Time Setup](#first-time-setup)
4. [Accessing the Application](#accessing-the-application)
5. [Managing Services](#managing-services)
6. [Troubleshooting](#troubleshooting)
7. [Uninstallation](#uninstallation)

---

## System Requirements

### Minimum Requirements
- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **RAM**: 4 GB minimum, 8 GB recommended
- **Disk Space**: 500 MB for application, additional space for trading data
- **Network**: Internet connection for market data updates (optional)

### Required Ports
- **5000**: Flask web server (default, configurable)
- **6379**: Redis cache service (localhost only)

### Administrator Access
- Installation requires administrator privileges
- Services run as Local System account

---

## Installation

### Step 1: Download the Installer

Download `FuturesTradingLog-Setup-1.0.0.exe` from your distribution source.

**File Size**: ~160-215 MB (includes all dependencies)

### Step 2: Run the Installer

1. Right-click `FuturesTradingLog-Setup-1.0.0.exe`
2. Select **Run as administrator**
3. If Windows SmartScreen appears, click **More info** → **Run anyway**

### Step 3: Installation Wizard

Follow the installation wizard:

#### Welcome Screen
- Click **Next** to continue

#### License Agreement
- Read and accept the license agreement
- Click **Next**

#### Installation Location
- **Default**: `C:\Program Files\Futures Trading Log`
- Click **Browse** to change (not recommended)
- Click **Next**

#### Data Directory Location
- **Default**: `C:\ProgramData\Futures Trading Log`
- This stores your database, logs, and configuration
- Click **Next**

#### Select Components
Choose installation components:
- ☑ **Core Application Files** (required)
- ☑ **Windows Services** (required)
- ☑ **Desktop and Start Menu Shortcuts** (optional)

Click **Next**

#### Additional Tasks
- ☑ **Create desktop shortcut** (optional)
- ☑ **Start services automatically on system boot** (recommended)

Click **Next**

#### Ready to Install
- Review your settings
- Click **Install**

#### Installation Progress
The installer will:
1. Copy application files
2. Install Redis for Windows
3. Configure Redis as Windows Service
4. Configure Flask app as Windows Service
5. Create shortcuts
6. Start services

**Estimated time**: 1-2 minutes

#### Completion
- ☑ **Launch Futures Trading Log** (opens browser)
- Click **Finish**

---

## First-Time Setup

### Verify Installation

After installation, verify services are running:

1. **Open Services Manager**:
   - Press `Win + R`
   - Type `services.msc`
   - Press Enter

2. **Check Services**:
   Look for these services with status **Running**:
   - `Futures Trading Log - Redis Cache`
   - `Futures Trading Log - Web Server`

### Access Web Interface

1. Open your web browser
2. Navigate to: `http://localhost:5000`
3. You should see the Futures Trading Log dashboard

### Initial Configuration

#### 1. Database Initialization
The first time you access the application, the database will be initialized automatically.

#### 2. Import Your First Data
- Click **Settings** → **Import Data**
- Select your NinjaTrader export CSV file
- Click **Import**

#### 3. Configure Auto-Import (Optional)
- Click **Settings** → **Auto Import**
- Set your NinjaTrader export directory
- Enable auto-import
- Set check interval (default: 5 minutes)

---

## Accessing the Application

### Web Browser
- URL: `http://localhost:5000`
- Bookmark this URL for easy access

### Desktop Shortcut
- Double-click **Futures Trading Log** icon on desktop
- Opens browser to `http://localhost:5000`

### Start Menu
- Press `Win` key
- Type "Futures Trading Log"
- Click the application icon

---

## Managing Services

### Start Menu Shortcuts

The installer creates Start Menu shortcuts for service management:

1. Press `Win` key
2. Type "Futures Trading Log"
3. Choose:
   - **Futures Trading Log** - Open application
   - **Start Services** - Start all services
   - **Stop Services** - Stop all services
   - **View Logs** - Open log directory

### Batch Files

Located in: `C:\Program Files\Futures Trading Log\tools\`

#### Start All Services
```batch
start_services.bat
```
Starts Redis and Web services in order.

#### Stop All Services
```batch
stop_services.bat
```
Stops all services gracefully.

#### Restart All Services
```batch
restart_services.bat
```
Restarts all services (useful after configuration changes).

#### Check Service Status
```batch
check_services.bat
```
Displays current status of all services and health check.

### Windows Services Manager

1. Press `Win + R`, type `services.msc`, press Enter
2. Find services:
   - `Futures Trading Log - Redis Cache`
   - `Futures Trading Log - Web Server`
3. Right-click service → **Start/Stop/Restart/Properties**

### Command Line

**Check Status**:
```powershell
sc query FuturesTradingLog-Redis
sc query FuturesTradingLog-Web
```

**Start Services**:
```powershell
net start FuturesTradingLog-Redis
net start FuturesTradingLog-Web
```

**Stop Services**:
```powershell
net stop FuturesTradingLog-Web
net stop FuturesTradingLog-Redis
```

---

## Troubleshooting

### Application Won't Start

**Symptom**: Cannot access `http://localhost:5000`

**Solutions**:
1. Check service status:
   ```powershell
   sc query FuturesTradingLog-Web
   ```
2. Check logs:
   - Open: `C:\ProgramData\Futures Trading Log\logs\`
   - Review: `web_stderr.log` and `web_stdout.log`
3. Verify port is available:
   ```powershell
   netstat -ano | findstr :5000
   ```
4. Restart services using `restart_services.bat`

### Services Won't Start

**Symptom**: Services show "Stopped" in Services Manager

**Solutions**:
1. Check Windows Event Viewer:
   - Press `Win + X` → **Event Viewer**
   - Navigate to **Windows Logs** → **Application**
   - Look for errors from "FuturesTradingLog" source

2. Verify dependencies:
   - Ensure Redis service starts before Web service
   - Check service dependencies in Properties

3. Check logs in `C:\ProgramData\Futures Trading Log\logs\`

4. Reinstall services:
   ```powershell
   # Run as Administrator
   cd "C:\Program Files\Futures Trading Log\tools"
   nssm remove FuturesTradingLog-Web confirm
   nssm remove FuturesTradingLog-Redis confirm
   # Then reinstall using installer
   ```

### Port 5000 Already in Use

**Symptom**: Error message about port 5000

**Solutions**:
1. Find process using port:
   ```powershell
   netstat -ano | findstr :5000
   tasklist /FI "PID eq [PID_NUMBER]"
   ```
2. Stop the conflicting process
3. Or change application port:
   - Edit: `C:\ProgramData\Futures Trading Log\config\.env`
   - Change: `FLASK_PORT=5001`
   - Restart services

### Redis Connection Errors

**Symptom**: Errors about Redis connection in logs

**Solutions**:
1. Check Redis service:
   ```powershell
   sc query FuturesTradingLog-Redis
   ```
2. Test Redis connection:
   ```powershell
   cd "C:\Program Files\Futures Trading Log\redis"
   redis-cli ping
   # Should respond: PONG
   ```
3. Restart Redis service:
   ```powershell
   net stop FuturesTradingLog-Redis
   net start FuturesTradingLog-Redis
   ```

### Performance Issues

**Symptom**: Slow loading, high CPU/memory usage

**Solutions**:
1. Check system resources:
   - Press `Ctrl + Shift + Esc` (Task Manager)
   - Look for high CPU/memory usage
2. Check Redis memory:
   - Current setting: 256 MB max
   - Edit: `C:\Program Files\Futures Trading Log\redis\redis.conf`
   - Adjust: `maxmemory 512mb` (if needed)
3. Review log files for errors
4. Restart services to clear cache

### Database Locked Errors

**Symptom**: "Database is locked" errors

**Solutions**:
1. Ensure only one instance is running
2. Close any database browsers/tools
3. Restart services
4. Check for crashed processes:
   ```powershell
   tasklist | findstr FuturesTradingLog
   ```
5. Kill zombie processes if needed

---

## Uninstallation

### Standard Uninstall

1. **Open Settings**:
   - Press `Win + I`
   - Click **Apps**
   - Click **Installed apps**

2. **Find Application**:
   - Search for "Futures Trading Log"
   - Click **...** → **Uninstall**

3. **Confirm Uninstall**:
   - Click **Uninstall** again

4. **Data Directory Prompt**:
   - **YES**: Remove database, logs, config (clean uninstall)
   - **NO**: Preserve your data (can reinstall later)

### Keep Data for Reinstallation

Choose **NO** when prompted about data directory.

Your data is preserved at:
- `C:\ProgramData\Futures Trading Log\`

This includes:
- ✅ Database (`db/futures_trades_clean.db`)
- ✅ Logs (`logs/`)
- ✅ Configuration (`.env` file)
- ✅ Charts and exports
- ✅ Backups

**To reinstall**: Run installer again, and it will use existing data.

### Complete Removal

Choose **YES** when prompted about data directory.

This removes:
- ❌ Application files
- ❌ Windows Services
- ❌ Database
- ❌ Logs
- ❌ Configuration
- ❌ All user data

**Warning**: This action cannot be undone!

### Manual Cleanup (If Needed)

If uninstaller fails or you need to manually clean up:

1. **Stop Services**:
   ```powershell
   net stop FuturesTradingLog-Web
   net stop FuturesTradingLog-Redis
   ```

2. **Remove Services**:
   ```powershell
   sc delete FuturesTradingLog-Web
   sc delete FuturesTradingLog-Redis
   ```

3. **Delete Files**:
   - `C:\Program Files\Futures Trading Log\`
   - `C:\ProgramData\Futures Trading Log\` (if desired)

4. **Remove Registry Entries**:
   - Press `Win + R`, type `regedit`, press Enter
   - Navigate to: `HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\`
   - Delete: `{FDB6E4F1-8C3D-4E9A-9B2A-5F7E3D6C8A9B}`

---

## Additional Information

### Logs Location
```
C:\ProgramData\Futures Trading Log\logs\
├── web_stdout.log          # Web server output
├── web_stderr.log          # Web server errors
├── redis_stdout.log        # Redis output
├── redis_stderr.log        # Redis errors
└── app.log                 # Application logs
```

### Configuration Location
```
C:\ProgramData\Futures Trading Log\config\.env
```

### Database Location
```
C:\ProgramData\Futures Trading Log\db\futures_trades_clean.db
```

### Health Check Endpoints
- **Basic**: `http://localhost:5000/health`
- **Detailed**: `http://localhost:5000/health/detailed`
- **Metrics**: `http://localhost:5000/metrics`

### Support

For issues not covered in this guide:
1. Check application logs
2. Review Windows Event Viewer
3. Consult the project documentation
4. Contact support or open an issue

---

## Quick Reference

### Common Tasks

| Task | Command |
|------|---------|
| Open application | `http://localhost:5000` |
| Start services | `net start FuturesTradingLog-Web` |
| Stop services | `net stop FuturesTradingLog-Web` |
| Check status | `sc query FuturesTradingLog-Web` |
| View logs | `C:\ProgramData\Futures Trading Log\logs\` |
| Edit config | `C:\ProgramData\Futures Trading Log\config\.env` |
| Health check | `http://localhost:5000/health` |

### Service Names

| Service | Name |
|---------|------|
| Redis Cache | `FuturesTradingLog-Redis` |
| Web Server | `FuturesTradingLog-Web` |

---

**Version**: 1.0.0
**Last Updated**: 2025-09-30
