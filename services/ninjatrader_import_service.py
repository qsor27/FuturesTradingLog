"""
NinjaTrader Import Service

Consolidated service for automatic detection, processing, and import of
NinjaTrader execution CSV files with account-aware position tracking.

Task Group 2: Core import service functionality
- File detection and stability checking
- CSV validation and parsing
- Execution ID deduplication with Redis
- Incremental processing support
- File archival logic

Task Group 4: Incremental CSV Processing with Deduplication
- Process same file multiple times incrementally
- Skip already-processed execution IDs
- Insert only new executions
- Trigger position rebuild for affected accounts
- Cache invalidation for updated data

Task Group 5: Auto-Start Background Watcher Service
- Background thread for automatic file detection
- Polling loop with configurable interval
- Graceful shutdown support
- Service status tracking
"""

import os
import time
import logging
import json
import shutil
import threading
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
import pandas as pd
import redis

from config import config


class NinjaTraderImportService:
    """
    Unified NinjaTrader CSV import service with automatic file detection,
    execution ID deduplication, and account-aware position building.
    """

    # Required CSV columns from NinjaTrader ExecutionExporter indicator
    REQUIRED_COLUMNS = [
        'Instrument', 'Action', 'Quantity', 'Price', 'Time', 'ID',
        'E/X', 'Position', 'Order ID', 'Name', 'Commission', 'Rate',
        'Account', 'Connection'
    ]

    # NinjaTrader file pattern
    FILE_PATTERN = 'NinjaTrader_Executions_*.csv'

    def __init__(self, data_dir: str = None):
        """
        Initialize NinjaTrader import service.

        Args:
            data_dir: Directory to monitor for CSV files (default: config.data_dir)
        """
        # Setup data directory
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = config.data_dir

        # State tracking
        # Track file modification times to detect mid-day updates
        self.file_mtimes: Dict[str, float] = {}
        self.last_processed_file: Optional[str] = None
        self.last_import_time: Optional[datetime] = None
        self.error_count: int = 0

        # Threading control (Task 5.2)
        self._watcher_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

        # Polling configuration (Task 5.3)
        self._poll_interval = 30  # Default: 30 seconds (configurable 30-60s)

        # Support legacy poll_interval attribute for tests
        self.poll_interval = self._poll_interval

        # Setup logger
        self.logger = self._setup_logger()

        # Setup Redis client for deduplication
        self.redis_client = self._setup_redis()

        # Database path
        self.db_path = config.db_path

        # Load instrument multipliers
        self.multipliers = self._load_instrument_multipliers()

        self.logger.info(f"NinjaTraderImportService initialized. Monitoring: {self.data_dir}")

    def _setup_logger(self) -> logging.Logger:
        """Setup dedicated logger for NinjaTrader import service"""
        logger = logging.getLogger('NinjaTraderImport')
        logger.setLevel(logging.INFO)

        # Avoid duplicate handlers
        if logger.handlers:
            return logger

        # Create logs directory
        log_dir = self.data_dir / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)

        # Rotating file handler (10MB max, 5 backups)
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_dir / 'import.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console handler for immediate feedback
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(file_formatter)
        logger.addHandler(console_handler)

        return logger

    def _setup_redis(self) -> Optional[redis.Redis]:
        """Setup Redis client for execution ID deduplication"""
        try:
            # Use redis_url from config to support Docker networking
            redis_url = config.redis_url
            redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            redis_client.ping()
            self.logger.info(f"Redis connection established for execution deduplication: {redis_url}")
            return redis_client
        except Exception as e:
            self.logger.warning(f"Redis connection failed: {e}. Deduplication disabled.")
            return None

    def _load_instrument_multipliers(self) -> Dict[str, float]:
        """Load instrument multipliers from configuration file"""
        try:
            multiplier_file = config.instrument_config
            if multiplier_file.exists():
                with open(multiplier_file, 'r') as f:
                    multipliers = json.load(f)
                    self.logger.info(f"Loaded {len(multipliers)} instrument multipliers")
                    return multipliers
            else:
                self.logger.warning(f"Instrument multipliers file not found: {multiplier_file}")
                return {}
        except Exception as e:
            self.logger.error(f"Error loading instrument multipliers: {e}")
            return {}

    # ========================================================================
    # File Detection and Stability Checking (Task 2.3)
    # ========================================================================

    def _watch_for_csv_files(self) -> List[Path]:
        """
        Watch for CSV files matching NinjaTrader pattern in data directory.

        Returns:
            List of CSV file paths found
        """
        try:
            csv_files = list(self.data_dir.glob(self.FILE_PATTERN))
            # Exclude archived files
            csv_files = [f for f in csv_files if 'archive' not in str(f)]
            return csv_files
        except Exception as e:
            self.logger.error(f"Error watching for CSV files: {e}")
            return []

    def _is_file_stable(self, file_path: Path, stability_seconds: int = 5) -> bool:
        """
        Check if file size has not changed for specified seconds.

        Args:
            file_path: Path to file to check
            stability_seconds: Seconds to wait for stability (default: 5)

        Returns:
            True if file is stable, False otherwise
        """
        try:
            if not file_path.exists():
                return False

            # Get initial file size
            initial_size = file_path.stat().st_size

            # Wait for stability period
            time.sleep(stability_seconds)

            # Check if size changed
            current_size = file_path.stat().st_size

            is_stable = (initial_size == current_size)

            if is_stable:
                self.logger.debug(f"File {file_path.name} is stable ({current_size} bytes)")
            else:
                self.logger.debug(
                    f"File {file_path.name} is not stable "
                    f"(size changed from {initial_size} to {current_size} bytes)"
                )

            return is_stable

        except Exception as e:
            self.logger.error(f"Error checking file stability for {file_path.name}: {e}")
            return False

    def _wait_for_file_available(self, file_path: Path, max_attempts: int = 4) -> bool:
        """
        Wait for file to become available with exponential backoff.

        Retry delays: 1s, 2s, 4s, 8s

        Args:
            file_path: Path to file
            max_attempts: Maximum retry attempts (default: 4)

        Returns:
            True if file becomes available, False otherwise
        """
        for attempt in range(max_attempts):
            try:
                # Try to open file for reading
                with open(file_path, 'r') as f:
                    f.read(1)  # Read single byte to test access
                return True

            except (PermissionError, OSError) as e:
                retry_delay = 2 ** attempt  # Exponential backoff: 1, 2, 4, 8
                self.logger.warning(
                    f"File {file_path.name} locked (attempt {attempt + 1}/{max_attempts}). "
                    f"Retrying in {retry_delay}s..."
                )
                if attempt < max_attempts - 1:
                    time.sleep(retry_delay)
                else:
                    self.logger.error(
                        f"File {file_path.name} still locked after {max_attempts} attempts. "
                        "Giving up."
                    )
                    return False

        return False

    # ========================================================================
    # CSV Validation and Parsing (Task 2.4)
    # ========================================================================

    def _validate_csv(self, file_path: Path) -> bool:
        """
        Validate CSV file has all required columns.

        Args:
            file_path: Path to CSV file

        Returns:
            True if valid, False otherwise
        """
        try:
            # Read just the header
            df = pd.read_csv(file_path, nrows=0)

            # Check for required columns
            missing_columns = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]

            if missing_columns:
                self.logger.warning(
                    f"CSV validation failed for {file_path.name}. "
                    f"Missing required columns: {missing_columns}"
                )
                return False

            self.logger.debug(f"CSV validation passed for {file_path.name}")
            return True

        except pd.errors.ParserError as e:
            self.logger.error(f"CSV parsing error for {file_path.name}: {e}")
            self._move_to_error_folder(file_path, f"Parser error: {e}")
            return False

        except Exception as e:
            self.logger.error(f"CSV validation error for {file_path.name}: {e}")
            return False

    def _parse_csv(self, file_path: Path) -> Optional[pd.DataFrame]:
        """
        Parse CSV file and return DataFrame.

        Args:
            file_path: Path to CSV file

        Returns:
            DataFrame if successful, None otherwise
        """
        try:
            df = pd.read_csv(file_path)

            if df.empty:
                self.logger.info(f"CSV file {file_path.name} is empty")
                return None

            self.logger.debug(f"Parsed {len(df)} rows from {file_path.name}")
            return df

        except pd.errors.ParserError as e:
            self.logger.error(f"Error parsing CSV {file_path.name}: {e}")
            self._move_to_error_folder(file_path, f"Parser error: {e}")
            return None

        except Exception as e:
            self.logger.error(f"Unexpected error parsing CSV {file_path.name}: {e}")
            return None

    def _move_to_error_folder(self, file_path: Path, reason: str):
        """
        Move corrupted file to error folder.

        Args:
            file_path: Path to file to move
            reason: Reason for moving to error folder
        """
        try:
            error_dir = self.data_dir / 'error'
            error_dir.mkdir(parents=True, exist_ok=True)

            # Add timestamp to filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            error_filename = f"{file_path.stem}_{timestamp}{file_path.suffix}"
            error_path = error_dir / error_filename

            shutil.move(str(file_path), str(error_path))

            self.logger.error(
                f"Moved corrupted file {file_path.name} to error folder: {error_path.name}. "
                f"Reason: {reason}"
            )

        except Exception as e:
            self.logger.error(f"Error moving file to error folder: {e}")

    # ========================================================================
    # Execution ID Deduplication with Redis (Task 2.5)
    # ========================================================================

    def _is_execution_processed(self, execution_id: str, date_str: str) -> bool:
        """
        Check if execution ID has already been processed.

        Args:
            execution_id: Execution ID from CSV
            date_str: Date string in YYYYMMDD format

        Returns:
            True if already processed, False otherwise
        """
        if not self.redis_client:
            # Without Redis, cannot track processed executions
            # Fall back to allowing all (may cause duplicates)
            return False

        try:
            redis_key = f'processed_executions:{date_str}'
            is_processed = self.redis_client.sismember(redis_key, execution_id)
            return bool(is_processed)

        except Exception as e:
            self.logger.error(f"Error checking execution processed status: {e}")
            return False

    def _mark_execution_processed(self, execution_id: str, date_str: str):
        """
        Mark execution ID as processed in Redis with 14-day TTL.

        Args:
            execution_id: Execution ID to mark
            date_str: Date string in YYYYMMDD format
        """
        if not self.redis_client:
            return

        try:
            redis_key = f'processed_executions:{date_str}'
            ttl_seconds = 14 * 24 * 60 * 60  # 14 days

            # Add to Redis set
            self.redis_client.sadd(redis_key, execution_id)

            # Set TTL on the key (14 days)
            self.redis_client.expire(redis_key, ttl_seconds)

            self.logger.debug(f"Marked execution {execution_id} as processed (TTL: 14 days)")

        except Exception as e:
            self.logger.error(f"Error marking execution as processed: {e}")

    def _generate_fallback_key(self, row: Dict) -> str:
        """
        Generate fallback composite key when execution ID is null.

        Format: {Time}_{Account}_{Instrument}_{Action}_{Quantity}_{Price}

        Args:
            row: CSV row data as dictionary

        Returns:
            Composite key string
        """
        return (
            f"{row['Time']}_"
            f"{row['Account']}_"
            f"{row['Instrument']}_"
            f"{row['Action']}_"
            f"{row['Quantity']}_"
            f"{row['Price']}"
        )

    # ========================================================================
    # Integration with EnhancedPositionServiceV2 (Task 2.6)
    # ========================================================================

    def _rebuild_positions_for_account_instrument(self, account: str, instrument: str):
        """
        Rebuild positions for specific account/instrument combination.

        Wrapper method that calls EnhancedPositionServiceV2 and invalidates cache.

        Args:
            account: Account identifier
            instrument: Instrument identifier
        """
        try:
            from services.enhanced_position_service_v2 import EnhancedPositionServiceV2

            with EnhancedPositionServiceV2(self.db_path) as position_service:
                result = position_service.rebuild_positions_for_account_instrument(
                    account=account,
                    instrument=instrument
                )

                self.logger.info(
                    f"Rebuilt {result['positions_created']} positions for "
                    f"{account}/{instrument}"
                )

                # Invalidate Redis cache for this account+instrument
                self._invalidate_cache_for_account_instrument(account, instrument)

                return result

        except Exception as e:
            self.logger.error(
                f"Error rebuilding positions for {account}/{instrument}: {e}",
                exc_info=True
            )
            return {'positions_created': 0, 'validation_errors': [str(e)]}

    def _invalidate_cache_for_account_instrument(self, account: str, instrument: str):
        """
        Invalidate Redis cache entries for account+instrument combination.

        Args:
            account: Account identifier
            instrument: Instrument identifier
        """
        if not self.redis_client:
            return

        try:
            # Cache key patterns to invalidate
            cache_keys = [
                f'positions:{account}:{instrument}',
                f'dashboard:{account}',
                f'statistics:{account}'
            ]

            for key in cache_keys:
                self.redis_client.delete(key)
                self.logger.debug(f"Invalidated cache key: {key}")

        except Exception as e:
            self.logger.error(f"Error invalidating cache: {e}")

    # ========================================================================
    # File Archival Logic (Task 2.7)
    # ========================================================================

    def _should_archive_file(self, file_path: Path, import_success: bool) -> bool:
        """
        Check if file should be archived.

        Both conditions must be met:
        1. All executions successfully imported (import_success=True)
        2. Current date > file date (next calendar day)

        Args:
            file_path: Path to file
            import_success: Whether import was successful

        Returns:
            True if should archive, False otherwise
        """
        if not import_success:
            return False

        try:
            # Extract date from filename: NinjaTrader_Executions_YYYYMMDD.csv
            filename = file_path.stem
            date_part = filename.split('_')[-1]  # Get YYYYMMDD part

            file_date = datetime.strptime(date_part, '%Y%m%d')
            current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            # Archive only if current date is after file date
            should_archive = current_date > file_date

            if should_archive:
                self.logger.info(
                    f"File {file_path.name} is ready for archival "
                    f"(dated {file_date.strftime('%Y-%m-%d')}, current date {current_date.strftime('%Y-%m-%d')})"
                )
            else:
                self.logger.debug(
                    f"File {file_path.name} not ready for archival yet "
                    f"(same day or future dated)"
                )

            return should_archive

        except (ValueError, IndexError) as e:
            self.logger.warning(
                f"Could not parse date from filename {file_path.name}: {e}. "
                "Skipping archival."
            )
            return False

    def _archive_file(self, file_path: Path):
        """
        Move file to archive directory, preserving filename.

        Args:
            file_path: Path to file to archive
        """
        try:
            # Create archive directory if needed
            archive_dir = self.data_dir / 'archive'
            archive_dir.mkdir(parents=True, exist_ok=True)

            # Destination path
            archive_path = archive_dir / file_path.name

            # Handle duplicate filenames
            if archive_path.exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                archive_path = archive_dir / f"{file_path.stem}_{timestamp}{file_path.suffix}"

            # Move file
            shutil.move(str(file_path), str(archive_path))

            self.logger.info(
                f"Archived file: {file_path.name} -> {archive_path.name} "
                f"at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

        except Exception as e:
            self.logger.error(f"Error archiving file {file_path.name}: {e}")

    # ========================================================================
    # Main Processing Logic (Task 4.2)
    # ========================================================================

    def process_csv_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a single CSV file incrementally.

        Main entry point for file processing that:
        - Validates CSV structure
        - Parses CSV data
        - Checks for already-processed execution IDs
        - Inserts new executions into database
        - Rebuilds affected positions
        - Archives file if conditions met

        Args:
            file_path: Path to CSV file

        Returns:
            Dictionary with processing results
        """
        self.logger.info(f"Starting processing of {file_path.name}")

        try:
            # Wait for file to be available (handle locks)
            if not self._wait_for_file_available(file_path):
                return {
                    'success': False,
                    'error': 'File locked or inaccessible',
                    'file': file_path.name
                }

            # Check file stability
            if not self._is_file_stable(file_path):
                self.logger.info(f"File {file_path.name} not stable yet, skipping for now")
                return {
                    'success': False,
                    'error': 'File not stable',
                    'file': file_path.name
                }

            # Validate CSV
            if not self._validate_csv(file_path):
                return {
                    'success': False,
                    'error': 'CSV validation failed',
                    'file': file_path.name
                }

            # Parse CSV
            df = self._parse_csv(file_path)
            if df is None or df.empty:
                return {
                    'success': True,
                    'executions_imported': 0,
                    'message': 'No data to process',
                    'file': file_path.name
                }

            # Process executions incrementally
            result = self._process_executions(df, file_path)

            # Archive file if conditions met
            if result['success'] and self._should_archive_file(file_path, result['success']):
                self._archive_file(file_path)

            # Update service state
            self.last_processed_file = file_path.name
            self.last_import_time = datetime.now()

            return result

        except Exception as e:
            self.logger.error(f"Error processing file {file_path.name}: {e}", exc_info=True)
            self.error_count += 1
            return {
                'success': False,
                'error': str(e),
                'file': file_path.name
            }

    def _process_executions(self, df: pd.DataFrame, file_path: Path) -> Dict[str, Any]:
        """
        Process executions from DataFrame.

        Task 4.2: Implement main processing workflow
        - Iterate rows and check _is_execution_processed() for each
        - Skip rows with already-processed execution IDs
        - Insert new executions with _insert_execution()
        - Mark processed with _mark_execution_processed()
        - Collect affected (account, instrument) pairs

        Task 4.5: Implement incremental position rebuilding
        - Collect unique (account, instrument) pairs from newly inserted executions
        - For each pair, call _rebuild_positions_for_account_instrument()

        Args:
            df: DataFrame with execution data
            file_path: Source file path

        Returns:
            Dictionary with processing results
        """
        # Extract date from filename for Redis key
        try:
            filename = file_path.stem
            date_str = filename.split('_')[-1]  # YYYYMMDD
        except:
            date_str = datetime.now().strftime('%Y%m%d')

        new_executions = 0
        skipped_executions = 0
        affected_combinations = set()

        for index, row in df.iterrows():
            try:
                # Get execution ID (or generate fallback)
                execution_id = str(row.get('ID', ''))
                if not execution_id or pd.isna(row.get('ID')):
                    execution_id = self._generate_fallback_key(row)

                # Check if already processed
                if self._is_execution_processed(execution_id, date_str):
                    skipped_executions += 1
                    continue

                # Insert execution into database
                trade_id = self._insert_execution(row)

                if trade_id:
                    # Mark as processed
                    self._mark_execution_processed(execution_id, date_str)
                    new_executions += 1

                    # Track affected account+instrument
                    account = str(row.get('Account', ''))
                    instrument = str(row.get('Instrument', ''))
                    affected_combinations.add((account, instrument))

            except Exception as e:
                self.logger.warning(
                    f"Error processing row {index} in {file_path.name}: {e}. "
                    "Skipping row."
                )
                continue

        # Task 4.5: Rebuild positions for affected combinations only
        for account, instrument in affected_combinations:
            self._rebuild_positions_for_account_instrument(account, instrument)

        self.logger.info(
            f"Processed {file_path.name}: "
            f"{new_executions} new, {skipped_executions} skipped"
        )

        return {
            'success': True,
            'executions_imported': new_executions,
            'executions_skipped': skipped_executions,
            'affected_accounts': len(set(a for a, _ in affected_combinations)),
            'affected_instruments': len(set(i for _, i in affected_combinations)),
            'file': file_path.name
        }

    # ========================================================================
    # Execution Insertion into Trades Table (Task 4.3)
    # ========================================================================

    def _insert_execution(self, row: Dict) -> Optional[int]:
        """
        Insert single execution into trades table.

        Task 4.3: Map CSV columns to trades table fields
        Task 4.4: Map CSV Action to MarketSide enum correctly

        Action mapping:
        - Buy -> MarketSide.BUY (entry_price)
        - Sell -> MarketSide.SELL (exit_price)
        - BuyToCover -> MarketSide.BUY_TO_COVER (exit_price)
        - SellShort -> MarketSide.SELL_SHORT (entry_price)

        Args:
            row: CSV row data

        Returns:
            Trade ID if successful, None otherwise
        """
        try:
            # Parse commission (remove $ prefix)
            commission_str = str(row.get('Commission', '0'))
            commission = float(commission_str.replace('$', ''))

            # Map Action to side_of_market and determine entry/exit price
            # NinjaTrader exports: "Buy", "Sell", "BuyToCover", "SellShort"
            action = str(row.get('Action', '')).strip()

            if action == 'Buy':
                side_of_market = 'Buy'
                entry_price = float(row.get('Price', 0))
                exit_price = None
            elif action == 'Sell':
                side_of_market = 'Sell'
                entry_price = None
                exit_price = float(row.get('Price', 0))
            elif action == 'BuyToCover':
                side_of_market = 'BuyToCover'
                entry_price = None
                exit_price = float(row.get('Price', 0))
            elif action == 'SellShort':
                side_of_market = 'SellShort'
                entry_price = float(row.get('Price', 0))
                exit_price = None
            else:
                self.logger.warning(f"Unknown action: {action}. Defaulting to Buy.")
                side_of_market = 'Buy'
                entry_price = float(row.get('Price', 0))
                exit_price = None

            # Parse timestamp (format: "M/d/yyyy h:mm:ss tt")
            time_str = str(row.get('Time', ''))
            entry_time = self._parse_ninjatrader_timestamp(time_str)

            # Prepare trade data
            trade_data = {
                'instrument': str(row.get('Instrument', '')),
                'account': str(row.get('Account', '')),
                'side_of_market': side_of_market,
                'quantity': abs(int(row.get('Quantity', 0))),  # Ensure positive
                'entry_price': entry_price,
                'exit_price': exit_price,
                'entry_time': entry_time,
                'exit_time': None,
                'entry_execution_id': str(row.get('ID', '')),
                'commission': commission,
                'points_gain_loss': None,
                'dollars_gain_loss': None
            }

            # Insert into database (use atomic transaction)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO trades (
                    instrument, account, side_of_market, quantity,
                    entry_price, exit_price, entry_time, exit_time,
                    entry_execution_id, commission, points_gain_loss, dollars_gain_loss
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_data['instrument'],
                trade_data['account'],
                trade_data['side_of_market'],
                trade_data['quantity'],
                trade_data['entry_price'],
                trade_data['exit_price'],
                trade_data['entry_time'],
                trade_data['exit_time'],
                trade_data['entry_execution_id'],
                trade_data['commission'],
                trade_data['points_gain_loss'],
                trade_data['dollars_gain_loss']
            ))

            trade_id = cursor.lastrowid
            conn.commit()
            conn.close()

            self.logger.debug(f"Inserted execution {trade_data['entry_execution_id']} as trade {trade_id}")
            return trade_id

        except Exception as e:
            self.logger.error(f"Error inserting execution: {e}", exc_info=True)
            return None

    def _parse_ninjatrader_timestamp(self, timestamp_str: str) -> Optional[str]:
        """
        Parse NinjaTrader timestamp format: "M/d/yyyy h:mm:ss tt"

        Args:
            timestamp_str: Timestamp string from CSV

        Returns:
            ISO format timestamp string or None
        """
        try:
            # Try common NinjaTrader format with AM/PM
            dt = datetime.strptime(timestamp_str, '%m/%d/%Y %I:%M:%S %p')
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            try:
                # Try alternative format without AM/PM
                dt = datetime.strptime(timestamp_str, '%m/%d/%Y %H:%M:%S')
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                self.logger.warning(f"Could not parse timestamp: {timestamp_str}")
                return None

    # ========================================================================
    # Background Service Methods (Task Group 5)
    # ========================================================================

    def start_watcher(self):
        """
        Start background watcher thread (Task 5.2).

        Creates and starts a non-daemon background thread that polls for new CSV files
        at the configured interval.
        """
        # Don't start if already running
        if self._running:
            self.logger.info("Background watcher already running")
            return

        # Clear stop event
        self._stop_event.clear()

        # Create and start watcher thread
        self._watcher_thread = threading.Thread(
            target=self._run_watcher_loop,
            name="NinjaTraderImportWatcher",
            daemon=False  # Non-daemon for controlled shutdown
        )

        # Mark as running
        self._running = True

        # Start thread
        self._watcher_thread.start()

        self.logger.info(
            f"Background watcher started. Polling every {self._poll_interval} seconds."
        )

    def stop_watcher(self):
        """
        Stop background watcher thread gracefully (Task 5.2).

        Sets stop event and waits for thread to complete current operation.
        """
        if not self._running:
            self.logger.debug("Background watcher not running, nothing to stop")
            return

        # Signal thread to stop
        self.logger.info("Stopping background watcher...")
        self._running = False
        self._stop_event.set()

        # Wait for thread to finish (with timeout)
        if self._watcher_thread and self._watcher_thread.is_alive():
            self._watcher_thread.join(timeout=30)

            if self._watcher_thread.is_alive():
                self.logger.warning(
                    "Background watcher thread did not stop within timeout"
                )
            else:
                self.logger.info("Background watcher stopped successfully")

        self._watcher_thread = None

    def _run_watcher_loop(self):
        """
        Main background loop for file detection (Task 5.3).

        Polls for CSV files at configured interval, checks stability,
        and processes new files automatically.
        """
        self.logger.info("Background watcher loop started")

        while not self._stop_event.is_set():
            try:
                # List CSV files in data folder matching pattern
                csv_files = self._watch_for_csv_files()

                for csv_file in csv_files:
                    # Check if stop requested
                    if self._stop_event.is_set():
                        break

                    # Get file modification time
                    try:
                        current_mtime = csv_file.stat().st_mtime
                        file_key = str(csv_file)
                        last_mtime = self.file_mtimes.get(file_key, 0)

                        # Skip if file hasn't been modified since last processing
                        if current_mtime <= last_mtime:
                            self.logger.debug(
                                f"File {csv_file.name} already processed (mtime: {current_mtime}), skipping"
                            )
                            continue

                        self.logger.info(
                            f"File {csv_file.name} is new or updated "
                            f"(mtime: {current_mtime} > {last_mtime})"
                        )

                    except Exception as e:
                        self.logger.error(f"Error checking file mtime for {csv_file.name}: {e}")
                        continue

                    # Check file stability (waits 5 seconds internally)
                    if self._is_file_stable(csv_file):
                        self.logger.info(
                            f"Detected stable file: {csv_file.name}. Processing..."
                        )

                        # Process the file
                        result = self.process_csv_file(csv_file)

                        if result['success']:
                            # Update modification time tracking
                            self.file_mtimes[file_key] = current_mtime

                            self.logger.info(
                                f"Successfully processed {csv_file.name}: "
                                f"{result.get('executions_imported', 0)} executions imported"
                            )
                        else:
                            self.logger.warning(
                                f"Failed to process {csv_file.name}: "
                                f"{result.get('error', 'Unknown error')}"
                            )
                    else:
                        self.logger.debug(
                            f"File {csv_file.name} not stable yet, will retry next cycle"
                        )

            except Exception as e:
                # Handle exceptions without crashing thread
                self.logger.error(
                    f"Error in background watcher loop: {e}",
                    exc_info=True
                )
                self.error_count += 1

            # Wait for poll interval (or until stop event)
            # Use wait with timeout to allow responsive shutdown
            self._stop_event.wait(timeout=self.poll_interval)

        self.logger.info("Background watcher loop stopped")

    def get_status(self) -> Dict[str, Any]:
        """
        Get service status (Task 5.6 - part of status endpoint).

        Returns:
            Dictionary with service state including:
            - running: Whether background service is running
            - last_processed_file: Name of last processed file
            - last_import_time: ISO timestamp of last import
            - error_count: Number of errors encountered
            - redis_connected: Whether Redis is available
        """
        # Count pending files
        pending_files = []
        try:
            csv_files = self._watch_for_csv_files()
            pending_files = [f.name for f in csv_files]
        except:
            pass

        return {
            'running': self._running,
            'last_processed_file': self.last_processed_file,
            'last_import_time': self.last_import_time.isoformat() if self.last_import_time else None,
            'error_count': self.error_count,
            'redis_connected': self.redis_client is not None,
            'pending_files': pending_files
        }


# Global service instance
ninjatrader_import_service = NinjaTraderImportService()
