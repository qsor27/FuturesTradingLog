<#
.SYNOPSIS
    Complete uninstaller for FuturesTradingLog on Windows

.DESCRIPTION
    This script completely removes FuturesTradingLog and all its components from Windows.
    It provides options to preserve or export user data before removal.

    Components removed:
    - Windows Service (FuturesTradingLog)
    - Installation directory (includes Python virtual environment)
    - Data directory (optional - database, logs, config)
    - NSSM (optional - only if installed by our setup)
    - Scheduled tasks

    Components NOT removed (shared):
    - Python
    - Git
    - Memurai/Redis

.PARAMETER InstallPath
    Path to the FuturesTradingLog installation directory
    Default: C:\Program Files\FuturesTradingLog

.PARAMETER DataPath
    Path to the data directory
    Default: C:\ProgramData\FuturesTradingLog

.PARAMETER NssmPath
    Path to NSSM executable
    Default: C:\nssm\nssm.exe

.PARAMETER BackupPath
    Path where backups will be saved
    Default: User's Desktop

.PARAMETER ServiceName
    Name of the Windows service
    Default: FuturesTradingLog

.PARAMETER Force
    Skip all confirmations (for automation)

.PARAMETER KeepData
    Non-interactive mode: preserve data directory

.PARAMETER RemoveAll
    Non-interactive mode: remove everything including data

.EXAMPLE
    .\uninstall-complete.ps1

.EXAMPLE
    .\uninstall-complete.ps1 -RemoveAll -Force

.EXAMPLE
    .\uninstall-complete.ps1 -KeepData

.NOTES
    Requires: Administrator privileges
    Version: 1.0.0
#>

[CmdletBinding()]
param(
    [string]$InstallPath = "C:\Program Files\FuturesTradingLog",
    [string]$DataPath = "C:\ProgramData\FuturesTradingLog",
    [string]$NssmPath = "C:\nssm\nssm.exe",
    [string]$BackupPath = "$env:USERPROFILE\Desktop",
    [string]$ServiceName = "FuturesTradingLog",
    [switch]$Force,
    [switch]$KeepData,
    [switch]$RemoveAll
)

$ErrorActionPreference = "Stop"
$Script:LogFile = "$env:USERPROFILE\FuturesTradingLog_Uninstall.log"

#region Utility Functions

function Test-Administrator {
    $CurrentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = New-Object Security.Principal.WindowsPrincipal($CurrentUser)
    return $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO"
    )
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogEntry = "[$Timestamp] [$Level] $Message"

    # Append to log file
    Add-Content -Path $Script:LogFile -Value $LogEntry -ErrorAction SilentlyContinue

    # Console output with color
    $Color = switch ($Level) {
        "ERROR"   { "Red" }
        "WARN"    { "Yellow" }
        "SUCCESS" { "Green" }
        "STEP"    { "Cyan" }
        default   { "White" }
    }
    Write-Host $LogEntry -ForegroundColor $Color
}

function Format-FileSize {
    param([long]$Bytes)
    if ($Bytes -ge 1GB) { return "{0:N2} GB" -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return "{0:N2} MB" -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return "{0:N2} KB" -f ($Bytes / 1KB) }
    return "$Bytes bytes"
}

#endregion

#region Component Detection Functions

function Get-InstalledComponents {
    $Components = @{
        Service = $null
        ServiceStatus = $null
        InstallPath = $null
        InstallSize = 0
        DataPath = $null
        DataInfo = $null
        Nssm = $null
        NssmInstalledByUs = $false
        ScheduledTasks = @()
        VenvPython = $null
    }

    # Check Windows Service
    $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($Service) {
        $Components.Service = $Service
        $Components.ServiceStatus = $Service.Status
    }

    # Check Installation Directory
    if (Test-Path $InstallPath) {
        $Components.InstallPath = $InstallPath
        $Components.InstallSize = (Get-ChildItem $InstallPath -Recurse -ErrorAction SilentlyContinue |
                                   Measure-Object -Property Length -Sum).Sum

        # Check for venv Python
        $VenvPython = Join-Path $InstallPath "venv\Scripts\python.exe"
        if (Test-Path $VenvPython) {
            $Components.VenvPython = $VenvPython
        }
    }

    # Check Data Directory
    if (Test-Path $DataPath) {
        $Components.DataPath = $DataPath
        $Components.DataInfo = Get-DataDirectoryInfo -Path $DataPath -VenvPython $Components.VenvPython
    }

    # Check NSSM
    if (Test-Path $NssmPath) {
        $Components.Nssm = $NssmPath
        $MarkerFile = Join-Path (Split-Path $NssmPath) ".installed-by-ftl"
        $Components.NssmInstalledByUs = Test-Path $MarkerFile
    }

    # Check Scheduled Tasks
    $Tasks = Get-ScheduledTask -TaskName "FuturesTradingLog*" -ErrorAction SilentlyContinue
    if ($Tasks) {
        $Components.ScheduledTasks = @($Tasks)
    }

    return $Components
}

