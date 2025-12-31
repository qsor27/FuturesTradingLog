# Technical Spec: Windows Complete Uninstall Method

## Architecture Overview

The uninstall solution consists of a single PowerShell script with modular functions for component detection, backup, and removal.

```
uninstall-complete.ps1
├── Component Detection Functions
│   ├── Get-InstalledComponents
│   ├── Get-DataDirectoryInfo
│   └── Test-NssmInstalledByUs
├── Backup Functions
│   ├── Export-TradeData
│   ├── Backup-Database
│   └── Create-BackupArchive
├── Removal Functions
│   ├── Remove-WindowsService
│   ├── Remove-InstallationDirectory
│   ├── Remove-DataDirectory
│   ├── Remove-Nssm
│   └── Remove-ScheduledTasks
└── Main Orchestration
    ├── Show-DetectedComponents
    ├── Get-UserChoice
    └── Invoke-Uninstall
```

## Implementation Details

### 1. Component Detection

```powershell
function Get-InstalledComponents {
    return @{
        Service = Get-Service -Name $ServiceName -EA SilentlyContinue
        InstallPath = if (Test-Path $InstallPath) {
            Get-Item $InstallPath
        } else { $null }
        DataPath = if (Test-Path $DataPath) {
            Get-Item $DataPath
        } else { $null }
        Nssm = if (Test-Path $NssmPath) {
            Get-Item $NssmPath
        } else { $null }
        NssmInstalledByUs = Test-Path "$NssmPath\.installed-by-ftl"
        ScheduledTasks = Get-ScheduledTask -TaskName "FuturesTradingLog*" -EA SilentlyContinue
    }
}

function Get-DataDirectoryInfo {
    param([string]$Path)

    if (-not (Test-Path $Path)) { return $null }

    $DbPath = Join-Path $Path "db"
    $LogPath = Join-Path $Path "logs"
    $ConfigPath = Join-Path $Path "config"

    # Count trades in database
    $TradeCount = 0
    $DbFile = Join-Path $DbPath "futures_trades_clean.db"
    if (Test-Path $DbFile) {
        try {
            # Use sqlite3 or Python to count trades
            $VenvPython = Join-Path $InstallPath "venv\Scripts\python.exe"
            if (Test-Path $VenvPython) {
                $TradeCount = & $VenvPython -c "import sqlite3; conn = sqlite3.connect('$DbFile'); print(conn.execute('SELECT COUNT(*) FROM executions').fetchone()[0])"
            }
        } catch { }
    }

    return @{
        DatabaseSize = (Get-ChildItem $DbPath -Recurse -EA SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        LogsSize = (Get-ChildItem $LogPath -Recurse -EA SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        ConfigSize = (Get-ChildItem $ConfigPath -Recurse -EA SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        TradeCount = $TradeCount
    }
}
```

### 2. Backup Functions

```powershell
function Create-BackupArchive {
    param(
        [string]$DataPath,
        [string]$BackupLocation,
        [switch]$IncludeCsvExport
    )

    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $BackupName = "FuturesTradingLog_Backup_$Timestamp"
    $BackupDir = Join-Path $BackupLocation $BackupName

    # Create backup directory
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

    # Copy database
    $DbSource = Join-Path $DataPath "db"
    if (Test-Path $DbSource) {
        Copy-Item -Path $DbSource -Destination $BackupDir -Recurse
    }

    # Copy config
    $ConfigSource = Join-Path $DataPath "config"
    if (Test-Path $ConfigSource) {
        Copy-Item -Path $ConfigSource -Destination $BackupDir -Recurse
    }

    # Export to CSV if requested
    if ($IncludeCsvExport) {
        Export-TradeData -DataPath $DataPath -OutputPath (Join-Path $BackupDir "exports")
    }

    # Create ZIP archive
    $ZipPath = "$BackupDir.zip"
    Compress-Archive -Path $BackupDir -DestinationPath $ZipPath

    # Clean up temp directory
    Remove-Item -Path $BackupDir -Recurse -Force

    return $ZipPath
}

function Export-TradeData {
    param(
        [string]$DataPath,
        [string]$OutputPath
    )

    New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null

    $DbFile = Join-Path $DataPath "db\futures_trades_clean.db"
    if (-not (Test-Path $DbFile)) { return }

    $VenvPython = Join-Path $InstallPath "venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) { return }

    # Export using Python script
    $ExportScript = @"
import sqlite3
import csv
import os

db_path = r'$DbFile'
output_path = r'$OutputPath'

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Export executions
with open(os.path.join(output_path, 'executions.csv'), 'w', newline='') as f:
    cursor = conn.execute('SELECT * FROM executions ORDER BY trade_date, entry_time')
    writer = csv.writer(f)
    writer.writerow([d[0] for d in cursor.description])
    writer.writerows(cursor.fetchall())

# Export positions
with open(os.path.join(output_path, 'positions.csv'), 'w', newline='') as f:
    cursor = conn.execute('SELECT * FROM positions ORDER BY entry_date')
    writer = csv.writer(f)
    writer.writerow([d[0] for d in cursor.description])
    writer.writerows(cursor.fetchall())

conn.close()
print('Export complete')
"@

    $ExportScript | & $VenvPython -
}
```

