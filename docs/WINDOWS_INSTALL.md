# Windows Installation Guide (Without Docker)

Complete guide for installing Futures Trading Log directly on Windows without Docker. This guide provides **full feature parity** with the Docker deployment including auto-updates, service management, and health monitoring.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation Steps](#installation-steps)
3. [Environment Variables](#environment-variables)
4. [File Paths & Directory Structure](#file-paths--directory-structure)
5. [Windows Service Setup](#windows-service-setup)
6. [Automatic Updates](#automatic-updates)
7. [Health Monitoring](#health-monitoring)
8. [Uninstall](#uninstall)
9. [Running Without Redis](#running-without-redis)
10. [Troubleshooting](#troubleshooting)
11. [Quick Reference](#quick-reference)

---

## Automated Setup (Recommended)

Run the automated setup script to install all dependencies:

```powershell
# Download and run setup script (if you have the repo)
cd C:\Program Files\FuturesTradingLog
.\scripts\setup-windows.ps1

# Or with custom paths
.\scripts\setup-windows.ps1 -InstallPath "D:\Apps\FTL" -DataPath "D:\Data\FTL"
```

The script will:
- Install Python 3.11+ via winget
- Install Git via winget
- Download and install NSSM (service manager)
- Clone/update the repository
- Create data directories
- Set up Python virtual environment
- Install all Python dependencies
- Generate `.env` configuration file

> **Note:** Memurai (Redis for Windows) must be installed manually from https://www.memurai.com/get-memurai

---

## Manual Prerequisites

If you prefer manual installation, follow these steps:

### 1. Python 3.11+

**Option A: Using winget (Recommended)**
```powershell
winget install Python.Python.3.11
```

**Option B: Official Python Installer**
1. Download from https://www.python.org/downloads/
2. Run installer, **check "Add Python to PATH"**
3. Verify installation:
   ```powershell
   python --version
   # Expected: Python 3.11.x or higher
   ```

### 2. Git

```powershell
winget install Git.Git
```

Or download from https://git-scm.com/download/win

Verify:
```powershell
git --version
```

### 3. Redis for Windows

Redis is **required** for full functionality (OHLC chart caching, background tasks). Choose one option:

**Option A: Memurai (Recommended for Windows)**

Memurai is a Redis-compatible Windows service with native support:

1. Download from https://www.memurai.com/get-memurai
2. Run installer with default settings
3. Memurai installs and starts as a Windows service automatically

Verify:
```powershell
# Check service status
Get-Service memurai

# Test connection
memurai-cli ping
# Expected: PONG
```

**Option B: Redis via WSL2**
```powershell
# Install WSL2 (if not installed)
wsl --install -d Ubuntu

# Inside Ubuntu terminal:
sudo apt update
sudo apt install redis-server
sudo service redis-server start

# Test from Windows PowerShell:
wsl redis-cli ping
# Expected: PONG
```

**Option C: Run without Redis** (Not recommended)

Set `CACHE_ENABLED=false` - see [Running Without Redis](#running-without-redis)

### 4. NSSM (for Windows Service)

Required for running as a Windows service:

1. Download from https://nssm.cc/download
2. Extract `nssm.exe` to `C:\nssm\`
3. Add to PATH or use full path in commands

---

## Installation Steps

### Step 1: Clone Repository

**Generic Path:**
```powershell
cd C:\Projects
git clone https://github.com/qsor27/FuturesTradingLog.git
cd FuturesTradingLog
```

**Example Real Paths:**
| Environment | Path |
|-------------|------|
| Development | `C:\Program Files\FuturesTradingLog` |
| Production-style | `C:\Program Files\FuturesTradingLog` |

### Step 2: Create Virtual Environment

```powershell
python -m venv venv
.\venv\Scripts\Activate
```

### Step 3: Install Dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Create Data Directories

**Generic Path (Recommended):**
```powershell
$DataPath = "C:\ProgramData\FuturesTradingLog"

New-Item -ItemType Directory -Path "$DataPath\db" -Force
New-Item -ItemType Directory -Path "$DataPath\logs" -Force
New-Item -ItemType Directory -Path "$DataPath\config" -Force
New-Item -ItemType Directory -Path "$DataPath\charts" -Force
New-Item -ItemType Directory -Path "$DataPath\archive" -Force
New-Item -ItemType Directory -Path "$DataPath\backups" -Force
```

**Example Real Paths:**
| Use Case | Data Path |
|----------|-----------|
| Generic/Production | `C:\ProgramData\FuturesTradingLog` |
| Development | `C:\Program Files\FuturesTradingLog\data` |
| Docker-equivalent | `C:\Containers\FuturesTradingLog\data` |

### Step 5: Configure Environment

Create a `.env` file in the project root:

```ini
# ==============================================
# FuturesTradingLog Environment Configuration
# ==============================================

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=0
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# Security - REQUIRED: Generate a unique key
# Run: python -c "import secrets; print(secrets.token_hex(32))"
FLASK_SECRET_KEY=your-generated-secret-key-here

# Data Directory - Where database, logs, and config are stored
DATA_DIR=C:\ProgramData\FuturesTradingLog

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
CACHE_ENABLED=true
CACHE_TTL_DAYS=14

# NinjaTrader Auto-Import
AUTO_IMPORT_ENABLED=true
AUTO_IMPORT_INTERVAL=300

# Discord Notifications (Optional)
# Get webhook URL from: Discord Server Settings → Integrations → Webhooks
DISCORD_WEBHOOK_URL=
```

**Generate Secret Key:**
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 6: Start the Application (Manual)

```powershell
# Activate virtual environment
.\venv\Scripts\Activate

# Set environment variables (if not using .env file)
$env:FLASK_ENV = "production"
$env:DATA_DIR = "C:\ProgramData\FuturesTradingLog"

# Start application
python app.py
```

### Step 7: Access the Application

Open browser: **http://localhost:5000**

Verify health: **http://localhost:5000/health**

---

## Environment Variables

Complete reference of all environment variables with Docker vs Windows defaults:

### Required Variables

| Variable | Docker Default | Windows Default | Description |
|----------|---------------|-----------------|-------------|
| `FLASK_SECRET_KEY` | `dev-secret-key` | **(Generate!)** | Session encryption key - **must be unique** |
| `DATA_DIR` | `/app/data` | `C:\ProgramData\FuturesTradingLog` | Data storage root directory |

### Flask Configuration

| Variable | Docker Default | Windows Default | Description |
|----------|---------------|-----------------|-------------|
| `FLASK_ENV` | `production` | `production` | Environment mode: `development`, `production` |
| `FLASK_DEBUG` | `0` | `0` | Debug mode: `0` (off), `1` (on) |
| `FLASK_HOST` | `0.0.0.0` | `0.0.0.0` | Bind address (`127.0.0.1` for local only) |
| `FLASK_PORT` | `5000` | `5000` | HTTP port |

### Network Configuration

| Variable | Docker Default | Windows Default | Description |
|----------|---------------|-----------------|-------------|
| `HOST_IP` | `0.0.0.0` | `127.0.0.1` | External bind IP |
| `EXTERNAL_PORT` | `5000` | `5000` | External access port |

### Redis/Caching

| Variable | Docker Default | Windows Default | Description |
|----------|---------------|-----------------|-------------|
| `REDIS_URL` | `redis://redis:6379/0` | `redis://localhost:6379/0` | Redis connection string |
| `CACHE_ENABLED` | `true` | `true` | Enable Redis caching |
| `CACHE_TTL_DAYS` | `14` | `14` | Cache retention in days |

### NinjaTrader Integration

| Variable | Docker Default | Windows Default | Description |
|----------|---------------|-----------------|-------------|
| `AUTO_IMPORT_ENABLED` | `true` | `true` | Enable automatic CSV import |
| `AUTO_IMPORT_INTERVAL` | `300` | `300` | Import check interval (seconds) |

### Notifications

| Variable | Docker Default | Windows Default | Description |
|----------|---------------|-----------------|-------------|
| `DISCORD_WEBHOOK_URL` | *(empty)* | *(empty)* | Discord webhook for notifications |

---

## File Paths & Directory Structure

### Generic Template Structure

```
C:\ProgramData\FuturesTradingLog\          # DATA_DIR
├── db\
│   └── futures_trades_clean.db            # SQLite database
├── config\
│   ├── instrument_multipliers.json        # Instrument settings
│   └── service-config.txt                 # Service configuration reference
├── logs\
│   ├── app.log                            # Application logs
│   ├── app.log.1 ... app.log.5            # Rotated logs
│   ├── error.log                          # Error logs
│   ├── flask.log                          # Flask-specific logs
│   ├── service_stdout.log                 # Service stdout (NSSM)
│   ├── service_stderr.log                 # Service stderr (NSSM)
│   ├── health-check.log                   # Health monitor logs
│   └── auto-update.log                    # Auto-update logs
├── charts\                                # Generated chart files
├── archive\                               # Archived data
└── backups\                               # Installation backups (auto-update)
```

### Example Real-World Configurations

**Development Setup:**
```
Project:       C:\Program Files\FuturesTradingLog\
├── app.py
├── venv\
├── requirements.txt
└── ...

Data:          C:\Program Files\FuturesTradingLog\data\
├── db\
├── logs\
└── config\
```

**Docker-Equivalent Native Setup:**
```
Project:       C:\Program Files\FuturesTradingLog\

Data:          C:\Containers\FuturesTradingLog\data\
├── db\
├── logs\
└── config\
```

**Production-Style Setup:**
```
Project:       C:\Program Files\FuturesTradingLog\

Data:          C:\ProgramData\FuturesTradingLog\
├── db\
├── logs\
└── config\
```

### Path Quick Reference

| Item | Generic Path | Example Path |
|------|--------------|--------------|
| **Installation** | `C:\Program Files\FuturesTradingLog` | `C:\Program Files\FuturesTradingLog` |
| **Virtual Env** | `{InstallPath}\venv` | `C:\Program Files\FuturesTradingLog\venv` |
| **Python Exe** | `{InstallPath}\venv\Scripts\python.exe` | `C:\Program Files\FuturesTradingLog\venv\Scripts\python.exe` |
| **Data Root** | `C:\ProgramData\FuturesTradingLog` | `C:\Containers\FuturesTradingLog\data` |
| **Database** | `{DataPath}\db\futures_trades_clean.db` | `C:\ProgramData\FuturesTradingLog\db\futures_trades_clean.db` |
| **Logs** | `{DataPath}\logs\` | `C:\ProgramData\FuturesTradingLog\logs\` |
| **Config** | `{DataPath}\config\` | `C:\ProgramData\FuturesTradingLog\config\` |
| **.env File** | `{InstallPath}\.env` | `C:\Program Files\FuturesTradingLog\.env` |

---

## Windows Service Setup

Run FuturesTradingLog as a Windows service that starts automatically on boot (equivalent to Docker's `restart: unless-stopped`).

### Option A: Automated Installation (Recommended)

Use the included installation script:

```powershell
# Run as Administrator
cd C:\Program Files\FuturesTradingLog\scripts
.\install-service.ps1
```

**With custom paths:**
```powershell
.\install-service.ps1 `
    -InstallPath "C:\Apps\FuturesTradingLog" `
    -DataPath "C:\Data\FTL" `
    -RedisUrl "redis://localhost:6379/0" `
    -DiscordWebhook "https://discord.com/api/webhooks/..."
```

### Option B: Manual NSSM Configuration

**1. Install the service:**
```powershell
# Run as Administrator
$NssmPath = "C:\nssm\nssm.exe"
$ServiceName = "FuturesTradingLog"
$InstallPath = "C:\Program Files\FuturesTradingLog"
$DataPath = "C:\ProgramData\FuturesTradingLog"
$VenvPython = "$InstallPath\venv\Scripts\python.exe"

# Install service
& $NssmPath install $ServiceName $VenvPython
& $NssmPath set $ServiceName AppDirectory $InstallPath
& $NssmPath set $ServiceName AppParameters "app.py"
& $NssmPath set $ServiceName DisplayName "Futures Trading Log"
& $NssmPath set $ServiceName Description "Flask-based futures trading analytics platform"
```

**2. Configure environment variables:**
```powershell
$EnvVars = @"
FLASK_ENV=production
FLASK_DEBUG=0
FLASK_SECRET_KEY=your-secret-key-here
DATA_DIR=$DataPath
REDIS_URL=redis://localhost:6379/0
CACHE_ENABLED=true
AUTO_IMPORT_ENABLED=true
"@

& $NssmPath set $ServiceName AppEnvironmentExtra $EnvVars
```

**3. Configure restart policy (Docker equivalent):**
```powershell
# Equivalent to restart: unless-stopped
& $NssmPath set $ServiceName AppExit Default Restart
& $NssmPath set $ServiceName AppRestartDelay 5000
& $NssmPath set $ServiceName AppThrottle 10000
```

**4. Configure logging:**
```powershell
& $NssmPath set $ServiceName AppStdout "$DataPath\logs\service_stdout.log"
& $NssmPath set $ServiceName AppStderr "$DataPath\logs\service_stderr.log"
& $NssmPath set $ServiceName AppRotateFiles 1
& $NssmPath set $ServiceName AppRotateBytes 10485760
```

**5. Set to auto-start:**
```powershell
& $NssmPath set $ServiceName Start SERVICE_AUTO_START
```

**6. Start the service:**
```powershell
Start-Service FuturesTradingLog
```

### Service Management Commands

```powershell
# Start service
Start-Service FuturesTradingLog

# Stop service
Stop-Service FuturesTradingLog

# Restart service
Restart-Service FuturesTradingLog

# Check status
Get-Service FuturesTradingLog

# View logs
Get-Content "C:\ProgramData\FuturesTradingLog\logs\service_stdout.log" -Tail 50
```

### Uninstall Service

```powershell
# Run as Administrator
cd C:\Program Files\FuturesTradingLog\scripts
.\uninstall-service.ps1

# To also remove data:
.\uninstall-service.ps1 -RemoveData
```

---

## Automatic Updates

Equivalent to Docker's Watchtower for automatic container updates.

### Setup Auto-Update Script

The auto-update script checks GitHub for new releases and applies updates automatically.

**Manual Update Check:**
```powershell
cd C:\Program Files\FuturesTradingLog\scripts
.\windows-auto-update.ps1 -DryRun
```

**Apply Update Manually:**
```powershell
.\windows-auto-update.ps1
```

### Configure Scheduled Task (Recommended)

Set up automatic daily updates via Task Scheduler:

**1. Open Task Scheduler:**
```powershell
taskschd.msc
```

**2. Create New Task:**
- Name: `FuturesTradingLog Auto-Update`
- Run whether user is logged on or not
- Run with highest privileges

**3. Trigger:**
- Daily at 3:00 AM (or preferred time)

**4. Action:**
- Program: `powershell.exe`
- Arguments: `-ExecutionPolicy Bypass -File "C:\Program Files\FuturesTradingLog\scripts\windows-auto-update.ps1"`
- Start in: `C:\Program Files\FuturesTradingLog\scripts`

**5. Settings:**
- Allow task to be run on demand
- Stop task if running longer than 1 hour

### Auto-Update Features

- **Version Check:** Compares current git tag with latest GitHub release
- **Backup:** Creates backup before updating
- **Service Management:** Stops/starts service automatically
- **Health Verification:** Checks application health after update
- **Discord Notifications:** Optional update status notifications
- **Logging:** Full update log at `{DataPath}\logs\auto-update.log`

---

## Health Monitoring

Equivalent to Docker's HEALTHCHECK functionality.

### Single Health Check

```powershell
cd C:\Program Files\FuturesTradingLog\scripts
.\health-check.ps1 -RunOnce
```

### Continuous Monitoring

```powershell
# Run as daemon (continuous monitoring)
.\health-check.ps1 -Daemon

# With custom settings
.\health-check.ps1 -Daemon -CheckInterval 60 -MaxFailures 5
```

### Health Check Features

- Checks `http://localhost:5000/health` endpoint
- Automatically restarts service after consecutive failures
- Configurable check interval and failure threshold
- Logs to `{DataPath}\logs\health-check.log`

### Setup as Scheduled Task

For continuous health monitoring, create a scheduled task that runs the health check daemon on startup.

---

## Uninstall

Complete removal of FuturesTradingLog from your Windows system.

### Complete Uninstall (Recommended)

Use the complete uninstall script for a clean removal:

```powershell
# Run as Administrator
cd "C:\Program Files\FuturesTradingLog\scripts"
.\uninstall-complete.ps1
```

The script provides three options:

| Option | Description |
|--------|-------------|
| **1. Keep my data** | Removes application but preserves database, logs, and config |
| **2. Export & remove** | Creates backup ZIP, then removes everything |
| **3. Remove everything** | Complete removal including all data (cannot be undone) |

### Non-Interactive Mode

For automation or scripting:

```powershell
# Keep data (app-only removal)
.\uninstall-complete.ps1 -KeepData -Force

# Remove everything without prompts
.\uninstall-complete.ps1 -RemoveAll -Force
```

### What Gets Removed

**Always removed:**
- Windows Service (FuturesTradingLog)
- Installation directory (`C:\Program Files\FuturesTradingLog`)
- Python virtual environment
- Scheduled tasks (auto-update, health-check)

**Optionally removed (based on selection):**
- Data directory (`C:\ProgramData\FuturesTradingLog`)
- NSSM (only if installed by our setup script)

**Never automatically removed (shared dependencies):**
- Python
- Git
- Memurai/Redis

To remove these shared dependencies manually:
```powershell
# Remove Python
winget uninstall Python.Python.3.11

# Remove Git
winget uninstall Git.Git

# Remove Memurai (via Programs and Features or installer)
```

### Service-Only Removal

To remove just the Windows service (preserves application files):

```powershell
cd "C:\Program Files\FuturesTradingLog\scripts"
.\uninstall-service.ps1

# To also remove data:
.\uninstall-service.ps1 -RemoveData
```

### Backup Location

When using option 2 (Export & remove), backups are saved to your Desktop:
```
C:\Users\{username}\Desktop\FuturesTradingLog_Backup_{timestamp}.zip
```

The backup contains:
- Database files (`db/`)
- Configuration files (`config/`)
- CSV exports of trades and positions (`csv_exports/`)

### Uninstall Log

A log file is preserved after uninstall for troubleshooting:
```
C:\Users\{username}\FuturesTradingLog_Uninstall.log
```

---

## Running Without Redis

Not recommended for production use, but possible for testing:

### Disable Caching

**In .env file:**
```ini
CACHE_ENABLED=false
```

**Or via environment variable:**
```powershell
$env:CACHE_ENABLED = "false"
```

### Limitations Without Redis

- OHLC chart data fetched from database on each request (slower)
- No background task queue
- No data caching for improved performance
- Some features may have degraded performance

---

## Troubleshooting

### Service Won't Start

**Check service status:**
```powershell
Get-Service FuturesTradingLog
```

**View service logs:**
```powershell
Get-Content "C:\ProgramData\FuturesTradingLog\logs\service_stderr.log" -Tail 100
```

**Common causes:**
- Virtual environment not found
- Missing dependencies
- Port 5000 already in use
- Redis not running (if CACHE_ENABLED=true)

### Port 5000 Already in Use

```powershell
# Find what's using port 5000
netstat -ano | findstr :5000

# Get process name
tasklist /FI "PID eq <PID_NUMBER>"

# Use a different port
$env:FLASK_PORT = "5001"
```

### Redis Connection Failed

**Check Memurai service:**
```powershell
Get-Service memurai
Start-Service memurai  # If stopped
memurai-cli ping       # Test connection
```

**Or disable caching:**
```powershell
$env:CACHE_ENABLED = "false"
```

### "Module not found" Errors

```powershell
# Ensure virtual environment is activated
.\venv\Scripts\Activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Database Locked Errors

- Ensure only one instance of the app is running
- Close any SQLite browser tools
- Check for zombie processes:
  ```powershell
  tasklist | findstr python
  taskkill /IM python.exe /F  # Force kill all Python (use with caution)
  ```

### Permission Denied on Data Directory

```powershell
# Run as Administrator
icacls "C:\ProgramData\FuturesTradingLog" /grant Users:F /t
```

### Application Health Check Failing

```powershell
# Manual health check
curl http://localhost:5000/health

# Detailed health
curl http://localhost:5000/health/detailed
```

---

## Quick Reference

### File Paths

| Item | Path |
|------|------|
| Installation | `C:\Program Files\FuturesTradingLog` |
| Python | `C:\Program Files\FuturesTradingLog\venv\Scripts\python.exe` |
| Data | `C:\ProgramData\FuturesTradingLog` |
| Database | `C:\ProgramData\FuturesTradingLog\db\futures_trades_clean.db` |
| Logs | `C:\ProgramData\FuturesTradingLog\logs\` |
| Config | `C:\ProgramData\FuturesTradingLog\config\` |

### Common Commands

| Task | Command |
|------|---------|
| Start app (manual) | `python app.py` |
| Start service | `Start-Service FuturesTradingLog` |
| Stop service | `Stop-Service FuturesTradingLog` |
| Restart service | `Restart-Service FuturesTradingLog` |
| Service status | `Get-Service FuturesTradingLog` |
| Health check | `curl http://localhost:5000/health` |
| View logs | `Get-Content "{DataPath}\logs\app.log" -Tail 50` |
| Check for updates | `.\scripts\windows-auto-update.ps1 -DryRun` |
| Apply update | `.\scripts\windows-auto-update.ps1` |

### URLs

| Endpoint | URL |
|----------|-----|
| Web Interface | http://localhost:5000 |
| Health Check | http://localhost:5000/health |
| Detailed Health | http://localhost:5000/health/detailed |
| Metrics | http://localhost:5000/metrics |

### PowerShell Scripts

| Script | Purpose |
|--------|---------|
| `scripts\setup-windows.ps1` | Automated setup of all dependencies |
| `scripts\install-service.ps1` | Install Windows service with NSSM |
| `scripts\uninstall-service.ps1` | Remove Windows service only |
| `scripts\uninstall-complete.ps1` | Complete uninstall with data options |
| `scripts\windows-auto-update.ps1` | Automatic version updates |
| `scripts\health-check.ps1` | Health monitoring |

---

## See Also

- [README.md](../README.md) - Main documentation
- [Docker deployment](../README.md#option-1-docker-recommended) - Container-based deployment
- [NinjaTrader Setup](NINJASCRIPT_SETUP.md) - Auto-import from NinjaTrader
- [Discord Notifications](DISCORD_NOTIFICATIONS_SETUP.md) - Notification setup
- [Windows Installer](../installer/README.md) - Pre-built Windows installer (alternative)