function Get-DataDirectoryInfo {
    param(
        [string]$Path,
        [string]$VenvPython
    )

    if (-not (Test-Path $Path)) { return $null }

    $DbPath = Join-Path $Path "db"
    $LogPath = Join-Path $Path "logs"
    $ConfigPath = Join-Path $Path "config"

    $Info = @{
        DatabaseSize = 0
        LogsSize = 0
        ConfigSize = 0
        TradeCount = 0
        PositionCount = 0
    }

    # Calculate sizes
    if (Test-Path $DbPath) {
        $Info.DatabaseSize = (Get-ChildItem $DbPath -Recurse -ErrorAction SilentlyContinue |
                              Measure-Object -Property Length -Sum).Sum
    }
    if (Test-Path $LogPath) {
        $Info.LogsSize = (Get-ChildItem $LogPath -Recurse -ErrorAction SilentlyContinue |
                          Measure-Object -Property Length -Sum).Sum
    }
    if (Test-Path $ConfigPath) {
        $Info.ConfigSize = (Get-ChildItem $ConfigPath -Recurse -ErrorAction SilentlyContinue |
                            Measure-Object -Property Length -Sum).Sum
    }

    # Count trades using Python/sqlite
    $DbFile = Join-Path $DbPath "futures_trades_clean.db"
    if ((Test-Path $DbFile) -and $VenvPython -and (Test-Path $VenvPython)) {
        try {
            $CountScript = @"
import sqlite3
try:
    conn = sqlite3.connect(r'$DbFile')
    trades = conn.execute('SELECT COUNT(*) FROM executions').fetchone()[0]
    positions = conn.execute('SELECT COUNT(*) FROM positions').fetchone()[0]
    print(f'{trades},{positions}')
    conn.close()
except:
    print('0,0')
"@
            $Result = $CountScript | & $VenvPython - 2>$null
            if ($Result -match '^(\d+),(\d+)$') {
                $Info.TradeCount = [int]$Matches[1]
                $Info.PositionCount = [int]$Matches[2]
            }
        } catch {
            # Ignore errors in counting
        }
    }

    return $Info
}

#endregion

#region Backup Functions

function Export-TradeData {
    param(
        [string]$DataPath,
        [string]$OutputPath,
        [string]$VenvPython
    )

    if (-not (Test-Path $OutputPath)) {
        New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null
    }

    $DbFile = Join-Path $DataPath "db\futures_trades_clean.db"
    if (-not (Test-Path $DbFile)) {
        Write-Log "Database not found, skipping CSV export" "WARN"
        return $false
    }

    if (-not $VenvPython -or -not (Test-Path $VenvPython)) {
        Write-Log "Python not available, skipping CSV export" "WARN"
        return $false
    }

    Write-Log "Exporting trade data to CSV..."

    $ExportScript = @"
import sqlite3
import csv
import os

db_path = r'$DbFile'
output_path = r'$OutputPath'

try:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Export executions
    executions_file = os.path.join(output_path, 'executions.csv')
    with open(executions_file, 'w', newline='', encoding='utf-8') as f:
        cursor = conn.execute('SELECT * FROM executions ORDER BY trade_date, entry_time')
        rows = cursor.fetchall()
        if rows:
            writer = csv.writer(f)
            writer.writerow([d[0] for d in cursor.description])
            writer.writerows(rows)
    print(f'Exported {len(rows)} executions')

    # Export positions
    positions_file = os.path.join(output_path, 'positions.csv')
    with open(positions_file, 'w', newline='', encoding='utf-8') as f:
        cursor = conn.execute('SELECT * FROM positions ORDER BY entry_date')
        rows = cursor.fetchall()
        if rows:
            writer = csv.writer(f)
            writer.writerow([d[0] for d in cursor.description])
            writer.writerows(rows)
    print(f'Exported {len(rows)} positions')

    conn.close()
    print('SUCCESS')
except Exception as e:
    print(f'ERROR: {e}')
"@

    try {
        $Result = $ExportScript | & $VenvPython - 2>&1
        Write-Log ($Result -join "`n")
        return $Result -match 'SUCCESS'
    } catch {
        Write-Log "CSV export failed: $_" "ERROR"
        return $false
    }
}

