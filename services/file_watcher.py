import os
import time
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import config
from services.unified_csv_import_service import unified_csv_import_service

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


class CSVFileEventHandler(FileSystemEventHandler):
    """
    Handles file system events for CSV files with debouncing logic.
    """

    def __init__(self, on_csv_change, debounce_seconds: float = 5.0):
        """
        Initialize the CSV file event handler.

        Args:
            on_csv_change: Callback function to call when a CSV file changes
            debounce_seconds: Delay before triggering import (default: 5 seconds)
        """
        super().__init__()
        self.on_csv_change = on_csv_change
        self.debounce_seconds = debounce_seconds
        self.pending_timers: dict = {}
        self.lock = threading.Lock()
        self.logger = logging.getLogger('FileWatcher')

    def on_modified(self, event):
        """Handle file modification events"""
        if not event.is_directory and event.src_path.endswith('.csv'):
            self._handle_csv_change(event.src_path, 'modified')

    def on_created(self, event):
        """Handle file creation events"""
        if not event.is_directory and event.src_path.endswith('.csv'):
            self._handle_csv_change(event.src_path, 'created')

    def _handle_csv_change(self, file_path: str, event_type: str):
        """
        Handle CSV file change with debouncing.

        Args:
            file_path: Path to the changed CSV file
            event_type: Type of event ('created' or 'modified')
        """
        file_path_obj = Path(file_path)
        filename = file_path_obj.name

        with self.lock:
            # Cancel existing timer for this file if any
            if filename in self.pending_timers:
                self.pending_timers[filename].cancel()
                self.logger.debug(f"Cancelled pending import for {filename}")

            # Create new timer to trigger import after debounce delay
            timer = threading.Timer(
                self.debounce_seconds,
                self._trigger_import,
                args=[file_path_obj, event_type]
            )
            self.pending_timers[filename] = timer
            timer.start()

            self.logger.info(
                f"CSV file {event_type}: {filename} - "
                f"import scheduled in {self.debounce_seconds}s"
            )

    def _trigger_import(self, file_path: Path, event_type: str):
        """
        Trigger the import callback after debounce period.

        Args:
            file_path: Path to the CSV file to import
            event_type: Type of event that triggered this import
        """
        filename = file_path.name

        with self.lock:
            # Remove from pending timers
            if filename in self.pending_timers:
                del self.pending_timers[filename]

        # Call the import callback
        self.logger.info(f"Triggering import for {filename} (event: {event_type})")
        try:
            self.on_csv_change(file_path)
        except Exception as e:
            self.logger.error(f"Error importing {filename}: {e}", exc_info=True)

    def cancel_all_timers(self):
        """Cancel all pending timers (called on shutdown)"""
        with self.lock:
            for filename, timer in self.pending_timers.items():
                timer.cancel()
                self.logger.debug(f"Cancelled pending import for {filename}")
            self.pending_timers.clear()


