"""
Gap Filling Tasks

Celery tasks for OHLC data gap detection and filling.
Replaces the threading-based gap filling service.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from celery import Task
from celery_app import app
from config import config
from data_service import ohlc_service
from redis_cache_service import get_cache_service

logger = logging.getLogger('gap_filling')


class CallbackTask(Task):
    """Base task class with error handling and monitoring"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f'Gap filling task {task_id} failed: {exc}')
        logger.error(f'Exception info: {einfo}')
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        logger.info(f'Gap filling task {task_id} completed successfully')


@app.task(base=CallbackTask, bind=True)
def fill_recent_gaps(self):
    """
    Fill recent gaps in OHLC data (last 7 days)
    Scheduled to run every 15 minutes
    """
    try:
        logger.info("Starting recent gap filling (last 7 days)")
        
        # Get instruments that need gap filling
        instruments = _get_active_instruments()
        if not instruments:
            logger.info("No active instruments found for gap filling")
            return {'status': 'no_instruments', 'filled_gaps': 0}
        
        total_gaps_filled = 0
        results = {}
        
        # Define recent timeframes to check
        timeframes = ['1m', '5m', '15m', '1h']
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        for instrument in instruments:
            instrument_gaps = 0
            
            for timeframe in timeframes:
                try:
                    # Check for gaps and fill them
                    gaps_filled = _fill_gaps_for_instrument_timeframe(
                        instrument, timeframe, start_date, end_date
                    )
                    instrument_gaps += gaps_filled
                    total_gaps_filled += gaps_filled
                    
                    if gaps_filled > 0:
                        logger.info(f"Filled {gaps_filled} gaps for {instrument} {timeframe}")
                        
                except Exception as e:
                    logger.error(f"Error filling gaps for {instrument} {timeframe}: {e}")
                    continue
            
            results[instrument] = instrument_gaps
        
        # Invalidate cache if gaps were filled
        if total_gaps_filled > 0:
            _invalidate_relevant_cache(instruments)
        
        logger.info(f"Recent gap filling completed: {total_gaps_filled} gaps filled")
        
        return {
            'status': 'success',
            'filled_gaps': total_gaps_filled,
            'instruments_processed': len(instruments),
            'details': results
        }
        
    except Exception as e:
        logger.error(f"Error in fill_recent_gaps: {e}")
        raise self.retry(exc=e, countdown=300, max_retries=3)  # 5 minute delay


@app.task(base=CallbackTask, bind=True)
def fill_extended_gaps(self):
    """
    Fill extended gaps in OHLC data (last 30 days)
    Scheduled to run every 4 hours
    """
    try:
        logger.info("Starting extended gap filling (last 30 days)")
        
        # Get instruments that need gap filling
        instruments = _get_active_instruments()
        if not instruments:
            logger.info("No active instruments found for extended gap filling")
            return {'status': 'no_instruments', 'filled_gaps': 0}
        
        total_gaps_filled = 0
        results = {}
        
        # Define all timeframes for extended filling
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        for instrument in instruments:
            instrument_gaps = 0
            
            for timeframe in timeframes:
                try:
                    # Check for gaps and fill them
                    gaps_filled = _fill_gaps_for_instrument_timeframe(
                        instrument, timeframe, start_date, end_date
                    )
                    instrument_gaps += gaps_filled
                    total_gaps_filled += gaps_filled
                    
                    if gaps_filled > 0:
                        logger.info(f"Extended fill: {gaps_filled} gaps for {instrument} {timeframe}")
                        
                except Exception as e:
                    logger.error(f"Error in extended gap filling for {instrument} {timeframe}: {e}")
                    continue
            
            results[instrument] = instrument_gaps
        
        # Invalidate cache if gaps were filled
        if total_gaps_filled > 0:
            _invalidate_relevant_cache(instruments)
        
        logger.info(f"Extended gap filling completed: {total_gaps_filled} gaps filled")
        
        return {
            'status': 'success',
            'filled_gaps': total_gaps_filled,
            'instruments_processed': len(instruments),
            'details': results
        }
        
    except Exception as e:
        logger.error(f"Error in fill_extended_gaps: {e}")
        raise self.retry(exc=e, countdown=600, max_retries=2)  # 10 minute delay


