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
    
    def _detect_file_type(self, df: pd.DataFrame, filename: str) -> str:
        """
        Detect the type of CSV file based on column structure.

        Args:
            df: DataFrame to analyze
            filename: Name of the file being analyzed

        Returns:
            'execution' for raw execution data, 'trade_log' for processed trades, 'unknown' if unclear
        """
        columns = set(df.columns)

        # Check for execution file pattern (NinjaTrader exports)
        execution_columns = {'ID', 'Account', 'Instrument', 'Time', 'Action', 'E/X', 'Quantity', 'Price', 'Commission'}
        if execution_columns.issubset(columns):
            return 'execution'

        # Check for trade log pattern (processed positions)
        trade_log_columns = {'Instrument', 'Side of Market', 'Quantity', 'Entry Price', 'Entry Time', 'Exit Time', 'Exit Price', 'ID', 'Account'}
        if trade_log_columns.issubset(columns):
            return 'trade_log'

        # Check for alternative execution formats (more flexible matching)
        alt_execution_patterns = [
            {'Instrument', 'Action', 'Quantity', 'Price', 'Time', 'ID', 'Account'},  # Minimal execution
            {'Instrument', 'Action', 'Qty', 'Price', 'Time', 'ID', 'Account'},      # Alternative quantity column
        ]

        for pattern in alt_execution_patterns:
            if pattern.issubset(columns):
                return 'execution_alt'

        return 'unknown'

    def _validate_csv_data(self, df: pd.DataFrame, filename: str) -> bool:
        """
        Validate CSV data structure and content based on detected file type.

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

            # Detect file type
            file_type = self._detect_file_type(df, filename)
            self.logger.info(f"Detected file type for {filename}: {file_type}")

            # Validate based on file type
            if file_type == 'execution':
                # Validate execution file columns (full NinjaTrader format)
                required_columns = ['ID', 'Account', 'Instrument', 'Time', 'Action', 'E/X', 'Quantity', 'Price', 'Commission']
                missing_columns = [col for col in required_columns if col not in df.columns]

                if missing_columns:
                    self.logger.warning(
                        f"Execution file {filename} missing required columns: {missing_columns}. "
                        f"Available columns: {list(df.columns)}"
                    )
                    return False

            elif file_type == 'execution_alt':
                # Validate alternative execution format
                required_columns = ['Instrument', 'Action', 'Quantity', 'Price', 'Time', 'ID', 'Account']
                missing_columns = [col for col in required_columns if col not in df.columns]

                if missing_columns:
                    # Try with 'Qty' instead of 'Quantity'
                    alt_required = ['Instrument', 'Action', 'Qty', 'Price', 'Time', 'ID', 'Account']
                    alt_missing = [col for col in alt_required if col not in df.columns]

                    if alt_missing:
                        self.logger.warning(
                            f"Alternative execution file {filename} missing required columns: {missing_columns}. "
                            f"Available columns: {list(df.columns)}"
                        )
                        return False

            elif file_type == 'trade_log':
                # Validate trade log columns
                required_columns = ['Instrument', 'Side of Market', 'Quantity', 'Entry Price', 'Entry Time', 'Exit Time', 'Exit Price', 'ID', 'Account']
                missing_columns = [col for col in required_columns if col not in df.columns]

                if missing_columns:
                    self.logger.warning(
                        f"Trade log file {filename} missing required columns: {missing_columns}. "
                        f"Available columns: {list(df.columns)}"
                    )
                    return False

            else:
                self.logger.warning(
                    f"Unknown file format for {filename}. "
                    f"Available columns: {list(df.columns)}"
                )
                return False

            # Additional validation checks
            if len(df) == 0:
                self.logger.info(f"File {filename} has no data rows")
                return False

            # Check for reasonable data in key columns (flexible based on detected columns)
            quantity_col = 'Quantity' if 'Quantity' in df.columns else 'Qty' if 'Qty' in df.columns else None
            if quantity_col and df[quantity_col].isna().all():
                self.logger.warning(f"File {filename} has no valid quantity data")
                return False

            price_cols = ['Price', 'Entry Price', 'Exit Price']
            has_valid_price = False
            for price_col in price_cols:
                if price_col in df.columns and not df[price_col].isna().all():
                    has_valid_price = True
                    break

            if not has_valid_price:
                self.logger.warning(f"File {filename} has no valid price data")
                return False

            self.logger.debug(f"File {filename} validation passed. Rows: {len(df)}, Type: {file_type}")
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

            # Detect file type for processing
            file_type = self._detect_file_type(df, file_path.name)

            # Process based on file type
            if file_type in ['execution', 'execution_alt']:
                # Process raw execution data using ExecutionProcessing
                self.logger.info(f"Processing execution file: {file_path.name}")

                # For execution_alt, we might need to add missing columns with defaults
                if file_type == 'execution_alt':
                    df = self._normalize_execution_columns(df)

                processed_trades = process_trades(df, self.multipliers)
                self.logger.info(f"Processed {len(processed_trades)} trades from execution file {file_path.name}")

            elif file_type == 'trade_log':
                # Process already-processed trade log data
                self.logger.info(f"Processing trade log file: {file_path.name}")
                processed_trades = self._process_trade_log(df)
                self.logger.info(f"Processed {len(processed_trades)} trades from trade log {file_path.name}")

            else:
                self.logger.error(f"Cannot process unknown file type: {file_path.name}")
                return []

            # Log processing summary
            if processed_trades:
                self._log_processing_summary(processed_trades, file_path.name)

            return processed_trades
            
        except Exception as e:
            self.logger.error(f"Error processing file {file_path.name}: {e}")
            return []
    
    def _log_processing_summary(self, trades: List[Dict[str, Any]], filename: str) -> None:
        """Log summary of processed trades/executions"""
        try:
            account_summary = {}
            instrument_summary = {}

            # Detect format
            is_individual_execution = trades and 'execution_id' in trades[0]

            for trade in trades:
                # Account summary
                account = trade.get('Account', 'Unknown')
                if account not in account_summary:
                    account_summary[account] = {'count': 0, 'total_pnl': 0}
                account_summary[account]['count'] += 1

                # For individual executions, P&L is not calculated yet
                if not is_individual_execution:
                    account_summary[account]['total_pnl'] += trade.get('Gain/Loss in Dollars', 0)

                # Instrument summary
                instrument = trade.get('Instrument', 'Unknown')
                if instrument not in instrument_summary:
                    instrument_summary[instrument] = 0
                instrument_summary[instrument] += 1

            record_type = "executions" if is_individual_execution else "trades"
            self.logger.info(f"Processing summary for {filename}:")
            self.logger.info(f"  Total {record_type}: {len(trades)}")

            for account, summary in account_summary.items():
                if is_individual_execution:
                    self.logger.info(f"  {account}: {summary['count']} executions")
                else:
                    self.logger.info(
                        f"  {account}: {summary['count']} trades, "
                        f"P&L: ${summary['total_pnl']:.2f}"
                    )

            for instrument, count in instrument_summary.items():
                self.logger.info(f"  {instrument}: {count} {record_type}")
                
        except Exception as e:
            self.logger.error(f"Error creating processing summary: {e}")
    
    def _import_trades_to_database(self, trades: List[Dict[str, Any]]) -> bool:
        """
        Import processed executions to the database.

        Handles both individual executions (new format) and complete trades (legacy format).

        Args:
            trades: List of execution/trade dictionaries to import

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
                    # Detect format: new individual execution format vs legacy trade format
                    is_individual_execution = 'execution_id' in trade and 'entry_exit' in trade

                    if is_individual_execution:
                        # New format: Individual execution
                        trade_data = {
                            'instrument': trade.get('Instrument', ''),
                            'side_of_market': trade.get('action', ''),  # Buy/Sell
                            'quantity': trade.get('quantity', 0),
                            'entry_price': trade.get('entry_price', None),
                            'entry_time': trade.get('entry_time', None),
                            'exit_time': trade.get('exit_time', None),
                            'exit_price': trade.get('exit_price', None),
                            'points_gain_loss': None,  # Position builder calculates this
                            'dollars_gain_loss': None,  # Position builder calculates this
                            'entry_execution_id': trade.get('execution_id', ''),
                            'commission': trade.get('commission', 0.0),
                            'account': trade.get('Account', '')
                        }
                        exec_id = trade_data['entry_execution_id']
                    else:
                        # Legacy format: Complete trade
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
                        exec_id = trade_data['entry_execution_id']

                    # Insert trade (database handles duplicates)
                    self.logger.debug(f"Importing execution: {exec_id}")
                    success = db.add_trade(trade_data)

                    if success:
                        imported_count += 1
                        self.logger.debug(f"Successfully imported execution {exec_id}")
                    else:
                        self.logger.warning(
                            f"Failed to import execution {exec_id} - possibly duplicate"
                        )

                self.logger.info(f"Successfully imported {imported_count} executions to database")
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
    
    def _detect_import_issues(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect potential issues in imported trades based on running quantity flow.

        This helps identify incorrect side_of_market classifications such as:
        - BuyToCover with no short position
        - Sell with no long position
        - Adding to existing positions unexpectedly

        Args:
            trades: List of trade dictionaries that were imported

        Returns:
            List of issue dictionaries containing details about potential problems
        """
        if not trades:
            return []

        detected_issues = []
        running_quantities: Dict[tuple, int] = {}

        # Sort by entry_time for proper analysis
        sorted_trades = sorted(trades, key=lambda t: t.get('entry_time', t.get('Entry Time', '')))

        for trade in sorted_trades:
            # Get trade details (handle both formats)
            account = trade.get('Account', trade.get('account', ''))
            instrument = trade.get('Instrument', trade.get('instrument', ''))
            action = trade.get('action', trade.get('Side of Market', trade.get('side_of_market', '')))
            quantity = abs(int(trade.get('quantity', trade.get('Quantity', 0))))
            entry_time = trade.get('entry_time', trade.get('Entry Time', ''))

            if not account or not instrument or not action:
                continue

            key = (account, instrument)
            prev_qty = running_quantities.get(key, 0)

            # Calculate signed quantity change
            if action in ['Buy', 'BuyToCover']:
                signed_change = quantity
            elif action in ['Sell', 'SellShort']:
                signed_change = -quantity
            else:
                signed_change = 0

            running_qty = prev_qty + signed_change
            running_quantities[key] = running_qty

            # Detect issues
            issue = self._detect_single_issue(action, prev_qty, running_qty)
            if issue:
                detected_issues.append({
                    'account': account,
                    'instrument': instrument,
                    'action': action,
                    'quantity': quantity,
                    'prev_qty': prev_qty,
                    'running_qty': running_qty,
                    'issue': issue,
                    'time': str(entry_time)
                })

        if detected_issues:
            self.logger.warning(
                f"Detected {len(detected_issues)} potential issues in imported trades. "
                "Review recommended in Execution Review screen."
            )

        return detected_issues

    def _detect_single_issue(self, action: str, prev_qty: int, running_qty: int) -> Optional[str]:
        """
        Detect potential issues with a single execution based on position state.

        Args:
            action: The execution action (Buy, Sell, BuyToCover, SellShort)
            prev_qty: Running quantity before this execution
            running_qty: Running quantity after this execution

        Returns:
            Issue description string if issue detected, None otherwise
        """
        # BuyToCover with no short position (prev_qty should be negative)
        if action == 'BuyToCover' and prev_qty >= 0:
            return 'BuyToCover with no short position'

        # SellShort when already short (adding to short - might be intentional but flag it)
        if action == 'SellShort' and prev_qty < 0:
            return 'SellShort adding to existing short'

        # Sell with no long position (prev_qty should be positive for a closing Sell)
        if action == 'Sell' and prev_qty <= 0:
            return 'Sell with no long position'

        # Buy when already long (adding to long - might be intentional but flag it)
        if action == 'Buy' and prev_qty > 0:
            return 'Buy adding to existing long'

        return None

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

                # Detect potential issues in imported trades
                issues_detected = self._detect_import_issues(all_trades)

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
                    'message': f'Successfully processed {len(processed_files)} files',
                    'issues_detected': issues_detected,
                    'has_issues': len(issues_detected) > 0
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

                # Detect potential issues in imported trades
                issues_detected = self._detect_import_issues(trades)

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
                    'message': f'Successfully reprocessed {file_path.name}',
                    'issues_detected': issues_detected,
                    'has_issues': len(issues_detected) > 0
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

    def _normalize_execution_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize execution DataFrame to match ExecutionProcessing expectations.

        Args:
            df: DataFrame to normalize

        Returns:
            Normalized DataFrame with required columns
        """
        df_normalized = df.copy()

        # Add missing columns with appropriate defaults if needed
        required_columns = ['ID', 'Account', 'Instrument', 'Time', 'Action', 'E/X', 'Quantity', 'Price', 'Commission']

        for col in required_columns:
            if col not in df_normalized.columns:
                if col == 'E/X':
                    df_normalized[col] = 'E'  # Default to 'E' for entry
                elif col == 'Commission':
                    df_normalized[col] = 0.0  # Default commission to 0
                else:
                    self.logger.warning(f"Missing required column {col}, cannot add default")

        # Handle alternative column names
        if 'Qty' in df_normalized.columns and 'Quantity' not in df_normalized.columns:
            df_normalized['Quantity'] = df_normalized['Qty']

        return df_normalized

    def _process_trade_log(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Process trade log data (already processed positions) into database format.

        Args:
            df: DataFrame containing trade log data

        Returns:
            List of trade dictionaries ready for database insertion
        """
        trades = []

        try:
            for index, row in df.iterrows():
                # Convert trade log format to database format
                trade = {
                    'instrument': row.get('Instrument', ''),
                    'side_of_market': row.get('Side of Market', ''),
                    'quantity': int(row.get('Quantity', 0)) if pd.notna(row.get('Quantity')) else 0,
                    'entry_price': float(row.get('Entry Price', 0)) if pd.notna(row.get('Entry Price')) else 0.0,
                    'exit_price': float(row.get('Exit Price', 0)) if pd.notna(row.get('Exit Price')) else 0.0,
                    'entry_time': self._parse_datetime(row.get('Entry Time', '')),
                    'exit_time': self._parse_datetime(row.get('Exit Time', '')),
                    'points_gain_loss': float(row.get('Result Gain/Loss in Points', 0)) if pd.notna(row.get('Result Gain/Loss in Points')) else 0.0,
                    'dollars_gain_loss': float(row.get('Gain/Loss in Dollars', 0)) if pd.notna(row.get('Gain/Loss in Dollars')) else 0.0,
                    'entry_execution_id': str(row.get('ID', '')),
                    'commission': float(row.get('Commission', 0)) if pd.notna(row.get('Commission')) else 0.0,
                    'account': row.get('Account', ''),
                }

                # Validate required fields
                if trade['instrument'] and trade['entry_time'] and trade['exit_time']:
                    trades.append(trade)
                else:
                    self.logger.warning(f"Skipping invalid trade at row {index}: missing required fields")

            self.logger.info(f"Converted {len(trades)} trade log entries to database format")
            return trades

        except Exception as e:
            self.logger.error(f"Error processing trade log: {e}")
            return []

    def _parse_datetime(self, datetime_str: str) -> str:
        """
        Parse datetime string from CSV and return in consistent format.

        Args:
            datetime_str: Datetime string to parse

        Returns:
            Formatted datetime string or empty string if parsing fails
        """
        if not datetime_str or pd.isna(datetime_str):
            return ''

        try:
            # Try common datetime formats
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f',
                '%m/%d/%Y %H:%M:%S',
                '%m/%d/%Y %I:%M:%S %p',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M:%S.%f'
            ]

            for fmt in formats:
                try:
                    dt = datetime.strptime(str(datetime_str), fmt)
                    return dt.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    continue

            # If all formats fail, return the original string
            self.logger.warning(f"Could not parse datetime: {datetime_str}")
            return str(datetime_str)

        except Exception as e:
            self.logger.error(f"Error parsing datetime {datetime_str}: {e}")
            return ''


# Global service instance
unified_csv_import_service = UnifiedCSVImportService()