class FileWatcher:
    """
    Real-time file monitoring system that uses watchdog to monitor the /Data directory
    for new CSV files and automatically processes them using the UnifiedCSVImportService.

    Falls back to polling mode if watchdog is not available.
    """

    def __init__(self, check_interval: int = None, debounce_seconds: float = 5.0):
        self.check_interval = check_interval or config.auto_import_interval or 300  # Default 5 minutes
        self.debounce_seconds = debounce_seconds
        self.running = False
        self.thread = None
        self.observer: Optional[Observer] = None
        self.event_handler: Optional[CSVFileEventHandler] = None
        self.logger = self._setup_logger()
        self.last_check_time = 0
        self.use_watchdog = WATCHDOG_AVAILABLE

        # Use the unified CSV import service
        self.import_service = unified_csv_import_service
        
    def _setup_logger(self) -> logging.Logger:
        """Setup logging for the file watcher"""
        logger = logging.getLogger('FileWatcher')
        logger.setLevel(logging.INFO)
        
        # Create logs directory if it doesn't exist
        log_dir = config.data_dir / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # File handler
        handler = logging.FileHandler(log_dir / 'file_watcher.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current file monitoring status"""
        return {
            'is_running': self.is_running(),
            'check_interval': self.check_interval,
            'last_check_time': self.last_check_time,
            'data_directory': str(config.data_dir),
            'processed_files': len(self.import_service.processed_files),
            'service_status': self.import_service.get_processing_status()
        }
    
    def _check_and_process_files(self) -> None:
        """Check for new files and process them using unified import service"""
        try:
            self.logger.info("Starting automatic file processing check...")
            self.last_check_time = time.time()
            
            # Use the unified CSV import service to process all new files
            result = self.import_service.process_all_new_files()
            
            if result['success']:
                if result['files_processed'] > 0:
                    self.logger.info(
                        f"Successfully processed {result['files_processed']} files, "
                        f"imported {result['trades_imported']} trades, "
                        f"created {result['positions_created']} positions"
                    )
                else:
                    self.logger.debug("No new files found to process")
            else:
                self.logger.error(f"File processing failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            self.logger.error(f"Error in check_and_process_files: {e}")
    
    def force_process_files(self) -> Dict[str, Any]:
        """Force immediate processing of all new files"""
        self.logger.info("Manual file processing triggered")
        result = self.import_service.process_all_new_files()
        self.last_check_time = time.time()
        return result
    
    def _run(self) -> None:
        """Main run loop for the file watcher"""
        self.logger.info(f"File watcher started. Checking every {self.check_interval} seconds")
        
        while self.running:
            try:
                self._check_and_process_files()
                
                # Sleep for the specified interval
                for _ in range(self.check_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Unexpected error in file watcher: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def _handle_csv_import_for_file(self, file_path: Path):
        """Handle CSV import for a specific file"""
        try:
            self.logger.info(f"Processing CSV file: {file_path.name}")
            result = self.import_service.manual_reprocess_file(file_path)
            self.last_check_time = time.time()

            if result['success']:
                self.logger.info(
                    f"Successfully processed {file_path.name}: "
                    f"{result.get('trades_imported', 0)} trades imported, "
                    f"{result.get('positions_created', 0)} positions created"
                )
            else:
                self.logger.error(f"Failed to process {file_path.name}: {result.get('error')}")
        except Exception as e:
            self.logger.error(f"Error processing {file_path.name}: {e}", exc_info=True)

    def start(self) -> None:
        """Start the file watcher service"""
        if self.running:
            self.logger.warning("File watcher is already running")
            return

        self.running = True

        if self.use_watchdog and WATCHDOG_AVAILABLE:
            # Use watchdog for real-time file monitoring
            self.logger.info(f"Starting watchdog-based file watcher (debounce: {self.debounce_seconds}s)")

            # Ensure directory exists
            config.data_dir.mkdir(parents=True, exist_ok=True)

            # Create event handler
            self.event_handler = CSVFileEventHandler(
                on_csv_change=self._handle_csv_import_for_file,
                debounce_seconds=self.debounce_seconds
            )

            # Create and start observer
            self.observer = Observer()
            self.observer.schedule(self.event_handler, str(config.data_dir), recursive=False)
            self.observer.start()

            self.logger.info("File watcher service started (watchdog mode)")
        else:
            # Fallback to polling mode
            self.logger.info(f"Starting polling-based file watcher (interval: {self.check_interval}s)")
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            self.logger.info("File watcher service started (polling mode)")

    def stop(self) -> None:
        """Stop the file watcher service"""
        if not self.running:
            self.logger.warning("File watcher is not running")
            return

        self.logger.info("Stopping file watcher...")
        self.running = False

        # Stop watchdog observer if running
        if self.observer:
            if self.event_handler:
                self.event_handler.cancel_all_timers()
            self.observer.stop()
            self.observer.join(timeout=5.0)
            self.observer = None
            self.event_handler = None

        # Stop polling thread if running
        if self.thread:
            self.thread.join(timeout=10)
            self.thread = None

        self.logger.info("File watcher service stopped")
    
    def is_running(self) -> bool:
        """Check if the file watcher is currently running"""
        if self.use_watchdog and self.observer:
            return self.running and self.observer.is_alive()
        elif self.thread:
            return self.running and self.thread.is_alive()
        else:
            return self.running
    
    def process_now(self) -> Dict[str, Any]:
        """Manually trigger file processing (for testing/manual operation)"""
        return self.force_process_files()

# Global file watcher instance
file_watcher = FileWatcher()