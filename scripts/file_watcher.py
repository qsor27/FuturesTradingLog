#!/usr/bin/env python3
"""
Standalone file watcher service for Futures Trading Log.
Monitors configured directories for NinjaTrader CSV files and triggers automatic import.
"""

import sys
import time
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from services.unified_csv_import_service import UnifiedCSVImportService
from config.config import Config


class CSVFileHandler(FileSystemEventHandler):
    """Handler for CSV file system events."""

    def __init__(self, import_service):
        self.import_service = import_service
        self.logger = logging.getLogger(__name__)

    def on_created(self, event):
        """Handle new file creation."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process CSV files
        if file_path.suffix.lower() != '.csv':
            return

        self.logger.info(f"Detected new CSV file: {file_path}")

        # Wait a moment to ensure file is fully written
        time.sleep(1)

        try:
            # Trigger import
            result = self.import_service.import_csv(str(file_path))

            if result.get('success'):
                self.logger.info(f"Successfully imported {file_path}")
            else:
                self.logger.error(f"Failed to import {file_path}: {result.get('error')}")

        except Exception as e:
            self.logger.error(f"Error importing {file_path}: {e}", exc_info=True)


def setup_logging():
    """Configure logging for the file watcher service."""
    log_dir = Path(Config.DATA_DIR) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "file_watcher.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )


def main():
    """Main entry point for file watcher service."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Futures Trading Log File Watcher Service")

    # Get watch directory from config
    watch_dir = Config.get_setting('auto_import', 'watch_directory')

    if not watch_dir:
        logger.error("No watch directory configured. Please configure auto_import.watch_directory in settings.")
        sys.exit(1)

    watch_path = Path(watch_dir)

    if not watch_path.exists():
        logger.warning(f"Watch directory does not exist, creating: {watch_path}")
        watch_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"Monitoring directory: {watch_path}")

    # Initialize import service
    import_service = UnifiedCSVImportService()

    # Create event handler and observer
    event_handler = CSVFileHandler(import_service)
    observer = Observer()
    observer.schedule(event_handler, str(watch_path), recursive=False)

    # Start watching
    observer.start()
    logger.info("File watcher started successfully")

    try:
        # Keep running until interrupted
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping file watcher...")
        observer.stop()
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        observer.stop()

    observer.join()
    logger.info("File watcher stopped")


if __name__ == "__main__":
    main()
