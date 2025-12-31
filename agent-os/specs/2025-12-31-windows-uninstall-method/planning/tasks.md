# Tasks: Windows Complete Uninstall Method

## Overview
Implementation of `uninstall-complete.ps1` - a comprehensive PowerShell script for complete removal of FuturesTradingLog from Windows.

---

## Task 1: Create Core Script Structure
**Priority:** High | **Estimate:** Small

Create the base `uninstall-complete.ps1` script with:
- Parameter definitions (InstallPath, DataPath, NssmPath, BackupPath, etc.)
- Administrator check function
- Logging infrastructure
- Main orchestration skeleton

**Files:**
- `scripts/uninstall-complete.ps1` (create)

**Acceptance Criteria:**
- [ ] Script has all parameters defined with defaults
- [ ] Administrator check exits with clear message if not elevated
- [ ] Logging writes to `%USERPROFILE%\FuturesTradingLog_Uninstall.log`
- [ ] Main function structure in place

---

## Task 2: Implement Component Detection
**Priority:** High | **Estimate:** Small

Implement functions to detect all installed components:
- `Get-InstalledComponents`: Detects service, paths, NSSM, scheduled tasks
- `Get-DataDirectoryInfo`: Gets database size, trade count, log sizes
- `Test-NssmInstalledByUs`: Checks for marker file

**Files:**
- `scripts/uninstall-complete.ps1` (modify)

**Acceptance Criteria:**
- [ ] Detects Windows service and its status
- [ ] Detects installation directory with size
- [ ] Detects data directory with breakdown (db, logs, config)
- [ ] Counts trades in database using Python/sqlite
- [ ] Detects NSSM and whether we installed it
- [ ] Detects any FuturesTradingLog scheduled tasks

---

## Task 3: Implement Data Backup Functions
**Priority:** High | **Estimate:** Medium

Implement backup functionality:
- `Export-TradeData`: Exports executions and positions to CSV
- `Backup-Database`: Copies database files
- `Create-BackupArchive`: Creates timestamped ZIP archive

**Files:**
- `scripts/uninstall-complete.ps1` (modify)

**Acceptance Criteria:**
- [ ] Creates backup directory with timestamp
- [ ] Copies database files to backup
- [ ] Copies config files to backup
- [ ] Exports trades to CSV format
- [ ] Creates ZIP archive of backup
- [ ] Returns path to created backup
- [ ] Handles missing database gracefully

---

## Task 4: Implement Removal Functions
**Priority:** High | **Estimate:** Medium

Implement removal functions:
- `Remove-WindowsService`: Stops and removes the service
- `Remove-InstallationDirectory`: Removes install dir and venv
- `Remove-DataDirectory`: Removes data directory
- `Remove-Nssm`: Removes NSSM if we installed it and no other services use it
- `Remove-ScheduledTasks`: Removes any FTL scheduled tasks

**Files:**
- `scripts/uninstall-complete.ps1` (modify)

**Acceptance Criteria:**
- [ ] Stops service before removal
- [ ] Kills any Python processes from our venv
- [ ] Removes installation directory completely
- [ ] Removes data directory if requested
- [ ] Only removes NSSM if marker file exists and no other services use it
- [ ] Removes all FuturesTradingLog scheduled tasks
- [ ] Each function returns success/failure status

---

## Task 5: Implement Interactive UI
**Priority:** High | **Estimate:** Small

Implement the user interface:
- `Show-DetectedComponents`: Displays found components with sizes
- `Get-UserChoice`: Presents menu and gets user selection
- Confirmation prompts for destructive actions

**Files:**
- `scripts/uninstall-complete.ps1` (modify)

**Acceptance Criteria:**
- [ ] Shows formatted list of detected components
- [ ] Displays sizes in human-readable format (MB, KB)
- [ ] Shows trade count from database
- [ ] Presents 4 options (keep data, export & remove, remove all, cancel)
- [ ] Requires explicit confirmation for data removal
- [ ] Shows progress during uninstall

---

## Task 6: Implement Main Orchestration
**Priority:** High | **Estimate:** Small

Implement the main uninstall flow:
- Detect components
- Show UI
- Execute selected option
- Verify and report results

**Files:**
- `scripts/uninstall-complete.ps1` (modify)

**Acceptance Criteria:**
- [ ] Orchestrates full uninstall flow
- [ ] Handles all three removal options
- [ ] Creates backup when option 2 selected
- [ ] Verifies each removal step succeeded
- [ ] Reports any components that couldn't be removed
- [ ] Shows final summary
- [ ] Provides reinstall instructions

---

## Task 7: Update setup-windows.ps1 for NSSM Marker
**Priority:** Medium | **Estimate:** Small

Modify setup script to create marker file when NSSM is installed.

**Files:**
- `scripts/setup-windows.ps1` (modify)

**Acceptance Criteria:**
- [ ] Creates `.installed-by-ftl` marker file when NSSM is installed
- [ ] Marker includes installation timestamp
- [ ] Existing installations without marker handled gracefully

---

## Task 8: Update Documentation
**Priority:** Medium | **Estimate:** Small

Update Windows installation documentation with uninstall instructions.

**Files:**
- `docs/WINDOWS_INSTALL.md` (modify)

**Acceptance Criteria:**
- [ ] Documents `uninstall-complete.ps1` usage
- [ ] Explains all options (keep data, export, remove all)
- [ ] Documents backup location and contents
- [ ] Explains what is and isn't removed
- [ ] Provides manual cleanup steps for shared dependencies

---

## Task 9: Testing
**Priority:** High | **Estimate:** Medium

Test the uninstall script thoroughly.

**Test Cases:**
- [ ] Full uninstall on complete installation
- [ ] Uninstall with data preservation
- [ ] Uninstall with data export
- [ ] Partial installation (missing components)
- [ ] NSSM used by other services (should not be removed)
- [ ] Locked files handling
- [ ] Backup archive integrity
- [ ] CSV export data verification

---

## Summary

| Task | Priority | Estimate | Dependencies |
|------|----------|----------|--------------|
| 1. Core Script Structure | High | Small | None |
| 2. Component Detection | High | Small | Task 1 |
| 3. Data Backup Functions | High | Medium | Task 1 |
| 4. Removal Functions | High | Medium | Task 1 |
| 5. Interactive UI | High | Small | Task 2 |
| 6. Main Orchestration | High | Small | Tasks 2-5 |
| 7. Setup Script Marker | Medium | Small | None |
| 8. Documentation | Medium | Small | Tasks 1-6 |
| 9. Testing | High | Medium | All |

**Total Estimated Effort:** Medium (2-3 hours implementation)
