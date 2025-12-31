# Raw Idea

We need a Windows uninstall method that removes all dependencies and allows the user to choose to either save the underlying data/trades they have imported or completely remove everything.

## Key Requirements:
- Uninstall script (PowerShell) that removes all installed dependencies
- Option to preserve user data (database, trades, config) or completely remove everything
- Clean removal of Windows service (FuturesTradingLog)
- Remove NSSM if installed by our setup
- Remove Python virtual environment
- Optionally remove Python/Git if they were installed by our setup
- Handle Memurai/Redis (notify user but don't auto-remove as it may be used by other apps)
- Create data backup before removal if user wants to preserve data
- Provide clear summary of what will be removed
