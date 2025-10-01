# Automatic Import Setup Guide

This guide explains how to set up and use the automatic import feature that monitors for new NinjaTrader execution files and imports them every 5 minutes.

## Overview

The automatic import system consists of:

1. **Background File Watcher Service** - Monitors the data directory for new execution files
2. **Automatic Processing** - Processes found files using the existing execution processing pipeline
3. **Direct Database Import** - Imports trades directly to the database with duplicate prevention
4. **Automatic Position Generation** - **NEW!** Automatically creates positions from imported trades
5. **File Archiving** - Moves processed files to the archive directory

## Setup Instructions

### 1. NinjaTrader Configuration

First, ensure your NinjaScript ExecutionExporter is properly configured:

- Install the `ExecutionExporter.cs` indicator in NinjaTrader
- Set `CreateDailyFiles = true` (this creates one file per day instead of multiple)
- Configure the export path to point to your application's data directory
- The indicator will now create files like: `NinjaTrader_Executions_20250617.csv`

### 2. Application Configuration

The automatic import feature is controlled by environment variables:

```bash
# Enable automatic import (default: true)
AUTO_IMPORT_ENABLED=true

# Set check interval in seconds (default: 300 = 5 minutes)
AUTO_IMPORT_INTERVAL=300

# Set data directory (where NinjaTrader files are exported)
DATA_DIR=/path/to/your/data/directory
```

### 3. Directory Structure

The application expects this directory structure:

```
data/
├── NinjaTrader_Executions_YYYYMMDD.csv  # Daily execution files
├── archive/                             # Processed files moved here
├── db/                                  # SQLite database
├── logs/                                # Application and file watcher logs
└── config/                              # Configuration files
```

## How It Works

### File Monitoring Process

1. **Every 5 minutes** (configurable), the file watcher checks the data directory
2. **Finds new files** matching pattern: `NinjaTrader_Executions_*.csv`
3. **Checks file age** - only processes files modified within 24 hours
4. **Processes executions** using the same logic as manual import
5. **Imports trades** directly to database with duplicate prevention
6. **Archives files** after successful processing

### File Processing Pipeline

```
NinjaTrader File → Process Executions → Match Entry/Exit → Calculate P&L → Import to DB → Archive File
```

### Duplicate Prevention

The system prevents duplicate imports by:

- Checking `account` + `entry_execution_id` combination
- Skipping trades that already exist in the database
- Logging duplicate detection for monitoring

## Monitoring and Control

### Web Interface

Access the upload page to see:

- **Auto-Import Status Banner** - Shows current status
- **Process Now Button** - Manually trigger file processing
- **Check Status Button** - View file watcher status

### API Endpoints

- `GET /api/file-watcher/status` - Get file watcher status
- `POST /api/file-watcher/process-now` - Manually trigger processing
- `GET /health` - Health check including file watcher status

### Log Files

Monitor these log files for troubleshooting:

- `data/logs/file_watcher.log` - File watcher activity and errors
- `data/logs/execution_export.log` - NinjaScript export activity (from NinjaTrader)

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTO_IMPORT_ENABLED` | `true` | Enable/disable automatic import |
| `AUTO_IMPORT_INTERVAL` | `300` | Check interval in seconds |
| `DATA_DIR` | `~/FuturesTradingLog/data` | Data directory path |

### NinjaScript Settings

| Setting | Recommended | Description |
|---------|-------------|-------------|
| `CreateDailyFiles` | `true` | Creates one file per day |
| `MaxFileSizeMB` | `10` | Maximum file size before rotation |
| `EnableLogging` | `true` | Enable logging for monitoring |

## Troubleshooting

### Common Issues

1. **Files not being processed**
   - Check if `AUTO_IMPORT_ENABLED=true`
   - Verify file naming pattern: `NinjaTrader_Executions_*.csv`
   - Check file age (must be < 24 hours old)
   - Review `file_watcher.log` for errors

2. **Duplicate trades**
   - System should automatically skip duplicates
   - Check logs for "Skipping duplicate trade" messages
   - Verify `entry_execution_id` values are unique

3. **File watcher not starting**
   - Check environment variable `AUTO_IMPORT_ENABLED`
   - Review application startup logs
   - Verify data directory exists and is writable

4. **Positions not being generated**
   - Check for "Auto-generating positions" messages in logs
   - Verify position service is functioning properly
   - Use manual rebuild: `POST /positions/rebuild`
   - Review position service logs for errors

## Automatic Position Generation

**New Feature**: The system now automatically generates positions when trades are imported!

### How It Works

1. **Immediate Processing**: After trades are imported (either via file watcher or manual upload), the system automatically analyzes the trades
2. **Position Building**: Related executions are grouped into complete position lifecycles 
3. **Execution Details**: Each position contains all its constituent executions accessible via the detail page
4. **Real-time Updates**: Positions appear immediately in the `/positions/` dashboard

### Benefits

- **No Manual Steps**: Positions are created automatically - no need to manually rebuild
- **Real-time Analysis**: See position-level P&L and metrics immediately after import
- **Complete Execution History**: Click into any position to see all fills and execution details
- **Consistent View**: Both manual uploads and automatic file imports generate positions

### Monitoring

Check the logs for position generation activity:

```bash
# Look for automatic position generation messages
tail -f data/logs/file_watcher.log | grep "Auto-generating"

# Example successful output:
# 2025-06-18 22:32:16,702 - FileWatcher - INFO - Auto-generating positions from imported trades...
# 2025-06-18 22:32:17,235 - FileWatcher - INFO - Generated 59 positions from 210 trades
```

### Manual Processing

If automatic processing fails, you can:

1. **Use the web interface** - Click "Process Now" button
2. **Use existing upload functionality** - Process files manually
3. **Check API endpoints** - Use `/api/file-watcher/process-now`

## Migration from Manual Process

To switch from manual to automatic import:

1. **Configure NinjaScript** - Set `CreateDailyFiles = true`
2. **Enable auto-import** - Set `AUTO_IMPORT_ENABLED=true`
3. **Remove manual steps** - No longer need to manually process files
4. **Monitor initially** - Watch logs to ensure proper operation

## Performance Notes

- **Efficient processing** - Only processes files modified in last 24 hours
- **Duplicate prevention** - Database-level checking prevents duplicates
- **Batch processing** - Processes all new files in one batch
- **Background operation** - Runs in separate thread, doesn't block web interface
- **Resource usage** - Minimal CPU/memory usage during idle periods

## Security Considerations

- **File validation** - Only processes files matching expected pattern
- **SQL injection protection** - Uses parameterized queries
- **Path traversal protection** - Restricts file access to data directory
- **Error handling** - Comprehensive error catching and logging

## Example Workflow

1. **Trade executions occur** in NinjaTrader
2. **NinjaScript exports** executions to `NinjaTrader_Executions_20250617.csv`
3. **File watcher detects** new file every 5 minutes
4. **Processing begins** - reads file, matches entry/exit pairs
5. **Trades calculated** - P&L computed with multipliers
6. **Database import** - trades added with duplicate checking
7. **File archived** - moved to archive directory
8. **Process complete** - trades visible in web interface

This automatic system eliminates the need for manual file processing while maintaining all the safety and validation features of the original import process.