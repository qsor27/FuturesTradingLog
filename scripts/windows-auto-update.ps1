<#
.SYNOPSIS
    Automatic update script for Futures Trading Log (Windows native installation)
    Equivalent to Docker's Watchtower for automatic container updates

.DESCRIPTION
    This script checks GitHub releases for new versions, downloads updates,
    and applies them automatically. Designed to run via Windows Task Scheduler.

.PARAMETER InstallPath
    Path to the FuturesTradingLog installation directory
    Default: C:\Program Files\FuturesTradingLog

.PARAMETER DataPath
    Path to the data directory (preserved during updates)
    Default: C:\ProgramData\FuturesTradingLog

.PARAMETER ServiceName
    Name of the Windows service to restart after update
    Default: FuturesTradingLog

.PARAMETER DiscordWebhook
    Optional Discord webhook URL for update notifications

.PARAMETER DryRun
    If specified, checks for updates without applying them

.EXAMPLE
    .\windows-auto-update.ps1

.EXAMPLE
    .\windows-auto-update.ps1 -InstallPath "C:\Apps\FuturesTradingLog" -DryRun

.NOTES
    Author: FuturesTradingLog
    Version: 1.0.0
    Requires: PowerShell 5.1+, Git
#>

[CmdletBinding()]
param(
    [string]$InstallPath = "C:\Program Files\FuturesTradingLog",
    [string]$DataPath = "C:\ProgramData\FuturesTradingLog",
    [string]$ServiceName = "FuturesTradingLog",
    [string]$DiscordWebhook = $env:DISCORD_WEBHOOK_URL,
    [switch]$DryRun
)

# Configuration
$ErrorActionPreference = "Stop"
$GitHubRepo = "qsor27/FuturesTradingLog"
$GitHubApiUrl = "https://api.github.com/repos/$GitHubRepo/releases/latest"
$LogFile = Join-Path $DataPath "logs\auto-update.log"

# Ensure log directory exists
$LogDir = Split-Path $LogFile -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogEntry = "[$Timestamp] [$Level] $Message"
    Add-Content -Path $LogFile -Value $LogEntry

    switch ($Level) {
        "ERROR" { Write-Host $LogEntry -ForegroundColor Red }
        "WARN"  { Write-Host $LogEntry -ForegroundColor Yellow }
        "SUCCESS" { Write-Host $LogEntry -ForegroundColor Green }
        default { Write-Host $LogEntry }
    }
}

function Send-DiscordNotification {
    param(
        [string]$Title,
        [string]$Message,
        [string]$Color = "3447003"  # Blue
    )

    if ([string]::IsNullOrEmpty($DiscordWebhook)) {
        return
    }

    try {
        $Payload = @{
            embeds = @(
                @{
                    title = $Title
                    description = $Message
                    color = [int]$Color
                    timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
                    footer = @{
                        text = "FuturesTradingLog Auto-Update"
                    }
                }
            )
        } | ConvertTo-Json -Depth 10

        Invoke-RestMethod -Uri $DiscordWebhook -Method Post -Body $Payload -ContentType "application/json" | Out-Null
        Write-Log "Discord notification sent: $Title"
    }
    catch {
        Write-Log "Failed to send Discord notification: $_" -Level "WARN"
    }
}

function Get-CurrentVersion {
    try {
        # Try to get version from git tag
        Push-Location $InstallPath
        $CurrentTag = git describe --tags --abbrev=0 2>$null
        Pop-Location

        if ($CurrentTag) {
            return $CurrentTag.TrimStart('v')
        }

        # Fallback: check VERSION file if exists
        $VersionFile = Join-Path $InstallPath "VERSION"
        if (Test-Path $VersionFile) {
            return (Get-Content $VersionFile -Raw).Trim()
        }

        return $null
    }
    catch {
        Write-Log "Could not determine current version: $_" -Level "WARN"
        return $null
    }
}

function Get-LatestRelease {
    try {
        $Headers = @{
            "Accept" = "application/vnd.github.v3+json"
            "User-Agent" = "FuturesTradingLog-AutoUpdate"
        }

        $Response = Invoke-RestMethod -Uri $GitHubApiUrl -Headers $Headers -Method Get

        return @{
            Version = $Response.tag_name.TrimStart('v')
            TagName = $Response.tag_name
            Name = $Response.name
            Body = $Response.body
            PublishedAt = $Response.published_at
            HtmlUrl = $Response.html_url
        }
    }
    catch {
        Write-Log "Failed to fetch latest release from GitHub: $_" -Level "ERROR"
        throw
    }
}

