import os
import time
import threading
import logging
from datetime import datetime
from pathlib import Path
import pandas as pd
import json
import shutil
from typing import List, Dict, Any

from config import config
from TradingLog_db import FuturesDB

# Import ExecutionProcessing conditionally
try:
    from ExecutionProcessing import process_trades
    EXECUTION_PROCESSING_AVAILABLE = True
except ImportError as e:
    print(f"Warning: ExecutionProcessing not available: {e}")
    process_trades = None
    EXECUTION_PROCESSING_AVAILABLE = False

class FileWatcher:
    """
    Background service that monitors the data directory for new NinjaTrader execution files
    and automatically processes them every 5 minutes.
    """
    
    def __init__(self, check_interval: int = None):
        self.check_interval = check_interval or config.auto_import_interval
        self.running = False
        self.thread = None
        self.processed_files = set()
        self.logger = self._setup_logger()
        
        # Load instrument multipliers
        self.multipliers = self._load_multipliers()
        
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
    
    def _load_multipliers(self) -> Dict[str, float]:
        """Load instrument multipliers from config"""
        try:
            with open(config.instrument_config, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading instrument multipliers: {e}")
            return {}
    
    def _find_new_files(self) -> List[Path]:
        """Find new NinjaTrader execution files that haven't been processed"""
        new_files = []
        
        # Look for NinjaTrader execution files
        pattern = "NinjaTrader_Executions_*.csv"
        for file_path in config.data_dir.glob(pattern):
            if file_path.name not in self.processed_files:
                # Check if file has been modified recently (within last 24 hours)
                # This prevents processing very old files on startup
                file_age = time.time() - file_path.stat().st_mtime
                if file_age < 86400:  # 24 hours in seconds
                    new_files.append(file_path)
        
        return new_files
    
    def _process_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Process a single NinjaTrader execution file"""
        try:
            self.logger.info(f"Processing file: {file_path.name}")
            
            if not EXECUTION_PROCESSING_AVAILABLE:
                self.logger.error("ExecutionProcessing module not available")
                return []
            
            # Read the CSV file
            df = pd.read_csv(file_path)
            
            # Check if file has any data
            if df.empty:
                self.logger.info(f"File {file_path.name} is empty, skipping")
                return []
            
            # Process the trades
            self.logger.info(f"Starting trade processing for {file_path.name}")
            processed_trades = process_trades(df, self.multipliers)
            
            self.logger.info(f"Processed {len(processed_trades)} trades from {file_path.name}")
            
            # Log summary of processed trades by account
            if processed_trades:
                account_summary = {}
                for trade in processed_trades:
                    account = trade['Account']
                    if account not in account_summary:
                        account_summary[account] = {'count': 0, 'total_pnl': 0}
                    account_summary[account]['count'] += 1
                    account_summary[account]['total_pnl'] += trade['Gain/Loss in Dollars']
                
                self.logger.info("Trade processing summary by account:")
                for account, summary in account_summary.items():
                    self.logger.info(f"  {account}: {summary['count']} trades, Total P&L: ${summary['total_pnl']:.2f}")
            
            return processed_trades
            
        except Exception as e:
            self.logger.error(f"Error processing file {file_path.name}: {e}")
            return []
    
    def _import_trades_to_db(self, trades: List[Dict[str, Any]]) -> bool:
        """Import processed trades directly to the database"""
        if not trades:
            return True
            
        try:
            with FuturesDB() as db:
                imported_count = 0
                for trade in trades:
                    # Convert the trade dictionary to match database format
                    trade_data = {
                        'instrument': trade['Instrument'],
                        'side_of_market': trade['Side of Market'],
                        'quantity': trade['Quantity'],
                        'entry_price': trade['Entry Price'],
                        'entry_time': trade['Entry Time'],
                        'exit_time': trade['Exit Time'],
                        'exit_price': trade['Exit Price'],
                        'points_gain_loss': trade['Result Gain/Loss in Points'],
                        'dollars_gain_loss': trade['Gain/Loss in Dollars'],
                        'entry_execution_id': trade['ID'],
                        'commission': trade['Commission'],
                        'account': trade['Account']
                    }
                    
                    # Insert trade into database (database handles duplicates)
                    self.logger.info(f"Attempting to add trade: {trade_data['entry_execution_id']} for {trade_data['instrument']}")
                    self.logger.debug(f"Trade data being inserted: {trade_data}")
                    success = db.add_trade(trade_data)
                    if success:
                        imported_count += 1
                        self.logger.info(f"Successfully added trade {trade_data['entry_execution_id']}")
                    else:
                        self.logger.warning(f"Failed to add trade {trade_data['entry_execution_id']} - possibly duplicate or data error")
                
                self.logger.info(f"Successfully imported {imported_count} trades to database")
                return True
                
        except Exception as e:
            self.logger.error(f"Error importing trades to database: {e}")
            return False
    
    def _archive_file(self, file_path: Path) -> None:
        """Move processed file to archive directory (only if file is older than 1 day)"""
        try:
            # Check if file is from today - if so, don't archive (NinjaTrader keeps it locked)
            file_age_hours = (time.time() - file_path.stat().st_mtime) / 3600
            if file_age_hours < 24:
                self.logger.info(f"Skipping archive of {file_path.name} - file is less than 24 hours old (NinjaTrader may have it locked)")
                return
            
            archive_dir = config.data_dir / 'archive'
            archive_dir.mkdir(parents=True, exist_ok=True)
            
            # Create unique filename if file already exists in archive
            archive_path = archive_dir / file_path.name
            counter = 1
            while archive_path.exists():
                name_parts = file_path.stem, counter, file_path.suffix
                archive_path = archive_dir / f"{name_parts[0]}_{name_parts[1]}{name_parts[2]}"
                counter += 1
            
            shutil.move(str(file_path), str(archive_path))
            self.logger.info(f"Archived file: {file_path.name} -> {archive_path.name}")
            
        except Exception as e:
            self.logger.error(f"Error archiving file {file_path.name}: {e}")
    
    def _check_and_process_files(self) -> None:
        """Check for new files and process them"""
        try:
            new_files = self._find_new_files()
            
            if not new_files:
                self.logger.debug("No new files to process")
                return
            
            self.logger.info(f"Found {len(new_files)} new files to process")
            
            all_trades = []
            processed_file_names = []
            
            for file_path in new_files:
                trades = self._process_file(file_path)
                all_trades.extend(trades)
                processed_file_names.append(file_path.name)
                
                # Mark file as processed
                self.processed_files.add(file_path.name)
            
            # Import all trades to database
            if all_trades:
                success = self._import_trades_to_db(all_trades)
                
                if success:
                    # Archive processed files
                    for file_path in new_files:
                        self._archive_file(file_path)
                    
                    self.logger.info(f"Successfully processed and archived {len(new_files)} files")
                else:
                    self.logger.error("Failed to import trades to database")
            else:
                self.logger.info("No trades found in processed files")
                
        except Exception as e:
            self.logger.error(f"Error in check_and_process_files: {e}")
    
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
    
    def process_now(self) -> None:
        """Manually trigger file processing (for testing/manual operation)"""
        self.logger.info("Manual file processing triggered")
        self._check_and_process_files()

# Global file watcher instance
file_watcher = FileWatcher()