"""
Unified CSV Import Service

Consolidates all CSV import functionality into a single, consistent service
that handles automatic file detection, processing, and import of trading data.
"""
import os
import time
import logging
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import pandas as pd

from config import config

# Import database with fallback for different environments
try:
    from scripts.TradingLog_db import FuturesDB
except ImportError:
    try:
        from TradingLog_db import FuturesDB
    except ImportError as e:
        logging.error(f"Could not import FuturesDB: {e}")
        FuturesDB = None

# Import dependencies with fallback handling
try:
    from scripts.ExecutionProcessing import process_trades, invalidate_cache_after_import
    EXECUTION_PROCESSING_AVAILABLE = True
    CACHE_INVALIDATION_AVAILABLE = True
except ImportError:
    try:
        from ExecutionProcessing import process_trades, invalidate_cache_after_import
        EXECUTION_PROCESSING_AVAILABLE = True
        CACHE_INVALIDATION_AVAILABLE = True
    except ImportError as e:
        logging.warning(f"ExecutionProcessing not available: {e}")
        process_trades = None
        invalidate_cache_after_import = None
        EXECUTION_PROCESSING_AVAILABLE = False
        CACHE_INVALIDATION_AVAILABLE = False

try:
    from services.enhanced_position_service_v2 import EnhancedPositionServiceV2
    POSITION_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Position service not available: {e}")
    EnhancedPositionServiceV2 = None
    POSITION_SERVICE_AVAILABLE = False

try:
    from scripts.cache_manager import get_cache_manager
    CACHE_MANAGER_AVAILABLE = True
except ImportError:
    try:
        from cache_manager import get_cache_manager
        CACHE_MANAGER_AVAILABLE = True
    except ImportError as e:
        logging.warning(f"Cache manager not available: {e}")
        get_cache_manager = None
        CACHE_MANAGER_AVAILABLE = False


