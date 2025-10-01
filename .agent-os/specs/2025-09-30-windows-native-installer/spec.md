# Spec Requirements Document

> Spec: Windows Native Installer
> Created: 2025-09-30
> Status: Planning

## Overview

Create a professional Windows installer using PyInstaller and Inno Setup that bundles the Python runtime, Redis portable binaries, and all application dependencies into a single-click installation experience. The installer will configure Windows Services using NSSM for background processes, establish proper directory structures in Program Files and ProgramData, and provide a complete uninstaller that cleanly removes all services, files, and registry entries.

## User Stories

1. **As an end user**, I want to install the Futures Trading Log application with a simple installer wizard that handles all dependencies and configuration automatically, so I don't need to manually install Python, Redis, or configure services.

2. **As a system administrator**, I want the application to run as a Windows Service that starts automatically on boot and can be managed through standard Windows service management tools, so the application integrates properly with Windows enterprise environments.

3. **As an end user uninstalling the application**, I want a complete uninstaller that removes all services, files, and registry entries cleanly, so there are no leftover components or background processes after removal.

## Spec Scope

1. **PyInstaller Application Bundling**: Package the Flask application, all Python dependencies, and Python 3.13.5 runtime into standalone executables for the main application, Celery workers, and file watcher components.

2. **Redis Integration**: Bundle Redis for Windows portable binaries (~5-10MB) with the installer and configure automatic startup as a Windows Service with appropriate persistence settings.

3. **Windows Service Configuration**: Use NSSM (Non-Sucking Service Manager) to create and configure Windows Services for the Flask application, Redis server, Celery workers, and file watcher, with proper startup dependencies and failure recovery settings.

4. **Installer Wizard**: Create an Inno Setup installer script that provides a professional installation wizard with license agreement, installation directory selection, service configuration options, and desktop/start menu shortcuts.

5. **Complete Uninstaller**: Implement comprehensive uninstallation that stops and removes all Windows Services, deletes application files from Program Files, optionally preserves or removes user data from ProgramData, cleans up registry entries, and removes shortcuts.

## Out of Scope

1. **Linux/macOS Installers**: This spec focuses exclusively on Windows installation. Cross-platform installers are not included.

2. **Docker Deployment Changes**: Existing Docker-based deployment will remain unchanged. This installer is an alternative deployment method.

3. **Auto-Update Functionality**: Automatic update checking and installation will be addressed in a future phase. Initial release requires manual reinstallation for updates.

4. **Multi-User Configuration**: Initial release targets single-user or single-instance installations. Multi-tenant support is deferred.

## Expected Deliverable

1. **Professional Windows Installer**: A single `FuturesTradingLog-Setup-vX.X.X.exe` installer file that bundles all components and provides a wizard-based installation experience with customization options.

2. **Windows Service Integration**: Four Windows Services configured via NSSM:
   - FuturesTradingLog-Web (Flask application on port 5555)
   - FuturesTradingLog-Redis (Redis server on port 6379)
   - FuturesTradingLog-Worker (Celery background worker)
   - FuturesTradingLog-FileWatcher (NinjaTrader CSV file monitoring)

3. **Clean Uninstall Process**: Complete uninstaller accessible via Windows Programs and Features that:
   - Stops all running services gracefully
   - Removes all Windows Services
   - Deletes application files from Program Files
   - Prompts user to preserve or delete data files in ProgramData
   - Removes all registry entries and shortcuts
   - Provides uninstallation progress feedback

4. **Build Automation Scripts**: Python scripts and batch files for automating the build process:
   - PyInstaller build script for creating executables
   - Inno Setup compilation script
   - Version management and release packaging
   - Testing and validation scripts

## Spec Documentation

- Tasks: @.agent-os/specs/2025-09-30-windows-native-installer/tasks.md
- Technical Specification: @.agent-os/specs/2025-09-30-windows-native-installer/sub-specs/technical-spec.md
