"""
CSV File Watcher Service

Monitors the CSV directory for file changes and automatically triggers imports
with debouncing to handle NinjaTrader's frequent file writes.
"""
import logging
import threading
import time
from pathlib import Path
from typing import Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

from config import config


class CSVFileEventHandler(FileSystemEventHandler):
    """
    Handles file system events for CSV files with debouncing logic.
    """

    def __init__(self, on_csv_change: Callable[[Path], None], debounce_seconds: float = 5.0):
        """
        Initialize the CSV file event handler.

        Args:
            on_csv_change: Callback function to call when a CSV file changes
            debounce_seconds: Delay before triggering import (default: 5 seconds)
        """
        super().__init__()
        self.on_csv_change = on_csv_change
        self.debounce_seconds = debounce_seconds
        self.pending_timers: dict[str, threading.Timer] = {}
        self.lock = threading.Lock()
        self.logger = logging.getLogger('CSVWatcher')

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


class CSVWatcherService:
    """
    Service that monitors CSV directory for file changes and triggers automatic imports.
    """

    def __init__(self, csv_dir: Optional[Path] = None, debounce_seconds: float = 5.0):
        """
        Initialize the CSV watcher service.

        Args:
            csv_dir: Directory to monitor for CSV files (defaults to config.data_dir)
            debounce_seconds: Delay before triggering import (default: 5 seconds)
        """
        self.csv_dir = csv_dir or config.data_dir
        self.debounce_seconds = debounce_seconds
        self.observer: Optional[Observer] = None
        self.event_handler: Optional[CSVFileEventHandler] = None
        self.running = False
        self.logger = self._setup_logger()

        # Import callback will be set when service is started
        self.import_callback: Optional[Callable[[Path], None]] = None

        self.logger.info(f"CSVWatcherService initialized. Monitoring: {self.csv_dir}")

    def _setup_logger(self) -> logging.Logger:
        """Setup dedicated logger for CSV watcher service"""
        logger = logging.getLogger('CSVWatcher')
        logger.setLevel(logging.INFO)

        # Avoid duplicate handlers
        if logger.handlers:
            return logger

        # Create logs directory
        log_dir = config.logs_dir
        log_dir.mkdir(parents=True, exist_ok=True)

        # File handler
        file_handler = logging.FileHandler(log_dir / 'csv_watcher.log')
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(file_formatter)
        logger.addHandler(console_handler)

        return logger

    def start(self, import_callback: Callable[[Path], None]):
        """
        Start the file watcher service.

        Args:
            import_callback: Function to call when CSV file changes are detected
        """
        if self.running:
            self.logger.warning("CSV watcher is already running")
            return

        self.import_callback = import_callback

        # Ensure directory exists
        self.csv_dir.mkdir(parents=True, exist_ok=True)

        # Create event handler
        self.event_handler = CSVFileEventHandler(
            on_csv_change=self._handle_csv_import,
            debounce_seconds=self.debounce_seconds
        )

        # Create and start observer
        self.observer = Observer()
        self.observer.schedule(self.event_handler, str(self.csv_dir), recursive=False)
        self.observer.start()

        self.running = True
        self.logger.info(
            f"CSV watcher started - monitoring {self.csv_dir} "
            f"(debounce: {self.debounce_seconds}s)"
        )

    def _handle_csv_import(self, file_path: Path):
        """
        Handle CSV import request from file watcher.

        Args:
            file_path: Path to the CSV file to import
        """
        if self.import_callback:
            try:
                self.logger.info(f"Processing CSV import for {file_path.name}")
                self.import_callback(file_path)
                self.logger.info(f"Successfully processed {file_path.name}")
            except Exception as e:
                self.logger.error(f"Error during CSV import for {file_path.name}: {e}", exc_info=True)
        else:
            self.logger.error("No import callback configured")

    def stop(self):
        """Stop the file watcher service"""
        if not self.running:
            self.logger.warning("CSV watcher is not running")
            return

        self.logger.info("Stopping CSV watcher...")

        # Cancel any pending imports
        if self.event_handler:
            self.event_handler.cancel_all_timers()

        # Stop observer
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5.0)

        self.running = False
        self.logger.info("CSV watcher stopped")

    def is_running(self) -> bool:
        """Check if the watcher service is currently running"""
        return self.running

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures clean shutdown"""
        if self.running:
            self.stop()
