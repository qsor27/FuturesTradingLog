# NinjaScript ExecutionExporter Setup Guide

This guide will help you install and configure the ExecutionExporter indicator to automatically export trade executions from NinjaTrader 8 to your FuturesTradingLog application.

## 📋 Prerequisites

- NinjaTrader 8 (any version)
- Active trading account or simulation account
- Write permissions to your FuturesTradingLog data directory
- Basic familiarity with NinjaTrader interface

## 🚀 Installation Steps

### Step 1: Import the NinjaScript Indicator

1. **Open NinjaTrader 8**
2. **Navigate to Tools → Import → NinjaScript Add-On**
3. **Browse and select** the `ExecutionExporter.cs` file from:
   ```
   {YourProject}/ninjascript/ExecutionExporter.cs
   ```
4. **Click Import** and wait for compilation to complete
5. **Restart NinjaTrader** if prompted

### Step 2: Add Indicator to Chart

1. **Open any chart** (instrument doesn't matter - indicator works globally)
2. **Right-click on chart → Indicators**
3. **Find "ExecutionExporter"** in the indicator list
4. **Double-click** to add it to your chart

### Step 3: Configure Settings

When adding the indicator, configure these critical settings:

#### **Required Settings:**
- **Export Path**: Set to your FuturesTradingLog data directory
  ```
  C:\Containers\FuturesTradingLog\data
  ```
  *(Adjust path based on your installation)*

#### **Optional Settings:**
- **Create Daily Files**: `True` (recommended)
- **Max File Size (MB)**: `10` (creates new file when exceeded)
- **Enable Logging**: `True` (recommended for troubleshooting)

### Step 4: Verify Installation

1. **Check the Output Window** (Tools → Output Window)
2. **Look for initialization message**:
   ```
   ExecutionExporter initialized. Export path: C:\Containers\FuturesTradingLog\data
   ```
3. **Verify directory structure** is created:
   ```
   C:\Containers\FuturesTradingLog\data\
   ├── exported/          (completed files)
   └── logs/              (error logs)
   ```

## ⚙️ Configuration Options

### Export Path Settings
- **Default**: `C:\Containers\FuturesTradingLog\data`
- **Custom**: Point to your actual data directory
- **Requirements**: Must have write permissions

### File Management Options
- **Create Daily Files**: Creates new CSV file each trading day
- **Max File Size**: Automatic file rotation when size limit reached
- **File Naming**: `NinjaTrader_Executions_YYYYMMDD_HHMMSS.csv`

### Logging Options
- **Enable Logging**: Detailed activity logs for troubleshooting
- **Log Location**: `{ExportPath}/logs/execution_export.log`

## 🔄 How It Works

### Real-Time Export Process
1. **Execution occurs** in any NinjaTrader account
2. **Indicator captures** execution immediately
3. **Formats data** to match your application's CSV format
4. **Writes to CSV file** in real-time
5. **Prevents duplicates** using unique execution IDs

### Data Format Generated
The indicator creates CSV files with exactly the format your application expects:
```csv
ID,E/X,Action,Instrument,Price,Quantity,Time,Commission,Account
MNQ_638123456789_12345,Entry,Buy,MNQ MAR25,15000.50,1,2024-12-17 09:30:15,$2.50,Sim101
MNQ_638123456790_12346,Exit,Sell,MNQ MAR25,15010.25,1,2024-12-17 09:45:22,$2.50,Sim101
```

### Entry/Exit Detection
- **Smart position tracking** determines if execution is entry or exit
- **Multi-instrument support** tracks positions separately for each instrument
- **Position reversal handling** correctly identifies complex scenarios

## 🔧 Troubleshooting

### Common Issues

#### **"No executions being exported"**
- **Check account permissions**: Ensure account has execution access
- **Verify path**: Confirm export path exists and is writable
- **Check logs**: Look in `{ExportPath}/logs/execution_export.log`

#### **"File permission errors"**
- **Run NinjaTrader as Administrator**
- **Check directory permissions** on export path
- **Verify disk space** availability

#### **"Duplicate executions"**
- **Normal behavior**: Indicator prevents duplicates automatically
- **Session restart**: May re-export recent executions (harmless)

### Debug Steps

1. **Check Output Window** for error messages
2. **Review log files** in `{ExportPath}/logs/`
3. **Verify file creation** in export directory
4. **Test with paper trading** before live trading

### Log File Examples

**Successful operation:**
```
2024-12-17 09:30:00 - INFO - ExecutionExporter initialized. Export path: C:\Data
2024-12-17 09:30:15 - INFO - Created new export file: NinjaTrader_Executions_20241217_093000.csv
2024-12-17 09:30:16 - INFO - Exported execution: MNQ Entry 1@15000.50
```

**Error condition:**
```
2024-12-17 09:30:00 - ERROR - Error setting up export directory: Access denied
```

## 🔄 Integration with FuturesTradingLog

### Automatic Processing
1. **Files are created** in your data directory
2. **Your Python monitor** (Phase 2) will detect new files
3. **Processing happens automatically** using existing `ExecutionProcessing.py`
4. **Trades appear** in your web interface

### Manual Processing (Current)
If not using file monitoring yet:
1. **Check for new CSV files** in your data directory
2. **Run processing manually**: `python ExecutionProcessing.py`
3. **Import via web interface** if needed

## 📊 Monitoring Performance

### File Output
- **Real-time export**: Executions appear immediately in CSV
- **File rotation**: New files created daily or when size limit reached
- **Completed files**: Moved to `exported/` subdirectory

### System Impact
- **Minimal overhead**: Lightweight indicator with efficient file I/O
- **Thread-safe**: Handles concurrent executions safely
- **Memory efficient**: Cleans up resources automatically

## 🎯 Next Steps

After successful installation:

1. **Test with simulation** trading first
2. **Verify CSV format** matches your application's expectations
3. **Implement Phase 2** (Python file monitoring) for full automation
4. **Monitor logs** for any issues during live trading

## 🆘 Support

If you encounter issues:

1. **Check the logs** first: `{ExportPath}/logs/execution_export.log`
2. **Review Output Window** in NinjaTrader
3. **Verify file permissions** and directory structure
4. **Test with minimal configuration** first

## 📝 Configuration Template

Save this configuration for easy setup:

```
Export Path: C:\Containers\FuturesTradingLog\data
Create Daily Files: True
Max File Size (MB): 10
Enable Logging: True
```

Your ExecutionExporter is now ready to automatically capture and export all trade executions in real-time!