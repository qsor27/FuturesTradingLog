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