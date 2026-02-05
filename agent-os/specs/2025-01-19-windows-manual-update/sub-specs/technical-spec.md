# Technical Spec: Windows Manual Update Method

## Architecture Overview

The update script is a single PowerShell file with modular functions, reusing logic from `windows-auto-update.ps1` where applicable.

```
update.ps1
├── Parameter Handling
│   ├── -Check (Check mode)
│   ├── -Yes (Non-interactive)
│   ├── -Rollback (Rollback mode)
│   ├── -ListBackups (List mode)
│   ├── -History (History mode)
│   └── -Version <tag> (Specific version)
├── Version Functions (reuse from auto-update)
│   ├── Get-CurrentVersion
│   ├── Get-LatestRelease
│   └── Compare-Versions
├── Display Functions
│   ├── Show-VersionComparison
│   ├── Show-ReleaseNotes
│   ├── Show-UpdateProgress
│   └── Show-BackupList
├── Update Functions (reuse from auto-update)
│   ├── Stop-ApplicationService
│   ├── Start-ApplicationService
│   ├── Backup-Installation
│   ├── Update-Application
│   └── Test-ApplicationHealth
├── Rollback Functions
│   ├── Get-AvailableBackups
│   ├── Restore-FromBackup
│   └── Checkout-Version
├── History Functions
│   ├── Write-UpdateHistory
│   └── Get-UpdateHistory
└── Main Orchestration
    ├── Invoke-CheckMode
    ├── Invoke-UpdateMode
    ├── Invoke-RollbackMode
    └── Invoke-HistoryMode
```

## Implementation Details

### 1. Script Parameters

```powershell
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
```

### 2. Version Check Mode

```powershell
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
        Write-Host "Run '.\update.ps1' to update interactively."
        exit 1  # Exit code 1 = update available
    }
    else {
        Write-Host "You are running the latest version." -ForegroundColor Green
        exit 0  # Exit code 0 = up to date
    }
}
```

### 3. Release Notes Display

```powershell
function Show-ReleaseNotes {
    param([hashtable]$Release)

    Write-Host ""
    Write-Host "Release Notes:" -ForegroundColor Yellow
    Write-Host ("-" * 50) -ForegroundColor DarkGray

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

    Write-Host ("-" * 50) -ForegroundColor DarkGray
    Write-Host ""
}
```

### 4. Interactive Update Flow

```powershell
function Invoke-UpdateMode {
    param([string]$TargetVersion)

    # Check admin rights for update
    if (-not (Test-AdminRights)) {
        Write-Host "ERROR: Administrator privileges required for updates." -ForegroundColor Red
        Write-Host "Right-click PowerShell and select 'Run as Administrator'"
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
        Write-Host "You are already running the latest version." -ForegroundColor Green
        exit 0
    }

    # Show release notes
    Show-ReleaseNotes -Release $LatestRelease

    # Confirm unless -Yes
    if (-not $Yes) {
        $Confirm = Read-Host "Do you want to update now? (y/n)"
        if ($Confirm -notmatch '^[yY]') {
            Write-Host "Update cancelled." -ForegroundColor Yellow
            exit 0
        }
    }

    Write-Host ""

    try {
        # Step 1: Backup
        Show-Progress -Step 1 -Total 6 -Message "Creating backup of v$CurrentVersion..."
        $BackupPath = Backup-Installation -Version $CurrentVersion
        Write-Host "      Backup saved to: $BackupPath" -ForegroundColor DarkGray

        # Step 2: Stop service
        Show-Progress -Step 2 -Total 6 -Message "Stopping $ServiceName service..."
        $ServiceWasRunning = Stop-ApplicationService

        # Step 3: Fetch
        Show-Progress -Step 3 -Total 6 -Message "Fetching latest changes..."
        Push-Location $InstallPath
        git fetch --all --tags 2>&1 | Out-Null

        # Step 4: Checkout
        Show-Progress -Step 4 -Total 6 -Message "Checking out $($LatestRelease.TagName)..."
        git checkout $LatestRelease.TagName 2>&1 | Out-Null
        Pop-Location

        # Step 5: Dependencies
        Show-Progress -Step 5 -Total 6 -Message "Updating Python dependencies..."
        $VenvPython = Join-Path $InstallPath "venv\Scripts\python.exe"
        & $VenvPython -m pip install -r (Join-Path $InstallPath "requirements.txt") -q 2>&1 | Out-Null

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

        # Log failure
        Write-UpdateHistory -FromVersion $CurrentVersion -ToVersion $LatestRelease.Version -Status "Failed" -Error $_

        # Try to restart service
        if ($ServiceWasRunning) {
            Write-Host "Attempting to restart service..."
            Start-ApplicationService | Out-Null
        }

        Write-Host ""
        Write-Host "To rollback: .\update.ps1 -Rollback" -ForegroundColor Yellow
        exit 1
    }
}
```