function Create-BackupArchive {
    param(
        [string]$DataPath,
        [string]$BackupLocation,
        [string]$VenvPython,
        [switch]$IncludeCsvExport
    )

    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $BackupName = "FuturesTradingLog_Backup_$Timestamp"
    $BackupDir = Join-Path $BackupLocation $BackupName

    Write-Log "Creating backup: $BackupDir" "STEP"

    # Create backup directory
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

    # Copy database
    $DbSource = Join-Path $DataPath "db"
    if (Test-Path $DbSource) {
        Write-Log "Backing up database..."
        Copy-Item -Path $DbSource -Destination (Join-Path $BackupDir "db") -Recurse
    }

    # Copy config
    $ConfigSource = Join-Path $DataPath "config"
    if (Test-Path $ConfigSource) {
        Write-Log "Backing up configuration..."
        Copy-Item -Path $ConfigSource -Destination (Join-Path $BackupDir "config") -Recurse
    }

    # Export to CSV if requested
    if ($IncludeCsvExport) {
        $ExportsDir = Join-Path $BackupDir "csv_exports"
        Export-TradeData -DataPath $DataPath -OutputPath $ExportsDir -VenvPython $VenvPython
    }

    # Create info file
    $InfoContent = @"
FuturesTradingLog Backup
========================
Created: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Source: $DataPath

Contents:
- db/: SQLite database files
- config/: Configuration files
$(if ($IncludeCsvExport) { "- csv_exports/: Trade data in CSV format" })

To restore:
1. Install FuturesTradingLog
2. Copy the 'db' folder to your DATA_DIR\db
3. Copy the 'config' folder to your DATA_DIR\config
"@
    $InfoContent | Set-Content (Join-Path $BackupDir "README.txt")

    # Create ZIP archive
    $ZipPath = "$BackupDir.zip"
    Write-Log "Creating ZIP archive..."

    try {
        Compress-Archive -Path $BackupDir -DestinationPath $ZipPath -Force

        # Clean up temp directory
        Remove-Item -Path $BackupDir -Recurse -Force

        Write-Log "Backup created: $ZipPath" "SUCCESS"
        return $ZipPath
    } catch {
        Write-Log "Failed to create ZIP archive: $_" "ERROR"
        return $BackupDir  # Return unzipped directory if ZIP fails
    }
}

#endregion

#region Removal Functions

function Remove-WindowsService {
    Write-Log "Removing Windows Service..." "STEP"

    $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $Service) {
        Write-Log "Service not found, skipping"
        return $true
    }

    # Stop service if running
    if ($Service.Status -eq 'Running') {
        Write-Log "Stopping service..."
        try {
            Stop-Service -Name $ServiceName -Force -ErrorAction Stop
            Start-Sleep -Seconds 5
            Write-Log "Service stopped"
        } catch {
            Write-Log "Failed to stop service gracefully, attempting taskkill..." "WARN"
            # Try to find and kill the process
            $ServiceWmi = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'" -ErrorAction SilentlyContinue
            if ($ServiceWmi -and $ServiceWmi.ProcessId) {
                Stop-Process -Id $ServiceWmi.ProcessId -Force -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 3
            }
        }
    }

    # Remove using NSSM if available, otherwise sc.exe
    if (Test-Path $NssmPath) {
        Write-Log "Removing service with NSSM..."
        & $NssmPath remove $ServiceName confirm 2>&1 | Out-Null
    } else {
        Write-Log "Removing service with sc.exe..."
        sc.exe delete $ServiceName 2>&1 | Out-Null
    }

    Start-Sleep -Seconds 2

    # Verify removal
    $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($Service) {
        Write-Log "Service still exists, may require reboot" "WARN"
        return $false
    }

    Write-Log "Service removed" "SUCCESS"
    return $true
}

