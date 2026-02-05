# Spec-Lite: Windows Manual Update Method

> Quick reference for the Windows Manual Update spec

## One-Liner

Interactive PowerShell script for user-initiated updates with version checking, release notes display, and rollback capability.

## Key Commands

| Command | Description |
|---------|-------------|
| `.\update.ps1 -Check` | Check if update available (no admin) |
| `.\update.ps1` | Interactive update with prompts |
| `.\update.ps1 -Yes` | Update without prompts |
| `.\update.ps1 -Rollback` | Rollback to previous version |
| `.\update.ps1 -ListBackups` | Show available backups |
| `.\update.ps1 -History` | Show update history |
| `.\update.ps1 -Version v1.2.3` | Update to specific version |

## Core Features

1. **Version Check** - Compare current vs latest without changes
2. **Release Notes** - Show changelog before updating
3. **Auto Backup** - Create backup before every update
4. **Rollback** - Restore from any available backup
5. **History** - Track all update attempts

## User Flow

```
Check Version → Show Release Notes → Confirm → Backup → Stop Service → Update → Start Service → Health Check
```

## Files

| File | Purpose |
|------|---------|
| `scripts/update.ps1` | Main update script |
| `<DataPath>/backups/` | Update backups |
| `<DataPath>/logs/update-history.log` | Update history |

## Difference from Auto-Update

| Aspect | `windows-auto-update.ps1` | `update.ps1` |
|--------|---------------------------|--------------|
| Trigger | Scheduled Task (3 AM daily) | User-initiated |
| Interaction | None (unattended) | Interactive prompts |
| Release Notes | Not shown | Displayed before update |
| Rollback | Not supported | Built-in |
| Admin Required | Yes | Only for update/rollback |
