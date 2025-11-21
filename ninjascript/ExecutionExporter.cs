#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Security;
using System.Text;
using System.Threading;
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
        private TimeZoneInfo pacificTimeZone;
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
                UseSessionCloseDate           = true;
                SessionStartHourPT            = 15; // 3pm Pacific Time
            }
            else if (State == State.DataLoaded)
            {
                // Initialize collections
                exportedExecutions = new HashSet<string>();
                positionTracker = new Dictionary<string, int>();

                // Initialize Pacific timezone
                try
                {
                    pacificTimeZone = TimeZoneInfo.FindSystemTimeZoneById("Pacific Standard Time");
                    LogMessage("Pacific timezone initialized successfully");
                }
                catch (Exception ex)
                {
                    LogError($"Failed to initialize Pacific timezone: {ex.Message}. Will use server time as fallback.");
                    pacificTimeZone = null;
                }

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
                Print($"Session date mode: {(UseSessionCloseDate ? "ENABLED - Using session close date logic" : "DISABLED - Using legacy current date logic")}");
                Print($"UseSessionCloseDate: {UseSessionCloseDate}, SessionStartHourPT: {SessionStartHourPT}");
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

        #region Timezone Conversion and Session Date Calculation

        /// <summary>
        /// Converts server time to Pacific Time
        /// </summary>
        /// <param name="serverTime">The server time to convert</param>
        /// <returns>Pacific Time equivalent</returns>
        public DateTime ConvertToPacificTime(DateTime serverTime)
        {
            try
            {
                if (pacificTimeZone != null)
                {
                    return TimeZoneInfo.ConvertTime(serverTime, pacificTimeZone);
                }
                else
                {
                    LogError("Pacific timezone not initialized. Using server time fallback due to timezone conversion error.");
                    return serverTime;
                }
            }
            catch (Exception ex)
            {
                LogError($"Timezone conversion failed: {ex.Message}. Using server time fallback due to timezone conversion error.");
                return serverTime;
            }
        }

        /// <summary>
        /// Converts server time to Pacific Time with explicit fallback handling
        /// Used primarily for testing
        /// </summary>
        /// <param name="serverTime">The server time to convert</param>
        /// <param name="timezone">The timezone to use (null triggers fallback)</param>
        /// <returns>Pacific Time equivalent or server time if conversion fails</returns>
        public DateTime ConvertToPacificTimeWithFallback(DateTime serverTime, TimeZoneInfo timezone)
        {
            try
            {
                if (timezone != null)
                {
                    return TimeZoneInfo.ConvertTime(serverTime, timezone);
                }
                else
                {
                    LogError("Timezone is null. Using server time fallback due to timezone conversion error.");
                    return serverTime;
                }
            }
            catch (Exception ex)
            {
                LogError($"Timezone conversion failed: {ex.Message}. Using server time fallback due to timezone conversion error.");
                return serverTime;
            }
        }

        /// <summary>
        /// Calculates the session closing date based on Pacific Time
        /// After 3pm PT (or configured hour): Use next day's date
        /// Before 3pm PT: Use current day's date
        /// </summary>
        /// <param name="pacificTime">Current time in Pacific timezone</param>
        /// <returns>Session closing date</returns>
        public DateTime CalculateSessionCloseDate(DateTime pacificTime)
        {
            DateTime sessionCloseDate;

            if (pacificTime.Hour >= SessionStartHourPT)
            {
                // After session start hour (e.g., 3pm PT) - use next day
                sessionCloseDate = pacificTime.AddDays(1).Date;
            }
            else
            {
                // Before session start hour - use current day
                sessionCloseDate = pacificTime.Date;
            }

            if (EnableLogging)
            {
                LogMessage($"Session date calculation - Pacific Time: {pacificTime:yyyy-MM-dd HH:mm:ss}, Session Close Date: {sessionCloseDate:yyyy-MM-dd}");
            }

            return sessionCloseDate;
        }

        /// <summary>
        /// Validates that the calculated session date is within reasonable bounds
        /// Logs warning if date seems incorrect but continues with calculated date
        /// </summary>
        /// <param name="calculatedDate">The calculated session close date</param>
        /// <param name="pacificNow">Current Pacific Time for validation context</param>
        /// <returns>True if date is valid, false if validation warning occurred</returns>
        public bool ValidateSessionDate(DateTime calculatedDate, DateTime pacificNow)
        {
            var daysDifference = (calculatedDate.Date - pacificNow.Date).Days;

            // Check if date is more than 1 day in the past
            if (daysDifference < -1)
            {
                LogError($"Date validation warning: Calculated date {calculatedDate:yyyy-MM-dd} is {Math.Abs(daysDifference)} days in the past (Pacific Now: {pacificNow:yyyy-MM-dd HH:mm:ss})");
                return false;
            }

            // Check if date is more than 2 days in the future
            if (daysDifference > 2)
            {
                LogError($"Date validation warning: Calculated date {calculatedDate:yyyy-MM-dd} is {daysDifference} days in the future (Pacific Now: {pacificNow:yyyy-MM-dd HH:mm:ss})");
                return false;
            }

            return true;
        }

        /// <summary>
        /// Gets the session closing date based on current time
        /// Handles timezone conversion and date calculation
        /// </summary>
        /// <returns>Session closing date to use for file naming</returns>
        private DateTime GetSessionCloseDate()
        {
            DateTime sessionCloseDate;

            if (UseSessionCloseDate)
            {
                // Get current server time
                DateTime serverTime = Core.Globals.Now;

                if (EnableLogging)
                {
                    LogMessage($"Server time: {serverTime:yyyy-MM-dd HH:mm:ss} ({TimeZoneInfo.Local.DisplayName})");
                }

                // Convert to Pacific Time
                DateTime pacificTime = ConvertToPacificTime(serverTime);

                if (EnableLogging)
                {
                    LogMessage($"Pacific time: {pacificTime:yyyy-MM-dd HH:mm:ss}");
                }

                // Calculate session closing date
                sessionCloseDate = CalculateSessionCloseDate(pacificTime);

                // Validate the date
                ValidateSessionDate(sessionCloseDate, pacificTime);
            }
            else
            {
                // Legacy mode: use current date
                sessionCloseDate = DateTime.Now.Date;

                if (EnableLogging)
                {
                    LogMessage($"Using legacy date logic (UseSessionCloseDate=false): {sessionCloseDate:yyyy-MM-dd}");
                }
            }

            return sessionCloseDate;
        }

        #endregion

        #region File Export and Path Management

        /// <summary>
        /// Generates the export filename based on session close date
        /// Format: NinjaTrader_Executions_YYYYMMDD.csv
        /// </summary>
        /// <param name="sessionCloseDate">The session closing date for the file</param>
        /// <returns>Filename string (without path)</returns>
        public string GenerateExportFilename(DateTime sessionCloseDate)
        {
            return string.Format("NinjaTrader_Executions_{0:yyyyMMdd}.csv", sessionCloseDate);
        }

        /// <summary>
        /// Constructs the full export file path
        /// </summary>
        /// <param name="exportDir">Export directory path</param>
        /// <param name="filename">Export filename</param>
        /// <returns>Full file path</returns>
        public string ConstructExportFilePath(string exportDir, string filename)
        {
            // Validate export directory exists
            if (!Directory.Exists(exportDir))
            {
                Directory.CreateDirectory(exportDir);
                LogMessage($"Created export directory: {exportDir}");
            }

            return Path.Combine(exportDir, filename);
        }

        /// <summary>
        /// Writes data to file with retry logic for transient failures
        /// </summary>
        /// <param name="filePath">Full path to the file</param>
        /// <param name="data">Data to write</param>
        /// <param name="append">Whether to append or overwrite</param>
        private void WriteToFileWithRetry(string filePath, string data, bool append)
        {
            int maxRetries = 3;
            int retryDelayMs = 1000;

            for (int attempt = 1; attempt <= maxRetries; attempt++)
            {
                try
                {
                    File.AppendAllText(filePath, data);
                    return; // Success
                }
                catch (IOException ex)
                {
                    if (attempt < maxRetries)
                    {
                        LogError($"File write attempt {attempt} failed (IOException): {ex.Message}. Retrying in {retryDelayMs}ms...");
                        Thread.Sleep(retryDelayMs);
                    }
                    else
                    {
                        LogError($"File write failed after {maxRetries} attempts (IOException): Path={filePath}, Error={ex.Message}");
                        throw;
                    }
                }
                catch (SecurityException ex)
                {
                    LogError($"File write failed (SecurityException): Permission denied for path {filePath}. Error: {ex.Message}. Please check folder permissions.");
                    throw;
                }
                catch (UnauthorizedAccessException ex)
                {
                    LogError($"File write failed (UnauthorizedAccessException): Access denied for path {filePath}. Error: {ex.Message}. Please check folder permissions.");
                    throw;
                }
                catch (Exception ex)
                {
                    LogError($"File write failed (Unexpected error): Type={ex.GetType().Name}, Path={filePath}, Error={ex.Message}");
                    throw;
                }
            }
        }

        #endregion

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

                    // Generate new file name using session close date logic
                    DateTime fileDate = GetSessionCloseDate();
                    currentFileDate = fileDate;

                    string fileName;
                    if (CreateDailyFiles)
                    {
                        // Use session close date for daily files
                        fileName = GenerateExportFilename(fileDate);
                    }
                    else
                    {
                        // Use timestamp for time-based rotation
                        var timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
                        fileName = $"NinjaTrader_Executions_{timestamp}.csv";
                    }

                    exportFilePath = ConstructExportFilePath(exportDirectory, fileName);

                    if (EnableLogging)
                    {
                        LogMessage($"Export filename: {fileName}");
                    }

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

                // Check if we should create a new daily file based on session date
                if (CreateDailyFiles)
                {
                    DateTime newSessionDate = GetSessionCloseDate();

                    if (newSessionDate > currentFileDate)
                    {
                        shouldRotate = true;
                        if (EnableLogging)
                        {
                            LogMessage($"File rotation triggered: Session date changed from {currentFileDate:yyyy-MM-dd} to {newSessionDate:yyyy-MM-dd}");
                        }
                    }
                }

                // Check file size limit
                if (File.Exists(exportFilePath))
                {
                    var fileInfo = new FileInfo(exportFilePath);
                    var fileSizeMB = fileInfo.Length / (1024.0 * 1024.0);

                    if (fileSizeMB > MaxFileSizeMB)
                    {
                        shouldRotate = true;
                        if (EnableLogging)
                        {
                            LogMessage($"File rotation triggered: File size {fileSizeMB:F2}MB exceeds limit {MaxFileSizeMB}MB");
                        }
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

        /// <summary>
        /// Directory path where CSV execution files will be exported.
        /// Default: User's Documents folder under FuturesTradingLog\data
        /// The directory will be created automatically if it doesn't exist.
        /// Subdirectories 'exported' and 'logs' will also be created.
        /// </summary>
        [NinjaScriptProperty]
        [Display(Name = "Export Path", Description = "Directory path for CSV export files (created automatically if missing)", GroupName = "Settings", Order = 1)]
        public string ExportPath { get; set; }

        /// <summary>
        /// When enabled, creates one CSV file per trading session using session close date.
        /// When disabled, creates time-stamped files that rotate based on size limit.
        /// Recommended: true for integration with FuturesTradingLog daily import.
        /// </summary>
        [NinjaScriptProperty]
        [Display(Name = "Create Daily Files", Description = "Create one CSV file per trading session (recommended for daily imports)", GroupName = "Settings", Order = 2)]
        public bool CreateDailyFiles { get; set; }

        /// <summary>
        /// Maximum file size in megabytes before rotating to a new file.
        /// Only applies when CreateDailyFiles is false.
        /// Valid range: 1-100 MB. Default: 10 MB.
        /// </summary>
        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Max File Size (MB)", Description = "Maximum CSV file size before rotation (1-100 MB)", GroupName = "Settings", Order = 3)]
        public int MaxFileSizeMB { get; set; }

        /// <summary>
        /// Enable detailed logging to execution_export.log file.
        /// Logs include timezone conversion, session date calculation, file operations, and errors.
        /// Recommended: true for initial setup and troubleshooting, can be disabled in production.
        /// Log file location: [ExportPath]\logs\execution_export.log
        /// </summary>
        [NinjaScriptProperty]
        [Display(Name = "Enable Logging", Description = "Enable detailed logging for troubleshooting (logs to execution_export.log)", GroupName = "Settings", Order = 4)]
        public bool EnableLogging { get; set; }

        /// <summary>
        /// Enable session close date logic for file naming.
        /// When true: Uses futures market session closing date (executions after 3pm PT use next day's date)
        /// When false: Uses legacy current date logic (backward compatibility mode)
        /// Recommended: true for correct session date alignment with futures market schedule.
        /// Example: Sunday 4pm PT trades export to Monday file (session closes Monday 2pm PT)
        /// </summary>
        [NinjaScriptProperty]
        [Display(Name = "Use Session Close Date", Description = "Enable session close date logic (after 3pm PT uses next day) - Recommended: true", GroupName = "Session Settings", Order = 5)]
        public bool UseSessionCloseDate { get; set; }

        /// <summary>
        /// Hour in Pacific Time when a new trading session begins (24-hour format).
        /// Default: 15 (3pm PT) - matches futures market session start time.
        /// Valid range: 0-23 hours.
        /// After this hour, executions are exported using the NEXT day's date.
        /// Before this hour, executions use the CURRENT day's date.
        /// Example: At 4pm PT (hour 16), session close date is tomorrow because 16 >= 15.
        /// </summary>
        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "Session Start Hour (PT)", Description = "Hour when new session begins in Pacific Time (0-23, default: 15 for 3pm PT)", GroupName = "Session Settings", Order = 6)]
        public int SessionStartHourPT { get; set; }

        #endregion
    }
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
    public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
    {
        private ExecutionExporter[] cacheExecutionExporter;
        public ExecutionExporter ExecutionExporter(string exportPath, bool createDailyFiles, int maxFileSizeMB, bool enableLogging, bool useSessionCloseDate, int sessionStartHourPT)
        {
            return ExecutionExporter(Input, exportPath, createDailyFiles, maxFileSizeMB, enableLogging, useSessionCloseDate, sessionStartHourPT);
        }

        public ExecutionExporter ExecutionExporter(ISeries<double> input, string exportPath, bool createDailyFiles, int maxFileSizeMB, bool enableLogging, bool useSessionCloseDate, int sessionStartHourPT)
        {
            if (cacheExecutionExporter != null)
                for (int idx = 0; idx < cacheExecutionExporter.Length; idx++)
                    if (cacheExecutionExporter[idx] != null && cacheExecutionExporter[idx].ExportPath == exportPath && cacheExecutionExporter[idx].CreateDailyFiles == createDailyFiles && cacheExecutionExporter[idx].MaxFileSizeMB == maxFileSizeMB && cacheExecutionExporter[idx].EnableLogging == enableLogging && cacheExecutionExporter[idx].UseSessionCloseDate == useSessionCloseDate && cacheExecutionExporter[idx].SessionStartHourPT == sessionStartHourPT && cacheExecutionExporter[idx].EqualsInput(input))
                        return cacheExecutionExporter[idx];
            return CacheIndicator<ExecutionExporter>(new ExecutionExporter(){ ExportPath = exportPath, CreateDailyFiles = createDailyFiles, MaxFileSizeMB = maxFileSizeMB, EnableLogging = enableLogging, UseSessionCloseDate = useSessionCloseDate, SessionStartHourPT = sessionStartHourPT }, input, ref cacheExecutionExporter);
        }
    }
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
    public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
    {
        public Indicators.ExecutionExporter ExecutionExporter(string exportPath, bool createDailyFiles, int maxFileSizeMB, bool enableLogging, bool useSessionCloseDate, int sessionStartHourPT)
        {
            return indicator.ExecutionExporter(Input, exportPath, createDailyFiles, maxFileSizeMB, enableLogging, useSessionCloseDate, sessionStartHourPT);
        }

        public Indicators.ExecutionExporter ExecutionExporter(ISeries<double> input , string exportPath, bool createDailyFiles, int maxFileSizeMB, bool enableLogging, bool useSessionCloseDate, int sessionStartHourPT)
        {
            return indicator.ExecutionExporter(input, exportPath, createDailyFiles, maxFileSizeMB, enableLogging, useSessionCloseDate, sessionStartHourPT);
        }
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
    {
        public Indicators.ExecutionExporter ExecutionExporter(string exportPath, bool createDailyFiles, int maxFileSizeMB, bool enableLogging, bool useSessionCloseDate, int sessionStartHourPT)
        {
            return indicator.ExecutionExporter(Input, exportPath, createDailyFiles, maxFileSizeMB, enableLogging, useSessionCloseDate, sessionStartHourPT);
        }

        public Indicators.ExecutionExporter ExecutionExporter(ISeries<double> input , string exportPath, bool createDailyFiles, int maxFileSizeMB, bool enableLogging, bool useSessionCloseDate, int sessionStartHourPT)
        {
            return indicator.ExecutionExporter(input, exportPath, createDailyFiles, maxFileSizeMB, enableLogging, useSessionCloseDate, sessionStartHourPT);
        }
    }
}

#endregion
