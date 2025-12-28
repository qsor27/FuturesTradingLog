<#
.SYNOPSIS
    Install FuturesTradingLog as a Windows service using NSSM

.DESCRIPTION
    This script automates the installation of FuturesTradingLog as a Windows service.
    It configures NSSM with proper environment variables, logging, and restart policies
    equivalent to Docker's restart: unless-stopped behavior.

.PARAMETER InstallPath
    Path to the FuturesTradingLog installation directory
    Default: C:\Projects\FuturesTradingLog

.PARAMETER DataPath
    Path to the data directory
    Default: C:\ProgramData\FuturesTradingLog

.PARAMETER ServiceName
    Name for the Windows service
    Default: FuturesTradingLog

.PARAMETER NssmPath
    Path to NSSM executable
    Default: C:\nssm\nssm.exe

.PARAMETER SecretKey
    Flask secret key (will be generated if not provided)

.PARAMETER RedisUrl
    Redis connection URL
    Default: redis://localhost:6379/0

.PARAMETER DiscordWebhook
    Optional Discord webhook URL for notifications

.EXAMPLE
    .\install-service.ps1

.EXAMPLE
    .\install-service.ps1 -InstallPath "C:\Apps\FuturesTradingLog" -DataPath "C:\Data\FTL"

.NOTES
    Requires: Administrator privileges, NSSM installed
#>

[CmdletBinding()]
param(
    [string]$InstallPath = "C:\Projects\FuturesTradingLog",
    [string]$DataPath = "C:\ProgramData\FuturesTradingLog",
    [string]$ServiceName = "FuturesTradingLog",
    [string]$NssmPath = "C:\nssm\nssm.exe",
    [string]$SecretKey = "",
    [string]$RedisUrl = "redis://localhost:6379/0",
    [string]$DiscordWebhook = "",
    [switch]$CacheEnabled = $true,
    [switch]$AutoImportEnabled = $true
)

$ErrorActionPreference = "Stop"

function Test-Administrator {
    $CurrentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = New-Object Security.Principal.WindowsPrincipal($CurrentUser)
    return $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    $Color = switch ($Status) {
        "SUCCESS" { "Green" }
        "ERROR" { "Red" }
        "WARN" { "Yellow" }
        default { "White" }
    }
    Write-Host "[$Status] $Message" -ForegroundColor $Color
}

function New-SecretKey {
    $Bytes = New-Object byte[] 32
    $Rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $Rng.GetBytes($Bytes)
    return [System.BitConverter]::ToString($Bytes).Replace("-", "").ToLower()
}

# Check administrator
if (-not (Test-Administrator)) {
    Write-Status "This script requires administrator privileges. Please run as Administrator." "ERROR"
    exit 1
}

Write-Host "=========================================="
Write-Host "FuturesTradingLog Service Installer"
Write-Host "=========================================="
Write-Host ""

# Validate NSSM
if (-not (Test-Path $NssmPath)) {
    Write-Status "NSSM not found at: $NssmPath" "ERROR"
    Write-Host ""
    Write-Host "Please download NSSM from https://nssm.cc/download"
    Write-Host "Extract nssm.exe to C:\nssm\ or specify path with -NssmPath"
    exit 1
}
Write-Status "NSSM found: $NssmPath" "SUCCESS"

# Validate installation path
if (-not (Test-Path $InstallPath)) {
    Write-Status "Installation path not found: $InstallPath" "ERROR"
    exit 1
}
Write-Status "Installation path: $InstallPath" "SUCCESS"

# Validate virtual environment
$VenvPython = Join-Path $InstallPath "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Status "Virtual environment not found. Expected: $VenvPython" "ERROR"
    Write-Host "Please run: python -m venv venv && .\venv\Scripts\Activate && pip install -r requirements.txt"
    exit 1
}
Write-Status "Python found: $VenvPython" "SUCCESS"

# Create data directories
$Directories = @(
    $DataPath,
    (Join-Path $DataPath "db"),
    (Join-Path $DataPath "logs"),
    (Join-Path $DataPath "config"),
    (Join-Path $DataPath "charts"),
    (Join-Path $DataPath "archive"),
    (Join-Path $DataPath "backups")
)

foreach ($Dir in $Directories) {
    if (-not (Test-Path $Dir)) {
        New-Item -ItemType Directory -Path $Dir -Force | Out-Null
        Write-Status "Created directory: $Dir"
    }
}
Write-Status "Data directories verified: $DataPath" "SUCCESS"

# Generate secret key if not provided
if ([string]::IsNullOrEmpty($SecretKey)) {
    $SecretKey = New-SecretKey
    Write-Status "Generated new secret key"
}

# Check if service already exists
$ExistingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($ExistingService) {
    Write-Status "Service '$ServiceName' already exists" "WARN"
    $Confirm = Read-Host "Remove existing service and reinstall? (y/n)"
    if ($Confirm -eq 'y') {
        Write-Status "Stopping and removing existing service..."
        if ($ExistingService.Status -eq 'Running') {
            Stop-Service -Name $ServiceName -Force
            Start-Sleep -Seconds 3
        }
        & $NssmPath remove $ServiceName confirm
        Start-Sleep -Seconds 2
    }
    else {
        Write-Status "Installation cancelled" "WARN"
        exit 0
    }
}