### 5. Rollback Functions

```powershell
function Get-AvailableBackups {
    $BackupDir = Join-Path $DataPath "backups"

    if (-not (Test-Path $BackupDir)) {
        return @()
    }

    $Backups = Get-ChildItem -Path $BackupDir -Directory |
        Where-Object { $_.Name -match '^v?[\d\.]+_\d{8}_\d{6}$' -or $_.Name -match '^backup_v' } |
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

function Invoke-RollbackMode {
    # Check admin rights
    if (-not (Test-AdminRights)) {
        Write-Host "ERROR: Administrator privileges required for rollback." -ForegroundColor Red
        exit 1
    }

    Show-Header "Rollback"

    $Backups = Get-AvailableBackups

    if ($Backups.Count -eq 0) {
        Write-Host "No backups available for rollback." -ForegroundColor Yellow
        Write-Host "Backups are created automatically before each update."
        exit 1
    }

    # Display backups
    Write-Host "Available Backups:" -ForegroundColor Cyan
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
            Write-Host "Rollback cancelled." -ForegroundColor Yellow
            exit 0
        }
    } while ($Selection -notmatch '^\d+$' -or [int]$Selection -lt 1 -or [int]$Selection -gt $Backups.Count)

    $SelectedBackup = $Backups[[int]$Selection - 1]

    # Confirm
    Write-Host ""
    Write-Host "WARNING: This will replace the current installation with v$($SelectedBackup.Version)" -ForegroundColor Yellow
    $Confirm = Read-Host "Are you sure? (y/n)"
    if ($Confirm -notmatch '^[yY]') {
        Write-Host "Rollback cancelled." -ForegroundColor Yellow
        exit 0
    }

    try {
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
        $CurrentVersion = Get-CurrentVersion
        Write-UpdateHistory -FromVersion $CurrentVersion -ToVersion $SelectedBackup.Version -Status "Rollback"

        # Success
        Write-Host ""
        Write-Host ("=" * 60) -ForegroundColor Cyan
        Write-Host "Rollback completed successfully!" -ForegroundColor Green
        Write-Host "  Restored to: v$($SelectedBackup.Version)"
        Write-Host ("=" * 60) -ForegroundColor Cyan
    }
    catch {
        Write-Host "ERROR: Rollback failed - $_" -ForegroundColor Red

        if ($ServiceWasRunning) {
            Write-Host "Attempting to restart service..."
            Start-ApplicationService | Out-Null
        }
        exit 1
    }
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
```

### 6. Update History

```powershell
function Write-UpdateHistory {
    param(
        [string]$FromVersion,
        [string]$ToVersion,
        [string]$Status,
        [string]$Error = ""
    )

    $HistoryFile = Join-Path $DataPath "logs\update-history.log"
    $HistoryDir = Split-Path $HistoryFile -Parent

    if (-not (Test-Path $HistoryDir)) {
        New-Item -ItemType Directory -Path $HistoryDir -Force | Out-Null
    }

    $Entry = @{
        Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        FromVersion = $FromVersion
        ToVersion = $ToVersion
        Status = $Status
        Error = $Error
    }

    $Line = "$($Entry.Timestamp) | $($Entry.Status.PadRight(8)) | v$($Entry.FromVersion) -> v$($Entry.ToVersion)"
    if ($Error) {
        $Line += " | Error: $Error"
    }

    Add-Content -Path $HistoryFile -Value $Line
}

function Get-UpdateHistory {
    $HistoryFile = Join-Path $DataPath "logs\update-history.log"

    if (-not (Test-Path $HistoryFile)) {
        return @()
    }

    return Get-Content $HistoryFile | Select-Object -Last 20
}

function Invoke-HistoryMode {
    Show-Header "Update History"

    $History = Get-UpdateHistory

    if ($History.Count -eq 0) {
        Write-Host "No update history found." -ForegroundColor Yellow
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
}
```