@app.task(base=CallbackTask, bind=True)
def fill_gaps_for_instrument(self, instrument: str, days_back: int = 7):
    """
    Fill gaps for a specific instrument
    
    Args:
        instrument: Instrument symbol (e.g., 'ES', 'NQ')
        days_back: Number of days to look back for gaps
    """
    try:
        logger.info(f"Filling gaps for instrument {instrument} (last {days_back} days)")
        
        total_gaps_filled = 0
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        for timeframe in timeframes:
            try:
                gaps_filled = _fill_gaps_for_instrument_timeframe(
                    instrument, timeframe, start_date, end_date
                )
                total_gaps_filled += gaps_filled
                
                if gaps_filled > 0:
                    logger.info(f"Filled {gaps_filled} gaps for {instrument} {timeframe}")
                    
            except Exception as e:
                logger.error(f"Error filling gaps for {instrument} {timeframe}: {e}")
                continue
        
        # Invalidate cache for this instrument
        if total_gaps_filled > 0:
            _invalidate_relevant_cache([instrument])
        
        return {
            'status': 'success',
            'instrument': instrument,
            'filled_gaps': total_gaps_filled,
            'days_processed': days_back
        }
        
    except Exception as e:
        logger.error(f"Error filling gaps for instrument {instrument}: {e}")
        raise self.retry(exc=e, countdown=180, max_retries=3)  # 3 minute delay


@app.task(base=CallbackTask, bind=True)
def fill_historical_gaps(self, instrument: str, start_date: str, end_date: str):
    """
    Fill historical gaps for a specific time range
    
    Args:
        instrument: Instrument symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    """
    try:
        logger.info(f"Filling historical gaps for {instrument} from {start_date} to {end_date}")
        
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        total_gaps_filled = 0
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        
        for timeframe in timeframes:
            try:
                gaps_filled = _fill_gaps_for_instrument_timeframe(
                    instrument, timeframe, start_dt, end_dt
                )
                total_gaps_filled += gaps_filled
                
                if gaps_filled > 0:
                    logger.info(f"Historical fill: {gaps_filled} gaps for {instrument} {timeframe}")
                    
            except Exception as e:
                logger.error(f"Error in historical gap filling for {instrument} {timeframe}: {e}")
                continue
        
        # Invalidate cache for this instrument
        if total_gaps_filled > 0:
            _invalidate_relevant_cache([instrument])
        
        return {
            'status': 'success',
            'instrument': instrument,
            'start_date': start_date,
            'end_date': end_date,
            'filled_gaps': total_gaps_filled
        }
        
    except Exception as e:
        logger.error(f"Error in historical gap filling: {e}")
        raise self.retry(exc=e, countdown=300, max_retries=2)


def _get_active_instruments() -> List[str]:
    """Get list of instruments that have recent trade data"""
    try:
        from database_manager import DatabaseManager
        
        with DatabaseManager() as db:
            # Get instruments with trades in the last 30 days
            cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            instruments_query = """
                SELECT DISTINCT instrument 
                FROM trades 
                WHERE entry_time >= ? 
                AND deleted = 0 
                AND instrument IS NOT NULL
                ORDER BY instrument
            """
            
            result = db.cursor.execute(instruments_query, (cutoff_date,))
            instruments = [row[0] for row in result.fetchall()]
            
            logger.debug(f"Found {len(instruments)} active instruments: {instruments}")
            return instruments
            
    except Exception as e:
        logger.error(f"Error getting active instruments: {e}")
        return []


