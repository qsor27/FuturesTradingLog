# Tasks: Windows Manual Update Method

## Implementation Tasks

### Phase 1: Core Script Structure

- [ ] **Task 1.1**: Create `scripts/update.ps1` with parameter handling
  - Define all command-line parameters (-Check, -Yes, -Rollback, etc.)
  - Set up parameter sets for mutually exclusive modes
  - Add script header with synopsis and examples
  - **Estimate**: Small

- [ ] **Task 1.2**: Implement helper functions
  - `Test-AdminRights` - Check if running as administrator
  - `Show-Header` - Display formatted section headers
  - `Show-Progress` - Display step progress
  - `Write-Log` - Logging utility
  - **Estimate**: Small

- [ ] **Task 1.3**: Copy core functions from windows-auto-update.ps1
  - `Get-CurrentVersion`
  - `Get-LatestRelease`
  - `Compare-Versions`
  - `Stop-ApplicationService`
  - `Start-ApplicationService`
  - `Backup-Installation`
  - `Test-ApplicationHealth`
  - Adapt as needed for interactive use
  - **Estimate**: Medium

### Phase 2: Version Check Mode

- [ ] **Task 2.1**: Implement `Invoke-CheckMode`
  - Fetch current and latest versions
  - Display comparison with release date
  - Show appropriate message (update available / up to date)
  - Return correct exit codes
  - **Estimate**: Small

- [ ] **Task 2.2**: Add `Get-SpecificRelease` function
  - Fetch release info for a specific tag/version
  - Support `-Version v1.2.3` parameter
  - **Estimate**: Small

### Phase 3: Interactive Update Flow

- [ ] **Task 3.1**: Implement `Show-ReleaseNotes`
  - Parse GitHub release body (markdown-ish)
  - Format and colorize output
  - Handle empty release notes
  - **Estimate**: Small

- [ ] **Task 3.2**: Implement `Invoke-UpdateMode`
  - Show version comparison
  - Display release notes
  - Prompt for confirmation (unless -Yes)
  - Execute update steps with progress
  - Handle errors and show recovery options
  - **Estimate**: Medium

- [ ] **Task 3.3**: Add completion summary display
  - Show previous and new versions
  - Show backup location
  - Provide rollback command hint
  - **Estimate**: Small

### Phase 4: Rollback Capability

- [ ] **Task 4.1**: Implement `Get-AvailableBackups`
  - Scan backup directory
  - Parse version and date from folder names
  - Calculate folder sizes
  - Return sorted list (newest first)
  - **Estimate**: Small

- [ ] **Task 4.2**: Implement `Restore-FromBackup`
  - Remove current application files
  - Copy files from backup
  - Preserve data directory
  - **Estimate**: Small

- [ ] **Task 4.3**: Implement `Invoke-RollbackMode`
  - Display available backups
  - Get user selection
  - Confirm before proceeding
  - Execute restore with progress
  - Checkout corresponding git tag
  - Restart service and health check
  - **Estimate**: Medium

### Phase 5: Update History

- [ ] **Task 5.1**: Implement `Write-UpdateHistory`
  - Append to update-history.log
  - Include timestamp, versions, status
  - Handle log file creation
  - **Estimate**: Small

- [ ] **Task 5.2**: Implement `Get-UpdateHistory` and `Invoke-HistoryMode`
  - Read and parse history file
  - Display with color coding by status
  - Limit to recent entries
  - **Estimate**: Small

- [ ] **Task 5.3**: Implement `Invoke-ListBackupsMode`
  - Show available backups without interactive selection
  - Include size and date info
  - **Estimate**: Small

### Phase 6: Documentation

- [ ] **Task 6.1**: Update `docs/WINDOWS_INSTALL.md`
  - Add "Manual Updates" section
  - Document all update.ps1 commands
  - Add examples for common scenarios
  - **Estimate**: Small

- [ ] **Task 6.2**: Add inline help to script
  - Complete Get-Help documentation
  - Examples for each mode
  - Parameter descriptions
  - **Estimate**: Small

### Phase 7: Testing & Polish

- [ ] **Task 7.1**: Test version check mode
  - Test when up to date
  - Test when update available
  - Test network failure handling
  - **Estimate**: Small

- [ ] **Task 7.2**: Test update flow
  - Test full update cycle
  - Test -Yes flag
  - Test -Version flag
  - Test error handling
  - **Estimate**: Medium

- [ ] **Task 7.3**: Test rollback flow
  - Test with multiple backups
  - Test with no backups
  - Test restore integrity
  - **Estimate**: Medium

- [ ] **Task 7.4**: Test edge cases
  - No admin rights handling
  - Service not installed
  - Git not available
  - Interrupted operations
  - **Estimate**: Medium

---

## Task Dependencies

```
Phase 1 (Core) ──┬── Phase 2 (Check) ────────────────┐
                 │                                    │
                 ├── Phase 3 (Update) ───────────────┼── Phase 6 (Docs)
                 │                                    │
                 ├── Phase 4 (Rollback) ─────────────┤
                 │                                    │
                 └── Phase 5 (History) ──────────────┘
                                                      │
                                                      └── Phase 7 (Testing)
```

## Acceptance Checklist

- [ ] `.\update.ps1 -Check` shows version comparison without admin
- [ ] `.\update.ps1` shows release notes and prompts for confirmation
- [ ] `.\update.ps1 -Yes` updates without prompts
- [ ] `.\update.ps1 -Version v1.2.3` updates to specific version
- [ ] `.\update.ps1 -Rollback` lists backups and restores selected
- [ ] `.\update.ps1 -ListBackups` shows available backups
- [ ] `.\update.ps1 -History` shows update history
- [ ] Backups are created before every update
- [ ] Health check runs after update/rollback
- [ ] Update history is logged
- [ ] Clear error messages on failures
- [ ] Documentation is updated