function Remove-InstallationDirectory {
    Write-Log "Removing installation directory..." "STEP"

    if (-not (Test-Path $InstallPath)) {
        Write-Log "Installation directory not found, skipping"
        return $true
    }

    # Kill any Python processes from our venv
    $VenvPython = Join-Path $InstallPath "venv\Scripts\python.exe"
    if (Test-Path $VenvPython) {
        Write-Log "Stopping any running Python processes..."
        Get-Process python -ErrorAction SilentlyContinue | Where-Object {
            $_.Path -eq $VenvPython
        } | ForEach-Object {
            Write-Log "Killing process: $($_.Id)"
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 2
    }

    # Remove directory
    try {
        Remove-Item -Path $InstallPath -Recurse -Force -ErrorAction Stop
        Write-Log "Installation directory removed" "SUCCESS"
        return $true
    } catch {
        Write-Log "Failed to remove installation directory: $_" "ERROR"
        Write-Log "Some files may be locked. Try closing any open files and run again." "WARN"
        return $false
    }
}

function Remove-DataDirectory {
    Write-Log "Removing data directory..." "STEP"

    if (-not (Test-Path $DataPath)) {
        Write-Log "Data directory not found, skipping"
        return $true
    }

    try {
        Remove-Item -Path $DataPath -Recurse -Force -ErrorAction Stop
        Write-Log "Data directory removed" "SUCCESS"
        return $true
    } catch {
        Write-Log "Failed to remove data directory: $_" "ERROR"
        return $false
    }
}

function Remove-ScheduledTasks {
    Write-Log "Removing scheduled tasks..." "STEP"

    $Tasks = Get-ScheduledTask -TaskName "FuturesTradingLog*" -ErrorAction SilentlyContinue
    if (-not $Tasks) {
        Write-Log "No scheduled tasks found, skipping"
        return $true
    }

    $AllRemoved = $true
    foreach ($Task in $Tasks) {
        try {
            Write-Log "Removing task: $($Task.TaskName)"
            Unregister-ScheduledTask -TaskName $Task.TaskName -Confirm:$false -ErrorAction Stop
        } catch {
            Write-Log "Failed to remove task $($Task.TaskName): $_" "WARN"
            $AllRemoved = $false
        }
    }

    if ($AllRemoved) {
        Write-Log "All scheduled tasks removed" "SUCCESS"
    }
    return $AllRemoved
}

function Remove-Nssm {
    Write-Log "Checking NSSM removal..." "STEP"

    if (-not (Test-Path $NssmPath)) {
        Write-Log "NSSM not found, skipping"
        return @{ Removed = $true; Reason = "Not installed" }
    }

    $NssmDir = Split-Path $NssmPath
    $MarkerFile = Join-Path $NssmDir ".installed-by-ftl"

    # Only remove if we installed it
    if (-not (Test-Path $MarkerFile)) {
        Write-Log "NSSM was not installed by FuturesTradingLog setup, preserving" "WARN"
        return @{ Removed = $false; Reason = "Not installed by FuturesTradingLog" }
    }

    # Check if other services use NSSM
    $OtherServices = Get-CimInstance Win32_Service -ErrorAction SilentlyContinue | Where-Object {
        $_.PathName -like "*nssm*" -and $_.Name -ne $ServiceName
    }

    if ($OtherServices) {
        $ServiceNames = ($OtherServices | Select-Object -ExpandProperty Name) -join ", "
        Write-Log "NSSM is used by other services ($ServiceNames), preserving" "WARN"
        return @{ Removed = $false; Reason = "Used by: $ServiceNames" }
    }

    # Safe to remove
    try {
        Remove-Item -Path $NssmDir -Recurse -Force -ErrorAction Stop
        Write-Log "NSSM removed" "SUCCESS"
        return @{ Removed = $true; Reason = "Removed successfully" }
    } catch {
        Write-Log "Failed to remove NSSM: $_" "ERROR"
        return @{ Removed = $false; Reason = "Removal failed: $_" }
    }
}

#endregion

#region Interactive UI Functions

function Show-Header {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "   FuturesTradingLog - Complete Uninstaller" -ForegroundColor Cyan
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Show-DetectedComponents {
    param($Components)

    Write-Host "Detected Components:" -ForegroundColor Cyan
    Write-Host ""

    # Service
    if ($Components.Service) {
        $StatusColor = if ($Components.ServiceStatus -eq 'Running') { "Green" } else { "Yellow" }
        Write-Host "  [x] Windows Service: $ServiceName " -NoNewline
        Write-Host "($($Components.ServiceStatus))" -ForegroundColor $StatusColor
    } else {
        Write-Host "  [ ] Windows Service: Not installed" -ForegroundColor DarkGray
    }

    # Installation
    if ($Components.InstallPath) {
        $Size = Format-FileSize $Components.InstallSize
        Write-Host "  [x] Installation: $($Components.InstallPath) ($Size)"
    } else {
        Write-Host "  [ ] Installation: Not found" -ForegroundColor DarkGray
    }

    # Data Directory
    if ($Components.DataPath -and $Components.DataInfo) {
        Write-Host "  [x] Data Directory: $($Components.DataPath)"
        $DbSize = Format-FileSize $Components.DataInfo.DatabaseSize
        $LogSize = Format-FileSize $Components.DataInfo.LogsSize
        $ConfigSize = Format-FileSize $Components.DataInfo.ConfigSize
        Write-Host "      - Database: $DbSize ($($Components.DataInfo.TradeCount) trades, $($Components.DataInfo.PositionCount) positions)" -ForegroundColor Gray
        Write-Host "      - Logs: $LogSize" -ForegroundColor Gray
        Write-Host "      - Config: $ConfigSize" -ForegroundColor Gray
    } elseif ($Components.DataPath) {
        Write-Host "  [x] Data Directory: $($Components.DataPath)"
    } else {
        Write-Host "  [ ] Data Directory: Not found" -ForegroundColor DarkGray
    }

    # NSSM
    if ($Components.Nssm) {
        $Marker = if ($Components.NssmInstalledByUs) { "(installed by FTL - will be removed)" } else { "(shared - will be preserved)" }
        Write-Host "  [x] NSSM: $($Components.Nssm) " -NoNewline
        Write-Host $Marker -ForegroundColor $(if ($Components.NssmInstalledByUs) { "Yellow" } else { "DarkGray" })
    } else {
        Write-Host "  [ ] NSSM: Not installed" -ForegroundColor DarkGray
    }

    # Scheduled Tasks
    if ($Components.ScheduledTasks.Count -gt 0) {
        Write-Host "  [x] Scheduled Tasks: $($Components.ScheduledTasks.Count) task(s)"
        foreach ($Task in $Components.ScheduledTasks) {
            Write-Host "      - $($Task.TaskName)" -ForegroundColor Gray
        }
    } else {
        Write-Host "  [ ] Scheduled Tasks: None" -ForegroundColor DarkGray
    }

    # Shared dependencies (informational)
    Write-Host ""
    Write-Host "  Shared dependencies (will NOT be removed):" -ForegroundColor DarkGray
    Write-Host "  [ ] Python (check: python --version)" -ForegroundColor DarkGray
    Write-Host "  [ ] Git (check: git --version)" -ForegroundColor DarkGray
    Write-Host "  [ ] Memurai/Redis (check: Get-Service Memurai)" -ForegroundColor DarkGray
}

function Get-UserChoice {
    Write-Host ""
    Write-Host "Choose uninstall option:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  1. Keep my data (remove app only)"
    Write-Host "  2. Export data to backup, then remove everything"
    Write-Host "  3. Remove everything " -NoNewline
    Write-Host "(WARNING: data will be lost)" -ForegroundColor Red
    Write-Host "  4. Cancel"
    Write-Host ""

    do {
        $Choice = Read-Host "Selection (1-4)"
    } while ($Choice -notmatch '^[1-4]$')

    return [int]$Choice
}

function Confirm-Action {
    param([string]$Message)

    if ($Force) { return $true }

    Write-Host ""
    Write-Host $Message -ForegroundColor Yellow
    $Confirm = Read-Host "Type 'YES' to confirm"
    return ($Confirm -eq 'YES')
}

#endregion

#region Main Orchestration

function Invoke-Uninstall {
    param(
        [int]$Option,
        $Components
    )

    $Results = @{
        ServiceRemoved = $false
        InstallRemoved = $false
        DataRemoved = $false
        TasksRemoved = $false
        NssmResult = $null
        BackupPath = $null
    }

    Write-Host ""
    Write-Log "=========================================="
    Write-Log "Starting uninstall (Option $Option)"
    Write-Log "=========================================="

    # Handle data backup/export for option 2
    if ($Option -eq 2 -and $Components.DataPath) {
        $Results.BackupPath = Create-BackupArchive `
            -DataPath $DataPath `
            -BackupLocation $BackupPath `
            -VenvPython $Components.VenvPython `
            -IncludeCsvExport

        if (-not $Results.BackupPath) {
            Write-Log "Backup failed! Aborting uninstall to preserve data." "ERROR"
            return $Results
        }
    }

    # Remove Windows Service
    if ($Components.Service) {
        $Results.ServiceRemoved = Remove-WindowsService
    } else {
        $Results.ServiceRemoved = $true
    }

    # Remove Scheduled Tasks
    $Results.TasksRemoved = Remove-ScheduledTasks

    # Remove Installation Directory
    if ($Components.InstallPath) {
        $Results.InstallRemoved = Remove-InstallationDirectory
    } else {
        $Results.InstallRemoved = $true
    }

    # Remove Data Directory (options 2 and 3 only)
    if ($Option -ge 2 -and $Components.DataPath) {
        $Results.DataRemoved = Remove-DataDirectory
    } elseif ($Option -eq 1) {
        Write-Log "Data directory preserved: $DataPath"
        $Results.DataRemoved = $false  # Not removed by design
    } else {
        $Results.DataRemoved = $true
    }

    # Remove NSSM if we installed it
    if ($Components.Nssm -and $Components.NssmInstalledByUs) {
        $Results.NssmResult = Remove-Nssm
    }

    return $Results
}

function Show-Summary {
    param($Results, $Option)

    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "   Uninstall Summary" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""

    # Results
    $StatusIcon = { param($Success) if ($Success) { "[OK]" } else { "[!!]" } }
    $StatusColor = { param($Success) if ($Success) { "Green" } else { "Red" } }

    Write-Host "  Windows Service: " -NoNewline
    Write-Host (& $StatusIcon $Results.ServiceRemoved) -ForegroundColor (& $StatusColor $Results.ServiceRemoved)

    Write-Host "  Installation Dir: " -NoNewline
    Write-Host (& $StatusIcon $Results.InstallRemoved) -ForegroundColor (& $StatusColor $Results.InstallRemoved)

    Write-Host "  Scheduled Tasks: " -NoNewline
    Write-Host (& $StatusIcon $Results.TasksRemoved) -ForegroundColor (& $StatusColor $Results.TasksRemoved)

    if ($Option -eq 1) {
        Write-Host "  Data Directory: " -NoNewline
        Write-Host "[PRESERVED]" -ForegroundColor Yellow
        Write-Host "    Location: $DataPath" -ForegroundColor Gray
    } else {
        Write-Host "  Data Directory: " -NoNewline
        Write-Host (& $StatusIcon $Results.DataRemoved) -ForegroundColor (& $StatusColor $Results.DataRemoved)
    }

    if ($Results.NssmResult) {
        Write-Host "  NSSM: " -NoNewline
        if ($Results.NssmResult.Removed) {
            Write-Host "[OK]" -ForegroundColor Green
        } else {
            Write-Host "[PRESERVED] $($Results.NssmResult.Reason)" -ForegroundColor Yellow
        }
    }

    if ($Results.BackupPath) {
        Write-Host ""
        Write-Host "  Backup Location:" -ForegroundColor Cyan
        Write-Host "    $($Results.BackupPath)" -ForegroundColor White
    }

    Write-Host ""
    Write-Host "  Log file: $Script:LogFile" -ForegroundColor Gray

    # Reinstall info
    Write-Host ""
    Write-Host "To reinstall FuturesTradingLog:" -ForegroundColor Cyan
    Write-Host "  1. Download from: https://github.com/qsor27/FuturesTradingLog"
    Write-Host "  2. Run: .\scripts\setup-windows.ps1"
    Write-Host "  3. Run: .\scripts\install-service.ps1"
    Write-Host ""
}

#endregion

#region Main Entry Point

function Main {
    # Initialize log
    Write-Log "=========================================="
    Write-Log "FuturesTradingLog Uninstaller Started"
    Write-Log "Install Path: $InstallPath"
    Write-Log "Data Path: $DataPath"
    Write-Log "=========================================="

    # Check Administrator
    if (-not (Test-Administrator)) {
        Write-Host ""
        Write-Host "ERROR: This script requires administrator privileges." -ForegroundColor Red
        Write-Host ""
        Write-Host "Please run PowerShell as Administrator:" -ForegroundColor Yellow
        Write-Host "  1. Right-click PowerShell"
        Write-Host "  2. Select 'Run as administrator'"
        Write-Host "  3. Run this script again"
        Write-Host ""
        Write-Log "Aborted: Not running as administrator" "ERROR"
        exit 1
    }

    Show-Header

    # Detect components
    Write-Host "Scanning for installed components..." -ForegroundColor Gray
    $Components = Get-InstalledComponents

    # Check if anything is installed
    $HasComponents = $Components.Service -or $Components.InstallPath -or $Components.DataPath
    if (-not $HasComponents) {
        Write-Host "No FuturesTradingLog components found." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Checked locations:"
        Write-Host "  - Service: $ServiceName"
        Write-Host "  - Install: $InstallPath"
        Write-Host "  - Data: $DataPath"
        Write-Host ""
        Write-Log "No components found to uninstall"
        exit 0
    }

    Show-DetectedComponents -Components $Components

    # Determine option
    $Option = 0
    if ($KeepData) {
        $Option = 1
        Write-Log "Non-interactive mode: KeepData"
    } elseif ($RemoveAll) {
        $Option = 3
        Write-Log "Non-interactive mode: RemoveAll"
    } else {
        $Option = Get-UserChoice
    }

    Write-Log "User selected option: $Option"

    # Handle cancel
    if ($Option -eq 4) {
        Write-Host ""
        Write-Host "Uninstall cancelled." -ForegroundColor Yellow
        Write-Log "Uninstall cancelled by user"
        exit 0
    }

    # Confirm destructive actions
    if ($Option -eq 3) {
        if (-not (Confirm-Action "This will permanently delete ALL data including your trade history. This cannot be undone!")) {
            Write-Host "Uninstall cancelled." -ForegroundColor Yellow
            Write-Log "Uninstall cancelled at confirmation"
            exit 0
        }
    } elseif ($Option -eq 2) {
        if (-not $Force) {
            Write-Host ""
            Write-Host "A backup will be created at: $BackupPath" -ForegroundColor Cyan
            if (-not (Confirm-Action "Proceed with backup and complete removal?")) {
                Write-Host "Uninstall cancelled." -ForegroundColor Yellow
                Write-Log "Uninstall cancelled at confirmation"
                exit 0
            }
        }
    } elseif ($Option -eq 1) {
        if (-not $Force) {
            if (-not (Confirm-Action "Remove FuturesTradingLog application? (Data will be preserved)")) {
                Write-Host "Uninstall cancelled." -ForegroundColor Yellow
                Write-Log "Uninstall cancelled at confirmation"
                exit 0
            }
        }
    }

    # Execute uninstall
    $Results = Invoke-Uninstall -Option $Option -Components $Components

    # Show summary
    Show-Summary -Results $Results -Option $Option

    Write-Log "Uninstall completed"
}

# Run
Main

#endregion
