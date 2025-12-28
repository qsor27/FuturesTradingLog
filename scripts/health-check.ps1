<#
.SYNOPSIS
    Health check script for FuturesTradingLog
    Equivalent to Docker's HEALTHCHECK functionality

.DESCRIPTION
    Monitors application health and automatically restarts the service
    if consecutive health checks fail. Designed to run as a background
    task or scheduled job.

.PARAMETER ServiceName
    Name of the Windows service to monitor
    Default: FuturesTradingLog

.PARAMETER HealthUrl
    URL to check for health status
    Default: http://localhost:5000/health

.PARAMETER CheckInterval
    Seconds between health checks
    Default: 30

.PARAMETER MaxFailures
    Number of consecutive failures before restart
    Default: 3

.PARAMETER Timeout
    HTTP request timeout in seconds
    Default: 10

.PARAMETER LogPath
    Path to log file
    Default: C:\ProgramData\FuturesTradingLog\logs\health-check.log

.PARAMETER RunOnce
    If specified, runs a single health check and exits

.PARAMETER Daemon
    If specified, runs continuously as a daemon

.EXAMPLE
    .\health-check.ps1 -RunOnce

.EXAMPLE
    .\health-check.ps1 -Daemon -CheckInterval 60

.NOTES
    For continuous monitoring, run as a scheduled task or separate service
#>

[CmdletBinding()]
param(
    [string]$ServiceName = "FuturesTradingLog",
    [string]$HealthUrl = "http://localhost:5000/health",
    [int]$CheckInterval = 30,
    [int]$MaxFailures = 3,
    [int]$Timeout = 10,
    [string]$LogPath = "C:\ProgramData\FuturesTradingLog\logs\health-check.log",
    [switch]$RunOnce,
    [switch]$Daemon
)

$ErrorActionPreference = "Continue"

# Ensure log directory exists
$LogDir = Split-Path $LogPath -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogEntry = "[$Timestamp] [$Level] $Message"

    # Append to log file
    Add-Content -Path $LogPath -Value $LogEntry

    # Also write to console
    $Color = switch ($Level) {
        "ERROR" { "Red" }
        "WARN" { "Yellow" }
        "SUCCESS" { "Green" }
        default { "White" }
    }
    Write-Host $LogEntry -ForegroundColor $Color
}

function Test-ServiceHealth {
    try {
        $Response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec $Timeout

        if ($Response.status -eq "healthy") {
            return @{
                Healthy = $true
                Status = $Response.status
                Details = $Response
            }
        }
        else {
            return @{
                Healthy = $false
                Status = $Response.status
                Details = $Response
                Error = "Unexpected status"
            }
        }
    }
    catch {
        return @{
            Healthy = $false
            Status = "error"
            Error = $_.Exception.Message
        }
    }
}

function Restart-ApplicationService {
    try {
        Write-Log "Attempting to restart service: $ServiceName" "WARN"

        $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if (-not $Service) {
            Write-Log "Service not found: $ServiceName" "ERROR"
            return $false
        }

        # Stop service
        if ($Service.Status -eq 'Running') {
            Stop-Service -Name $ServiceName -Force
            Start-Sleep -Seconds 5
        }

        # Start service
        Start-Service -Name $ServiceName
        Start-Sleep -Seconds 10

        # Verify
        $Service = Get-Service -Name $ServiceName
        if ($Service.Status -eq 'Running') {
            Write-Log "Service restarted successfully" "SUCCESS"
            return $true
        }
        else {
            Write-Log "Service failed to start. Status: $($Service.Status)" "ERROR"
            return $false
        }
    }
    catch {
        Write-Log "Failed to restart service: $_" "ERROR"
        return $false
    }
}

function Start-HealthMonitor {
    $FailureCount = 0
    $TotalChecks = 0
    $TotalFailures = 0

    Write-Log "=========================================="
    Write-Log "Health Monitor Started"
    Write-Log "Service: $ServiceName"
    Write-Log "Health URL: $HealthUrl"
    Write-Log "Check Interval: ${CheckInterval}s"
    Write-Log "Max Failures: $MaxFailures"
    Write-Log "=========================================="

    while ($true) {
        $TotalChecks++

        # Check if service is running first
        $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if (-not $Service) {
            Write-Log "Service not found: $ServiceName" "ERROR"
            $FailureCount++
        }
        elseif ($Service.Status -ne 'Running') {
            Write-Log "Service not running. Status: $($Service.Status)" "WARN"
            $FailureCount++

            # Try to start if stopped
            if ($FailureCount -ge $MaxFailures) {
                Start-Service -Name $ServiceName -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 10
            }
        }
        else {
            # Service is running, check health endpoint
            $HealthResult = Test-ServiceHealth

            if ($HealthResult.Healthy) {
                if ($FailureCount -gt 0) {
                    Write-Log "Health restored after $FailureCount failures" "SUCCESS"
                }
                $FailureCount = 0
            }
            else {
                $FailureCount++
                $TotalFailures++
                Write-Log "Health check failed ($FailureCount/$MaxFailures): $($HealthResult.Error)" "WARN"

                if ($FailureCount -ge $MaxFailures) {
                    Write-Log "Max failures reached. Initiating restart..." "ERROR"
                    $Restarted = Restart-ApplicationService

                    if ($Restarted) {
                        $FailureCount = 0
                    }
                }
            }
        }

        # Log periodic summary
        if ($TotalChecks % 100 -eq 0) {
            $SuccessRate = [math]::Round((($TotalChecks - $TotalFailures) / $TotalChecks) * 100, 2)
            Write-Log "Health Summary: $TotalChecks checks, $TotalFailures failures, ${SuccessRate}% success rate"
        }

        Start-Sleep -Seconds $CheckInterval
    }
}

function Invoke-SingleHealthCheck {
    Write-Log "Performing single health check..."

    $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $Service) {
        Write-Log "Service not found: $ServiceName" "ERROR"
        exit 1
    }

    Write-Log "Service Status: $($Service.Status)"

    if ($Service.Status -ne 'Running') {
        Write-Log "Service is not running" "ERROR"
        exit 1
    }

    $HealthResult = Test-ServiceHealth

    if ($HealthResult.Healthy) {
        Write-Log "Application is healthy" "SUCCESS"

        # Show details
        if ($HealthResult.Details) {
            $HealthResult.Details.PSObject.Properties | ForEach-Object {
                Write-Log "  $($_.Name): $($_.Value)"
            }
        }
        exit 0
    }
    else {
        Write-Log "Application is unhealthy: $($HealthResult.Error)" "ERROR"
        exit 1
    }
}

# Main execution
if ($RunOnce) {
    Invoke-SingleHealthCheck
}
elseif ($Daemon) {
    Start-HealthMonitor
}
else {
    Write-Host "FuturesTradingLog Health Check"
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\health-check.ps1 -RunOnce     # Single health check"
    Write-Host "  .\health-check.ps1 -Daemon      # Continuous monitoring"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -ServiceName      Service to monitor (default: FuturesTradingLog)"
    Write-Host "  -HealthUrl        Health endpoint URL"
    Write-Host "  -CheckInterval    Seconds between checks (default: 30)"
    Write-Host "  -MaxFailures      Failures before restart (default: 3)"
    Write-Host ""

    # Default: run single check
    Invoke-SingleHealthCheck
}
