# Spec: Windows Complete Uninstall Method

## Overview

Create a comprehensive Windows uninstall script that removes all FuturesTradingLog components and dependencies with user options to preserve or delete underlying data/trades.

## Problem Statement

Currently, the `uninstall-service.ps1` script only removes the Windows service. Users who want to completely uninstall FuturesTradingLog from their Windows system must manually:
1. Remove the Windows service
2. Delete the Python virtual environment
3. Remove NSSM (if not used by other apps)
4. Delete the installation directory
5. Optionally remove Python/Git (if installed specifically for this app)
6. Clean up data directories
7. Remove scheduled tasks (auto-update, health-check)

This creates friction for users and may leave remnants on the system.

## Goals

1. **Complete Cleanup**: Provide a single script that can remove all FuturesTradingLog components
2. **Data Preservation Options**: Allow users to choose between complete removal or preserving their trade data
3. **Safe Defaults**: Default to preserving user data to prevent accidental data loss
4. **Transparency**: Show users exactly what will be removed before proceeding
5. **Dependency Awareness**: Handle shared dependencies (Python, Git, Memurai) appropriately

## User Stories

### US1: Complete Uninstall
As a user who no longer needs FuturesTradingLog, I want to completely remove all components from my system so that no remnants are left behind.

### US2: Reinstall Preparation
As a user who wants to do a fresh install, I want to remove the application while preserving my trade data so that I can reimport it after reinstalling.

### US3: Data Export Before Removal
As a user uninstalling the application, I want to export my data before removal so that I have a backup of my trading history.

## Functional Requirements

### FR1: Component Detection
The script MUST detect and list all installed components:
- Windows Service (FuturesTradingLog)
- Installation directory (C:\Program Files\FuturesTradingLog)
- Data directory (C:\ProgramData\FuturesTradingLog)
- Python virtual environment
- NSSM installation (C:\nssm)
- Scheduled Tasks (auto-update, health-check if any)
- Registry entries (if any)

### FR2: Interactive Removal Options
The script MUST provide interactive options for:
- **Full Uninstall**: Remove everything including data
- **Partial Uninstall**: Remove application but preserve data
- **Export & Uninstall**: Create data backup before full removal

### FR3: Data Backup
When requested, the script MUST:
- Create a timestamped backup of the database
- Export trade data to CSV format
- Save configuration files
- Store backups in a user-specified or default location

### FR4: Safe Dependency Handling
The script MUST handle dependencies safely:
- **NSSM**: Remove only if installed by our setup script (check marker file)
- **Python**: Notify user but do NOT auto-remove (may be used by other apps)
- **Git**: Notify user but do NOT auto-remove
- **Memurai/Redis**: Notify user but do NOT auto-remove

### FR5: Verification
The script MUST:
- Verify each removal step succeeded
- Report any components that couldn't be removed
- Suggest manual steps for any failures

## Non-Functional Requirements

### NFR1: Administrator Privileges
The script MUST require and verify administrator privileges upfront.

### NFR2: Confirmation Prompts
The script MUST require explicit confirmation before any destructive action.

### NFR3: Logging
The script MUST log all actions to a file that persists after uninstall.

### NFR4: Rollback Information
The script MUST provide information on how to reinstall if the user changes their mind.

## Components to Remove

| Component | Location | Always Remove | Optional |
|-----------|----------|---------------|----------|
| Windows Service | N/A | Yes | No |
| Installation Dir | C:\Program Files\FuturesTradingLog | Yes | No |
| Virtual Environment | <InstallPath>\venv | Yes | No |
| Data Directory | C:\ProgramData\FuturesTradingLog | No | Yes |
| Database | <DataPath>\db\ | No | Yes |
| Logs | <DataPath>\logs\ | No | Yes |
| Config | <DataPath>\config\ | No | Yes |
| NSSM | C:\nssm\ | No | Yes (if our marker exists) |
| Scheduled Tasks | Task Scheduler | Yes | No |

## User Interface Flow

```
========================================================
   FuturesTradingLog - Complete Uninstaller
========================================================

Detected Components:
  [x] Windows Service: FuturesTradingLog (Running)
  [x] Installation: C:\Program Files\FuturesTradingLog
  [x] Data Directory: C:\ProgramData\FuturesTradingLog
      - Database: 15.2 MB (1,234 trades)
      - Logs: 2.1 MB
      - Config: 12 KB
  [x] NSSM: C:\nssm\nssm.exe (installed by FTL setup)
  [ ] Python 3.11 (shared - will not be removed)
  [ ] Git 2.43 (shared - will not be removed)

Choose uninstall option:
  1. Keep my data (remove app only)
  2. Export data, then remove everything
  3. Remove everything (WARNING: data will be lost)
  4. Cancel

Selection: _
```

## Success Criteria

1. Single script removes all FuturesTradingLog components
2. User data can be preserved or exported before removal
3. No orphaned files or registry entries after uninstall
4. Clear feedback on what was removed
5. Admin privileges checked upfront
6. Shared dependencies (Python, Git, Memurai) not automatically removed

## Out of Scope

- Uninstalling Python, Git, or Memurai automatically
- Remote/silent uninstall (always interactive)
- Undo/rollback functionality
- Docker-based installations (use docker-compose down)

## Technical Notes

- Script will be named `uninstall-complete.ps1`
- Existing `uninstall-service.ps1` will be kept for service-only removal
- Marker file `.installed-by-ftl` will track NSSM installation source
- Backup format: ZIP archive with database + CSV exports + configs
