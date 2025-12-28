# Spec Requirements Document

> Spec: Windows Installation Documentation Update
> Created: 2025-12-27

## Overview

Update the Windows installation documentation to achieve full feature parity with Docker deployment, including auto-update mechanisms, comprehensive service management, and explicit file path configurations for both generic and real-world environments.

## User Stories

### Complete Windows Native Setup

As a Windows user, I want comprehensive installation documentation that mirrors all Docker deployment features, so that I can run the application natively with the same capabilities as the containerized version.

I need clear instructions for:
- Installing all prerequisites (Python, Git, Redis/Memurai)
- Configuring environment variables with the same options as docker-compose
- Setting up automatic updates similar to Watchtower
- Managing the application as a Windows service
- Understanding exactly which files go where

### Automatic Version Updates

As a user running the native Windows installation, I want automatic update functionality equivalent to Docker's Watchtower, so that my application stays current without manual intervention.

The documentation should explain how to configure scheduled tasks or scripts that:
- Check for new versions on GitHub
- Download and apply updates automatically
- Restart services after updates
- Optionally notify me of update status

### Clear File Path Configuration

As a user setting up on a personal workstation, I want both generic path templates and real-world examples, so that I understand exactly where to place files and can customize for my specific setup.

## Spec Scope

1. **Environment Variable Parity** - Document all environment variables from docker-compose.yml and .env.template with Windows-specific paths and values

2. **Auto-Update System** - Create Windows equivalent of Watchtower using Task Scheduler and PowerShell scripts for automatic GitHub release updates

3. **Windows Service Management** - Complete NSSM configuration including environment variables, logging, and restart policies matching Docker's healthcheck/restart behavior

4. **File Path Documentation** - Explicit paths for all data directories, config files, logs, and database with both generic templates and real examples (C:\Projects\FuturesTradingLog, C:\Containers\FuturesTradingLog\data)

5. **Discord Notifications** - Document DISCORD_WEBHOOK_URL configuration for Windows native installation

## Out of Scope

- Linux/macOS native installation (separate documentation)
- Docker Desktop for Windows configuration
- WSL2 as primary installation method (only as Redis option)
- Production server deployment (focus is personal workstation)

## Expected Deliverable

1. Updated `docs/WINDOWS_INSTALL.md` with complete feature parity to Docker deployment, including auto-update scripts, full environment variable reference, and explicit file paths

2. New PowerShell script `scripts/windows-auto-update.ps1` for automated version updates via Task Scheduler

3. Updated quick reference table showing all file paths with both generic and example values
