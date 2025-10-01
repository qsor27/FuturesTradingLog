# Windows Installer - Quick Start

## For Developers: Build the Installer

### Prerequisites
1. **Inno Setup 6.0+** - Download from https://jrsoftware.org/isdl.php
   - Install to default location
   - Takes ~2 minutes

### Build Command
```bash
cd installer
python build_installer.py
```

### Output
```
installer/output/FuturesTradingLog-Setup-1.0.0.exe (~160-215 MB)
```

### Build Time
- First build: ~3-5 minutes
- Subsequent builds: ~2-3 minutes

---

## For End Users: Install the Application

### Installation (5 clicks)
1. Download `FuturesTradingLog-Setup-1.0.0.exe`
2. Right-click → **Run as administrator**
3. Click **Next** → **Next** → **Install**
4. Click **Finish**
5. Browser opens to `http://localhost:5000` ✅

### What Gets Installed
- ✅ Python application (bundled, no Python installation needed)
- ✅ Redis cache service
- ✅ Windows Services (auto-start on boot)
- ✅ Start Menu shortcuts
- ✅ Service management tools

### Installation Locations
- **Application**: `C:\Program Files\Futures Trading Log`
- **Data**: `C:\ProgramData\Futures Trading Log`
  - Database
  - Logs
  - Configuration
  - Charts

---

## Verify Installation

### Check Services
Press `Win + R`, type `services.msc`, look for:
- ✅ **Futures Trading Log - Redis Cache** (Running)
- ✅ **Futures Trading Log - Web Server** (Running)

### Check Application
Open browser: `http://localhost:5000`
- Should see dashboard ✅

### Check Health
Visit: `http://localhost:5000/health`
- Should return: `{"status": "healthy"}` ✅

---

## Manage Services

### Start Menu Shortcuts
Press `Win`, type "Futures Trading Log":
- **Futures Trading Log** - Open application
- **Start Services** - Start all services
- **Stop Services** - Stop all services
- **View Logs** - Open logs directory

### Command Line
```powershell
# Start
net start FuturesTradingLog-Web

# Stop
net stop FuturesTradingLog-Web

# Check status
sc query FuturesTradingLog-Web
```

---

## Uninstall

### Standard Uninstall
1. Press `Win + I` → **Apps** → **Installed apps**
2. Find "Futures Trading Log"
3. Click **Uninstall**
4. Choose:
   - **YES** = Remove everything (clean uninstall)
   - **NO** = Keep data (can reinstall later)

### Data Preservation
If you choose **NO**, your data stays at:
```
C:\ProgramData\Futures Trading Log\
```

Reinstalling will use existing data ✅

---

## Troubleshooting

### Can't Access http://localhost:5000
```powershell
# Check if service is running
sc query FuturesTradingLog-Web

# Check logs
cd "C:\ProgramData\Futures Trading Log\logs"
type web_stderr.log
```

### Services Won't Start
```powershell
# Check Redis first (Web depends on it)
sc query FuturesTradingLog-Redis
net start FuturesTradingLog-Redis

# Then start Web
net start FuturesTradingLog-Web
```

### Port 5000 In Use
```powershell
# Find what's using port 5000
netstat -ano | findstr :5000

# Change app port (edit .env file)
notepad "C:\ProgramData\Futures Trading Log\config\.env"
# Change: FLASK_PORT=5001
# Restart services
```

---

## Support

### Documentation
- **User Guide**: `installer/INSTALLATION_GUIDE.md`
- **Technical Docs**: `installer/README.md`
- **Build Status**: `installer/BUILD_STATUS.md`

### Logs Location
```
C:\ProgramData\Futures Trading Log\logs\
```

### Health Endpoints
- Basic: `http://localhost:5000/health`
- Detailed: `http://localhost:5000/health/detailed`
- Metrics: `http://localhost:5000/metrics`

---

## Quick Reference

| Task | Command |
|------|---------|
| **Build installer** | `python installer/build_installer.py` |
| **Install app** | Run .exe as admin |
| **Open app** | `http://localhost:5000` |
| **Start services** | `net start FuturesTradingLog-Web` |
| **Stop services** | `net stop FuturesTradingLog-Web` |
| **Check status** | `sc query FuturesTradingLog-Web` |
| **View logs** | `C:\ProgramData\Futures Trading Log\logs\` |
| **Uninstall** | Windows Settings → Apps |

---

**That's it!** 🎉

Simple installation, easy management, clean uninstall.
