# Spec Tasks

## Tasks

- [x] 1. Create PowerShell Auto-Update Script
  - [x] 1.1 Create `scripts/windows-auto-update.ps1` with GitHub release checking
  - [x] 1.2 Implement version comparison logic
  - [x] 1.3 Add download and extraction functionality
  - [x] 1.4 Add service stop/start with backup
  - [x] 1.5 Add optional Discord notification on update
  - [x] 1.6 Test script manually with current version

- [x] 2. Create Service Management Scripts
  - [x] 2.1 Create `scripts/install-service.ps1` with full NSSM configuration
  - [x] 2.2 Create `scripts/uninstall-service.ps1` for clean removal
  - [x] 2.3 Create `scripts/health-check.ps1` for service monitoring
  - [x] 2.4 Add environment variable configuration in install script
  - [x] 2.5 Test service installation and restart behavior

- [x] 3. Update WINDOWS_INSTALL.md - Prerequisites Section
  - [x] 3.1 Add detailed Memurai installation steps
  - [x] 3.2 Document winget installation commands for all prerequisites
  - [x] 3.3 Add verification commands for each prerequisite

- [x] 4. Update WINDOWS_INSTALL.md - Environment Variables Section
  - [x] 4.1 Create complete environment variable reference table
  - [x] 4.2 Document Docker vs Windows default differences
  - [x] 4.3 Add .env file template with all variables
  - [x] 4.4 Document DISCORD_WEBHOOK_URL setup

- [x] 5. Update WINDOWS_INSTALL.md - File Paths Section
  - [x] 5.1 Document complete directory structure
  - [x] 5.2 Add generic template paths
  - [x] 5.3 Add real-world example paths (C:\Projects\, C:\Containers\)
  - [x] 5.4 Create file path quick reference table

- [x] 6. Update WINDOWS_INSTALL.md - Auto-Update Section
  - [x] 6.1 Document PowerShell script usage
  - [x] 6.2 Add Task Scheduler setup instructions
  - [x] 6.3 Document update notification options

- [x] 7. Update WINDOWS_INSTALL.md - Service Management Section
  - [x] 7.1 Document NSSM installation and configuration
  - [x] 7.2 Add restart policy configuration (Docker equivalent)
  - [x] 7.3 Document logging configuration
  - [x] 7.4 Add health check setup instructions

- [x] 8. Final Verification
  - [x] 8.1 Review documentation completeness vs docker-compose.yml
  - [x] 8.2 Verify all file paths are correct
  - [x] 8.3 All scripts created and functional
  - [x] 8.4 Spec completed

## Summary

All tasks completed. Created:
- `scripts/windows-auto-update.ps1` - Watchtower equivalent for automatic updates
- `scripts/install-service.ps1` - One-command NSSM service installation
- `scripts/uninstall-service.ps1` - Clean service removal
- `scripts/health-check.ps1` - Health monitoring with auto-restart
- `docs/WINDOWS_INSTALL.md` - Comprehensive Windows installation guide with full Docker parity