# Install service with NSSM
Write-Host ""
Write-Status "Installing service..."

# Basic service configuration
& $NssmPath install $ServiceName $VenvPython
& $NssmPath set $ServiceName AppDirectory $InstallPath
& $NssmPath set $ServiceName AppParameters "app.py"
& $NssmPath set $ServiceName DisplayName "Futures Trading Log"
& $NssmPath set $ServiceName Description "Flask-based futures trading analytics platform"

# Environment variables
$EnvVars = @(
    "FLASK_ENV=production",
    "FLASK_DEBUG=0",
    "FLASK_SECRET_KEY=$SecretKey",
    "FLASK_HOST=0.0.0.0",
    "FLASK_PORT=5000",
    "DATA_DIR=$DataPath",
    "REDIS_URL=$RedisUrl",
    "CACHE_ENABLED=$(if ($CacheEnabled) { 'true' } else { 'false' })",
    "AUTO_IMPORT_ENABLED=$(if ($AutoImportEnabled) { 'true' } else { 'false' })",
    "AUTO_IMPORT_INTERVAL=300"
)

if (-not [string]::IsNullOrEmpty($DiscordWebhook)) {
    $EnvVars += "DISCORD_WEBHOOK_URL=$DiscordWebhook"
}

$EnvString = $EnvVars -join "`n"
& $NssmPath set $ServiceName AppEnvironmentExtra $EnvString

# Restart policy (equivalent to Docker restart: unless-stopped)
& $NssmPath set $ServiceName AppExit Default Restart
& $NssmPath set $ServiceName AppRestartDelay 5000
& $NssmPath set $ServiceName AppThrottle 10000

# Logging configuration
$StdoutLog = Join-Path $DataPath "logs\service_stdout.log"
$StderrLog = Join-Path $DataPath "logs\service_stderr.log"
& $NssmPath set $ServiceName AppStdout $StdoutLog
& $NssmPath set $ServiceName AppStderr $StderrLog
& $NssmPath set $ServiceName AppStdoutCreationDisposition 4
& $NssmPath set $ServiceName AppStderrCreationDisposition 4
& $NssmPath set $ServiceName AppRotateFiles 1
& $NssmPath set $ServiceName AppRotateOnline 1
& $NssmPath set $ServiceName AppRotateBytes 10485760

# Start type
& $NssmPath set $ServiceName Start SERVICE_AUTO_START

Write-Status "Service installed successfully" "SUCCESS"

# Start the service
Write-Host ""
$StartNow = Read-Host "Start the service now? (y/n)"
if ($StartNow -eq 'y') {
    Write-Status "Starting service..."
    Start-Service -Name $ServiceName
    Start-Sleep -Seconds 5

    $Service = Get-Service -Name $ServiceName
    if ($Service.Status -eq 'Running') {
        Write-Status "Service started successfully" "SUCCESS"

        # Health check
        Write-Status "Performing health check..."
        Start-Sleep -Seconds 10
        try {
            $Response = Invoke-RestMethod -Uri "http://localhost:5000/health" -TimeoutSec 10
            Write-Status "Application is healthy: $($Response.status)" "SUCCESS"
        }
        catch {
            Write-Status "Health check failed: $_" "WARN"
            Write-Host "The service is running but may need more time to initialize."
        }
    }
    else {
        Write-Status "Service failed to start. Status: $($Service.Status)" "ERROR"
        Write-Host "Check logs at: $StderrLog"
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "Installation Complete"
Write-Host "=========================================="
Write-Host ""
Write-Host "Service Name:    $ServiceName"
Write-Host "Install Path:    $InstallPath"
Write-Host "Data Path:       $DataPath"
Write-Host "Logs:            $DataPath\logs\"
Write-Host "Database:        $DataPath\db\futures_trades_clean.db"
Write-Host "Config:          $DataPath\config\"
Write-Host ""
Write-Host "Useful Commands:"
Write-Host "  Start:   Start-Service $ServiceName"
Write-Host "  Stop:    Stop-Service $ServiceName"
Write-Host "  Restart: Restart-Service $ServiceName"
Write-Host "  Status:  Get-Service $ServiceName"
Write-Host "  Logs:    Get-Content '$StdoutLog' -Tail 50"
Write-Host ""
Write-Host "Web Interface: http://localhost:5000"
Write-Host ""

# Save configuration for reference
$ConfigFile = Join-Path $DataPath "config\service-config.txt"
@"
# FuturesTradingLog Service Configuration
# Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

Service Name: $ServiceName
Install Path: $InstallPath
Data Path: $DataPath
Python: $VenvPython
NSSM: $NssmPath

Environment Variables:
$($EnvVars | ForEach-Object { "  $_" } | Out-String)

Note: Secret key is stored in NSSM service configuration.
"@ | Set-Content $ConfigFile

Write-Status "Configuration saved to: $ConfigFile"