### 3. Removal Functions

```powershell
function Remove-WindowsService {
    param([string]$ServiceName, [string]$NssmPath)

    $Service = Get-Service -Name $ServiceName -EA SilentlyContinue
    if (-not $Service) { return $true }

    # Stop service if running
    if ($Service.Status -eq 'Running') {
        Stop-Service -Name $ServiceName -Force
        Start-Sleep -Seconds 5
    }

    # Remove using NSSM or sc.exe
    if (Test-Path $NssmPath) {
        & $NssmPath remove $ServiceName confirm
    } else {
        sc.exe delete $ServiceName
    }

    Start-Sleep -Seconds 2

    # Verify removal
    $Service = Get-Service -Name $ServiceName -EA SilentlyContinue
    return ($null -eq $Service)
}

function Remove-InstallationDirectory {
    param([string]$Path)

    if (-not (Test-Path $Path)) { return $true }

    # Kill any Python processes from our venv
    $VenvPython = Join-Path $Path "venv\Scripts\python.exe"
    Get-Process python -EA SilentlyContinue | Where-Object {
        $_.Path -eq $VenvPython
    } | Stop-Process -Force

    Start-Sleep -Seconds 2

    # Remove directory
    Remove-Item -Path $Path -Recurse -Force -EA SilentlyContinue

    return (-not (Test-Path $Path))
}

function Remove-ScheduledTasks {
    $Tasks = Get-ScheduledTask -TaskName "FuturesTradingLog*" -EA SilentlyContinue
    foreach ($Task in $Tasks) {
        Unregister-ScheduledTask -TaskName $Task.TaskName -Confirm:$false
    }
    return $true
}

function Remove-Nssm {
    param([string]$NssmPath)

    # Only remove if we installed it
    $MarkerFile = Join-Path (Split-Path $NssmPath) ".installed-by-ftl"
    if (-not (Test-Path $MarkerFile)) {
        return @{
            Removed = $false
            Reason = "Not installed by FuturesTradingLog setup"
        }
    }

    # Check if other services use NSSM
    $OtherServices = Get-CimInstance Win32_Service | Where-Object {
        $_.PathName -like "*nssm*" -and $_.Name -ne "FuturesTradingLog"
    }

    if ($OtherServices) {
        return @{
            Removed = $false
            Reason = "Used by other services: $($OtherServices.Name -join ', ')"
        }
    }

    # Safe to remove
    $NssmDir = Split-Path $NssmPath
    Remove-Item -Path $NssmDir -Recurse -Force

    return @{
        Removed = $true
        Reason = "Removed successfully"
    }
}
```

### 4. Main Orchestration

```powershell
function Show-DetectedComponents {
    param($Components, $DataInfo)

    Write-Host ""
    Write-Host "Detected Components:" -ForegroundColor Cyan

    # Service
    if ($Components.Service) {
        $Status = $Components.Service.Status
        Write-Host "  [x] Windows Service: $ServiceName ($Status)" -ForegroundColor White
    }

    # Installation
    if ($Components.InstallPath) {
        $Size = (Get-ChildItem $InstallPath -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
        Write-Host "  [x] Installation: $InstallPath ($('{0:N1}' -f $Size) MB)" -ForegroundColor White
    }

    # Data Directory
    if ($Components.DataPath) {
        Write-Host "  [x] Data Directory: $DataPath" -ForegroundColor White
        if ($DataInfo) {
            Write-Host "      - Database: $('{0:N1}' -f ($DataInfo.DatabaseSize / 1MB)) MB ($($DataInfo.TradeCount) trades)" -ForegroundColor Gray
            Write-Host "      - Logs: $('{0:N1}' -f ($DataInfo.LogsSize / 1MB)) MB" -ForegroundColor Gray
            Write-Host "      - Config: $('{0:N1}' -f ($DataInfo.ConfigSize / 1KB)) KB" -ForegroundColor Gray
        }
    }

    # NSSM
    if ($Components.Nssm) {
        $Marker = if ($Components.NssmInstalledByUs) { "(installed by FTL)" } else { "(shared)" }
        Write-Host "  [x] NSSM: $NssmPath $Marker" -ForegroundColor White
    }

    # Shared dependencies (informational)
    Write-Host "  [ ] Python (shared - will not be removed)" -ForegroundColor DarkGray
    Write-Host "  [ ] Git (shared - will not be removed)" -ForegroundColor DarkGray
    Write-Host "  [ ] Memurai/Redis (shared - will not be removed)" -ForegroundColor DarkGray
}

function Get-UserChoice {
    Write-Host ""
    Write-Host "Choose uninstall option:" -ForegroundColor Yellow
    Write-Host "  1. Keep my data (remove app only)"
    Write-Host "  2. Export data, then remove everything"
    Write-Host "  3. Remove everything (WARNING: data will be lost)"
    Write-Host "  4. Cancel"
    Write-Host ""

    do {
        $Choice = Read-Host "Selection (1-4)"
    } while ($Choice -notmatch '^[1-4]$')

    return [int]$Choice
}
```