function Compare-Versions {
    param(
        [string]$Current,
        [string]$Latest
    )

    if ([string]::IsNullOrEmpty($Current)) {
        return $true  # No current version, update needed
    }

    try {
        $CurrentParts = $Current.Split('.') | ForEach-Object { [int]$_ }
        $LatestParts = $Latest.Split('.') | ForEach-Object { [int]$_ }

        for ($i = 0; $i -lt [Math]::Max($CurrentParts.Count, $LatestParts.Count); $i++) {
            $CurrentPart = if ($i -lt $CurrentParts.Count) { $CurrentParts[$i] } else { 0 }
            $LatestPart = if ($i -lt $LatestParts.Count) { $LatestParts[$i] } else { 0 }

            if ($LatestPart -gt $CurrentPart) {
                return $true
            }
            elseif ($LatestPart -lt $CurrentPart) {
                return $false
            }
        }

        return $false  # Versions are equal
    }
    catch {
        Write-Log "Version comparison failed, assuming update needed: $_" -Level "WARN"
        return $true
    }
}

function Stop-ApplicationService {
    try {
        $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue

        if ($Service -and $Service.Status -eq 'Running') {
            Write-Log "Stopping service: $ServiceName"
            Stop-Service -Name $ServiceName -Force
            Start-Sleep -Seconds 5
            Write-Log "Service stopped successfully"
            return $true
        }
        else {
            Write-Log "Service not running or not found" -Level "WARN"
            return $false
        }
    }
    catch {
        Write-Log "Failed to stop service: $_" -Level "ERROR"
        return $false
    }
}

function Start-ApplicationService {
    try {
        $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue

        if ($Service) {
            Write-Log "Starting service: $ServiceName"
            Start-Service -Name $ServiceName
            Start-Sleep -Seconds 10

            $Service = Get-Service -Name $ServiceName
            if ($Service.Status -eq 'Running') {
                Write-Log "Service started successfully" -Level "SUCCESS"
                return $true
            }
            else {
                Write-Log "Service failed to start. Status: $($Service.Status)" -Level "ERROR"
                return $false
            }
        }
        else {
            Write-Log "Service not found: $ServiceName" -Level "WARN"
            return $false
        }
    }
    catch {
        Write-Log "Failed to start service: $_" -Level "ERROR"
        return $false
    }
}

function Backup-Installation {
    param([string]$Version)

    try {
        $BackupDir = Join-Path $DataPath "backups"
        $BackupName = "backup_v$Version`_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        $BackupPath = Join-Path $BackupDir $BackupName

        if (-not (Test-Path $BackupDir)) {
            New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
        }

        Write-Log "Creating backup: $BackupPath"

        # Backup only essential files (not venv, not data)
        $ItemsToBackup = @(
            "app.py",
            "config.py",
            "requirements.txt",
            "routes",
            "services",
            "domain",
            "repositories",
            "templates",
            "static",
            "scripts",
            "utils"
        )

        New-Item -ItemType Directory -Path $BackupPath -Force | Out-Null

        foreach ($Item in $ItemsToBackup) {
            $SourcePath = Join-Path $InstallPath $Item
            if (Test-Path $SourcePath) {
                Copy-Item -Path $SourcePath -Destination $BackupPath -Recurse -Force
            }
        }

        Write-Log "Backup created successfully"

        # Clean old backups (keep last 5)
        $OldBackups = Get-ChildItem -Path $BackupDir -Directory |
                      Sort-Object CreationTime -Descending |
                      Select-Object -Skip 5

        foreach ($OldBackup in $OldBackups) {
            Remove-Item -Path $OldBackup.FullName -Recurse -Force
            Write-Log "Removed old backup: $($OldBackup.Name)"
        }

        return $BackupPath
    }
    catch {
        Write-Log "Backup failed: $_" -Level "ERROR"
        throw
    }
}

function Update-Application {
    param([string]$TagName)

    try {
        Write-Log "Updating application to $TagName"

        Push-Location $InstallPath

        # Fetch and checkout new version
        Write-Log "Fetching latest changes from git..."
        git fetch --all --tags 2>&1 | ForEach-Object { Write-Log $_ }

        Write-Log "Checking out $TagName..."
        git checkout $TagName 2>&1 | ForEach-Object { Write-Log $_ }

        # Update dependencies
        Write-Log "Updating Python dependencies..."
        $VenvPython = Join-Path $InstallPath "venv\Scripts\python.exe"

        if (Test-Path $VenvPython) {
            & $VenvPython -m pip install --upgrade pip 2>&1 | ForEach-Object { Write-Log $_ }
            & $VenvPython -m pip install -r requirements.txt 2>&1 | ForEach-Object { Write-Log $_ }
        }
        else {
            Write-Log "Virtual environment not found at expected path" -Level "WARN"
        }

        Pop-Location

        Write-Log "Application updated successfully" -Level "SUCCESS"
        return $true
    }
    catch {
        Pop-Location
        Write-Log "Update failed: $_" -Level "ERROR"
        throw
    }
}

