#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Text;
using System.Windows;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

//This namespace holds Indicators in this folder and is required. Do not change it. 
namespace NinjaTrader.NinjaScript.Indicators
{
    /// <summary>
    /// ExecutionExporter - Automatically exports trade executions to CSV format
    /// Compatible with FuturesTradingLog application
    /// </summary>
    public class ExecutionExporter : Indicator
    {
        #region Variables
        private StreamWriter streamWriter;
        private string exportFilePath;
        private string exportDirectory;
        private DateTime currentFileDate;
        private readonly object lockObject = new object();
        private HashSet<string> exportedExecutions;
        private Dictionary<string, int> positionTracker;
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description                     = @"Automatically exports trade executions to CSV format for FuturesTradingLog application";
                Name                           = "ExecutionExporter";
                Calculate                      = Calculate.OnBarClose;
                IsOverlay                      = false;
                DisplayInDataBox               = true;
                DrawOnPricePanel              = false;
                DrawHorizontalGridLines       = true;
                DrawVerticalGridLines         = true;
                PaintPriceMarkers             = true;
                ScaleJustification            = NinjaTrader.Gui.Chart.ScaleJustification.Right;
                IsSuspendedWhileInactive      = false;
                
                // Default settings - use user's Documents folder for cross-platform compatibility
                ExportPath                    = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "FuturesTradingLog", "data");
                CreateDailyFiles              = true;
                MaxFileSizeMB                 = 10;
                EnableLogging                 = true;
            }
            else if (State == State.DataLoaded)
            {
                // Initialize collections
                exportedExecutions = new HashSet<string>();
                positionTracker = new Dictionary<string, int>();
                
                // Setup export directory
                SetupExportDirectory();
                
                // Subscribe to execution events for all accounts
                if (Account.All != null)
                {
                    foreach (Account account in Account.All)
                    {
                        if (account != null)
                        {
                            account.ExecutionUpdate += OnExecutionUpdate;
                        }
                    }
                }
                
                Print($"ExecutionExporter initialized. Export path: {exportDirectory}");
            }
            else if (State == State.Terminated)
            {
                // Cleanup
                CleanupResources();
                
                // Unsubscribe from execution events
                if (Account.All != null)
                {
                    foreach (Account account in Account.All)
                    {
                        if (account != null)
                        {
                            account.ExecutionUpdate -= OnExecutionUpdate;
                        }
                    }
                }
            }
        }

        private void SetupExportDirectory()
        {
            try
            {
                exportDirectory = ExportPath;
                
                if (!Directory.Exists(exportDirectory))
                {
                    Directory.CreateDirectory(exportDirectory);
                    LogMessage($"Created export directory: {exportDirectory}");
                }
                
                // Create subdirectories
                var exportedDir = Path.Combine(exportDirectory, "exported");
                var logsDir = Path.Combine(exportDirectory, "logs");
                
                if (!Directory.Exists(exportedDir))
                    Directory.CreateDirectory(exportedDir);
                    
                if (!Directory.Exists(logsDir))
                    Directory.CreateDirectory(logsDir);
                
                // Initialize first file
                CreateNewExportFile();
            }
            catch (Exception ex)
            {
                LogError($"Error setting up export directory: {ex.Message}");
            }
        }

        private void CreateNewExportFile()
        {
            try
            {
                lock (lockObject)
                {
                    // Close existing file if open
                    if (streamWriter != null)
                    {
                        streamWriter.Close();
                        streamWriter.Dispose();
                        
                        // Only move completed files to exported directory if not using daily files
                        // Daily files should remain in place for continued appending
                        if (!CreateDailyFiles && File.Exists(exportFilePath))
                        {
                            var existingFileName = Path.GetFileName(exportFilePath);
                            var exportedPath = Path.Combine(exportDirectory, "exported", existingFileName);
                            File.Move(exportFilePath, exportedPath);
                            LogMessage($"Moved completed file to: {exportedPath}");
                        }
                    }
                    
                    // Generate new file name
                    currentFileDate = DateTime.Now.Date;
                    
                    string fileName;
                    if (CreateDailyFiles)
                    {
                        // Use only date for daily files (one file per day)
                        var dateString = DateTime.Now.ToString("yyyyMMdd");
                        fileName = $"NinjaTrader_Executions_{dateString}.csv";
                    }
                    else
                    {
                        // Use timestamp for time-based rotation
                        var timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
                        fileName = $"NinjaTrader_Executions_{timestamp}.csv";
                    }
                    
                    exportFilePath = Path.Combine(exportDirectory, fileName);
                    
                    // Check if file already exists (for daily files)
                    bool fileExists = File.Exists(exportFilePath);
                    
                    // Create or append to file
                    streamWriter = new StreamWriter(exportFilePath, append: fileExists, Encoding.UTF8);
                    
                    // Only write header if file is new
                    if (!fileExists)
                    {
                        WriteCSVHeader();
                    }
                    
                    streamWriter.Flush();
                    
                    if (fileExists)
                    {
                        LogMessage($"Reopened existing daily file: {fileName}");
                    }
                    else
                    {
                        LogMessage($"Created new export file: {fileName}");
                    }
                }
            }
            catch (Exception ex)
            {
                LogError($"Error creating new export file: {ex.Message}");
            }
        }

        private void WriteCSVHeader()
        {
            const string header = "Instrument,Action,Quantity,Price,Time,ID,E/X,Position,Order ID,Name,Commission,Rate,Account,Connection,";
            streamWriter.WriteLine(header);
        }

        private void OnExecutionUpdate(object sender, ExecutionEventArgs e)
        {
            try
            {
                if (e?.Execution == null) return;
                if (e.Execution.Instrument?.MasterInstrument == null) return;
                if (e.Execution.Order == null) return;
                
                // Generate unique execution ID
                var executionId = GenerateExecutionId(e.Execution);
                
                // Check for duplicates
                if (exportedExecutions.Contains(executionId))
                    return;
                
                // Determine entry/exit status
                var entryExit = DetermineEntryExit(e.Execution);
                
                // Export the execution
                ExportExecution(e.Execution, executionId, entryExit);
                
                // Track exported execution
                exportedExecutions.Add(executionId);
                
                // Check if we need to rotate files
                CheckFileRotation();
            }
            catch (Exception ex)
            {
                LogError($"Error processing execution: {ex.Message}");
            }
        }

        private string GenerateExecutionId(Execution execution)
        {
            try
            {
                // Use NinjaTrader's built-in execution ID if available
                if (!string.IsNullOrEmpty(execution?.ExecutionId))
                    return execution.ExecutionId;
                    
                // Fallback to creating unique ID using instrument + timestamp + order ID
                var instrument = execution?.Instrument?.MasterInstrument?.Name ?? "UNKNOWN";
                var timestamp = execution?.Time.Ticks.ToString() ?? DateTime.Now.Ticks.ToString();
                var orderId = execution?.Order?.Id.ToString() ?? "0";
                
                return $"{instrument}_{timestamp}_{orderId}";
            }
            catch (Exception ex)
            {
                LogError($"Error generating execution ID: {ex.Message}");
                return $"ERROR_{DateTime.Now.Ticks}";
            }
        }

        private string DetermineEntryExit(Execution execution)
        {
            try
            {
                // Track positions separately by account and instrument
                var accountName = execution.Account?.Name ?? "Unknown";
                var instrumentKey = $"{accountName}_{execution.Instrument.FullName}";

                // Initialize position tracking for this account+instrument combination
                if (!positionTracker.ContainsKey(instrumentKey))
                {
                    positionTracker[instrumentKey] = 0;
                    LogMessage($"Created new position tracker for key: {instrumentKey}");
                }

                var previousPosition = positionTracker[instrumentKey];
                LogMessage($"DetermineEntryExit - Key: {instrumentKey}, Previous Position: {previousPosition}, OrderAction: {execution.Order.OrderAction}");

                // Determine signed quantity based on order action
                // Buy/BuyToCover = positive, Sell/SellShort = negative
                int signedQuantity;
                if (execution.Order.OrderAction == OrderAction.Buy || execution.Order.OrderAction == OrderAction.BuyToCover)
                {
                    signedQuantity = Math.Abs(execution.Quantity);
                }
                else if (execution.Order.OrderAction == OrderAction.Sell || execution.Order.OrderAction == OrderAction.SellShort)
                {
                    signedQuantity = -Math.Abs(execution.Quantity);
                }
                else
                {
                    // Fallback for unknown order actions
                    signedQuantity = execution.Quantity;
                }
                
                var newPosition = previousPosition + signedQuantity;

                // Update position tracker
                positionTracker[instrumentKey] = newPosition;
                LogMessage($"Updated position - Key: {instrumentKey}, New Position: {newPosition}");
                
                // Determine if this is entry or exit based on position change
                if (previousPosition == 0)
                {
                    return "Entry"; // Opening new position
                }
                else if (newPosition == 0)
                {
                    return "Exit"; // Closing entire position
                }
                else if (Math.Sign(previousPosition) == Math.Sign(newPosition))
                {
                    // Same direction - check if adding or reducing
                    if (Math.Abs(newPosition) > Math.Abs(previousPosition))
                    {
                        return "Entry"; // Adding to position
                    }
                    else
                    {
                        return "Exit"; // Reducing position
                    }
                }
                else
                {
                    return "Exit"; // Position reversal (closing and reopening)
                }
            }
            catch
            {
                return "Entry"; // Default to entry if unable to determine
            }
        }

        private void ExportExecution(Execution execution, string executionId, string entryExit)
        {
            try
            {
                lock (lockObject)
                {
                    if (streamWriter == null)
                        CreateNewExportFile();
                    
                    // Format execution data according to required CSV format
                    var csvLine = FormatExecutionAsCSV(execution, executionId, entryExit);
                    
                    streamWriter.WriteLine(csvLine);
                    streamWriter.Flush();
                    
                    if (EnableLogging)
                    {
                        var accountName = execution.Account?.Name ?? "Unknown";
                        var instrumentKey = $"{accountName}_{execution.Instrument.FullName}";
                        var currentPos = positionTracker.ContainsKey(instrumentKey) ? positionTracker[instrumentKey] : 0;
                        LogMessage($"Exported execution: [{accountName}] {execution.Instrument.FullName} {entryExit} {execution.Quantity}@{execution.Price} - Position: {currentPos}");
                    }
                }
            }
            catch (Exception ex)
            {
                LogError($"Error exporting execution: {ex.Message}");
            }
        }

        private string FormatExecutionAsCSV(Execution execution, string executionId, string entryExit)
        {
            // Map execution data to match manual NinjaTrader report format
            var instrument = execution.Instrument.FullName;
            var action = execution.Order.OrderAction.ToString(); // "Buy" or "Sell"
            var quantity = Math.Abs(execution.Quantity).ToString();
            var price = execution.Price.ToString("F2");
            var time = execution.Time.ToString("M/d/yyyy h:mm:ss tt");
            var id = executionId;
            var entryExitValue = entryExit;
            
            // Get current position after this execution from position tracker (account-specific)
            var accountName = execution.Account?.Name ?? "Unknown";
            var instrumentKey = $"{accountName}_{execution.Instrument.FullName}";
            var currentPosition = positionTracker.ContainsKey(instrumentKey) ? positionTracker[instrumentKey] : 0;
            
            string position;
            if (currentPosition > 0)
                position = $"{currentPosition} L";
            else if (currentPosition < 0)
                position = $"{Math.Abs(currentPosition)} S";
            else
                position = "-";
            
            var orderId = execution.Order?.Id.ToString() ?? "";
            var name = execution.Order?.Name ?? entryExit;
            
            // Handle commission
            var commission = "$" + execution.Commission.ToString("F2");
            
            var rate = "1"; // Default rate
            var account = execution.Account?.Name ?? "Unknown";
            var connection = "Apex Trader Funding "; // Default connection
            
            // Escape any commas in data fields
            instrument = EscapeCSVField(instrument);
            action = EscapeCSVField(action);
            id = EscapeCSVField(id);
            position = EscapeCSVField(position);
            orderId = EscapeCSVField(orderId);
            name = EscapeCSVField(name);
            account = EscapeCSVField(account);
            connection = EscapeCSVField(connection);
            
            return $"{instrument},{action},{quantity},{price},{time},{id},{entryExitValue},{position},{orderId},{name},{commission},{rate},{account},{connection},";
        }

        private string EscapeCSVField(string field)
        {
            if (string.IsNullOrEmpty(field))
                return "";
                
            if (field.Contains(",") || field.Contains("\"") || field.Contains("\n"))
            {
                return "\"" + field.Replace("\"", "\"\"") + "\"";
            }
            
            return field;
        }

        private void CheckFileRotation()
        {
            try
            {
                bool shouldRotate = false;
                
                // Check if we should create a new daily file
                if (CreateDailyFiles && DateTime.Now.Date > currentFileDate)
                {
                    shouldRotate = true;
                }
                
                // Check file size limit
                if (File.Exists(exportFilePath))
                {
                    var fileInfo = new FileInfo(exportFilePath);
                    var fileSizeMB = fileInfo.Length / (1024.0 * 1024.0);
                    
                    if (fileSizeMB > MaxFileSizeMB)
                    {
                        shouldRotate = true;
                    }
                }
                
                if (shouldRotate)
                {
                    CreateNewExportFile();
                }
            }
            catch (Exception ex)
            {
                LogError($"Error checking file rotation: {ex.Message}");
            }
        }

        private void LogMessage(string message)
        {
            try
            {
                if (!EnableLogging) return;
                
                var logPath = Path.Combine(exportDirectory, "logs", "execution_export.log");
                var logEntry = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} - INFO - {message}";
                
                File.AppendAllText(logPath, logEntry + Environment.NewLine);
                Print(message); // Also print to NinjaTrader output window
            }
            catch
            {
                // Silently ignore logging errors to prevent cascading failures
            }
        }

        private void LogError(string message)
        {
            try
            {
                var logPath = Path.Combine(exportDirectory, "logs", "execution_export.log");
                var logEntry = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} - ERROR - {message}";
                
                File.AppendAllText(logPath, logEntry + Environment.NewLine);
                Print($"ERROR: {message}"); // Also print to NinjaTrader output window
            }
            catch
            {
                // Silently ignore logging errors to prevent cascading failures
            }
        }

        private void CleanupResources()
        {
            try
            {
                lock (lockObject)
                {
                    if (streamWriter != null)
                    {
                        streamWriter.Close();
                        streamWriter.Dispose();
                        streamWriter = null;
                        
                        LogMessage("ExecutionExporter resources cleaned up");
                    }
                }
            }
            catch (Exception ex)
            {
                LogError($"Error during cleanup: {ex.Message}");
            }
        }

        protected override void OnBarUpdate()
        {
            // This indicator doesn't need to process bar updates
            // All logic is handled in execution events
        }

        #region Properties
        [NinjaScriptProperty]
        [Display(Name = "Export Path", GroupName = "Settings", Order = 1)]
        public string ExportPath { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Create Daily Files", GroupName = "Settings", Order = 2)]
        public bool CreateDailyFiles { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Max File Size (MB)", GroupName = "Settings", Order = 3)]
        public int MaxFileSizeMB { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable Logging", GroupName = "Settings", Order = 4)]
        public bool EnableLogging { get; set; }
        #endregion
    }
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
    public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
    {
        private ExecutionExporter[] cacheExecutionExporter;
        public ExecutionExporter ExecutionExporter(string exportPath, bool createDailyFiles, int maxFileSizeMB, bool enableLogging)
        {
            return ExecutionExporter(Input, exportPath, createDailyFiles, maxFileSizeMB, enableLogging);
        }

        public ExecutionExporter ExecutionExporter(ISeries<double> input, string exportPath, bool createDailyFiles, int maxFileSizeMB, bool enableLogging)
        {
            if (cacheExecutionExporter != null)
                for (int idx = 0; idx < cacheExecutionExporter.Length; idx++)
                    if (cacheExecutionExporter[idx] != null && cacheExecutionExporter[idx].ExportPath == exportPath && cacheExecutionExporter[idx].CreateDailyFiles == createDailyFiles && cacheExecutionExporter[idx].MaxFileSizeMB == maxFileSizeMB && cacheExecutionExporter[idx].EnableLogging == enableLogging && cacheExecutionExporter[idx].EqualsInput(input))
                        return cacheExecutionExporter[idx];
            return CacheIndicator<ExecutionExporter>(new ExecutionExporter(){ ExportPath = exportPath, CreateDailyFiles = createDailyFiles, MaxFileSizeMB = maxFileSizeMB, EnableLogging = enableLogging }, input, ref cacheExecutionExporter);
        }
    }
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
    public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
    {
        public Indicators.ExecutionExporter ExecutionExporter(string exportPath, bool createDailyFiles, int maxFileSizeMB, bool enableLogging)
        {
            return indicator.ExecutionExporter(Input, exportPath, createDailyFiles, maxFileSizeMB, enableLogging);
        }

        public Indicators.ExecutionExporter ExecutionExporter(ISeries<double> input , string exportPath, bool createDailyFiles, int maxFileSizeMB, bool enableLogging)
        {
            return indicator.ExecutionExporter(input, exportPath, createDailyFiles, maxFileSizeMB, enableLogging);
        }
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
    {
        public Indicators.ExecutionExporter ExecutionExporter(string exportPath, bool createDailyFiles, int maxFileSizeMB, bool enableLogging)
        {
            return indicator.ExecutionExporter(Input, exportPath, createDailyFiles, maxFileSizeMB, enableLogging);
        }

        public Indicators.ExecutionExporter ExecutionExporter(ISeries<double> input , string exportPath, bool createDailyFiles, int maxFileSizeMB, bool enableLogging)
        {
            return indicator.ExecutionExporter(input, exportPath, createDailyFiles, maxFileSizeMB, enableLogging);
        }
    }
}

#endregion