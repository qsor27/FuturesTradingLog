<#
.SYNOPSIS
    Uninstall FuturesTradingLog Windows service

.DESCRIPTION
    This script removes the FuturesTradingLog Windows service cleanly.
    Optionally preserves or removes data directory.

.PARAMETER ServiceName
    Name of the Windows service to remove
    Default: FuturesTradingLog

.PARAMETER NssmPath
    Path to NSSM executable
    Default: C:\nssm\nssm.exe

.PARAMETER RemoveData
    If specified, also removes the data directory

.PARAMETER DataPath
    Path to data directory (only used if -RemoveData is specified)
    Default: C:\ProgramData\FuturesTradingLog

.EXAMPLE
    .\uninstall-service.ps1

.EXAMPLE
    .\uninstall-service.ps1 -RemoveData -DataPath "C:\Data\FTL"

.NOTES
    Requires: Administrator privileges
#>

[CmdletBinding()]
param(
    [string]$ServiceName = "FuturesTradingLog",
    [string]$NssmPath = "C:\nssm\nssm.exe",
    [switch]$RemoveData,
    [string]$DataPath = "C:\ProgramData\FuturesTradingLog"
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

# Check administrator
if (-not (Test-Administrator)) {
    Write-Status "This script requires administrator privileges. Please run as Administrator." "ERROR"
    exit 1
}

Write-Host "=========================================="
Write-Host "FuturesTradingLog Service Uninstaller"
Write-Host "=========================================="
Write-Host ""

# Check if service exists
$Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $Service) {
    Write-Status "Service '$ServiceName' not found" "WARN"
    exit 0
}

Write-Status "Found service: $ServiceName (Status: $($Service.Status))"

# Confirm uninstall
$Confirm = Read-Host "Are you sure you want to uninstall the service? (y/n)"
if ($Confirm -ne 'y') {
    Write-Status "Uninstall cancelled"
    exit 0
}

# Stop service if running
if ($Service.Status -eq 'Running') {
    Write-Status "Stopping service..."
    Stop-Service -Name $ServiceName -Force
    Start-Sleep -Seconds 5
    Write-Status "Service stopped" "SUCCESS"
}

# Remove service using NSSM if available
if (Test-Path $NssmPath) {
    Write-Status "Removing service with NSSM..."
    & $NssmPath remove $ServiceName confirm
}
else {
    Write-Status "NSSM not found, using sc.exe..."
    sc.exe delete $ServiceName
}

Start-Sleep -Seconds 2

# Verify removal
$Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($Service) {
    Write-Status "Service still exists. May require reboot to complete removal." "WARN"
}
else {
    Write-Status "Service removed successfully" "SUCCESS"
}

# Remove data if requested
if ($RemoveData) {
    Write-Host ""
    Write-Status "RemoveData flag specified" "WARN"
    Write-Host "This will delete ALL data including:"
    Write-Host "  - Database: $DataPath\db\"
    Write-Host "  - Logs: $DataPath\logs\"
    Write-Host "  - Config: $DataPath\config\"
    Write-Host "  - Backups: $DataPath\backups\"
    Write-Host ""

    $ConfirmData = Read-Host "Delete all data? This cannot be undone! (type 'DELETE' to confirm)"
    if ($ConfirmData -eq 'DELETE') {
        if (Test-Path $DataPath) {
            Remove-Item -Path $DataPath -Recurse -Force
            Write-Status "Data directory removed: $DataPath" "SUCCESS"
        }
        else {
            Write-Status "Data directory not found: $DataPath" "WARN"
        }
    }
    else {
        Write-Status "Data preservation - directory kept: $DataPath"
    }
}
else {
    Write-Host ""
    Write-Status "Data directory preserved: $DataPath"
    Write-Host "To remove data, run: .\uninstall-service.ps1 -RemoveData"
}

Write-Host ""
Write-Host "=========================================="
Write-Host "Uninstall Complete"
Write-Host "=========================================="