function Test-ApplicationHealth {
    param([int]$MaxRetries = 5, [int]$DelaySeconds = 10)

    $HealthUrl = "http://localhost:5000/health"

    for ($i = 1; $i -le $MaxRetries; $i++) {
        try {
            Write-Log "Health check attempt $i of $MaxRetries..."
            $Response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 10

            if ($Response.status -eq "healthy") {
                Write-Log "Application is healthy" -Level "SUCCESS"
                return $true
            }
            else {
                Write-Log "Unexpected health response: $($Response | ConvertTo-Json)" -Level "WARN"
            }
        }
        catch {
            Write-Log "Health check failed: $_" -Level "WARN"
        }

        if ($i -lt $MaxRetries) {
            Start-Sleep -Seconds $DelaySeconds
        }
    }

    Write-Log "Application health check failed after $MaxRetries attempts" -Level "ERROR"
    return $false
}

# Main execution
function Main {
    Write-Log "=========================================="
    Write-Log "FuturesTradingLog Auto-Update Started"
    Write-Log "Install Path: $InstallPath"
    Write-Log "Data Path: $DataPath"
    Write-Log "Dry Run: $DryRun"
    Write-Log "=========================================="

    # Validate paths
    if (-not (Test-Path $InstallPath)) {
        Write-Log "Installation path not found: $InstallPath" -Level "ERROR"
        exit 1
    }

    # Get current version
    $CurrentVersion = Get-CurrentVersion
    Write-Log "Current version: $(if ($CurrentVersion) { $CurrentVersion } else { 'Unknown' })"

    # Get latest release
    $LatestRelease = Get-LatestRelease
    Write-Log "Latest version: $($LatestRelease.Version)"

    # Check if update needed
    $UpdateNeeded = Compare-Versions -Current $CurrentVersion -Latest $LatestRelease.Version

    if (-not $UpdateNeeded) {
        Write-Log "Already running latest version. No update needed."
        exit 0
    }

    Write-Log "Update available: $CurrentVersion -> $($LatestRelease.Version)" -Level "SUCCESS"

    if ($DryRun) {
        Write-Log "Dry run mode - skipping actual update"
        Write-Log "Release notes: $($LatestRelease.Body)"
        exit 0
    }

    # Perform update
    try {
        # Stop service
        $ServiceWasRunning = Stop-ApplicationService

        # Create backup
        $BackupPath = Backup-Installation -Version $CurrentVersion

        # Apply update
        Update-Application -TagName $LatestRelease.TagName

        # Start service
        if ($ServiceWasRunning) {
            Start-ApplicationService

            # Verify health
            $IsHealthy = Test-ApplicationHealth

            if (-not $IsHealthy) {
                Write-Log "Update completed but health check failed" -Level "WARN"
                Send-DiscordNotification -Title "Update Warning" `
                    -Message "Updated to v$($LatestRelease.Version) but health check failed. Manual verification recommended." `
                    -Color "16776960"  # Yellow
            }
            else {
                Send-DiscordNotification -Title "Update Successful" `
                    -Message "Updated from v$CurrentVersion to v$($LatestRelease.Version)`n`nRelease: $($LatestRelease.Name)" `
                    -Color "3066993"  # Green
            }
        }

        Write-Log "=========================================="
        Write-Log "Update completed successfully!"
        Write-Log "Previous version: $CurrentVersion"
        Write-Log "New version: $($LatestRelease.Version)"
        Write-Log "Backup location: $BackupPath"
        Write-Log "=========================================="
    }
    catch {
        Write-Log "Update failed: $_" -Level "ERROR"

        Send-DiscordNotification -Title "Update Failed" `
            -Message "Failed to update from v$CurrentVersion to v$($LatestRelease.Version)`n`nError: $_" `
            -Color "15158332"  # Red

        # Try to restart service even if update failed
        if ($ServiceWasRunning) {
            Write-Log "Attempting to restart service after failed update..."
            Start-ApplicationService
        }

        exit 1
    }
}

# Run main function
Main
