"""
Data Completeness Service for OHLC Data Monitoring
Provides gap detection, completeness matrix, and data freshness tracking
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from scripts.TradingLog_db import FuturesDB
from services.redis_cache_service import get_cache_service
from config import config

logger = logging.getLogger(__name__)


class DataCompletenessService:
    """Service for monitoring OHLC data completeness and detecting gaps"""

    # Instruments to monitor (base symbols)
    INSTRUMENTS = ['ES', 'MNQ', 'NQ', 'YM', 'RTY', 'CL', 'GC']

    # Priority timeframes to monitor
    PRIORITY_TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d']

    # Expected minimum record counts based on Yahoo Finance limits
    # These are approximate values for data that should be available
    EXPECTED_MINIMUMS = {
        '1m': 2730,    # 7 days * 390 bars/day (6.5 hours * 60 mins)
        '5m': 4680,    # 60 days * 78 bars/day
        '15m': 1560,   # 60 days * 26 bars/day
        '1h': 2372,    # 365 days * 6.5 bars/day
        '4h': 584,     # 365 days * 1.6 bars/day
        '1d': 365,     # 365 days * 1 bar/day
    }

    # Freshness thresholds in hours - data older than this is considered stale
    FRESHNESS_THRESHOLDS_HOURS = {
        '1m': 24,      # 1-minute data stale after 24 hours
        '5m': 48,      # 5-minute data stale after 48 hours
        '15m': 72,     # 15-minute data stale after 72 hours
        '1h': 72,      # 1-hour data stale after 72 hours
        '4h': 168,     # 4-hour data stale after 7 days
        '1d': 168,     # Daily data stale after 7 days
    }

    # Cache TTL in seconds (5 minutes)
    CACHE_TTL = 300

    def __init__(self):
        """Initialize the service with cache connection (DB accessed via context manager)"""
        self.cache_service = get_cache_service()

    def _get_db_connection(self) -> FuturesDB:
        """Get a database connection (must be used as context manager)"""
        return FuturesDB()

    def _get_cache_key(self) -> str:
        """Generate cache key for completeness matrix"""
        return "data_completeness:matrix"

    def _calculate_freshness_status(self, timeframe: str, last_timestamp: Optional[int]) -> str:
        """Calculate freshness status based on data age

        Args:
            timeframe: The timeframe to check
            last_timestamp: Unix timestamp of most recent data

        Returns:
            'fresh', 'stale', or 'missing'
        """
        if last_timestamp is None:
            return 'missing'

        threshold_hours = self.FRESHNESS_THRESHOLDS_HOURS.get(timeframe, 72)
        threshold_timestamp = datetime.now() - timedelta(hours=threshold_hours)

        data_datetime = datetime.fromtimestamp(last_timestamp)

        if data_datetime >= threshold_timestamp:
            return 'fresh'
        else:
            return 'stale'

    def _calculate_completeness_pct(self, record_count: int, timeframe: str) -> float:
        """Calculate completeness percentage based on expected minimum

        Args:
            record_count: Actual number of records
            timeframe: The timeframe to check

        Returns:
            Percentage of expected minimum (can exceed 100%)
        """
        expected = self.EXPECTED_MINIMUMS.get(timeframe, 1000)
        if expected == 0:
            return 100.0

        return round((record_count / expected) * 100, 1)

    def _determine_status(self, record_count: int, timeframe: str) -> str:
        """Determine status based on record count vs expected minimum

        Args:
            record_count: Actual number of records
            timeframe: The timeframe to check

        Returns:
            'complete', 'partial', or 'missing'
        """
        if record_count == 0:
            return 'missing'

        expected = self.EXPECTED_MINIMUMS.get(timeframe, 1000)
        percentage = (record_count / expected) * 100

        if percentage >= 100:
            return 'complete'
        else:
            return 'partial'

    def _calculate_data_age_hours(self, last_timestamp: Optional[int]) -> Optional[float]:
        """Calculate data age in hours

        Args:
            last_timestamp: Unix timestamp of most recent data

        Returns:
            Age in hours, or None if no timestamp
        """
        if last_timestamp is None:
            return None

        data_datetime = datetime.fromtimestamp(last_timestamp)
        age = datetime.now() - data_datetime
        return round(age.total_seconds() / 3600, 1)

    def get_completeness_matrix(self, bypass_cache: bool = False) -> Dict[str, Any]:
        """Get completeness matrix for all instruments and timeframes

        Args:
            bypass_cache: If True, skip cache and query database directly

        Returns:
            Dictionary with 'matrix' and 'summary' keys
        """
        # Try to get from cache first
        if not bypass_cache and self.cache_service and self.cache_service.redis_client:
            try:
                cached = self.cache_service.redis_client.get(self._get_cache_key())
                if cached:
                    logger.debug("Returning cached completeness matrix")
                    result = json.loads(cached)
                    result['cached'] = True
                    return result
            except Exception as e:
                logger.warning(f"Cache read failed: {e}")

        # Query database for all counts in single batch query
        rows = []
        try:
            with self._get_db_connection() as db:
                db.cursor.execute("""
                    SELECT instrument, timeframe, COUNT(*) as count, MAX(timestamp) as latest
                    FROM ohlc_data
                    WHERE instrument IN (?, ?, ?, ?, ?, ?, ?)
                    AND timeframe IN (?, ?, ?, ?, ?, ?)
                    GROUP BY instrument, timeframe
                """, (*self.INSTRUMENTS, *self.PRIORITY_TIMEFRAMES))

                rows = db.cursor.fetchall()
        except Exception as e:
            logger.error(f"Database query failed: {e}")

        # Build lookup from query results
        data_lookup = {}
        for row in rows:
            instrument, timeframe, count, latest = row
            if instrument not in data_lookup:
                data_lookup[instrument] = {}
            data_lookup[instrument][timeframe] = {
                'count': count,
                'latest': latest
            }

        # Build complete matrix with all instruments/timeframes
        matrix = {}
        complete_count = 0
        partial_count = 0
        missing_count = 0

        for instrument in self.INSTRUMENTS:
            matrix[instrument] = {}
            for timeframe in self.PRIORITY_TIMEFRAMES:
                # Get data from lookup or default to zeros
                data = data_lookup.get(instrument, {}).get(timeframe, {'count': 0, 'latest': None})
                record_count = data['count']
                last_timestamp = data['latest']

                status = self._determine_status(record_count, timeframe)
                freshness = self._calculate_freshness_status(timeframe, last_timestamp)

                matrix[instrument][timeframe] = {
                    'record_count': record_count,
                    'expected_minimum': self.EXPECTED_MINIMUMS.get(timeframe, 0),
                    'completeness_pct': self._calculate_completeness_pct(record_count, timeframe),
                    'status': status,
                    'last_timestamp': datetime.fromtimestamp(last_timestamp).isoformat() if last_timestamp else None,
                    'data_age_hours': self._calculate_data_age_hours(last_timestamp),
                    'freshness_status': freshness
                }

                # Update counters
                if status == 'complete':
                    complete_count += 1
                elif status == 'partial':
                    partial_count += 1
                else:
                    missing_count += 1

        total_cells = len(self.INSTRUMENTS) * len(self.PRIORITY_TIMEFRAMES)
        health_score = round((complete_count / total_cells) * 100, 1) if total_cells > 0 else 0

        result = {
            'matrix': matrix,
            'summary': {
                'total_cells': total_cells,
                'complete_cells': complete_count,
                'partial_cells': partial_count,
                'missing_cells': missing_count,
                'health_score': health_score,
                'last_updated': datetime.now().isoformat(),
                'instruments': self.INSTRUMENTS,
                'timeframes': self.PRIORITY_TIMEFRAMES
            },
            'cached': False
        }

        # Cache the result
        if self.cache_service and self.cache_service.redis_client:
            try:
                self.cache_service.redis_client.setex(
                    self._get_cache_key(),
                    self.CACHE_TTL,
                    json.dumps(result, default=str)
                )
                logger.debug(f"Cached completeness matrix for {self.CACHE_TTL}s")
            except Exception as e:
                logger.warning(f"Cache write failed: {e}")

        return result

    def get_gap_details(self, instrument: str, timeframe: str) -> Dict[str, Any]:
        """Get detailed gap analysis for a specific instrument/timeframe

        Args:
            instrument: Base instrument symbol (e.g., 'ES')
            timeframe: Timeframe string (e.g., '15m')

        Returns:
            Dictionary with detailed gap analysis
        """
        # Validate inputs
        if instrument not in self.INSTRUMENTS:
            return {
                'error': f"Invalid instrument: {instrument}",
                'status': 'invalid',
                'valid_instruments': self.INSTRUMENTS
            }

        if timeframe not in self.PRIORITY_TIMEFRAMES:
            return {
                'error': f"Invalid timeframe: {timeframe}",
                'status': 'invalid',
                'valid_timeframes': self.PRIORITY_TIMEFRAMES
            }

        # Query for details
        try:
            with self._get_db_connection() as db:
                db.cursor.execute("""
                    SELECT COUNT(*) as count, MAX(timestamp) as latest, MIN(timestamp) as earliest
                    FROM ohlc_data
                    WHERE instrument = ? AND timeframe = ?
                """, (instrument, timeframe))

                row = db.cursor.fetchone()
                record_count = row[0] if row else 0
                latest_timestamp = row[1] if row else None
                earliest_timestamp = row[2] if row else None
        except Exception as e:
            logger.error(f"Database query failed for gap details: {e}")
            return {
                'error': str(e),
                'status': 'error'
            }

        status = self._determine_status(record_count, timeframe)
        expected_minimum = self.EXPECTED_MINIMUMS.get(timeframe, 0)

        # Calculate expected date range based on Yahoo Finance limits
        historical_days = {
            '1m': 7,
            '5m': 60,
            '15m': 60,
            '1h': 365,
            '4h': 365,
            '1d': 365
        }
        days_back = historical_days.get(timeframe, 60)
        expected_start = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        expected_end = datetime.now().strftime('%Y-%m-%d')

        return {
            'instrument': instrument,
            'timeframe': timeframe,
            'record_count': record_count,
            'expected_minimum': expected_minimum,
            'completeness_pct': self._calculate_completeness_pct(record_count, timeframe),
            'status': status,
            'freshness_status': self._calculate_freshness_status(timeframe, latest_timestamp),
            'data_age_hours': self._calculate_data_age_hours(latest_timestamp),
            'date_range': {
                'earliest': datetime.fromtimestamp(earliest_timestamp).isoformat() if earliest_timestamp else None,
                'latest': datetime.fromtimestamp(latest_timestamp).isoformat() if latest_timestamp else None,
                'expected_start': expected_start,
                'expected_end': expected_end
            },
            'repair_available': True,
            'yahoo_symbol': f"{instrument}=F"
        }

    def invalidate_cache(self):
        """Invalidate the cached completeness matrix"""
        if self.cache_service and self.cache_service.redis_client:
            try:
                self.cache_service.redis_client.delete(self._get_cache_key())
                logger.info("Completeness matrix cache invalidated")
            except Exception as e:
                logger.warning(f"Cache invalidation failed: {e}")

    # ========== Sync Health Tracking ==========

    # Maximum sync history entries to keep (approx 100 entries = ~14 days at 7 syncs/day)
    MAX_SYNC_HISTORY_ENTRIES = 100

    # Sync history TTL in seconds (7 days)
    SYNC_HISTORY_TTL = 7 * 24 * 60 * 60

    def _get_sync_history_key(self) -> str:
        """Generate cache key for sync history"""
        return "data_completeness:sync_history"

    def record_sync_result(self, trigger: str, instruments_synced: List[str],
                          timeframes_synced: List[str], total_records_added: int,
                          duration_seconds: float, success: bool,
                          errors: List[Dict[str, Any]]) -> bool:
        """Record a sync result to the history

        Args:
            trigger: What triggered the sync ('scheduled', 'manual', 'repair')
            instruments_synced: List of instrument symbols that were synced
            timeframes_synced: List of timeframes that were synced
            total_records_added: Total number of OHLC records added
            duration_seconds: How long the sync took
            success: Whether the sync was successful overall
            errors: List of error details for any failures

        Returns:
            True if recorded successfully, False otherwise
        """
        if not self.cache_service or not self.cache_service.redis_client:
            logger.warning("Cannot record sync result: cache service unavailable")
            return False

        try:
            sync_record = {
                'timestamp': datetime.now().isoformat(),
                'trigger': trigger,
                'instruments_synced': len(instruments_synced) if isinstance(instruments_synced, list) else instruments_synced,
                'instruments_list': instruments_synced[:10] if isinstance(instruments_synced, list) else [],  # Store first 10
                'timeframes_synced': len(timeframes_synced) if isinstance(timeframes_synced, list) else timeframes_synced,
                'timeframes_list': timeframes_synced,
                'total_records_added': total_records_added,
                'duration_seconds': round(duration_seconds, 2),
                'success': success,
                'errors': errors[:10] if errors else []  # Store first 10 errors
            }

            # Push to front of list (most recent first)
            self.cache_service.redis_client.lpush(
                self._get_sync_history_key(),
                json.dumps(sync_record, default=str)
            )

            # Trim list to max entries
            self.cache_service.redis_client.ltrim(
                self._get_sync_history_key(),
                0,
                self.MAX_SYNC_HISTORY_ENTRIES - 1
            )

            # Set expiry on the list
            self.cache_service.redis_client.expire(
                self._get_sync_history_key(),
                self.SYNC_HISTORY_TTL
            )

            logger.debug(f"Recorded sync result: trigger={trigger}, success={success}, records={total_records_added}")
            return True

        except Exception as e:
            logger.error(f"Failed to record sync result: {e}")
            return False

    def get_sync_health_history(self, days: int = 7) -> Dict[str, Any]:
        """Get sync health history for the specified number of days

        Args:
            days: Number of days of history to retrieve (max 30)

        Returns:
            Dictionary with 'history' list and 'summary' stats
        """
        days = min(days, 30)  # Cap at 30 days

        if not self.cache_service or not self.cache_service.redis_client:
            return {
                'history': [],
                'summary': {
                    'total_syncs': 0,
                    'successful_syncs': 0,
                    'failed_syncs': 0,
                    'success_rate': 0,
                    'avg_records_per_sync': 0
                },
                'error': 'Cache service unavailable'
            }

        try:
            # Get all history entries (we'll filter by date client-side)
            raw_history = self.cache_service.redis_client.lrange(
                self._get_sync_history_key(),
                0,
                -1  # Get all entries
            )

            # Parse and filter by date
            cutoff_date = datetime.now() - timedelta(days=days)
            history = []
            total_records = 0
            successful_count = 0
            failed_count = 0

            for raw_entry in raw_history:
                try:
                    entry = json.loads(raw_entry)
                    entry_date = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00').split('+')[0])

                    if entry_date >= cutoff_date:
                        history.append(entry)
                        total_records += entry.get('total_records_added', 0)
                        if entry.get('success', False):
                            successful_count += 1
                        else:
                            failed_count += 1
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning(f"Failed to parse sync history entry: {e}")
                    continue

            total_syncs = successful_count + failed_count
            success_rate = round((successful_count / total_syncs) * 100, 1) if total_syncs > 0 else 0
            avg_records = round(total_records / total_syncs, 1) if total_syncs > 0 else 0

            return {
                'history': history,
                'summary': {
                    'total_syncs': total_syncs,
                    'successful_syncs': successful_count,
                    'failed_syncs': failed_count,
                    'success_rate': success_rate,
                    'avg_records_per_sync': avg_records,
                    'days_included': days
                }
            }

        except Exception as e:
            logger.error(f"Failed to get sync health history: {e}")
            return {
                'history': [],
                'summary': {
                    'total_syncs': 0,
                    'successful_syncs': 0,
                    'failed_syncs': 0,
                    'success_rate': 0,
                    'avg_records_per_sync': 0
                },
                'error': str(e)
            }


# Singleton instance
_service_instance = None


def get_data_completeness_service() -> DataCompletenessService:
    """Get or create singleton instance of DataCompletenessService"""
    global _service_instance
    if _service_instance is None:
        _service_instance = DataCompletenessService()
    return _service_instance