class UnifiedCSVImportService:
    """
    Unified service for processing all CSV imports from trading data sources.
    
    This service consolidates the fragmented import functionality and provides:
    - Automatic detection of new CSV files
    - Consistent validation and processing
    - Unified error handling and logging
    - Position generation and cache updates
    - File archiving and management
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize the unified CSV import service.
        
        Args:
            data_dir: Directory to monitor for CSV files (defaults to config.data_dir)
        """
        self.data_dir = data_dir or config.data_dir
        self.processed_files = set()
        self.logger = self._setup_logger()
        self.multipliers = self._load_instrument_multipliers()
        
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"UnifiedCSVImportService initialized. Monitoring: {self.data_dir}")
    
    def _setup_logger(self) -> logging.Logger:
        """Setup dedicated logger for CSV import service"""
        logger = logging.getLogger('UnifiedCSVImport')
        logger.setLevel(logging.INFO)
        
        # Avoid duplicate handlers
        if logger.handlers:
            return logger
        
        # Create logs directory
        log_dir = self.data_dir / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # File handler
        file_handler = logging.FileHandler(log_dir / 'csv_import.log')
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
    
    def _load_instrument_multipliers(self) -> Dict[str, float]:
        """Load instrument multipliers from configuration"""
        try:
            if config.instrument_config.exists():
                with open(config.instrument_config, 'r') as f:
                    multipliers = json.load(f)
                    self.logger.info(f"Loaded {len(multipliers)} instrument multipliers")
                    return multipliers
            else:
                self.logger.warning("Instrument configuration file not found")
                return {}
        except Exception as e:
            self.logger.error(f"Error loading instrument multipliers: {e}")
            return {}
    
    def _find_new_csv_files(self) -> List[Path]:
        """
        Find new CSV files that haven't been processed.
        
        Returns:
            List of Path objects for unprocessed CSV files
        """
        new_files = []
        
        try:
            # Look for all CSV files in the data directory
            for file_path in self.data_dir.glob("*.csv"):
                # Skip if already processed
                if file_path.name in self.processed_files:
                    continue
                
                # Only process recent files (within last 24 hours for safety)
                file_age = time.time() - file_path.stat().st_mtime
                if file_age < 86400:  # 24 hours in seconds
                    new_files.append(file_path)
                    self.logger.debug(f"Found new CSV file: {file_path.name}")
            
            if new_files:
                self.logger.info(f"Found {len(new_files)} new CSV files to process")
            else:
                self.logger.debug("No new CSV files found")
                
        except Exception as e:
            self.logger.error(f"Error scanning for CSV files: {e}")
        
        return new_files
    
    def _validate_csv_data(self, df: pd.DataFrame, filename: str) -> bool:
        """
        Validate CSV data structure and content.
        
        Args:
            df: DataFrame to validate
            filename: Name of file being validated (for logging)
            
        Returns:
            True if validation passes, False otherwise
        """
        try:
            # Check if DataFrame is empty
            if df.empty:
                self.logger.info(f"File {filename} is empty, skipping")
                return False
            
            # Check for required columns (flexible for different formats)
            required_base_columns = ['Time', 'Instrument', 'Qty', 'Price']
            
            # Check if we have basic required columns
            missing_columns = [col for col in required_base_columns 
                             if col not in df.columns]
            
            if missing_columns:
                self.logger.warning(
                    f"File {filename} missing required columns: {missing_columns}. "
                    f"Available columns: {list(df.columns)}"
                )
                return False
            
            # Additional validation checks
            if len(df) == 0:
                self.logger.info(f"File {filename} has no data rows")
                return False
            
            # Check for reasonable data in key columns
            if df['Qty'].isna().all():
                self.logger.warning(f"File {filename} has no valid quantity data")
                return False
            
            if df['Price'].isna().all():
                self.logger.warning(f"File {filename} has no valid price data")
                return False
            
            self.logger.debug(f"File {filename} validation passed. Rows: {len(df)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating CSV data for {filename}: {e}")
            return False
    
    def _process_csv_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Process a single CSV file and extract trading data.
        
        Args:
            file_path: Path to the CSV file to process
            
        Returns:
            List of processed trade dictionaries
        """
        try:
            self.logger.info(f"Processing CSV file: {file_path.name}")
            
            # Check if file exists
            if not file_path.exists():
                self.logger.error(f"File not found: {file_path}")
                return []
            
            # Check if ExecutionProcessing is available
            if not EXECUTION_PROCESSING_AVAILABLE or not process_trades:
                self.logger.error("ExecutionProcessing module not available")
                return []
            
            # Read CSV file
            try:
                df = pd.read_csv(file_path)
            except Exception as e:
                self.logger.error(f"Error reading CSV file {file_path.name}: {e}")
                return []
            
            # Validate data
            if not self._validate_csv_data(df, file_path.name):
                return []
            
            # Process trades using existing ExecutionProcessing logic
            self.logger.info(f"Starting trade processing for {file_path.name}")
            processed_trades = process_trades(df, self.multipliers)
            
            self.logger.info(f"Processed {len(processed_trades)} trades from {file_path.name}")
            
            # Log processing summary
            if processed_trades:
                self._log_processing_summary(processed_trades, file_path.name)
            
            return processed_trades
            
        except Exception as e:
            self.logger.error(f"Error processing file {file_path.name}: {e}")
            return []
    
    def _log_processing_summary(self, trades: List[Dict[str, Any]], filename: str) -> None:
        """Log summary of processed trades"""
        try:
            account_summary = {}
            instrument_summary = {}
            
            for trade in trades:
                # Account summary
                account = trade.get('Account', 'Unknown')
                if account not in account_summary:
                    account_summary[account] = {'count': 0, 'total_pnl': 0}
                account_summary[account]['count'] += 1
                account_summary[account]['total_pnl'] += trade.get('Gain/Loss in Dollars', 0)
                
                # Instrument summary
                instrument = trade.get('Instrument', 'Unknown')
                if instrument not in instrument_summary:
                    instrument_summary[instrument] = 0
                instrument_summary[instrument] += 1
            
            self.logger.info(f"Processing summary for {filename}:")
            self.logger.info(f"  Total trades: {len(trades)}")
            
            for account, summary in account_summary.items():
                self.logger.info(
                    f"  {account}: {summary['count']} trades, "
                    f"P&L: ${summary['total_pnl']:.2f}"
                )
            
            for instrument, count in instrument_summary.items():
                self.logger.info(f"  {instrument}: {count} trades")
                
        except Exception as e:
            self.logger.error(f"Error creating processing summary: {e}")
    
    def _import_trades_to_database(self, trades: List[Dict[str, Any]]) -> bool:
        """
        Import processed trades to the database.
        
        Args:
            trades: List of trade dictionaries to import
            
        Returns:
            True if import successful, False otherwise
        """
        if not trades:
            self.logger.debug("No trades to import")
            return True
        
        try:
            if not FuturesDB:
                self.logger.error("FuturesDB not available - cannot import trades")
                return False
                
            imported_count = 0
            
            with FuturesDB() as db:
                for trade in trades:
                    # Convert trade dictionary to database format
                    trade_data = {
                        'instrument': trade.get('Instrument', ''),
                        'side_of_market': trade.get('Side of Market', ''),
                        'quantity': trade.get('Quantity', 0),
                        'entry_price': trade.get('Entry Price', 0.0),
                        'entry_time': trade.get('Entry Time', ''),
                        'exit_time': trade.get('Exit Time', ''),
                        'exit_price': trade.get('Exit Price', 0.0),
                        'points_gain_loss': trade.get('Result Gain/Loss in Points', 0.0),
                        'dollars_gain_loss': trade.get('Gain/Loss in Dollars', 0.0),
                        'entry_execution_id': trade.get('ID', ''),
                        'commission': trade.get('Commission', 0.0),
                        'account': trade.get('Account', '')
                    }
                    
                    # Insert trade (database handles duplicates)
                    self.logger.debug(f"Importing trade: {trade_data['entry_execution_id']}")
                    success = db.add_trade(trade_data)
                    
                    if success:
                        imported_count += 1
                        self.logger.debug(f"Successfully imported trade {trade_data['entry_execution_id']}")
                    else:
                        self.logger.warning(
                            f"Failed to import trade {trade_data['entry_execution_id']} "
                            f"- possibly duplicate"
                        )
                
                self.logger.info(f"Successfully imported {imported_count} trades to database")
                return True
                
        except Exception as e:
            self.logger.error(f"Error importing trades to database: {e}")
            return False
    
    def _rebuild_positions(self, db) -> Dict[str, int]:
        """
        Rebuild positions from imported trades.
        
        Args:
            db: Database instance
            
        Returns:
            Dictionary with rebuild results
        """
        try:
            if not POSITION_SERVICE_AVAILABLE or not EnhancedPositionServiceV2:
                self.logger.error("Position service not available")
                return {'positions_created': 0, 'trades_processed': 0}
            
            self.logger.info("Rebuilding positions from imported trades...")
            
            with EnhancedPositionServiceV2() as position_service:
                result = position_service.rebuild_positions_from_trades()
                
                self.logger.info(
                    f"Position rebuild complete: {result['positions_created']} positions "
                    f"created from {result['trades_processed']} trades"
                )
                
                return result
                
        except Exception as e:
            self.logger.error(f"Error rebuilding positions: {e}")
            return {'positions_created': 0, 'trades_processed': 0}
    
    def _invalidate_cache_after_import(self, trades: List[Dict[str, Any]]) -> None:
        """
        Invalidate relevant cache entries after importing trades.
        
        Args:
            trades: List of imported trades for cache invalidation
        """
        if not trades:
            return
        
        try:
            # Use existing cache invalidation if available
            if CACHE_INVALIDATION_AVAILABLE and invalidate_cache_after_import:
                invalidate_cache_after_import(trades)
                return
            
            # Fallback: manual cache invalidation using cache manager
            if not CACHE_MANAGER_AVAILABLE or not get_cache_manager:
                self.logger.warning("Cache invalidation not available")
                return
            
            # Extract unique instruments and accounts
            instruments = set()
            accounts = set()
            
            for trade in trades:
                if 'Instrument' in trade:
                    instruments.add(trade['Instrument'])
                if 'Account' in trade:
                    accounts.add(trade['Account'])
            
            instruments = list(instruments)
            accounts = list(accounts)
            
            if instruments or accounts:
                cache_manager = get_cache_manager()
                result = cache_manager.on_trade_import(instruments, accounts)
                
                self.logger.info(
                    f"Cache invalidated for {len(instruments)} instruments, "
                    f"{len(accounts)} accounts"
                )
            
        except Exception as e:
            self.logger.error(f"Error invalidating cache after import: {e}")
    
    def _archive_file(self, file_path: Path) -> None:
        """
        Archive processed file to archive directory.
        Only archives files older than 24 hours to avoid NinjaTrader file locks.
        
        Args:
            file_path: Path to file to archive
        """
        try:
            # Check file age - don't archive recent files (NinjaTrader may have them locked)
            file_age_hours = (time.time() - file_path.stat().st_mtime) / 3600
            if file_age_hours < 24:
                self.logger.info(
                    f"Skipping archive of {file_path.name} - file is less than 24 hours old"
                )
                return
            
            # Create archive directory
            archive_dir = self.data_dir / 'archive'
            archive_dir.mkdir(parents=True, exist_ok=True)
            
            # Handle duplicate filenames in archive
            archive_path = archive_dir / file_path.name
            counter = 1
            while archive_path.exists():
                stem = file_path.stem
                suffix = file_path.suffix
                archive_path = archive_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            
            # Move file to archive
            shutil.move(str(file_path), str(archive_path))
            self.logger.info(f"Archived file: {file_path.name} -> {archive_path.name}")
            
        except Exception as e:
            self.logger.error(f"Error archiving file {file_path.name}: {e}")
    
    def process_all_new_files(self) -> Dict[str, Any]:
        """
        Process all new CSV files found in the data directory.
        
        Returns:
            Dictionary with processing results
        """
        try:
            # Find new files
            new_files = self._find_new_csv_files()
            
            if not new_files:
                return {
                    'success': True,
                    'files_processed': 0,
                    'trades_imported': 0,
                    'positions_created': 0,
                    'message': 'No new files to process'
                }
            
            # Process all files
            all_trades = []
            processed_files = []
            
            for file_path in new_files:
                trades = self._process_csv_file(file_path)
                all_trades.extend(trades)
                processed_files.append(file_path)
                
                # Mark as processed
                self.processed_files.add(file_path.name)
            
            # Import trades to database
            if all_trades:
                import_success = self._import_trades_to_database(all_trades)
                
                if not import_success:
                    return {
                        'success': False,
                        'error': 'Failed to import trades to database',
                        'files_processed': len(processed_files),
                        'trades_imported': 0
                    }
                
                # Rebuild positions
                if FuturesDB:
                    with FuturesDB() as db:
                        position_result = self._rebuild_positions(db)
                else:
                    self.logger.warning("FuturesDB not available - skipping position rebuild")
                    position_result = {'positions_created': 0, 'trades_processed': 0}
                
                # Invalidate cache for imported trades
                self._invalidate_cache_after_import(all_trades)
                
                # Archive processed files
                for file_path in processed_files:
                    self._archive_file(file_path)
                
                return {
                    'success': True,
                    'files_processed': len(processed_files),
                    'trades_imported': len(all_trades),
                    'positions_created': position_result.get('positions_created', 0),
                    'message': f'Successfully processed {len(processed_files)} files'
                }
            else:
                return {
                    'success': True,
                    'files_processed': len(processed_files),
                    'trades_imported': 0,
                    'positions_created': 0,
                    'message': 'No trades found in processed files'
                }
                
        except Exception as e:
            self.logger.error(f"Error in process_all_new_files: {e}")
            return {
                'success': False,
                'error': str(e),
                'files_processed': 0,
                'trades_imported': 0
            }
    
    def manual_reprocess_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Manually reprocess a specific CSV file.
        
        Args:
            file_path: Path to the file to reprocess
            
        Returns:
            Dictionary with reprocessing results
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                return {
                    'success': False,
                    'error': f'File not found: {file_path}'
                }
            
            self.logger.info(f"Manual reprocessing requested for: {file_path.name}")
            
            # Process the file
            trades = self._process_csv_file(file_path)
            
            if trades:
                # Import to database
                import_success = self._import_trades_to_database(trades)
                
                if not import_success:
                    return {
                        'success': False,
                        'error': 'Failed to import trades to database'
                    }
                
                # Rebuild positions
                if FuturesDB:
                    with FuturesDB() as db:
                        position_result = self._rebuild_positions(db)
                else:
                    self.logger.warning("FuturesDB not available - skipping position rebuild")
                    position_result = {'positions_created': 0, 'trades_processed': 0}
                
                # Invalidate cache for imported trades
                self._invalidate_cache_after_import(trades)
                
                # Mark as processed
                self.processed_files.add(file_path.name)
                
                return {
                    'success': True,
                    'trades_imported': len(trades),
                    'positions_created': position_result.get('positions_created', 0),
                    'message': f'Successfully reprocessed {file_path.name}'
                }
            else:
                return {
                    'success': True,
                    'trades_imported': 0,
                    'positions_created': 0,
                    'message': f'No trades found in {file_path.name}'
                }
                
        except Exception as e:
            self.logger.error(f"Error in manual_reprocess_file: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_processing_status(self) -> Dict[str, Any]:
        """
        Get current processing status and statistics.
        
        Returns:
            Dictionary with status information
        """
        return {
            'total_processed_files': len(self.processed_files),
            'processed_files': list(self.processed_files),
            'data_directory': str(self.data_dir),
            'last_check': datetime.now().isoformat(),
            'execution_processing_available': EXECUTION_PROCESSING_AVAILABLE,
            'position_service_available': POSITION_SERVICE_AVAILABLE,
            'cache_invalidation_available': CACHE_INVALIDATION_AVAILABLE,
            'cache_manager_available': CACHE_MANAGER_AVAILABLE
        }
    
    def reset_processed_files(self) -> None:
        """Reset the list of processed files (for testing/debugging)"""
        self.processed_files.clear()
        self.logger.info("Processed files list reset")
    
    def is_file_processed(self, filename: str) -> bool:
        """Check if a file has been processed"""
        return filename in self.processed_files
    
    def get_available_files(self) -> List[Path]:
        """Get list of all available CSV files in data directory"""
        try:
            return list(self.data_dir.glob("*.csv"))
        except Exception as e:
            self.logger.error(f"Error getting available files: {e}")
            return []


# Global service instance
unified_csv_import_service = UnifiedCSVImportService()