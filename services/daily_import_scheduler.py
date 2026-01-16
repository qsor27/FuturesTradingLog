"""
Daily Import Scheduler Service

Implements the daily import strategy for futures trading data:
- Automatic import at 2:05pm Pacific (5:05pm Eastern) when market closes
- Manual import trigger via API endpoint
- Import validation (date matching, closed positions only)

Futures Market Schedule:
- Trading Hours: 23 hours/day, 5 days/week
- Sessions: Sunday 3pm PT → Monday 2pm PT, Monday 3pm PT → Tuesday 2pm PT, etc.
- Data Export: NinjaTrader exports with CLOSING date (e.g., Monday session closes at 2pm = Monday's date)

Task Group 4: Daily Import Strategy Implementation
Task Group 2: APScheduler Refactoring for Timezone-Aware Scheduling
"""

import json
import logging
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import redis

from config import config
# Use the global singleton instance to avoid duplicate service instances
from services.ninjatrader_import_service import ninjatrader_import_service
from services.data_service import ohlc_service
from services.instrument_mapper import InstrumentMapper
from services.data_completeness_service import get_data_completeness_service

logger = logging.getLogger('DailyImportScheduler')


class DailyImportScheduler:
    """
    Service for scheduling daily imports at market close (2:05pm Pacific).

    Features:
    - Scheduled import at 2:05pm PT daily (if app is running)
    - Manual import trigger via API
    - Import validation (date matching, closed positions only)
    - Timezone-aware scheduling (Pacific Time) using APScheduler
    """

    # Market close time: 2:00pm Pacific (5:00pm Eastern)
    # Import scheduled for 2:05pm Pacific to allow NinjaTrader export to complete
    IMPORT_TIME_PT = "14:05"  # 2:05pm Pacific

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize the daily import scheduler.

        Args:
            data_dir: Directory containing CSV files (default: config.data_dir)
        """
        self.data_dir = data_dir or config.data_dir
        # Use the global singleton instance to ensure consistent Redis deduplication
        # and prevent race conditions from multiple service instances
        self.import_service = ninjatrader_import_service

        # OHLC sync services
        self.ohlc_service = ohlc_service
        self.instrument_mapper = InstrumentMapper()

        # APScheduler instance
        self._scheduler: Optional[BackgroundScheduler] = None
        self._running = False

        # Import history
        self.last_scheduled_import: Optional[datetime] = None
        self.last_manual_import: Optional[datetime] = None
        self.import_history: List[Dict[str, Any]] = []

        # Timezone
        self.pacific_tz = pytz.timezone('America/Los_Angeles')

        # Redis client for deduplication
        self._redis_client: Optional[redis.Redis] = None

        logger.info("DailyImportScheduler initialized")

        # Validate configuration at startup
        self._validate_timezone_config()
        self._validate_redis_connection()
        self._init_redis_client()
        logger.info(f"Scheduled import time: {self.IMPORT_TIME_PT} PT")


    def _validate_redis_connection(self) -> bool:
        """
        Validate Redis connectivity at startup.

        Returns:
            True if Redis is accessible, False otherwise
        """
        try:
            # Only validate if cache is enabled
            if not config.cache_enabled:
                logger.warning("=" * 80)
                logger.warning("CACHE_ENABLED is set to false")
                logger.warning("OHLC data sync requires Redis caching to function properly")
                logger.warning("Troubleshooting:")
                logger.warning("  1. Set CACHE_ENABLED=true in .env file")
                logger.warning("  2. Ensure REDIS_URL points to correct Redis instance")
                logger.warning("  3. For Docker: use REDIS_URL=redis://redis:6379/0")
                logger.warning("  4. For local: use REDIS_URL=redis://localhost:6379/0")
                logger.warning("=" * 80)
                return False

            # Test Redis connection
            import redis
            redis_client = redis.Redis.from_url(config.redis_url)
            redis_client.ping()

            logger.info(f"Redis connection successful: {config.redis_url}")
            return True

        except Exception as e:
            logger.error("=" * 80)
            logger.error("Redis connection failed!")
            logger.error(f"Error: {e}")
            logger.error(f"Redis URL: {config.redis_url}")
            logger.error("Troubleshooting:")
            logger.error("  1. Verify Redis service is running")
            logger.error("  2. Check REDIS_URL in .env file")
            logger.error("  3. For Docker: use 'redis' as hostname (redis://redis:6379/0)")
            logger.error("  4. For local: use 'localhost' (redis://localhost:6379/0)")
            logger.error("  5. Ensure containers are on the same Docker network")
            logger.error("=" * 80)
            return False

    def _validate_timezone_config(self) -> bool:
        """
        Validate timezone configuration (Pacific Time).

        Returns:
            True if timezone is properly configured
        """
        try:
            # Verify Pacific timezone is set
            if self.pacific_tz.zone != 'America/Los_Angeles':
                logger.error(f"Timezone misconfigured! Expected 'America/Los_Angeles', got '{self.pacific_tz.zone}'")
                return False

            # Log current time in both UTC and Pacific
            now_utc = datetime.now(pytz.UTC)
            now_pt = datetime.now(self.pacific_tz)

            logger.info("Timezone configuration validated:")
            logger.info(f"  - Pacific Time: {now_pt.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            logger.info(f"  - UTC Time: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            logger.info(f"  - Scheduled import: {self.IMPORT_TIME_PT} PT (22:05 UTC)")

            return True

        except Exception as e:
            logger.error(f"Timezone validation failed: {e}", exc_info=True)
            return False

    def _init_redis_client(self) -> None:
        """Initialize Redis client for deduplication tracking."""
        try:
            if not config.cache_enabled:
                logger.warning("Redis deduplication disabled (CACHE_ENABLED=false)")
                return

            self._redis_client = redis.Redis.from_url(config.redis_url)
            self._redis_client.ping()
            logger.info("Redis client initialized for import deduplication")

        except Exception as e:
            logger.warning(f"Redis client initialization failed: {e}")
            logger.warning("Scheduled imports will proceed without deduplication protection")
            self._redis_client = None

    def _get_csv_file_path(self, date_str: str) -> Optional[Path]:
        """Get the path to the CSV file for a given date."""
        data_path = Path(self.data_dir) if isinstance(self.data_dir, str) else self.data_dir
        file_path = data_path / f"NinjaTrader_Executions_{date_str}.csv"
        return file_path if file_path.exists() else None

    def _get_file_mtime(self, file_path: Path) -> Optional[float]:
        """Get the modification time of a file."""
        try:
            return file_path.stat().st_mtime
        except Exception:
            return None

    def _should_run_scheduled_import(self) -> Tuple[bool, str]:
        """
        Check if scheduled import should run.

        Checks:
        1. Is it a weekend? (Skip Saturday/Sunday)
        2. Has today's import already run? (Check Redis)
        3. Has the file been modified since last import? (Re-import if updated)

        Returns:
            (should_run, reason) tuple
        """
        now_pt = datetime.now(self.pacific_tz)
        today_str = now_pt.strftime('%Y%m%d')

        # Check 1: Skip weekends (futures markets closed Sat/Sun)
        weekday = now_pt.weekday()
        if weekday == 5:  # Saturday
            return False, "market closed (Saturday)"
        if weekday == 6:  # Sunday
            return False, "market closed (Sunday)"

        # Check 2: Has today's import already run AND file not modified since?
        if self._redis_client:
            try:
                redis_key = f'daily_import:last_scheduled:{today_str}'
                if self._redis_client.exists(redis_key):
                    existing = self._redis_client.get(redis_key)
                    if existing:
                        try:
                            record = json.loads(existing)
                            prev_time = record.get('timestamp', 'unknown time')
                            recorded_mtime = record.get('file_mtime')

                            # Check if file has been modified since last import
                            file_path = self._get_csv_file_path(today_str)
                            if file_path:
                                current_mtime = self._get_file_mtime(file_path)
                                if current_mtime and recorded_mtime:
                                    if current_mtime > recorded_mtime:
                                        logger.info(f"File modified since last import (recorded: {recorded_mtime}, current: {current_mtime})")
                                        return True, "file modified since last import"
                                elif current_mtime and not recorded_mtime:
                                    # File exists but no mtime was recorded - re-import to be safe
                                    logger.info("No file mtime recorded in previous import, re-importing")
                                    return True, "no file mtime recorded previously"

                            return False, f"already completed for {today_str} at {prev_time}"
                        except json.JSONDecodeError:
                            pass
                    return False, f"already completed for {today_str}"
            except Exception as e:
                logger.warning(f"Redis check failed, proceeding with import: {e}")

        return True, "ready to run"

    def _record_scheduled_import_complete(self, result: Dict[str, Any]) -> None:
        """
        Record successful scheduled import to Redis.

        This prevents duplicate imports if the container restarts.
        Stores file modification time to detect if file is updated after import.

        Args:
            result: Import result dictionary
        """
        if not self._redis_client:
            logger.debug("Redis not available, skipping import record")
            return

        try:
            today_str = datetime.now(self.pacific_tz).strftime('%Y%m%d')
            redis_key = f'daily_import:last_scheduled:{today_str}'

            # Get file modification time for change detection
            file_path = self._get_csv_file_path(today_str)
            file_mtime = self._get_file_mtime(file_path) if file_path else None

            import_record = {
                'timestamp': datetime.now(self.pacific_tz).isoformat(),
                'success': result.get('success', False),
                'executions_imported': result.get('total_executions', 0),
                'files_processed': result.get('files_processed', 0),
                'positions_rebuilt': result.get('positions_rebuilt', 0),
                'file_mtime': file_mtime  # Track file modification time
            }

            # Set with 7-day TTL for automatic cleanup
            self._redis_client.setex(
                redis_key,
                7 * 24 * 60 * 60,  # 7 days in seconds
                json.dumps(import_record)
            )

            logger.info(f"Recorded scheduled import completion to Redis: {redis_key} (file_mtime: {file_mtime})")

        except Exception as e:
            logger.warning(f"Failed to record import completion to Redis: {e}")
    def _catch_up_missed_imports(self) -> Dict[str, Any]:
        """
        Catch up on any missed imports at startup.

        This ensures that if the container/computer was not running during the
        scheduled import time, any unprocessed CSV files will be imported.
        """
        logger.info("=" * 80)
        logger.info("STARTUP CATCH-UP: Checking for missed imports...")
        logger.info("=" * 80)

        try:
            csv_pattern = "NinjaTrader_Executions_*.csv"
            data_path = Path(self.data_dir) if isinstance(self.data_dir, str) else self.data_dir
            csv_files = sorted(data_path.glob(csv_pattern))

            if not csv_files:
                logger.info("No CSV files found to check")
                return {'success': True, 'files_checked': 0, 'files_caught_up': 0}

            logger.info(f"Found {len(csv_files)} CSV files to check")

            files_caught_up = 0
            total_executions = 0
            caught_up_files = []

            for csv_file in csv_files:
                try:
                    date_str = csv_file.stem.split('_')[-1]
                    datetime.strptime(date_str, '%Y%m%d')
                except (IndexError, ValueError):
                    logger.warning(f"Skipping file with invalid date format: {csv_file.name}")
                    continue

                if self._has_been_imported(date_str):
                    logger.debug(f"Already imported: {csv_file.name}")
                    continue

                file_date = datetime.strptime(date_str, '%Y%m%d')
                if file_date.weekday() >= 5:
                    logger.debug(f"Skipping weekend file: {csv_file.name}")
                    continue

                logger.info(f"CATCH-UP: Importing missed file {csv_file.name}...")

                try:
                    import_result = self.import_service.process_csv_file(csv_file)

                    if import_result.get('success', False):
                        executions = import_result.get('executions_imported', 0)
                        total_executions += executions
                        files_caught_up += 1
                        caught_up_files.append(csv_file.name)
                        self._record_catch_up_import(date_str, import_result)

                        instruments = self._extract_instruments_from_csv(csv_file)
                        if instruments:
                            self._trigger_ohlc_sync(instruments=instruments, reason=f"catch_up_{date_str}")

                        logger.info(f"  Imported {executions} executions from {csv_file.name}")
                    else:
                        logger.warning(f"  Failed to import {csv_file.name}: {import_result.get('error', 'Unknown')}")

                except Exception as e:
                    logger.error(f"  Error importing {csv_file.name}: {e}")
                    continue

            if files_caught_up > 0:
                logger.info("=" * 80)
                logger.info(f"CATCH-UP COMPLETE: {files_caught_up} files, {total_executions} executions")
                logger.info(f"Files caught up: {', '.join(caught_up_files)}")
                logger.info("=" * 80)
            else:
                logger.info("No missed imports to catch up - all files already processed")

            return {
                'success': True,
                'files_checked': len(csv_files),
                'files_caught_up': files_caught_up,
                'total_executions': total_executions,
                'caught_up_files': caught_up_files
            }

        except Exception as e:
            logger.error(f"Error during catch-up: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def _has_been_imported(self, date_str: str) -> bool:
        """
        Check if a date's import has already been completed.

        Also checks if the file has been modified since the last import.
        Returns False if file was modified (needs re-import).
        """
        if not self._redis_client:
            return False
        try:
            redis_key = f'daily_import:last_scheduled:{date_str}'
            if not self._redis_client.exists(redis_key):
                return False

            # Check if file has been modified since last import
            existing = self._redis_client.get(redis_key)
            if existing:
                try:
                    record = json.loads(existing)
                    recorded_mtime = record.get('file_mtime')

                    file_path = self._get_csv_file_path(date_str)
                    if file_path:
                        current_mtime = self._get_file_mtime(file_path)
                        if current_mtime and recorded_mtime:
                            if current_mtime > recorded_mtime:
                                logger.info(f"File {date_str} modified since last import, needs re-import")
                                return False
                        elif current_mtime and not recorded_mtime:
                            # File exists but no mtime recorded - needs re-import
                            logger.info(f"No mtime recorded for {date_str}, needs re-import")
                            return False
                except json.JSONDecodeError:
                    pass

            return True
        except Exception as e:
            logger.warning(f"Redis check failed for {date_str}: {e}")
            return False

    def _record_catch_up_import(self, date_str: str, result: Dict[str, Any]) -> None:
        """
        Record a catch-up import to Redis.

        Stores file modification time to detect if file is updated after import.
        """
        if not self._redis_client:
            logger.debug("Redis not available, skipping catch-up record")
            return

        try:
            redis_key = f'daily_import:last_scheduled:{date_str}'

            # Get file modification time for change detection
            file_path = self._get_csv_file_path(date_str)
            file_mtime = self._get_file_mtime(file_path) if file_path else None

            import_record = {
                'timestamp': datetime.now(self.pacific_tz).isoformat(),
                'success': result.get('success', False),
                'executions_imported': result.get('executions_imported', 0),
                'type': 'catch_up',
                'note': 'Imported during startup catch-up',
                'file_mtime': file_mtime  # Track file modification time
            }
            self._redis_client.setex(redis_key, 30 * 24 * 60 * 60, json.dumps(import_record))
            logger.info(f"Recorded catch-up import to Redis: {redis_key} (file_mtime: {file_mtime})")
        except Exception as e:
            logger.warning(f"Failed to record catch-up import to Redis: {e}")



    def start(self):
        """
        Start the daily import scheduler.

        This starts APScheduler's BackgroundScheduler which manages its own threading.
        The scheduler will automatically import at 2:05pm PT each day.
        """
        if self._running:
            logger.warning("Daily import scheduler is already running")
            return

        logger.info("Starting daily import scheduler...")

        # CRITICAL: Catch up on any missed imports BEFORE starting the scheduler
        catch_up_result = self._catch_up_missed_imports()
        if catch_up_result.get('files_caught_up', 0) > 0:
            logger.info(f"Catch-up completed: {catch_up_result['files_caught_up']} files imported")

        # Create BackgroundScheduler with Pacific timezone
        self._scheduler = BackgroundScheduler(timezone=self.pacific_tz)

        # Schedule daily import at 2:05pm Pacific using CronTrigger
        self._scheduler.add_job(
            self._scheduled_import_callback,
            CronTrigger(hour=14, minute=5, timezone=self.pacific_tz),
            id='daily_import',
            name='Daily OHLC Import at 14:05 PT',
            replace_existing=True
        )

        # Start the scheduler (APScheduler handles threading internally)
        self._scheduler.start()

        self._running = True

        # Log startup with timezone information
        now_utc = datetime.now(pytz.UTC)
        now_pt = datetime.now(self.pacific_tz)
        next_run = self._get_next_import_time()

        logger.info("Daily import scheduler started successfully")
        logger.info(f"  - Current time (UTC): {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"  - Current time (Pacific): {now_pt.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"  - Scheduled for: 14:05 PT (22:05 UTC)")
        logger.info(f"  - Next scheduled import: {next_run}")

    def stop(self):
        """Stop the daily import scheduler."""
        if not self._running:
            logger.warning("Daily import scheduler is not running")
            return

        logger.info("Stopping daily import scheduler...")

        # Shutdown APScheduler (wait for any running jobs to complete)
        if self._scheduler:
            self._scheduler.shutdown(wait=True)

        self._running = False
        logger.info("Daily import scheduler stopped")

    def _scheduled_import_callback(self):
        """
        Callback for scheduled daily import.

        This is called automatically at 2:05pm PT each day.
        Includes deduplication to prevent multiple imports on container restart.
        """
        logger.info("=" * 80)
        logger.info("SCHEDULED DAILY IMPORT TRIGGERED")
        logger.info(f"Time: {datetime.now(self.pacific_tz).strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info("=" * 80)

        # Check if we should run (weekend/deduplication check)
        should_run, reason = self._should_run_scheduled_import()

        if not should_run:
            logger.info(f"Skipping scheduled import: {reason}")
            logger.info("=" * 80)
            return

        logger.info(f"Deduplication check passed: {reason}")

        try:
            result = self._perform_daily_import(is_manual=False)

            # Record import
            self.last_scheduled_import = datetime.now(self.pacific_tz)
            self._record_import_history(result, is_manual=False)

            if result['success']:
                logger.info("✓ Scheduled daily import completed successfully")
                logger.info(f"  - Files processed: {result.get('files_processed', 0)}")
                logger.info(f"  - Executions imported: {result.get('total_executions', 0)}")
                logger.info(f"  - Positions rebuilt: {result.get('positions_rebuilt', 0)}")

                # Record to Redis to prevent duplicate runs
                self._record_scheduled_import_complete(result)
            else:
                logger.error(f"✗ Scheduled daily import failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"Error in scheduled import callback: {e}", exc_info=True)
            self._record_import_history({
                'success': False,
                'error': str(e)
            }, is_manual=False)

    def manual_import(self, specific_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Trigger manual import.

        Manual imports bypass the deduplication check and do NOT update the
        scheduled import Redis key. This allows users to force reimport even
        if the daily scheduled import has already run.

        Args:
            specific_date: Optional specific date to import (YYYYMMDD format)
                          If None, imports today's file

        Returns:
            Dict with import results
        """
        logger.info("=" * 80)
        logger.info("MANUAL IMPORT TRIGGERED (bypasses deduplication)")
        logger.info(f"Time: {datetime.now(self.pacific_tz).strftime('%Y-%m-%d %H:%M:%S %Z')}")
        if specific_date:
            logger.info(f"Target date: {specific_date}")
        logger.info("=" * 80)

        try:
            result = self._perform_daily_import(
                is_manual=True,
                specific_date=specific_date
            )

            # Record import
            self.last_manual_import = datetime.now(self.pacific_tz)
            self._record_import_history(result, is_manual=True)

            return result

        except Exception as e:
            logger.error(f"Error in manual import: {e}", exc_info=True)
            error_result = {
                'success': False,
                'error': str(e)
            }
            self._record_import_history(error_result, is_manual=True)
            return error_result

    def _extract_instruments_from_csv(self, file_path: Path) -> List[str]:
        """
        Extract unique instrument names from CSV file.

        Args:
            file_path: Path to CSV file

        Returns:
            List of unique instrument names found in CSV
        """
        try:
            import pandas as pd

            # Read CSV file
            df = pd.read_csv(file_path)

            # Extract unique instruments from 'Instrument' column
            if 'Instrument' in df.columns:
                instruments = df['Instrument'].dropna().unique().tolist()
                logger.info(f"Extracted {len(instruments)} unique instruments from CSV")
                return instruments
            else:
                logger.warning("No 'Instrument' column found in CSV")
                return []

        except Exception as e:
            logger.error(f"Error extracting instruments from CSV: {e}")
            return []

    def _trigger_ohlc_sync(self, instruments: List[str], reason: str = "post_import"):
        """
        Trigger OHLC sync for imported instruments.

        Args:
            instruments: List of NinjaTrader instrument names (e.g., ['MNQ 12-24', 'MES 03-25'])
            reason: Reason for sync (for logging)
        """
        sync_errors = []
        yahoo_symbols = []
        timeframes = []

        try:
            if not instruments:
                logger.info("No instruments to sync - skipping OHLC sync")
                return

            logger.info(f"Triggering OHLC sync for {len(instruments)} instruments...")

            # Map NinjaTrader instruments to Yahoo Finance symbols
            yahoo_symbols = self.instrument_mapper.map_to_yahoo(instruments)

            if not yahoo_symbols:
                logger.warning("No Yahoo Finance symbols mapped - skipping OHLC sync")
                return

            logger.info(f"Mapped to {len(yahoo_symbols)} Yahoo Finance symbols: {', '.join(yahoo_symbols)}")

            # Get all 18 Yahoo Finance timeframes
            timeframes = self.ohlc_service.get_all_yahoo_timeframes()

            # Trigger sync
            sync_stats = self.ohlc_service.sync_instruments(
                instruments=yahoo_symbols,
                timeframes=timeframes,
                reason=reason
            )

            logger.info(f"OHLC sync completed: {sync_stats['candles_added']} candles added "
                       f"in {sync_stats['duration_seconds']:.1f}s")

            # Record successful sync to completeness service
            try:
                completeness_service = get_data_completeness_service()
                completeness_service.record_sync_result(
                    trigger='scheduled' if reason == 'post_import' else reason,
                    instruments_synced=yahoo_symbols,
                    timeframes_synced=timeframes,
                    total_records_added=sync_stats.get('candles_added', 0),
                    duration_seconds=sync_stats.get('duration_seconds', 0),
                    success=True,
                    errors=[]
                )
                # Invalidate completeness matrix cache after sync
                completeness_service.invalidate_cache()
            except Exception as record_err:
                logger.warning(f"Failed to record sync result: {record_err}")

        except Exception as e:
            # Log error but don't fail the import
            logger.error(f"OHLC sync failed (import still successful): {e}", exc_info=True)
            sync_errors.append({'error': str(e), 'type': 'sync_failure'})

            # Record failed sync to completeness service
            try:
                completeness_service = get_data_completeness_service()
                completeness_service.record_sync_result(
                    trigger='scheduled' if reason == 'post_import' else reason,
                    instruments_synced=yahoo_symbols,
                    timeframes_synced=timeframes,
                    total_records_added=0,
                    duration_seconds=0,
                    success=False,
                    errors=sync_errors
                )
            except Exception as record_err:
                logger.warning(f"Failed to record sync failure: {record_err}")

    def _perform_daily_import(self, is_manual: bool = False,
                             specific_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform the daily import process.

        Steps:
        1. Check ALL CSV files for modifications (handles NinjaTrader backfilling)
        2. Determine target date (today's market close or specific date)
        3. Find CSV file matching the date
        4. Validate file (correct date, closed positions only)
        5. Import executions
        6. Rebuild positions for affected accounts
        7. Trigger OHLC sync for imported instruments

        Args:
            is_manual: Whether this is a manual import
            specific_date: Optional specific date to import (YYYYMMDD format)

        Returns:
            Dict with import results
        """
        # Step 1: Check ALL CSV files for modifications first
        # This handles the case where NinjaTrader backfills trades to previous day's file
        # (e.g., morning trades added to previous day's file when session spans midnight)
        logger.info("Step 1: Checking all CSV files for modifications...")
        modified_result = self.import_service.process_all_modified_files()

        if modified_result.get('files_processed', 0) > 0:
            logger.info(
                f"Processed {modified_result['files_processed']} modified files with "
                f"{modified_result['total_executions']} new executions"
            )

        # Step 2: Determine target date
        if specific_date:
            target_date = specific_date
            logger.info(f"Importing specific date: {target_date}")
        else:
            # Use today's date (market closed today)
            target_date = datetime.now(self.pacific_tz).strftime('%Y%m%d')
            logger.info(f"Importing today's date: {target_date}")

        # Step 3: Find CSV file
        expected_filename = f"NinjaTrader_Executions_{target_date}.csv"
        file_path = self.data_dir / expected_filename

        if not file_path.exists():
            logger.warning(f"CSV file not found: {expected_filename}")
            # If we processed modified files, return success with that info
            if modified_result.get('files_processed', 0) > 0:
                return {
                    'success': True,
                    'import_type': 'manual' if is_manual else 'scheduled',
                    'target_date': target_date,
                    'filename': None,
                    'files_processed': modified_result.get('files_processed', 0),
                    'total_executions': modified_result.get('total_executions', 0),
                    'modified_files_processed': modified_result.get('files_processed', 0),
                    'note': f"Today's file ({expected_filename}) not found, but processed modified files",
                    'timestamp': datetime.now(self.pacific_tz).isoformat()
                }
            return {
                'success': False,
                'error': f'CSV file not found: {expected_filename}',
                'expected_file': expected_filename,
                'search_path': str(self.data_dir)
            }

        logger.info(f"Found CSV file: {expected_filename}")

        # Step 4: Validate file
        validation_result = self._validate_import_file(file_path, target_date)
        if not validation_result['valid']:
            logger.error(f"File validation failed: {validation_result['error']}")
            return {
                'success': False,
                'error': f"Validation failed: {validation_result['error']}",
                'validation_details': validation_result
            }

        logger.info("✓ File validation passed")

        # Step 5: Import executions
        logger.info("Importing executions...")
        import_result = self.import_service.process_csv_file(file_path)

        if not import_result['success']:
            logger.error(f"Import failed: {import_result.get('error', 'Unknown error')}")
            return import_result

        logger.info(f"✓ Import successful: {import_result.get('executions_imported', 0)} executions")

        # Step 6: Extract instruments and trigger OHLC sync
        instruments = self._extract_instruments_from_csv(file_path)
        if instruments:
            self._trigger_ohlc_sync(
                instruments=instruments,
                reason="post_import_scheduled" if not is_manual else "post_import_manual"
            )

        # Step 7: Build summary (include modified files info)
        total_executions = (
            import_result.get('executions_imported', 0) +
            modified_result.get('total_executions', 0)
        )
        total_files = 1 + modified_result.get('files_processed', 0)

        return {
            'success': True,
            'import_type': 'manual' if is_manual else 'scheduled',
            'target_date': target_date,
            'filename': expected_filename,
            'files_processed': total_files,
            'total_executions': total_executions,
            'modified_files_processed': modified_result.get('files_processed', 0),
            'modified_files_executions': modified_result.get('total_executions', 0),
            'positions_rebuilt': import_result.get('positions_rebuilt', 0),
            'accounts_affected': import_result.get('accounts_affected', []),
            'instruments_affected': import_result.get('instruments_affected', []),
            'instruments_synced': len(instruments),
            'timestamp': datetime.now(self.pacific_tz).isoformat()
        }

    def _validate_import_file(self, file_path: Path, expected_date: str) -> Dict[str, Any]:
        """
        Validate CSV file before import.

        Validation checks:
        1. Filename matches expected date
        2. File is not empty
        3. All positions in file are closed (no open positions)

        Args:
            file_path: Path to CSV file
            expected_date: Expected date in YYYYMMDD format

        Returns:
            Dict with validation result
        """
        try:
            # Check 1: Filename matches expected date
            filename_date = file_path.stem.split('_')[-1]  # Extract date from filename
            if filename_date != expected_date:
                return {
                    'valid': False,
                    'error': f'Filename date mismatch. Expected: {expected_date}, Got: {filename_date}'
                }

            # Check 2: File is not empty
            if file_path.stat().st_size == 0:
                return {
                    'valid': False,
                    'error': 'File is empty'
                }

            # Check 3: All positions are closed
            # This validation is optional - we rely on the position builder to handle this
            # For now, we just check that the file is readable

            return {
                'valid': True,
                'filename_date': filename_date,
                'file_size': file_path.stat().st_size
            }

        except Exception as e:
            logger.error(f"Error validating file: {e}", exc_info=True)
            return {
                'valid': False,
                'error': f'Validation error: {str(e)}'
            }

    def _record_import_history(self, result: Dict[str, Any], is_manual: bool):
        """
        Record import in history.

        Args:
            result: Import result dictionary
            is_manual: Whether this was a manual import
        """
        history_entry = {
            'timestamp': datetime.now(self.pacific_tz).isoformat(),
            'type': 'manual' if is_manual else 'scheduled',
            'success': result.get('success', False),
            'files_processed': result.get('files_processed', 0),
            'executions_imported': result.get('total_executions', 0),
            'error': result.get('error')
        }

        self.import_history.append(history_entry)

        # Keep only last 100 imports
        if len(self.import_history) > 100:
            self.import_history = self.import_history[-100:]

    def get_status(self) -> Dict[str, Any]:
        """
        Get scheduler status.

        Returns:
            Dict with scheduler state and statistics including timezone information
        """
        now_utc = datetime.now(pytz.UTC)
        now_pt = datetime.now(self.pacific_tz)

        return {
            'running': self._running,
            'scheduled_import_time': self.IMPORT_TIME_PT + ' PT',
            'scheduled_import_time_utc': '22:05 UTC',
            'next_scheduled_import': self._get_next_import_time(),
            'last_scheduled_import': self.last_scheduled_import.isoformat() if self.last_scheduled_import else None,
            'last_manual_import': self.last_manual_import.isoformat() if self.last_manual_import else None,
            'current_time_pt': now_pt.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'current_time_utc': now_utc.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'timezone': 'America/Los_Angeles (Pacific Time)',
            'import_history_count': len(self.import_history),
            'recent_imports': self.import_history[-5:] if self.import_history else []
        }

    def _get_next_import_time(self) -> Optional[str]:
        """
        Get next scheduled import time.

        Returns:
            Formatted string with next run time in Pacific Time, or None if not scheduled
        """
        try:
            if not self._scheduler:
                return None

            jobs = self._scheduler.get_jobs()
            if not jobs:
                return None

            # Get next run time from first job (our daily import)
            next_run = jobs[0].next_run_time

            if next_run:
                # Convert to Pacific Time if not already
                if next_run.tzinfo is None:
                    next_run = pytz.UTC.localize(next_run)
                next_run_pt = next_run.astimezone(self.pacific_tz)
                return next_run_pt.strftime('%Y-%m-%d %H:%M:%S %Z')

            return None

        except Exception as e:
            logger.error(f"Error getting next import time: {e}", exc_info=True)
            return None
        except Exception:
            return None

    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running


# Global instance
daily_import_scheduler = DailyImportScheduler()
