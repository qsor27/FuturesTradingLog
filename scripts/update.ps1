<#
.SYNOPSIS
    Interactive update manager for Futures Trading Log (Windows native installation)

.DESCRIPTION
    This script provides an interactive way to check for updates, view release notes,
    apply updates, and rollback to previous versions. Complements the scheduled
    auto-update functionality with user-initiated controls.

.PARAMETER Check
    Check for updates without applying them (no admin required)

.PARAMETER Yes
    Skip confirmation prompts (for automation)

.PARAMETER Version
    Update to a specific version tag (e.g., v1.2.3)

.PARAMETER Rollback
    Rollback to a previous version from backup

.PARAMETER ListBackups
    List available backups

.PARAMETER History
    Show update history

.PARAMETER InstallPath
    Path to the FuturesTradingLog installation directory
    Default: C:\Program Files\FuturesTradingLog

.PARAMETER DataPath
    Path to the data directory
    Default: C:\ProgramData\FuturesTradingLog

.PARAMETER ServiceName
    Name of the Windows service
    Default: FuturesTradingLog

.PARAMETER MaxBackups
    Maximum number of backups to keep
    Default: 5

.EXAMPLE
    .\update.ps1 -Check
    Check if an update is available

.EXAMPLE
    .\update.ps1
    Interactively update to the latest version

.EXAMPLE
    .\update.ps1 -Yes
    Update without prompts

.EXAMPLE
    .\update.ps1 -Rollback
    Rollback to a previous version

.EXAMPLE
    .\update.ps1 -Version v1.2.3
    Update to a specific version

.NOTES
    Author: FuturesTradingLog
    Version: 1.0.0
    Requires: PowerShell 5.1+, Git
#>

[CmdletBinding(DefaultParameterSetName = 'Update')]
param(
    [Parameter(ParameterSetName = 'Check')]
    [switch]$Check,

    [Parameter(ParameterSetName = 'Update')]
    [switch]$Yes,

    [Parameter(ParameterSetName = 'Update')]
    [string]$Version,

    [Parameter(ParameterSetName = 'Rollback')]
    [switch]$Rollback,

    [Parameter(ParameterSetName = 'ListBackups')]
    [switch]$ListBackups,

    [Parameter(ParameterSetName = 'History')]
    [switch]$History,

    [string]$InstallPath = "C:\Program Files\FuturesTradingLog",
    [string]$DataPath = "C:\ProgramData\FuturesTradingLog",
    [string]$ServiceName = "FuturesTradingLog",
    [int]$MaxBackups = 5
)

# Configuration
$ErrorActionPreference = "Stop"
$GitHubRepo = "qsor27/FuturesTradingLog"
$GitHubApiUrl = "https://api.github.com/repos/$GitHubRepo/releases/latest"
$LogFile = Join-Path $DataPath "logs\update.log"
$HistoryFile = Join-Path $DataPath "logs\update-history.log"

#region Helper Functions

function Test-AdminRights {
    $Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = New-Object Security.Principal.WindowsPrincipal($Identity)
    return $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")

    # Ensure log directory exists
    $LogDir = Split-Path $LogFile -Parent
    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    }

    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogEntry = "[$Timestamp] [$Level] $Message"
    Add-Content -Path $LogFile -Value $LogEntry -ErrorAction SilentlyContinue
}

function Show-Header {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 64) -ForegroundColor Cyan
    Write-Host "   FuturesTradingLog - $Title" -ForegroundColor White
    Write-Host ("=" * 64) -ForegroundColor Cyan
    Write-Host ""
}

function Show-Progress {
    param(
        [int]$Step,
        [int]$Total,
        [string]$Message
    )
    Write-Host "[$Step/$Total] $Message" -ForegroundColor White
}

#endregion

#region Version Functions

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

        return "Unknown"
    }
    catch {
        Write-Log "Could not determine current version: $_" -Level "WARN"
        return "Unknown"
    }
}