### 7. Helper Functions

```powershell
function Test-AdminRights {
    $Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = New-Object Security.Principal.WindowsPrincipal($Identity)
    return $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Show-Header {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "   FuturesTradingLog - $Title" -ForegroundColor White
    Write-Host ("=" * 60) -ForegroundColor Cyan
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

function Show-CompletionMessage {
    param(
        [string]$Previous,
        [string]$Current,
        [string]$BackupPath
    )

    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "Update completed successfully!" -ForegroundColor Green
    Write-Host "  Previous: v$Previous"
    Write-Host "  Current:  v$Current"
    Write-Host "  Backup:   $(Split-Path $BackupPath -Leaf)"
    Write-Host ""
    Write-Host "To rollback: .\update.ps1 -Rollback" -ForegroundColor DarkGray
    Write-Host ("=" * 60) -ForegroundColor Cyan
}
```

## File Structure

```
scripts/
├── update.ps1                    # NEW: Manual update script
├── windows-auto-update.ps1       # EXISTING: Scheduled auto-update
├── install-service.ps1           # EXISTING: Service installation
├── uninstall-service.ps1         # EXISTING: Service removal
└── uninstall-complete.ps1        # PLANNED: Complete uninstall

<DataPath>/
├── backups/
│   ├── v1.0.0_20250119_143022/   # Backup before update
│   ├── v0.9.5_20250110_091500/
│   └── ...
└── logs/
    ├── auto-update.log           # EXISTING: Auto-update log
    └── update-history.log        # NEW: Manual update history
```

## Code Reuse from windows-auto-update.ps1

The following functions should be extracted/shared:

| Function | Current Location | Reuse Strategy |
|----------|-----------------|----------------|
| `Get-CurrentVersion` | windows-auto-update.ps1 | Copy or dot-source |
| `Get-LatestRelease` | windows-auto-update.ps1 | Copy or dot-source |
| `Compare-Versions` | windows-auto-update.ps1 | Copy or dot-source |
| `Stop-ApplicationService` | windows-auto-update.ps1 | Copy or dot-source |
| `Start-ApplicationService` | windows-auto-update.ps1 | Copy or dot-source |
| `Backup-Installation` | windows-auto-update.ps1 | Copy or dot-source |
| `Update-Application` | windows-auto-update.ps1 | Copy or dot-source |
| `Test-ApplicationHealth` | windows-auto-update.ps1 | Copy or dot-source |

**Recommendation**: Keep functions duplicated in `update.ps1` for simplicity (single-file distribution). Document that changes should be synced between both files.

## Error Handling

| Scenario | Handling |
|----------|----------|
| No network | Show clear error, suggest checking connection |
| GitHub API rate limit | Show error with retry suggestion |
| Git not found | Show error with installation instructions |
| Service won't stop | Attempt taskkill, then warn user |
| Backup fails | Abort update, preserve current state |
| Pip install fails | Continue but warn, may need manual fix |
| Health check fails | Complete update but warn user |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success / Up to date |
| 1 | Update available (check mode) / Error |
| 2 | User cancelled |

## Testing Considerations

1. **Version check without admin** - Should work for non-admin users
2. **Update with no backup dir** - Should create directory
3. **Rollback with no backups** - Should show clear message
4. **Network failure during update** - Should not corrupt installation
5. **Service not installed** - Should handle gracefully
6. **Interrupted update** - Should be recoverable
