# Spec-Lite: Windows Complete Uninstall Method

## What We're Building

A comprehensive PowerShell uninstall script (`uninstall-complete.ps1`) that removes all FuturesTradingLog components from Windows with options to preserve or backup user data.

## The Problem

Current `uninstall-service.ps1` only removes the Windows service. Users must manually clean up:
- Installation directory and Python venv
- Data directory (database, logs, config)
- NSSM installation
- Scheduled tasks

## The Solution

A single interactive script that:
1. **Detects** all installed components
2. **Shows** what will be removed with sizes
3. **Offers** three removal options:
   - Keep data (app-only removal)
   - Export data then full removal
   - Full removal without backup
4. **Removes** all FTL components cleanly
5. **Preserves** shared dependencies (Python, Git, Memurai)

## Key Features

| Feature | Description |
|---------|-------------|
| Component Detection | Finds service, install dir, data dir, NSSM, scheduled tasks |
| Data Backup | Creates ZIP with database + CSV exports + configs |
| Safe Defaults | Preserves data unless explicitly removed |
| NSSM Handling | Only removes if installed by our setup (marker file) |
| Verification | Confirms each step succeeded |
| Logging | Persists log after uninstall |

## User Flow

```
1. Run script as Administrator
2. See detected components and data sizes
3. Choose: Keep Data | Export & Remove | Remove All | Cancel
4. Confirm selection
5. Watch removal progress
6. Get summary of what was removed
```

## What Gets Removed

**Always Removed:**
- Windows Service (FuturesTradingLog)
- Installation directory + venv
- Scheduled tasks

**Optionally Removed:**
- Data directory (database, logs, config)
- NSSM (if we installed it)

**Never Auto-Removed:**
- Python (shared)
- Git (shared)
- Memurai/Redis (shared)

## Success Criteria

- Single script handles complete uninstall
- User data preserved by default
- Export option creates usable backup
- No orphaned files after uninstall
- Clear feedback throughout process
