# Technical Specification

This is the technical specification for the spec detailed in @agent-os/specs/2025-12-27-windows-install-docs/spec.md

## Technical Requirements

### 1. Environment Variable Documentation

Document all environment variables with Windows-specific values:

| Variable | Docker Default | Windows Native Default | Description |
|----------|---------------|------------------------|-------------|
| `FLASK_ENV` | `production` | `production` | Environment mode |
| `FLASK_DEBUG` | `0` | `0` | Debug mode (0/1) |
| `FLASK_SECRET_KEY` | `dev-secret-key` | Generate with Python | Session encryption key |
| `FLASK_HOST` | `0.0.0.0` | `127.0.0.1` or `0.0.0.0` | Bind address |
| `FLASK_PORT` | `5000` | `5000` | HTTP port |
| `DATA_DIR` | `/app/data` | `C:\ProgramData\FuturesTradingLog` | Data storage root |
| `REDIS_URL` | `redis://redis:6379/0` | `redis://localhost:6379/0` | Redis connection |
| `CACHE_ENABLED` | `true` | `true` | Enable Redis caching |
| `CACHE_TTL_DAYS` | `14` | `14` | Cache retention |
| `DISCORD_WEBHOOK_URL` | *(empty)* | *(empty)* | Discord notifications |
| `AUTO_IMPORT_ENABLED` | `true` | `true` | NinjaTrader auto-import |
| `AUTO_IMPORT_INTERVAL` | `300` | `300` | Import check interval (seconds) |
| `HOST_IP` | `0.0.0.0` | `127.0.0.1` | Network bind IP |
| `EXTERNAL_PORT` | `5000` | `5000` | External access port |

### 2. File Path Structure

#### Generic Template Paths
```
C:\ProgramData\FuturesTradingLog\
├── db\
│   └── futures_trades_clean.db      # SQLite database
├── config\
│   └── instrument_multipliers.json  # Instrument settings
├── logs\
│   ├── app.log                      # Application logs
│   ├── app.log.1 ... app.log.5      # Rotated logs
│   ├── error.log                    # Error logs
│   └── flask.log                    # Flask-specific logs
├── charts\                          # Generated chart files
└── archive\                         # Archived data
```

#### Real-World Example Paths

**Development Setup:**
```
Project:     C:\Projects\FuturesTradingLog\
Data:        C:\Projects\FuturesTradingLog\data\
Virtual Env: C:\Projects\FuturesTradingLog\venv\
```

**Docker-Equivalent Native Setup:**
```
Project:     C:\Projects\FuturesTradingLog\
Data:        C:\Containers\FuturesTradingLog\data\
```

**Production-Style Setup:**
```
Project:     C:\Program Files\FuturesTradingLog\
Data:        C:\ProgramData\FuturesTradingLog\
```

### 3. Auto-Update System (Watchtower Equivalent)

Create PowerShell script: `scripts/windows-auto-update.ps1`

**Functionality:**
- Check GitHub releases API for new versions
- Compare with current installed version
- Download release assets if update available
- Stop Windows service
- Backup current installation
- Apply update
- Restart Windows service
- Log update status
- Optional Discord notification

**Task Scheduler Configuration:**
- Trigger: Daily at 3:00 AM (or custom interval)
- Action: Run PowerShell script
- Run whether user is logged on or not
- Run with highest privileges

### 4. Windows Service Configuration (NSSM)

**Service Installation Command:**
```powershell
nssm install FuturesTradingLog "C:\Projects\FuturesTradingLog\venv\Scripts\python.exe"
nssm set FuturesTradingLog AppDirectory "C:\Projects\FuturesTradingLog"
nssm set FuturesTradingLog AppParameters "app.py"
```

**Environment Variables (NSSM):**
```powershell
nssm set FuturesTradingLog AppEnvironmentExtra ^
    "FLASK_ENV=production" ^
    "FLASK_SECRET_KEY=your-secret-key" ^
    "DATA_DIR=C:\ProgramData\FuturesTradingLog" ^
    "REDIS_URL=redis://localhost:6379/0" ^
    "CACHE_ENABLED=true" ^
    "AUTO_IMPORT_ENABLED=true" ^
    "DISCORD_WEBHOOK_URL="
```

**Restart Policy (Docker Equivalent):**
```powershell
# Equivalent to restart: unless-stopped
nssm set FuturesTradingLog AppExit Default Restart
nssm set FuturesTradingLog AppRestartDelay 5000
```

**Logging Configuration:**
```powershell
nssm set FuturesTradingLog AppStdout "C:\ProgramData\FuturesTradingLog\logs\service_stdout.log"
nssm set FuturesTradingLog AppStderr "C:\ProgramData\FuturesTradingLog\logs\service_stderr.log"
nssm set FuturesTradingLog AppRotateFiles 1
nssm set FuturesTradingLog AppRotateBytes 10485760
```

### 5. Health Check (Docker Equivalent)

**Windows Scheduled Task for Health Monitoring:**
- Check `http://localhost:5000/health` every 30 seconds
- Restart service if 3 consecutive failures
- Log health check status

**PowerShell Health Check Script:**
```powershell
# scripts/health-check.ps1
$maxRetries = 3
$failCount = 0

while ($true) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:5000/health" -TimeoutSec 10
        if ($response.StatusCode -eq 200) {
            $failCount = 0
        }
    } catch {
        $failCount++
        if ($failCount -ge $maxRetries) {
            Restart-Service FuturesTradingLog
            $failCount = 0
        }
    }
    Start-Sleep -Seconds 30
}
```

### 6. Redis Service (Memurai)

**Installation Verification:**
```powershell
# Check Memurai service
Get-Service memurai

# Test connection
memurai-cli ping
```

**Configuration File Location:**
```
C:\Program Files\Memurai\memurai.conf
```

**Key Settings:**
```conf
maxmemory 256mb
port 6379
bind 127.0.0.1
```

## Files to Create/Update

| File | Action | Purpose |
|------|--------|---------|
| `docs/WINDOWS_INSTALL.md` | Update | Complete Windows installation guide |
| `scripts/windows-auto-update.ps1` | Create | Automated version updates |
| `scripts/health-check.ps1` | Create | Service health monitoring |
| `scripts/install-service.ps1` | Create | One-command service installation |
| `scripts/uninstall-service.ps1` | Create | Clean service removal |

## Integration with Existing Systems

- Uses existing `config.py` for path resolution
- Compatible with existing `.env` file format
- Maintains same database schema and migrations
- Works with existing Redis caching layer
- Integrates with Discord notification system