function Get-LatestRelease {
    try {
        $Headers = @{
            "Accept" = "application/vnd.github.v3+json"
            "User-Agent" = "FuturesTradingLog-Update"
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
        throw "Failed to fetch latest release. Check your internet connection."
    }
}

function Get-SpecificRelease {
    param([string]$Tag)

    try {
        $Headers = @{
            "Accept" = "application/vnd.github.v3+json"
            "User-Agent" = "FuturesTradingLog-Update"
        }

        $Url = "https://api.github.com/repos/$GitHubRepo/releases/tags/$Tag"
        $Response = Invoke-RestMethod -Uri $Url -Headers $Headers -Method Get

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
        Write-Log "Failed to fetch release $Tag from GitHub: $_" -Level "ERROR"
        throw "Failed to fetch release $Tag. Check if the version exists."
    }
}

function Compare-Versions {
    param(
        [string]$Current,
        [string]$Latest
    )

    if ($Current -eq "Unknown" -or [string]::IsNullOrEmpty($Current)) {
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

#endregion

#region Display Functions

function Show-VersionComparison {
    param(
        [string]$Current,
        [hashtable]$Latest
    )

    Write-Host "Current Version: " -NoNewline
    Write-Host $Current -ForegroundColor Cyan

    Write-Host "Latest Version:  " -NoNewline
    Write-Host "$($Latest.Version)" -ForegroundColor Green -NoNewline
    Write-Host " (released $(Get-Date $Latest.PublishedAt -Format 'yyyy-MM-dd'))"
}

function Show-ReleaseNotes {
    param([hashtable]$Release)

    Write-Host ""
    Write-Host "Release Notes:" -ForegroundColor Yellow
    Write-Host ("-" * 64) -ForegroundColor DarkGray

    if ([string]::IsNullOrWhiteSpace($Release.Body)) {
        Write-Host "(No release notes provided)" -ForegroundColor DarkGray
    }
    else {
        # Parse and display markdown-ish content
        $Lines = $Release.Body -split "`n"
        foreach ($Line in $Lines) {
            if ($Line -match '^##\s+(.+)') {
                Write-Host ""
                Write-Host $Matches[1] -ForegroundColor Cyan
            }
            elseif ($Line -match '^-\s+(.+)') {
                Write-Host "  - $($Matches[1])"
            }
            elseif ($Line -match '^\*\s+(.+)') {
                Write-Host "  * $($Matches[1])"
            }
            else {
                Write-Host $Line
            }
        }
    }

    Write-Host ("-" * 64) -ForegroundColor DarkGray
    Write-Host ""
}

function Show-CompletionMessage {
    param(
        [string]$Previous,
        [string]$Current,
        [string]$BackupPath
    )

    Write-Host ""
    Write-Host ("=" * 64) -ForegroundColor Cyan
    Write-Host "Update completed successfully!" -ForegroundColor Green
    Write-Host "  Previous: v$Previous"
    Write-Host "  Current:  v$Current"
    Write-Host "  Backup:   $(Split-Path $BackupPath -Leaf)"
    Write-Host ""
    Write-Host "To rollback: .\update.ps1 -Rollback" -ForegroundColor DarkGray
    Write-Host ("=" * 64) -ForegroundColor Cyan
}

#endregion

#region Service Functions

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
                Write-Log "Service started successfully"
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

function Test-ApplicationHealth {
    param([int]$MaxRetries = 3, [int]$DelaySeconds = 5)

    $HealthUrl = "http://localhost:5000/health"

    for ($i = 1; $i -le $MaxRetries; $i++) {
        try {
            Write-Log "Health check attempt $i of $MaxRetries..."
            $Response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 10

            if ($Response.status -eq "healthy") {
                Write-Log "Application is healthy"
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

#endregion

#region Backup Functions

function Backup-Installation {
    param([string]$Version)

    try {
        $BackupDir = Join-Path $DataPath "backups"
        $BackupName = "v$Version`_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
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

        # Clean old backups (keep last N)
        $OldBackups = Get-ChildItem -Path $BackupDir -Directory |
                      Sort-Object CreationTime -Descending |
                      Select-Object -Skip $MaxBackups

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

function Get-AvailableBackups {
    $BackupDir = Join-Path $DataPath "backups"

    if (-not (Test-Path $BackupDir)) {
        return @()
    }

    $Backups = Get-ChildItem -Path $BackupDir -Directory |
        Where-Object { $_.Name -match '^v?[\d\.]+_\d{8}_\d{6}$' } |
        Sort-Object CreationTime -Descending |
        ForEach-Object {
            $VersionMatch = $_.Name -match 'v?([\d\.]+)'
            $Version = if ($VersionMatch) { $Matches[1] } else { "Unknown" }

            @{
                Path = $_.FullName
                Name = $_.Name
                Version = $Version
                Created = $_.CreationTime
                Size = (Get-ChildItem $_.FullName -Recurse | Measure-Object -Property Length -Sum).Sum
            }
        }

    return $Backups
}

function Restore-FromBackup {
    param([string]$BackupPath)

    # Items to restore
    $ItemsToRestore = @(
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

    foreach ($Item in $ItemsToRestore) {
        $SourcePath = Join-Path $BackupPath $Item
        $DestPath = Join-Path $InstallPath $Item

        if (Test-Path $SourcePath) {
            # Remove existing
            if (Test-Path $DestPath) {
                Remove-Item -Path $DestPath -Recurse -Force
            }
            # Copy from backup
            Copy-Item -Path $SourcePath -Destination $DestPath -Recurse -Force
        }
    }
}

#endregion

#region Update Functions

function Update-Application {
    param([string]$TagName)

    try {
        Write-Log "Updating application to $TagName"

        Push-Location $InstallPath

        # Fetch and checkout new version
        Write-Log "Fetching latest changes from git..."
        git fetch --all --tags 2>&1 | Out-Null

        Write-Log "Checking out $TagName..."
        git checkout $TagName 2>&1 | Out-Null

        # Update dependencies
        Write-Log "Updating Python dependencies..."
        $VenvPython = Join-Path $InstallPath "venv\Scripts\python.exe"

        if (Test-Path $VenvPython) {
            & $VenvPython -m pip install --upgrade pip -q 2>&1 | Out-Null
            & $VenvPython -m pip install -r (Join-Path $InstallPath "requirements.txt") -q 2>&1 | Out-Null
        }
        else {
            Write-Log "Virtual environment not found at expected path" -Level "WARN"
        }

        Pop-Location

        Write-Log "Application updated successfully"
        return $true
    }
    catch {
        Pop-Location
        Write-Log "Update failed: $_" -Level "ERROR"
        throw
    }
}

#endregion

#region History Functions

function Write-UpdateHistory {
    param(
        [string]$FromVersion,
        [string]$ToVersion,
        [string]$Status,
        [string]$ErrorMessage = ""
    )

    $HistoryDir = Split-Path $HistoryFile -Parent

    if (-not (Test-Path $HistoryDir)) {
        New-Item -ItemType Directory -Path $HistoryDir -Force | Out-Null
    }

    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $Line = "$Timestamp | $($Status.PadRight(8)) | v$FromVersion -> v$ToVersion"
    if ($ErrorMessage) {
        $Line += " | Error: $ErrorMessage"
    }

    Add-Content -Path $HistoryFile -Value $Line -ErrorAction SilentlyContinue
}

function Get-UpdateHistory {
    if (-not (Test-Path $HistoryFile)) {
        return @()
    }

    return Get-Content $HistoryFile | Select-Object -Last 20
}

#endregion

#region Mode Functions

function Invoke-CheckMode {
    $CurrentVersion = Get-CurrentVersion
    $LatestRelease = Get-LatestRelease

    Write-Host ""
    Write-Host "Current Version: " -NoNewline
    Write-Host $CurrentVersion -ForegroundColor Cyan

    Write-Host "Latest Version:  " -NoNewline
    Write-Host "$($LatestRelease.Version)" -ForegroundColor Cyan -NoNewline
    Write-Host " (released $(Get-Date $LatestRelease.PublishedAt -Format 'yyyy-MM-dd'))"

    $UpdateNeeded = Compare-Versions -Current $CurrentVersion -Latest $LatestRelease.Version

    Write-Host ""
    if ($UpdateNeeded) {
        Write-Host "Update available!" -ForegroundColor Green
        Write-Host "Run '.\update.ps1' to update interactively." -ForegroundColor DarkGray
        exit 1  # Exit code 1 = update available
    }
    else {
        Write-Host "You are running the latest version." -ForegroundColor Green
        exit 0  # Exit code 0 = up to date
    }
}

function Invoke-UpdateMode {
    param([string]$TargetVersion)

    # Check admin rights for update
    if (-not (Test-AdminRights)) {
        Write-Host ""
        Write-Host "ERROR: Administrator privileges required for updates." -ForegroundColor Red
        Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }

    # Validate paths
    if (-not (Test-Path $InstallPath)) {
        Write-Host ""
        Write-Host "ERROR: Installation path not found: $InstallPath" -ForegroundColor Red
        Write-Host ""
        exit 1
    }

    $CurrentVersion = Get-CurrentVersion

    # Determine target version
    if ($TargetVersion) {
        $LatestRelease = Get-SpecificRelease -Tag $TargetVersion
    }
    else {
        $LatestRelease = Get-LatestRelease
    }

    # Show header
    Show-Header "Update Manager"
    Show-VersionComparison -Current $CurrentVersion -Latest $LatestRelease

    # Check if update needed
    $UpdateNeeded = Compare-Versions -Current $CurrentVersion -Latest $LatestRelease.Version
    if (-not $UpdateNeeded -and -not $TargetVersion) {
        Write-Host ""
        Write-Host "You are already running the latest version." -ForegroundColor Green
        Write-Host ""
        exit 0
    }

    # Show release notes
    Show-ReleaseNotes -Release $LatestRelease

    # Confirm unless -Yes
    if (-not $Yes) {
        $Confirm = Read-Host "Do you want to update now? (y/n)"
        if ($Confirm -notmatch '^[yY]') {
            Write-Host ""
            Write-Host "Update cancelled." -ForegroundColor Yellow
            Write-Host ""
            exit 0
        }
    }

    Write-Host ""

    try {
        # Step 1: Backup
        Show-Progress -Step 1 -Total 6 -Message "Creating backup of v$CurrentVersion..."
        $BackupPath = Backup-Installation -Version $CurrentVersion
        Write-Host "      Backup saved to: $(Split-Path $BackupPath -Leaf)" -ForegroundColor DarkGray

        # Step 2: Stop service
        Show-Progress -Step 2 -Total 6 -Message "Stopping $ServiceName service..."
        $ServiceWasRunning = Stop-ApplicationService

        # Step 3-5: Update
        Show-Progress -Step 3 -Total 6 -Message "Fetching latest changes..."
        Show-Progress -Step 4 -Total 6 -Message "Checking out $($LatestRelease.TagName)..."
        Show-Progress -Step 5 -Total 6 -Message "Updating Python dependencies..."
        Update-Application -TagName $LatestRelease.TagName | Out-Null

        # Step 6: Start service
        Show-Progress -Step 6 -Total 6 -Message "Starting $ServiceName service..."
        if ($ServiceWasRunning) {
            Start-ApplicationService | Out-Null
        }

        # Health check
        Write-Host ""
        Write-Host "Health check: " -NoNewline
        $IsHealthy = Test-ApplicationHealth -MaxRetries 3 -DelaySeconds 5
        if ($IsHealthy) {
            Write-Host "OK" -ForegroundColor Green
        }
        else {
            Write-Host "FAILED" -ForegroundColor Red
            Write-Host "Application may need manual verification." -ForegroundColor Yellow
        }

        # Log update
        Write-UpdateHistory -FromVersion $CurrentVersion -ToVersion $LatestRelease.Version -Status "Success"

        # Success message
        Show-CompletionMessage -Previous $CurrentVersion -Current $LatestRelease.Version -BackupPath $BackupPath
    }
    catch {
        Write-Host ""
        Write-Host "ERROR: Update failed - $_" -ForegroundColor Red
        Write-Host ""

        # Log failure
        Write-UpdateHistory -FromVersion $CurrentVersion -ToVersion $LatestRelease.Version -Status "Failed" -ErrorMessage $_

        # Try to restart service
        if ($ServiceWasRunning) {
            Write-Host "Attempting to restart service..." -ForegroundColor Yellow
            Start-ApplicationService | Out-Null
        }

        Write-Host ""
        Write-Host "To rollback: .\update.ps1 -Rollback" -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }
}

function Invoke-RollbackMode {
    # Check admin rights
    if (-not (Test-AdminRights)) {
        Write-Host ""
        Write-Host "ERROR: Administrator privileges required for rollback." -ForegroundColor Red
        Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }

    Show-Header "Rollback"

    $Backups = Get-AvailableBackups

    if ($Backups.Count -eq 0) {
        Write-Host "No backups available for rollback." -ForegroundColor Yellow
        Write-Host "Backups are created automatically before each update." -ForegroundColor DarkGray
        Write-Host ""
        exit 1
    }

    # Display backups
    Write-Host "Available Backups:" -ForegroundColor Cyan
    Write-Host ""
    for ($i = 0; $i -lt $Backups.Count; $i++) {
        $B = $Backups[$i]
        $SizeMB = [math]::Round($B.Size / 1MB, 1)
        Write-Host "  $($i + 1). v$($B.Version) ($($B.Created.ToString('yyyy-MM-dd HH:mm:ss'))) - $SizeMB MB"
    }
    Write-Host ""

    # Get selection
    do {
        $Selection = Read-Host "Select backup to restore (1-$($Backups.Count), or 'c' to cancel)"
        if ($Selection -eq 'c') {
            Write-Host ""
            Write-Host "Rollback cancelled." -ForegroundColor Yellow
            Write-Host ""
            exit 0
        }
    } while ($Selection -notmatch '^\d+$' -or [int]$Selection -lt 1 -or [int]$Selection -gt $Backups.Count)

    $SelectedBackup = $Backups[[int]$Selection - 1]

    # Confirm
    Write-Host ""
    Write-Host "WARNING: This will replace the current installation with v$($SelectedBackup.Version)" -ForegroundColor Yellow
    $Confirm = Read-Host "Are you sure? (y/n)"
    if ($Confirm -notmatch '^[yY]') {
        Write-Host ""
        Write-Host "Rollback cancelled." -ForegroundColor Yellow
        Write-Host ""
        exit 0
    }

    Write-Host ""

    try {
        $CurrentVersion = Get-CurrentVersion

        # Step 1: Stop service
        Show-Progress -Step 1 -Total 4 -Message "Stopping $ServiceName service..."
        $ServiceWasRunning = Stop-ApplicationService

        # Step 2: Restore files
        Show-Progress -Step 2 -Total 4 -Message "Restoring files from backup..."
        Restore-FromBackup -BackupPath $SelectedBackup.Path

        # Step 3: Checkout version
        Show-Progress -Step 3 -Total 4 -Message "Checking out v$($SelectedBackup.Version)..."
        Push-Location $InstallPath
        git checkout "v$($SelectedBackup.Version)" 2>&1 | Out-Null
        Pop-Location

        # Step 4: Start service
        Show-Progress -Step 4 -Total 4 -Message "Starting $ServiceName service..."
        if ($ServiceWasRunning) {
            Start-ApplicationService | Out-Null
        }

        # Health check
        Write-Host ""
        Write-Host "Health check: " -NoNewline
        $IsHealthy = Test-ApplicationHealth -MaxRetries 3 -DelaySeconds 5
        if ($IsHealthy) {
            Write-Host "OK" -ForegroundColor Green
        }
        else {
            Write-Host "FAILED" -ForegroundColor Red
        }

        # Log rollback
        Write-UpdateHistory -FromVersion $CurrentVersion -ToVersion $SelectedBackup.Version -Status "Rollback"

        # Success
        Write-Host ""
        Write-Host ("=" * 64) -ForegroundColor Cyan
        Write-Host "Rollback completed successfully!" -ForegroundColor Green
        Write-Host "  Restored to: v$($SelectedBackup.Version)"
        Write-Host ("=" * 64) -ForegroundColor Cyan
        Write-Host ""
    }
    catch {
        Write-Host ""
        Write-Host "ERROR: Rollback failed - $_" -ForegroundColor Red
        Write-Host ""

        if ($ServiceWasRunning) {
            Write-Host "Attempting to restart service..." -ForegroundColor Yellow
            Start-ApplicationService | Out-Null
        }
        exit 1
    }
}

function Invoke-ListBackupsMode {
    Show-Header "Available Backups"

    $Backups = Get-AvailableBackups

    if ($Backups.Count -eq 0) {
        Write-Host "No backups available." -ForegroundColor Yellow
        Write-Host "Backups are created automatically before each update." -ForegroundColor DarkGray
        Write-Host ""
        exit 0
    }

    Write-Host "Backups:" -ForegroundColor Cyan
    Write-Host ""
    foreach ($B in $Backups) {
        $SizeMB = [math]::Round($B.Size / 1MB, 1)
        Write-Host "  v$($B.Version)" -ForegroundColor White -NoNewline
        Write-Host " - $($B.Created.ToString('yyyy-MM-dd HH:mm:ss')) - $SizeMB MB" -ForegroundColor DarkGray
    }
    Write-Host ""
    Write-Host "To rollback: .\update.ps1 -Rollback" -ForegroundColor DarkGray
    Write-Host ""
}

function Invoke-HistoryMode {
    Show-Header "Update History"

    $History = Get-UpdateHistory

    if ($History.Count -eq 0) {
        Write-Host "No update history found." -ForegroundColor Yellow
        Write-Host ""
        exit 0
    }

    Write-Host "Recent Updates:" -ForegroundColor Cyan
    Write-Host ""
    foreach ($Entry in $History) {
        if ($Entry -match 'Success') {
            Write-Host $Entry -ForegroundColor Green
        }
        elseif ($Entry -match 'Failed') {
            Write-Host $Entry -ForegroundColor Red
        }
        elseif ($Entry -match 'Rollback') {
            Write-Host $Entry -ForegroundColor Yellow
        }
        else {
            Write-Host $Entry
        }
    }
    Write-Host ""
}

#endregion

#region Main Execution

function Main {
    try {
        if ($Check) {
            Invoke-CheckMode
        }
        elseif ($Rollback) {
            Invoke-RollbackMode
        }
        elseif ($ListBackups) {
            Invoke-ListBackupsMode
        }
        elseif ($History) {
            Invoke-HistoryMode
        }
        else {
            # Default: Update mode
            Invoke-UpdateMode -TargetVersion $Version
        }
    }
    catch {
        Write-Host ""
        Write-Host "FATAL ERROR: $_" -ForegroundColor Red
        Write-Host ""
        Write-Log "Fatal error: $_" -Level "ERROR"
        exit 1
    }
}

# Run main function
Main

#endregion
