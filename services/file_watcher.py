import os
import time
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from config import config
from services.unified_csv_import_service import unified_csv_import_service

class FileWatcher:
    """
    Enhanced file monitoring system that monitors the /Data directory for new CSV files
    and automatically processes them using the UnifiedCSVImportService.
    """
    
    def __init__(self, check_interval: int = None):
        self.check_interval = check_interval or config.auto_import_interval or 300  # Default 5 minutes
        self.running = False
        self.thread = None
        self.logger = self._setup_logger()
        self.last_check_time = 0
        
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
    
    def start(self) -> None:
        """Start the file watcher service"""
        if self.running:
            self.logger.warning("File watcher is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.logger.info("File watcher service started")
    
    def stop(self) -> None:
        """Stop the file watcher service"""
        if not self.running:
            self.logger.warning("File watcher is not running")
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
        
        self.logger.info("File watcher service stopped")
    
    def is_running(self) -> bool:
        """Check if the file watcher is currently running"""
        return self.running and self.thread and self.thread.is_alive()
    
    def process_now(self) -> Dict[str, Any]:
        """Manually trigger file processing (for testing/manual operation)"""
        return self.force_process_files()

# Global file watcher instance
file_watcher = FileWatcher()