## File Structure

```
scripts/
├── uninstall-complete.ps1     # NEW: Complete uninstall script
├── uninstall-service.ps1      # EXISTING: Service-only removal
├── install-service.ps1        # EXISTING: Service installation
├── setup-windows.ps1          # EXISTING: Full setup (modify to add marker)
├── windows-auto-update.ps1    # EXISTING: Auto-update
└── health-check.ps1           # EXISTING: Health monitoring
```

## Changes to Existing Files

### setup-windows.ps1

Add NSSM marker file creation:

```powershell
# After NSSM installation succeeds
$MarkerFile = Join-Path "C:\nssm" ".installed-by-ftl"
"Installed by FuturesTradingLog setup on $(Get-Date)" | Set-Content $MarkerFile
```

## Configuration

### Default Paths

| Path | Default Value |
|------|---------------|
| InstallPath | C:\Program Files\FuturesTradingLog |
| DataPath | C:\ProgramData\FuturesTradingLog |
| NssmPath | C:\nssm\nssm.exe |
| BackupPath | Desktop\FuturesTradingLog_Backups |

### Script Parameters

```powershell
param(
    [string]$InstallPath = "C:\Program Files\FuturesTradingLog",
    [string]$DataPath = "C:\ProgramData\FuturesTradingLog",
    [string]$NssmPath = "C:\nssm\nssm.exe",
    [string]$BackupPath = "$env:USERPROFILE\Desktop",
    [switch]$Force,      # Skip confirmations (for automation)
    [switch]$KeepData,   # Preserve data (non-interactive mode)
    [switch]$RemoveAll   # Remove everything (non-interactive mode)
)
```

## Error Handling

| Error | Handling |
|-------|----------|
| Not Administrator | Exit with clear message |
| Service won't stop | Attempt taskkill, warn user |
| Directory in use | Identify locking process, offer to kill |
| Database locked | Wait and retry, then warn |
| Backup failed | Cancel uninstall, preserve data |
| Partial removal | Log remaining items, provide manual steps |

## Logging

Log file location: `%USERPROFILE%\FuturesTradingLog_Uninstall.log`

The log persists after uninstall to allow troubleshooting if issues arise.

```
[2025-12-31 14:30:00] [INFO] FuturesTradingLog Uninstaller Started
[2025-12-31 14:30:00] [INFO] Install Path: C:\Program Files\FuturesTradingLog
[2025-12-31 14:30:00] [INFO] Data Path: C:\ProgramData\FuturesTradingLog
[2025-12-31 14:30:01] [INFO] Detected: Windows Service (Running)
[2025-12-31 14:30:01] [INFO] Detected: Installation (245.3 MB)
[2025-12-31 14:30:01] [INFO] Detected: Data Directory (17.5 MB, 1234 trades)
[2025-12-31 14:30:05] [INFO] User selected: Export data, then remove everything
[2025-12-31 14:30:06] [INFO] Creating backup archive...
[2025-12-31 14:30:15] [SUCCESS] Backup created: C:\Users\...\Desktop\FuturesTradingLog_Backup_20251231_143015.zip
[2025-12-31 14:30:16] [INFO] Stopping Windows Service...
[2025-12-31 14:30:21] [SUCCESS] Service stopped
[2025-12-31 14:30:22] [INFO] Removing Windows Service...
[2025-12-31 14:30:24] [SUCCESS] Service removed
...
```

## Testing Considerations

1. **Test on clean install**: Verify detection of all components
2. **Test partial install**: Missing NSSM, missing data dir
3. **Test backup integrity**: Verify backup can be restored
4. **Test CSV export**: Verify data is properly exported
5. **Test shared NSSM**: Verify NSSM not removed when used by other services
6. **Test locked files**: Simulate locked database, verify handling
