# Windows Installation Guide (Without Docker)

Complete guide for installing Futures Trading Log directly on Windows without Docker.

## Prerequisites

### 1. Python 3.11+

**Option A: Microsoft Store (Recommended)**
```powershell
winget install Python.Python.3.11
```

**Option B: Official Python Installer**
1. Download from https://www.python.org/downloads/
2. Run installer, check "Add Python to PATH"
3. Verify: `python --version`

### 2. Git

```powershell
winget install Git.Git
```

Or download from https://git-scm.com/download/win

### 3. Redis for Windows

Redis is optional but recommended for caching. Choose one option:

**Option A: Memurai (Recommended for Windows)**
Memurai is a Redis-compatible Windows service:
1. Download from https://www.memurai.com/get-memurai
2. Install with default settings
3. Memurai runs as a Windows service automatically

**Option B: Redis via WSL2**
```powershell
# Install WSL2
wsl --install -d Ubuntu

# Inside Ubuntu
sudo apt update
sudo apt install redis-server
sudo service redis-server start
```

**Option C: Run without Redis**
Set `CACHE_ENABLED=false` to disable Redis caching (performance will be reduced)

---

## Installation Steps

### Step 1: Clone Repository

```powershell
cd C:\Projects
git clone https://github.com/qsor27/FuturesTradingLog.git
cd FuturesTradingLog
```

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

### Step 4: Create Data Directory

```powershell
# Create data directory
mkdir C:\ProgramData\FuturesTradingLog
mkdir C:\ProgramData\FuturesTradingLog\db
mkdir C:\ProgramData\FuturesTradingLog\logs
mkdir C:\ProgramData\FuturesTradingLog\config
```

### Step 5: Configure Environment

Create a `.env` file in the project root or set environment variables:

**Option A: Create .env file**
```ini
# .env file in project root
FLASK_ENV=production
FLASK_SECRET_KEY=generate-a-secure-random-key-here
DATA_DIR=C:\ProgramData\FuturesTradingLog
REDIS_URL=redis://localhost:6379/0
CACHE_ENABLED=true
AUTO_IMPORT_ENABLED=true
```

**Option B: Set Environment Variables in PowerShell**
```powershell
$env:FLASK_ENV = "production"
$env:FLASK_SECRET_KEY = "generate-a-secure-random-key-here"
$env:DATA_DIR = "C:\ProgramData\FuturesTradingLog"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:CACHE_ENABLED = "true"
$env:AUTO_IMPORT_ENABLED = "true"
```

**Generate a Secure Secret Key:**
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 6: Start the Application

```powershell
# Activate virtual environment (if not already active)
.\venv\Scripts\Activate

# Start the application
python app.py
```

### Step 7: Access the Application

Open your browser to: http://localhost:5000

---

## Running as a Windows Service

To run the application as a Windows service that starts automatically:

### Using NSSM (Non-Sucking Service Manager)

1. **Download NSSM**
   - Get it from https://nssm.cc/download
   - Extract to `C:\nssm\`

2. **Install the Service**
   ```powershell
   # Run as Administrator
   C:\nssm\nssm.exe install FuturesTradingLog
   ```

3. **Configure in the GUI:**
   - **Path**: `C:\Projects\FuturesTradingLog\venv\Scripts\python.exe`
   - **Startup directory**: `C:\Projects\FuturesTradingLog`
   - **Arguments**: `app.py`
   - **Environment tab**: Add your environment variables

4. **Start the Service**
   ```powershell
   net start FuturesTradingLog
   ```

### Using Task Scheduler (Alternative)

1. Open Task Scheduler (`taskschd.msc`)
2. Create Basic Task
3. Trigger: "When the computer starts"
4. Action: Start a program
   - Program: `C:\Projects\FuturesTradingLog\venv\Scripts\python.exe`
   - Arguments: `app.py`
   - Start in: `C:\Projects\FuturesTradingLog`

---

## Running Without Redis

If you don't want to install Redis:

1. Set environment variable:
   ```powershell
   $env:CACHE_ENABLED = "false"
   ```

2. Or add to `.env` file:
   ```ini
   CACHE_ENABLED=false
   ```

**Note:** Without Redis, OHLC chart data will be fetched from the database on each request, which is slower but still functional.

---

## Verify Installation

### Check Application Health
```powershell
curl http://localhost:5000/health
```

Expected response:
```json
{"status": "healthy", "database": "connected", "cache": "connected"}
```

### Check Redis Connection (if enabled)
```powershell
# If using Memurai
memurai-cli ping
# Expected: PONG

# If using WSL Redis
wsl redis-cli ping
# Expected: PONG
```

---

## Troubleshooting

### "Module not found" Errors
```powershell
# Ensure virtual environment is activated
.\venv\Scripts\Activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Port 5000 Already in Use
```powershell
# Find what's using port 5000
netstat -ano | findstr :5000

# Kill the process or use a different port
$env:FLASK_PORT = "5001"
```

### Redis Connection Failed
- Check if Redis/Memurai service is running
- Verify REDIS_URL is correct
- Or disable caching: `$env:CACHE_ENABLED = "false"`

### Database Locked Errors
- Ensure only one instance of the app is running
- Close any SQLite browser tools
- Check for zombie Python processes: `tasklist | findstr python`

### Permission Denied on Data Directory
```powershell
# Run PowerShell as Administrator
icacls "C:\ProgramData\FuturesTradingLog" /grant Users:F /t
```

---

## Updating the Application

```powershell
cd C:\Projects\FuturesTradingLog

# Stop the application/service first

# Pull latest changes
git pull origin main

# Update dependencies
.\venv\Scripts\Activate
pip install -r requirements.txt

# Restart the application
python app.py
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Start app | `python app.py` |
| Access UI | http://localhost:5000 |
| Health check | http://localhost:5000/health |
| View logs | `C:\ProgramData\FuturesTradingLog\logs\` |
| Database location | `C:\ProgramData\FuturesTradingLog\db\` |
| Config files | `C:\ProgramData\FuturesTradingLog\config\` |

---

## See Also

- [README.md](../README.md) - Main documentation
- [Docker deployment](../README.md#option-1-docker-recommended) - Recommended for production
- [NinjaTrader Setup](NINJASCRIPT_SETUP.md) - Auto-import from NinjaTrader
- [Windows Installer](../installer/README.md) - Pre-built Windows installer
