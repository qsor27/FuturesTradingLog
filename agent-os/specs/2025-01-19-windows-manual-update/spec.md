# Spec: Windows Manual Update Method

> Created: 2025-01-19
> Related: 2025-12-27-windows-install-docs, 2025-12-31-windows-uninstall-method

## Overview

Create an interactive, user-initiated update script for Windows native installations that allows users to easily check for updates, review changes, and apply updates on demand with rollback capability.

## Problem Statement

The existing `windows-auto-update.ps1` is designed for unattended scheduled execution (like Docker's Watchtower). However, users need a way to:

1. Manually check if updates are available without waiting for the scheduled task
2. Review release notes before deciding to update
3. Apply updates immediately when they want them
4. Rollback to a previous version if an update causes issues
5. Update even if the scheduled auto-update task isn't configured

Currently, users must either wait for the scheduled task or manually run git commands, which is error-prone and doesn't provide a good user experience.

## Goals

1. **Easy Version Check**: Single command to see current vs available version
2. **Informed Updates**: Display release notes/changelog before updating
3. **User Control**: Interactive prompts for confirmation before changes
4. **Rollback Support**: Easy way to revert to previous version from backup
5. **Independence**: Works without requiring scheduled task configuration
6. **Consistency**: Uses same update logic as auto-update for reliability

## User Stories

### US1: Check for Updates
As a Windows user, I want to quickly check if a new version is available so I can decide whether to update now or later.

**Acceptance Criteria:**
- Single command shows current version and latest available version
- Indicates if update is available or if already on latest
- Shows when the latest release was published
- Non-destructive (read-only check)

### US2: Interactive Update
As a Windows user, I want to update the application interactively so I can review what's changing before applying the update.

**Acceptance Criteria:**
- Shows current version, new version, and release notes
- Asks for confirmation before proceeding
- Stops service, applies update, restarts service
- Creates backup before updating
- Shows progress and completion status
- Verifies application health after update

### US3: Rollback to Previous Version
As a Windows user who updated and encountered issues, I want to rollback to the previous version so I can restore working functionality.

**Acceptance Criteria:**
- Lists available backups with versions and dates
- Allows selection of which backup to restore
- Confirms before overwriting current installation
- Restores from backup and restarts service
- Verifies application health after rollback

### US4: View Update History
As a Windows user, I want to see the history of updates applied so I can track what versions have been installed.

**Acceptance Criteria:**
- Shows list of past updates with dates and versions
- Indicates success/failure status of each update
- Shows available backups for rollback

## Functional Requirements

### FR1: Version Check Mode
The script MUST support a check-only mode that:
- Queries GitHub releases API for latest version
- Compares with currently installed version
- Displays version comparison without making changes
- Returns exit code indicating if update is available (0=up-to-date, 1=update available)

### FR2: Interactive Update Flow
The script MUST provide an interactive update flow:
1. Display current version
2. Fetch and display latest version with release notes
3. Prompt for confirmation to proceed
4. Create backup of current installation
5. Stop Windows service
6. Apply update (git fetch + checkout)
7. Update Python dependencies
8. Start Windows service
9. Verify application health
10. Display completion summary

### FR3: Backup Management
The script MUST manage update backups:
- Create timestamped backup before each update
- Store backups in `<DataPath>\backups\`
- Keep configurable number of recent backups (default: 5)
- Include version info in backup folder name

### FR4: Rollback Capability
The script MUST support rollback:
- List available backups with version and date
- Allow user to select backup to restore
- Restore application files from backup
- Checkout corresponding git tag
- Restart service after rollback
- Verify application health

### FR5: Update History
The script MUST maintain update history:
- Log each update attempt with timestamp, versions, and status
- Store in persistent log file
- Display history on request

## Non-Functional Requirements

### NFR1: Administrator Privileges
The script MUST check for and require administrator privileges for update/rollback operations. Version check mode should work without admin rights.

### NFR2: Error Handling
The script MUST handle errors gracefully:
- Network failures during GitHub API calls
- Git operation failures
- Service start/stop failures
- Backup/restore failures
- Provide clear error messages and recovery suggestions

### NFR3: Idempotency
The script MUST be safe to run multiple times:
- Re-running update when already on latest should no-op gracefully
- Interrupted updates should be recoverable

### NFR4: Minimal Downtime
The script MUST minimize service downtime:
- Only stop service when ready to apply changes
- Restart service as soon as update is complete

## User Interface

### Command Examples

```powershell
# Check for updates (no admin required)
.\update.ps1 -Check

# Interactive update (requires admin)
.\update.ps1

# Update without prompts (for scripting)
.\update.ps1 -Yes

# List available backups
.\update.ps1 -ListBackups

# Rollback to previous version
.\update.ps1 -Rollback

# View update history
.\update.ps1 -History

# Update to specific version
.\update.ps1 -Version v1.2.3
```

### Interactive Update Flow

```
================================================================
   FuturesTradingLog - Update Manager
================================================================

Current Version: 1.0.0
Latest Version:  1.1.0 (released 2025-01-15)

Release Notes:
--------------
## What's New
- Added position custom fields
- Improved chart performance
- Fixed CSV import edge cases

## Breaking Changes
- None

Do you want to update now? (y/n): y

[1/6] Creating backup of v1.0.0...
      Backup saved to: C:\ProgramData\FuturesTradingLog\backups\v1.0.0_20250119_143022
[2/6] Stopping FuturesTradingLog service...
[3/6] Fetching latest changes...
[4/6] Checking out v1.1.0...
[5/6] Updating Python dependencies...
[6/6] Starting FuturesTradingLog service...

Health check: OK

================================================================
Update completed successfully!
  Previous: v1.0.0
  Current:  v1.1.0
  Backup:   v1.0.0_20250119_143022

To rollback: .\update.ps1 -Rollback
================================================================
```

### Rollback Flow

```
================================================================
   FuturesTradingLog - Rollback
================================================================

Available Backups:
  1. v1.0.0 (2025-01-19 14:30:22) - 15.2 MB
  2. v0.9.5 (2025-01-10 09:15:00) - 14.8 MB
  3. v0.9.0 (2025-01-01 12:00:00) - 14.5 MB

Select backup to restore (1-3, or 'c' to cancel): 1

WARNING: This will replace the current installation with v1.0.0
Are you sure? (y/n): y

[1/4] Stopping FuturesTradingLog service...
[2/4] Restoring files from backup...
[3/4] Checking out v1.0.0...
[4/4] Starting FuturesTradingLog service...

Health check: OK

================================================================
Rollback completed successfully!
  Restored to: v1.0.0
================================================================
```

## Success Criteria

1. Users can check for updates with a single command
2. Interactive update shows release notes before proceeding
3. Updates create backups automatically
4. Rollback restores from backup successfully
5. Update history is maintained and viewable
6. Works independently of scheduled auto-update
7. Clear error messages guide users on failures

## Out of Scope

- Automatic/scheduled updates (handled by existing `windows-auto-update.ps1`)
- GUI interface (CLI only)
- Remote update management
- Multi-instance updates
- Database migrations (handled by application startup)

## Dependencies

- Existing `windows-auto-update.ps1` logic (reuse where possible)
- Git installed and in PATH
- PowerShell 5.1+
- Windows Service installed via NSSM

## Deliverables

1. **`scripts/update.ps1`** - Main interactive update script
2. **Updated `docs/WINDOWS_INSTALL.md`** - Document manual update commands
3. **`<DataPath>/logs/update-history.log`** - Persistent update history log