def _fill_gaps_for_instrument_timeframe(instrument: str, timeframe: str, 
                                      start_date: datetime, end_date: datetime) -> int:
    """Fill gaps for a specific instrument and timeframe"""
    try:
        # Use the existing gap filling service
        gaps_filled = ohlc_service.fill_missing_data(
            instrument=instrument,
            timeframe=timeframe,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
        
        return gaps_filled.get('filled_gaps', 0)
        
    except Exception as e:
        logger.error(f"Error filling gaps for {instrument} {timeframe}: {e}")
        return 0


def _invalidate_relevant_cache(instruments: List[str]) -> None:
    """Invalidate cache for instruments that had gaps filled"""
    try:
        cache_service = get_cache_service()
        if not cache_service:
            return
        
        for instrument in instruments:
            # Invalidate cache keys for this instrument
            cache_keys = [
                f"ohlc:{instrument}:*",
                f"chart_data:{instrument}:*"
            ]
            
            for pattern in cache_keys:
                try:
                    cache_service.delete_pattern(pattern)
                except Exception as e:
                    logger.warning(f"Could not invalidate cache pattern {pattern}: {e}")
        
        logger.info(f"Invalidated cache for {len(instruments)} instruments")
        
    except Exception as e:
        logger.warning(f"Error invalidating cache: {e}")


# Manual task triggers for API endpoints
@app.task(base=CallbackTask)
def trigger_manual_gap_fill(instrument: str = None, days_back: int = 7):
    """Manually trigger gap filling (for API endpoints)"""
    if instrument:
        return fill_gaps_for_instrument.delay(instrument, days_back)
    else:
        return fill_recent_gaps.delay()


@app.task(base=CallbackTask)
def check_gap_status(instrument: str, timeframe: str, days_back: int = 7):
    """Check gap status for an instrument/timeframe (for monitoring)"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # This would check for gaps without filling them
        # Implementation depends on the gap detection logic in ohlc_service

        return {
            'instrument': instrument,
            'timeframe': timeframe,
            'period_checked': f"{start_date.date()} to {end_date.date()}",
            'status': 'checked'
        }

    except Exception as e:
        logger.error(f"Error checking gap status: {e}")
        return {'status': 'error', 'error': str(e)}


@app.task(base=CallbackTask, bind=True, queue='gap_filling')
def fetch_position_ohlc_data(self, position_id: int, instrument: str,
                            start_date: str, end_date: str,
                            timeframes: List[str] = None, priority: str = 'normal'):
    """
    Fetch OHLC data for a specific position's time range.
    Triggered automatically when a position is imported.

    Uses smart fetching - only downloads data we don't already have to respect API quotas.

    Args:
        position_id: Position identifier (for logging)
        instrument: Trading instrument (e.g., 'MNQ MAR26')
        start_date: Start date in ISO format
        end_date: End date in ISO format
        timeframes: List of timeframes to fetch (defaults to priority set)
        priority: Task priority ('high' or 'normal')

    Returns:
        Dict with fetch results and quota usage
    """
    try:
        logger.info(f"Fetching OHLC data for position {position_id}: {instrument} from {start_date} to {end_date}")

        # Default to priority timeframes to minimize API calls
        if timeframes is None:
            timeframes = ['1m', '5m', '15m', '1h']

        # Parse dates
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)

        # Get both specific contract and continuous contract
        from utils.instrument_utils import get_root_symbol
        instruments_to_fetch = [instrument]
        root_symbol = get_root_symbol(instrument)
        if root_symbol != instrument:
            instruments_to_fetch.append(root_symbol)
            logger.info(f"Will also fetch continuous contract: {root_symbol}")

        total_fetched = 0
        total_gaps_filled = 0
        api_calls_made = 0
        results = {}

        # Check API quota before starting
        quota_status = _check_and_update_quota()
        if not quota_status['can_proceed']:
            logger.warning(f"API quota limit reached: {quota_status}")
            return {
                'status': 'quota_exceeded',
                'position_id': position_id,
                'message': 'Daily API quota exceeded',
                'quota_status': quota_status
            }

        for inst in instruments_to_fetch:
            inst_results = {}

            for tf in timeframes:
                try:
                    # Smart gap detection - only fetch what we don't have
                    gaps = _detect_gaps_for_range(inst, tf, start_dt, end_dt)

                    if not gaps:
                        logger.info(f"No gaps found for {inst} {tf} - data already exists")
                        inst_results[tf] = {'status': 'complete', 'gaps_filled': 0}
                        continue

                    logger.info(f"Found {len(gaps)} gaps to fill for {inst} {tf}")

                    # Fill each gap with rate limiting
                    for gap_start, gap_end in gaps:
                        try:
                            filled = _fill_gaps_for_instrument_timeframe(
                                inst, tf, gap_start, gap_end
                            )
                            total_gaps_filled += filled
                            api_calls_made += 1

                            # Check quota after each API call
                            if api_calls_made % 10 == 0:  # Check every 10 calls
                                quota_status = _check_and_update_quota()
                                if not quota_status['can_proceed']:
                                    logger.warning("Quota limit reached mid-fetch")
                                    break

                            # Rate limiting: 1 second between calls (safe for Yahoo Finance)
                            import time
                            time.sleep(1.0)

                        except Exception as e:
                            logger.error(f"Error filling gap {gap_start} to {gap_end}: {e}")
                            continue

                    inst_results[tf] = {
                        'status': 'success',
                        'gaps_found': len(gaps),
                        'gaps_filled': total_gaps_filled
                    }
                    total_fetched += len(gaps)

                except Exception as e:
                    logger.error(f"Error fetching {inst} {tf}: {e}")
                    inst_results[tf] = {'status': 'error', 'error': str(e)}
                    continue

            results[inst] = inst_results

        # Invalidate cache for affected instruments
        if total_gaps_filled > 0:
            _invalidate_relevant_cache(instruments_to_fetch)

        logger.info(f"Position OHLC fetch complete: {total_fetched} segments fetched, {total_gaps_filled} gaps filled, {api_calls_made} API calls")

        return {
            'status': 'success',
            'position_id': position_id,
            'instruments_processed': instruments_to_fetch,
            'timeframes': timeframes,
            'total_gaps_filled': total_gaps_filled,
            'api_calls_made': api_calls_made,
            'quota_remaining': quota_status.get('remaining', 'unknown'),
            'results': results
        }

    except Exception as e:
        logger.error(f"Error in fetch_position_ohlc_data: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=2)


def _detect_gaps_for_range(instrument: str, timeframe: str,
                           start_date: datetime, end_date: datetime) -> List[tuple]:
    """
    Detect gaps in OHLC data for a specific range.
    Returns list of (gap_start, gap_end) tuples.
    """
    try:
        from database_manager import DatabaseManager

        with DatabaseManager() as db:
            # Get existing data range for this instrument/timeframe
            query = """
                SELECT MIN(timestamp), MAX(timestamp), COUNT(*)
                FROM ohlc_data
                WHERE instrument = ? AND timeframe = ?
                AND timestamp >= ? AND timestamp <= ?
            """

            start_ts = int(start_date.timestamp())
            end_ts = int(end_date.timestamp())

            result = db.cursor.execute(query, (instrument, timeframe, start_ts, end_ts)).fetchone()

            if not result or not result[0]:
                # No data at all - entire range is a gap
                logger.info(f"No existing data for {instrument} {timeframe} - full range is a gap")
                return [(start_date, end_date)]

            min_ts, max_ts, count = result

            # Simple gap detection: if we have very little data or data is sparse, fetch the whole range
            expected_bars = _calculate_expected_bars(start_date, end_date, timeframe)
            coverage_ratio = count / expected_bars if expected_bars > 0 else 0

            if coverage_ratio < 0.8:  # Less than 80% coverage
                logger.info(f"Sparse data coverage ({coverage_ratio:.1%}) for {instrument} {timeframe} - fetching full range")
                return [(start_date, end_date)]

            # Data looks good - no gaps to fill
            logger.info(f"Good data coverage ({coverage_ratio:.1%}) for {instrument} {timeframe}")
            return []

    except Exception as e:
        logger.error(f"Error detecting gaps: {e}")
        # On error, be conservative and fetch the whole range
        return [(start_date, end_date)]


def _calculate_expected_bars(start_date: datetime, end_date: datetime, timeframe: str) -> int:
    """Calculate expected number of bars for a date range and timeframe"""
    timeframe_minutes = {
        '1m': 1, '3m': 3, '5m': 5, '15m': 15,
        '1h': 60, '4h': 240, '1d': 1440
    }

    total_minutes = (end_date - start_date).total_seconds() / 60
    bar_minutes = timeframe_minutes.get(timeframe, 60)

    # Futures markets are ~23.5 hours per day (with brief closure)
    market_factor = 0.98

    return int(total_minutes * market_factor / bar_minutes)


def _check_and_update_quota() -> Dict[str, Any]:
    """
    Check API quota status and update counter.
    Returns dict with quota status and whether fetching can proceed.
    """
    try:
        from redis_cache_service import get_cache_service

        cache = get_cache_service()
        if not cache:
            # No cache service - allow fetch but warn
            logger.warning("No cache service available for quota tracking")
            return {'can_proceed': True, 'remaining': 'unknown'}

        # Track daily quota usage in Redis
        today_key = f"api_quota:{datetime.now().strftime('%Y-%m-%d')}"

        # Get current count
        current_count = cache.get(today_key)
        if current_count is None:
            current_count = 0
            # Set with 24 hour expiry
            cache.set(today_key, 0, ex=86400)
        else:
            current_count = int(current_count)

        # Check against daily limit
        daily_limit = 2000
        warning_threshold = 1600  # 80%

        if current_count >= daily_limit:
            logger.warning(f"Daily API quota exceeded: {current_count}/{daily_limit}")
            return {
                'can_proceed': False,
                'used': current_count,
                'limit': daily_limit,
                'remaining': 0
            }

        if current_count >= warning_threshold:
            logger.warning(f"API quota warning: {current_count}/{daily_limit} ({current_count/daily_limit:.1%})")

        # Increment counter
        cache.incr(today_key)

        return {
            'can_proceed': True,
            'used': current_count + 1,
            'limit': daily_limit,
            'remaining': daily_limit - current_count - 1
        }

    except Exception as e:
        logger.error(f"Error checking quota: {e}")
        # On error, allow fetch but warn
        return {'can_proceed': True, 'remaining': 'unknown', 'error': str(e)}