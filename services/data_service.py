"""
OHLC Data Service for Futures Trading Log
Handles fetching, caching, and gap detection for market data
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
from typing import List, Dict, Tuple, Optional
import logging
from scripts.TradingLog_db import FuturesDB
from config import config, YAHOO_FINANCE_CONFIG
from services.redis_cache_service import get_cache_service
from services.symbol_service import symbol_service
from services.error_handling import CircuitBreaker, RateLimitError, NetworkError, DataQualityError, InvalidSymbolError
import redis

class BatchOptimizedRateLimiter:
    """Intelligent rate limiting for batch-optimized Yahoo Finance API requests"""
    
    def __init__(self, cache_service, yahoo_config):
        self.logger = logging.getLogger(__name__)
        self.cache_service = cache_service
        self.config = yahoo_config.get('rate_limiting', {})
        self.batch_config = yahoo_config.get('batch_processing', {})
        
        from config import config as main_config
        self.redis_client = redis.from_url(main_config.redis_url)
        self.success_key = "rate_limiter:success_window"
        self.failure_key = "rate_limiter:failure_window"
        self.window_size = self.config.get('success_window', 100)
        
        self.max_concurrent_requests = self.batch_config.get('max_concurrent_instruments', 3)
        self.endpoint_delays = {}

    def _update_window(self, key: str, event_time: float):
        """Add event to sliding window and remove old entries in Redis"""
        pipeline = self.redis_client.pipeline()
        pipeline.lpush(key, event_time)
        pipeline.ltrim(key, 0, self.window_size - 1)
        pipeline.expire(key, 60)  # 1-minute window
        pipeline.execute()

    def register_success(self):
        self._update_window(self.success_key, time.time())

    def register_failure(self):
        self._update_window(self.failure_key, time.time())

    def get_current_delay(self) -> float:
        """Calculate adaptive delay based on recent success/failure rates"""
        if not self.config.get('adaptive_enabled', False):
            return self.config.get('base_delay', 2.5)

        success_count = self.redis_client.llen(self.success_key)
        failure_count = self.redis_client.llen(self.failure_key)
        total_requests = success_count + failure_count

        if total_requests < 10: # Not enough data for adaptive delay
            return self.config.get('base_delay', 2.5)

        failure_rate = failure_count / total_requests
        
        if failure_rate > self.config.get('failure_threshold', 0.1):
            return min(self.config.get('max_delay', 30.0), self.config.get('base_delay', 2.5) * (1 + failure_rate * 10))
        else:
            return self.config.get('base_delay', 2.5)

    def enforce(self):
        """Enforce rate limit delay"""
        delay = self.get_current_delay()
        time.sleep(delay)

    def validate_cache_first(self, instrument: str, timeframes: List[str]) -> Tuple[List[str], Dict[str, List[Dict]]]:
        """Check cache for multiple timeframes to minimize API calls"""
        if not self.cache_service:
            return timeframes, {}
        
        cached_data = {}
        missing_timeframes = []
        
        for timeframe in timeframes:
            start_date, end_date = self._get_timeframe_specific_date_range(timeframe)
            start_ts = int(start_date.timestamp())
            end_ts = int(end_date.timestamp())
            
            data = self.cache_service.get_cached_ohlc_data(instrument, timeframe, start_ts, end_ts)
            if data:
                cached_data[timeframe] = data
            else:
                missing_timeframes.append(timeframe)
        
        return missing_timeframes, cached_data

    def _get_timeframe_specific_date_range(self, timeframe: str) -> Tuple[datetime, datetime]:
        """Helper to get date range for yfinance limitations"""
        end_date = datetime.now()
        if timeframe == '1m':
            start_date = end_date - timedelta(days=7)
        elif timeframe in ['3m', '5m', '15m', '1h', '4h']:
            start_date = end_date - timedelta(days=60)
        else:
            start_date = end_date - timedelta(days=365)
        return start_date, end_date

class OHLCDataService:
    """Service for managing OHLC market data with gap detection and backfilling"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        self.cache_service = get_cache_service() if config.cache_enabled else None
        if self.cache_service:
            self.logger.info("Redis cache service initialized")
        else:
            self.logger.info("Cache service disabled or unavailable")

        self.rate_limiter = BatchOptimizedRateLimiter(self.cache_service, YAHOO_FINANCE_CONFIG)
        
        error_handling_config = YAHOO_FINANCE_CONFIG.get('error_handling', {})
        self.max_retries = error_handling_config.get('max_retries', 3)
        self.retry_delays = error_handling_config.get('retry_delays', [5, 15, 45])
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=error_handling_config.get('circuit_breaker_threshold', 5),
            recovery_timeout=error_handling_config.get('circuit_breaker_timeout', 300)
        )
        
        self.market_open_utc = {
            'sunday': 22, 'monday': 22, 'tuesday': 22,
            'wednesday': 22, 'thursday': 22, 'friday': 21
        }
        
        self.maintenance_break = (21, 22)
        
        self._migrate_instrument_names()

    def _migrate_instrument_names(self):
        """Run database migration to normalize instrument names"""
        try:
            with FuturesDB() as db:
                results = db.migrate_instrument_names_to_base_symbols()
                if results:
                    self.logger.info(f"Migrated instrument names: {results}")
        except Exception as e:
            self.logger.error(f"Error during instrument name migration: {e}")

    def _enforce_rate_limit(self):
        """Enforce rate limiting between API requests"""
        self.rate_limiter.enforce()

    def _get_base_instrument(self, instrument: str) -> str:
        return symbol_service.get_base_symbol(instrument)
    
    def _get_yfinance_symbol(self, instrument: str) -> str:
        return symbol_service.get_yfinance_symbol(instrument)

    def _convert_timeframe_to_yfinance(self, timeframe: str) -> str:
        timeframe_map = {
            '1m': '1m', '3m': '3m', '5m': '5m', 
            '15m': '15m', '1h': '1h', '4h': '4h', '1d': '1d'
        }
        return timeframe_map.get(timeframe, '1m')

    def _enforce_rate_limit_with_retry(self, func, *args, **kwargs):
        """Enhanced rate limiting with retry logic for production reliability"""
        if not self.circuit_breaker.can_execute():
            raise RateLimitError("Circuit breaker is open")

        for attempt in range(self.max_retries + 1):
            try:
                self._enforce_rate_limit()
                result = func(*args, **kwargs)
                self.rate_limiter.register_success()
                self.circuit_breaker.record_success()
                return result
            except Exception as e:
                self.rate_limiter.register_failure()
                self.circuit_breaker.record_failure()
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ["429", "too many requests", "rate limit", "quota"]):
                    if attempt < self.max_retries:
                        wait_time = self.retry_delays[attempt]
                        self.logger.warning(f"Rate limited on attempt {attempt + 1}, retrying in {wait_time}s: {e}")
                        time.sleep(wait_time)
                        continue
                    else:
                        self.logger.error(f"Rate limited after {self.max_retries} retries, giving up: {e}")
                        raise RateLimitError(f"Rate limited after {self.max_retries} retries") from e
                else:
                    raise NetworkError("A network error occurred") from e
        return None

    def fetch_ohlc_data(self, instrument: str, timeframe: str, 
                       start_date: datetime, end_date: datetime) -> List[Dict]:
        return self._enforce_rate_limit_with_retry(
            self._fetch_ohlc_data_internal, instrument, timeframe, start_date, end_date
        )
    
    def _fetch_ohlc_data_internal(self, instrument: str, timeframe: str, 
                                 start_date: datetime, end_date: datetime) -> List[Dict]:
        try:
            yf_symbol = self._get_yfinance_symbol(instrument)
            yf_interval = self._convert_timeframe_to_yfinance(timeframe)
            
            self.logger.info(f"Fetching {instrument} ({yf_symbol}) {timeframe} data from {start_date} to {end_date}")
            
            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(
                start=start_date, end=end_date, interval=yf_interval, prepost=True
            )
            
            if data.empty:
                self.logger.warning(f"No data returned for {instrument} {timeframe}")
                return []
            
            ohlc_records = []
            for timestamp, row in data.iterrows():
                unix_timestamp = int(timestamp.timestamp())
                record = {
                    'instrument': self._get_base_instrument(instrument),
                    'timeframe': timeframe,
                    'timestamp': unix_timestamp,
                    'open_price': float(row['Open']),
                    'high_price': float(row['High']),
                    'low_price': float(row['Low']),
                    'close_price': float(row['Close']),
                    'volume': int(row['Volume']) if pd.notna(row['Volume']) else None
                }
                ohlc_records.append(record)
            
            self.logger.info(f"Successfully fetched {len(ohlc_records)} records for {instrument}")
            return ohlc_records
            
        except Exception as e:
            self.logger.error(f"Error fetching OHLC data for {instrument}: {e}")
            return []

    def is_market_open(self, timestamp: datetime) -> bool:
        weekday = timestamp.weekday()
        hour_utc = timestamp.hour
        
        if weekday == 5: return False
        if weekday == 6: return hour_utc >= 22
        if weekday <= 3:
            if self.maintenance_break[0] <= hour_utc < self.maintenance_break[1]:
                return False
            return True
        if weekday == 4: return hour_utc < 21
        
        return True

    def detect_and_fill_gaps(self, instrument: str, timeframe: str, 
                           start_date: datetime, end_date: datetime) -> bool:
        try:
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            with FuturesDB() as db:
                gaps = db.find_ohlc_gaps(instrument, timeframe, start_timestamp, end_timestamp)
                
                if not gaps: return True
                
                for gap_start_ts, gap_end_ts in gaps:
                    gap_start_dt = datetime.fromtimestamp(gap_start_ts)
                    gap_end_dt = datetime.fromtimestamp(gap_end_ts)
                    
                    if not self.is_market_open(gap_start_dt): continue
                    
                    gap_data = self.fetch_ohlc_data(instrument, timeframe, gap_start_dt, gap_end_dt)
                    
                    for record in gap_data:
                        db.insert_ohlc_data(
                            record['instrument'], record['timeframe'], record['timestamp'],
                            record['open_price'], record['high_price'], record['low_price'],
                            record['close_price'], record['volume']
                        )
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error detecting/filling gaps: {e}")
            return False

    def get_chart_data(self, instrument: str, timeframe: str, 
                      start_date: datetime, end_date: datetime) -> List[Dict]:
        try:
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            if self.cache_service:
                cached_data = self.cache_service.get_cached_ohlc__data(
                    instrument, timeframe, start_timestamp, end_timestamp
                )
                if cached_data: return cached_data
            
            with FuturesDB() as db:
                data = db.get_ohlc_data(instrument, timeframe, start_timestamp, end_timestamp, limit=None)
                if not data:
                    base_instrument = self._get_base_instrument(instrument)
                    if base_instrument != instrument:
                        data = db.get_ohlc_data(base_instrument, timeframe, start_timestamp, end_timestamp, limit=None)
            
            if self.cache_service and data:
                self.cache_service.cache_ohlc_data(
                    instrument, timeframe, start_timestamp, end_timestamp, 
                    data, ttl_days=config.cache_ttl_days
                )
            
            return data
                
        except Exception as e:
            self.logger.error(f"Error getting chart data: {e}")
            return []

    def update_recent_data(self, instrument: str, timeframes: List[str] = None) -> bool:
        if timeframes is None:
            timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
        
        success_count = 0
        
        for timeframe in timeframes:
            try:
                start_date, end_date = self.get_timeframe_specific_date_range(timeframe)
                recent_data = self.fetch_ohlc_data(instrument, timeframe, start_date, end_date)
                
                if recent_data:
                    with FuturesDB() as db:
                        for record in recent_data:
                            try:
                                db.insert_ohlc_data(
                                    record['instrument'], record['timeframe'], record['timestamp'], 
                                    record['open_price'], record['high_price'], record['low_price'],
                                    record['close_price'], record['volume']
                                )
                            except Exception:
                                continue
                    success_count += 1
            except Exception as e:
                self.logger.error(f"Failed to process timeframe {timeframe} for {instrument}: {e}")
                continue
        
        return success_count > 0

    def get_optimal_timeframe_order(self, timeframes: List[str]) -> List[str]:
        priority_order = {'1d': 1, '1h': 2, '4h': 3, '15m': 4, '5m': 5, '3m': 6, '1m': 7}
        return sorted(timeframes, key=lambda tf: priority_order.get(tf, 999))

    def get_timeframe_specific_date_range(self, timeframe: str) -> Tuple[datetime, datetime]:
        end_date = datetime.now()
        if timeframe == '1m':
            start_date = end_date - timedelta(days=7)
        elif timeframe in ['3m', '5m', '15m', '1h', '4h']:
            start_date = end_date - timedelta(days=60)
        else:
            start_date = end_date - timedelta(days=365)
        return start_date, end_date

    def batch_update_multiple_instruments(self, instruments: List[str], 
                                        timeframes: List[str] = None) -> Dict[str, Dict[str, bool]]:
        if timeframes is None:
            timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
        
        optimized_timeframes = self.get_optimal_timeframe_order(timeframes)
        
        results = {}
        for instrument in instruments:
            results[instrument] = {}
            for timeframe in optimized_timeframes:
                try:
                    start_date, end_date = self.get_timeframe_specific_date_range(timeframe)
                    data = self.fetch_ohlc_data(instrument, timeframe, start_date, end_date)
                    if data:
                        with FuturesDB() as db:
                            for record in data:
                                try:
                                    db.insert_ohlc_data(
                                        record['instrument'], record['timeframe'], record['timestamp'], 
                                        record['open_price'], record['high_price'], record['low_price'],
                                        record['close_price'], record['volume']
                                    )
                                except Exception:
                                    pass
                        results[instrument][timeframe] = True
                    else:
                        results[instrument][timeframe] = False
                except Exception as e:
                    self.logger.error(f"Failed to process {instrument} {timeframe}: {e}")
                    results[instrument][timeframe] = False
        return results

    def update_all_active_instruments(self, timeframes: List[str] = None) -> Dict[str, Dict[str, bool]]:
        if timeframes is None:
            timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
        
        with FuturesDB() as db:
            recent_date = datetime.now() - timedelta(days=30)
            instruments = db.get_active_instruments_since(recent_date)
        
        if not instruments:
            return {}
        
        return self.batch_update_multiple_instruments(instruments, timeframes)

# Global instance
ohlc_service = OHLCDataService()

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
from typing import List, Dict, Tuple, Optional
import logging
from scripts.TradingLog_db import FuturesDB
from config import config, YAHOO_FINANCE_CONFIG
from services.redis_cache_service import get_cache_service
from services.symbol_service import symbol_service

class BatchOptimizedRateLimiter:
    """Intelligent rate limiting for batch-optimized Yahoo Finance API requests"""
    
    def __init__(self, cache_service, config):
        self.logger = logging.getLogger(__name__)
        self.cache_service = cache_service
        self.config = config.get('rate_limiting', {})
        self.batch_config = config.get('batch_processing', {})
        
        # Sliding window for success/failure tracking
        self.success_window = []
        self.failure_window = []
        self.window_size = 100  # Track last 100 requests
        
        # Concurrency control
        self.max_concurrent_requests = self.batch_config.get('max_concurrent_instruments', 3)
        
        # Per-endpoint rate limiting (future use)
        self.endpoint_delays = {}

    def _update_window(self, window: List, event_time: float):
        """Add event to sliding window and remove old entries"""
        window.append(event_time)
        cutoff = time.time() - 60  # 1-minute window
        while window and window[0] < cutoff:
            window.pop(0)

    def register_success(self):
        self._update_window(self.success_window, time.time())

    def register_failure(self):
        self._update_window(self.failure_window, time.time())

    def get_current_delay(self) -> float:
        """Calculate adaptive delay based on recent success/failure rates"""
        if not self.config.get('adaptive_enabled', False):
            return self.config.get('base_delay', 2.5)

        # Placeholder for adaptive logic
        return self.config.get('base_delay', 2.5)

    def enforce(self):
        """Enforce rate limit delay"""
        delay = self.get_current_delay()
        time.sleep(delay)

    def validate_cache_first(self, instrument: str, timeframes: List[str]) -> Tuple[List[str], Dict[str, List[Dict]]]:
        """Check cache for multiple timeframes to minimize API calls"""
        if not self.cache_service:
            return timeframes, {}
        
        cached_data = {}
        missing_timeframes = []
        
        for timeframe in timeframes:
            start_date, end_date = self._get_timeframe_specific_date_range(timeframe)
            start_ts = int(start_date.timestamp())
            end_ts = int(end_date.timestamp())
            
            data = self.cache_service.get_cached_ohlc_data(instrument, timeframe, start_ts, end_ts)
            if data:
                cached_data[timeframe] = data
            else:
                missing_timeframes.append(timeframe)
        
        return missing_timeframes, cached_data

    def _get_timeframe_specific_date_range(self, timeframe: str) -> Tuple[datetime, datetime]:
        """Helper to get date range for yfinance limitations"""
        end_date = datetime.now()
        if timeframe == '1m':
            start_date = end_date - timedelta(days=7)
        elif timeframe in ['3m', '5m', '15m', '1h', '4h']:
            start_date = end_date - timedelta(days=60)
        else:
            start_date = end_date - timedelta(days=365)
        return start_date, end_date

class OHLCDataService:
    """Service for managing OHLC market data with gap detection and backfilling"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize cache service if enabled
        self.cache_service = get_cache_service() if config.cache_enabled else None
        if self.cache_service:
            self.logger.info("Redis cache service initialized")
        else:
            self.logger.info("Cache service disabled or unavailable")

        self.rate_limiter = BatchOptimizedRateLimiter(self.cache_service, YAHOO_FINANCE_CONFIG)
        
        error_handling_config = YAHOO_FINANCE_CONFIG.get('error_handling', {})
        self.max_retries = error_handling_config.get('max_retries', 3)
        self.retry_delays = error_handling_config.get('retry_delays', [5, 15, 45])
        
        # Market hours (CME Group) - UTC times
        self.market_open_utc = {
            'sunday': 22,
            'monday': 22,
            'tuesday': 22,
            'wednesday': 22,
            'thursday': 22,
            'friday': 21
        }
        
        self.maintenance_break = (21, 22)
        
        self._migrate_instrument_names()

    def _migrate_instrument_names(self):
        """Run database migration to normalize instrument names"""
        try:
            with FuturesDB() as db:
                results = db.migrate_instrument_names_to_base_symbols()
                if results:
                    self.logger.info(f"Migrated instrument names: {results}")
        except Exception as e:
            self.logger.error(f"Error during instrument name migration: {e}")

    def _enforce_rate_limit(self):
        """Enforce rate limiting between API requests"""
        self.rate_limiter.enforce()

    def _get_base_instrument(self, instrument: str) -> str:
        """Extract base instrument symbol (e.g., 'MNQ SEP25' -> 'MNQ')"""
        return symbol_service.get_base_symbol(instrument)
    
    def _get_yfinance_symbol(self, instrument: str) -> str:
        """Convert instrument symbol to yfinance symbol"""
        return symbol_service.get_yfinance_symbol(instrument)

    def _convert_timeframe_to_yfinance(self, timeframe: str) -> str:
        """Convert our timeframe format to yfinance interval"""
        timeframe_map = {
            '1m': '1m', '3m': '3m', '5m': '5m', 
            '15m': '15m', '1h': '1h', '4h': '4h', '1d': '1d'
        }
        return timeframe_map.get(timeframe, '1m')

    def _enforce_rate_limit_with_retry(self, func, *args, **kwargs):
        """Enhanced rate limiting with retry logic for production reliability"""
        for attempt in range(self.max_retries + 1):
            try:
                self._enforce_rate_limit()
                return func(*args, **kwargs)
            except Exception as e:
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ["429", "too many requests", "rate limit", "quota"]):
                    if attempt < self.max_retries:
                        wait_time = self.retry_delays[attempt]
                        self.logger.warning(f"Rate limited on attempt {attempt + 1}, retrying in {wait_time}s: {e}")
                        time.sleep(wait_time)
                        continue
                    else:
                        self.logger.error(f"Rate limited after {self.max_retries} retries, giving up: {e}")
                        raise e
                else:
                    raise e
        return None

    def fetch_ohlc_data(self, instrument: str, timeframe: str, 
                       start_date: datetime, end_date: datetime) -> List[Dict]:
        """Fetch OHLC data from yfinance with enhanced retry logic"""
        return self._enforce_rate_limit_with_retry(
            self._fetch_ohlc_data_internal, instrument, timeframe, start_date, end_date
        )
    
    def _fetch_ohlc_data_internal(self, instrument: str, timeframe: str, 
                                 start_date: datetime, end_date: datetime) -> List[Dict]:
        """Internal method for fetching OHLC data (used by retry wrapper)"""
        try:
            yf_symbol = self._get_yfinance_symbol(instrument)
            yf_interval = self._convert_timeframe_to_yfinance(timeframe)
            
            self.logger.info(f"Fetching {instrument} ({yf_symbol}) {timeframe} data from {start_date} to {end_date}")
            
            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(
                start=start_date, end=end_date, interval=yf_interval, prepost=True
            )
            
            if data.empty:
                self.logger.warning(f"No data returned for {instrument} {timeframe}")
                return []
            
            ohlc_records = []
            for timestamp, row in data.iterrows():
                unix_timestamp = int(timestamp.timestamp())
                record = {
                    'instrument': self._get_base_instrument(instrument),
                    'timeframe': timeframe,
                    'timestamp': unix_timestamp,
                    'open_price': float(row['Open']),
                    'high_price': float(row['High']),
                    'low_price': float(row['Low']),
                    'close_price': float(row['Close']),
                    'volume': int(row['Volume']) if pd.notna(row['Volume']) else None
                }
                ohlc_records.append(record)
            
            self.logger.info(f"Successfully fetched {len(ohlc_records)} records for {instrument}")
            return ohlc_records
            
        except Exception as e:
            self.logger.error(f"Error fetching OHLC data for {instrument}: {e}")
            return []

    def is_market_open(self, timestamp: datetime) -> bool:
        """Check if market is open at given time (simplified version)"""
        weekday = timestamp.weekday()
        hour_utc = timestamp.hour
        
        if weekday == 5: return False
        if weekday == 6: return hour_utc >= 22
        if weekday <= 3:
            if self.maintenance_break[0] <= hour_utc < self.maintenance_break[1]:
                return False
            return True
        if weekday == 4: return hour_utc < 21
        
        return True

    def detect_and_fill_gaps(self, instrument: str, timeframe: str, 
                           start_date: datetime, end_date: datetime) -> bool:
        """Detect gaps in OHLC data and fill them intelligently"""
        try:
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            with FuturesDB() as db:
                gaps = db.find_ohlc_gaps(instrument, timeframe, start_timestamp, end_timestamp)
                
                if not gaps:
                    self.logger.info(f"No gaps found for {instrument} {timeframe}")
                    return True
                
                self.logger.info(f"Found {len(gaps)} gaps for {instrument} {timeframe}")
                
                for gap_start_ts, gap_end_ts in gaps:
                    gap_start_dt = datetime.fromtimestamp(gap_start_ts)
                    gap_end_dt = datetime.fromtimestamp(gap_end_ts)
                    
                    if not self.is_market_open(gap_start_dt): continue
                    
                    self.logger.info(f"Filling gap: {gap_start_dt} to {gap_end_dt}")
                    
                    gap_data = self.fetch_ohlc_data(instrument, timeframe, gap_start_dt, gap_end_dt)
                    
                    for record in gap_data:
                        db.insert_ohlc_data(
                            record['instrument'], record['timeframe'], record['timestamp'],
                            record['open_price'], record['high_price'], record['low_price'],
                            record['close_price'], record['volume']
                        )
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error detecting/filling gaps: {e}")
            return False

    def get_chart_data(self, instrument: str, timeframe: str, 
                      start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get chart data with Redis caching and automatic gap filling"""
        try:
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            if self.cache_service:
                cached_data = self.cache_service.get_cached_ohlc_data(
                    instrument, timeframe, start_timestamp, end_timestamp
                )
                if cached_data:
                    return cached_data
            
            with FuturesDB() as db:
                data = db.get_ohlc_data(instrument, timeframe, start_timestamp, end_timestamp, limit=None)
                if not data:
                    base_instrument = self._get_base_instrument(instrument)
                    if base_instrument != instrument:
                        data = db.get_ohlc_data(base_instrument, timeframe, start_timestamp, end_timestamp, limit=None)
            
            if self.cache_service and data:
                self.cache_service.cache_ohlc_data(
                    instrument, timeframe, start_timestamp, end_timestamp, 
                    data, ttl_days=config.cache_ttl_days
                )
            
            return data
                
        except Exception as e:
            self.logger.error(f"Error getting chart data: {e}")
            return []

    def update_recent_data(self, instrument: str, timeframes: List[str] = None) -> bool:
        """Update recent data for an instrument across multiple timeframes"""
        if timeframes is None:
            timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
        
        success_count = 0
        total_records = 0
        
        for timeframe in timeframes:
            try:
                start_date, end_date = self.get_timeframe_specific_date_range(timeframe)
                recent_data = self.fetch_ohlc_data(instrument, timeframe, start_date, end_date)
                
                if recent_data:
                    with FuturesDB() as db:
                        records_inserted = 0
                        for record in recent_data:
                            try:
                                db.insert_ohlc_data(
                                    record['instrument'], record['timeframe'], record['timestamp'], 
                                    record['open_price'], record['high_price'], record['low_price'],
                                    record['close_price'], record['volume']
                                )
                                records_inserted += 1
                            except Exception:
                                continue
                    total_records += records_inserted
                    success_count += 1
            except Exception as e:
                self.logger.error(f"Failed to process timeframe {timeframe} for {instrument}: {e}")
                continue
        
        return success_count > 0

    def get_optimal_timeframe_order(self, timeframes: List[str]) -> List[str]:
        """Prioritize timeframes by data availability and reliability"""
        priority_order = {'1d': 1, '1h': 2, '4h': 3, '15m': 4, '5m': 5, '3m': 6, '1m': 7}
        return sorted(timeframes, key=lambda tf: priority_order.get(tf, 999))

    def get_timeframe_specific_date_range(self, timeframe: str) -> Tuple[datetime, datetime]:
        """Get optimal date range based on yfinance timeframe limitations"""
        end_date = datetime.now()
        if timeframe == '1m':
            start_date = end_date - timedelta(days=7)
        elif timeframe in ['3m', '5m', '15m', '1h', '4h']:
            start_date = end_date - timedelta(days=60)
        else:
            start_date = end_date - timedelta(days=365)
        return start_date, end_date

    def batch_update_multiple_instruments(self, instruments: List[str], 
                                        timeframes: List[str] = None) -> Dict[str, Dict[str, bool]]:
        """Efficiently update multiple instruments across multiple timeframes"""
        if timeframes is None:
            timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
        
        optimized_timeframes = self.get_optimal_timeframe_order(timeframes)
        total_requests = len(instruments) * len(optimized_timeframes)
        
        results = {}
        for instrument in instruments:
            results[instrument] = {}
            for timeframe in optimized_timeframes:
                try:
                    start_date, end_date = self.get_timeframe_specific_date_range(timeframe)
                    data = self.fetch_ohlc_data(instrument, timeframe, start_date, end_date)
                    if data:
                        with FuturesDB() as db:
                            for record in data:
                                try:
                                    db.insert_ohlc_data(
                                        record['instrument'], record['timeframe'], record['timestamp'], 
                                        record['open_price'], record['high_price'], record['low_price'],
                                        record['close_price'], record['volume']
                                    )
                                except Exception:
                                    pass
                        results[instrument][timeframe] = True
                    else:
                        results[instrument][timeframe] = False
                except Exception as e:
                    self.logger.error(f"Failed to process {instrument} {timeframe}: {e}")
                    results[instrument][timeframe] = False
        return results

    def update_all_active_instruments(self, timeframes: List[str] = None) -> Dict[str, Dict[str, bool]]:
        """Update all instruments that have recent trade activity"""
        if timeframes is None:
            timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
        
        with FuturesDB() as db:
            recent_date = datetime.now() - timedelta(days=30)
            instruments = db.get_active_instruments_since(recent_date)
        
        if not instruments:
            return {}
        
        return self.batch_update_multiple_instruments(instruments, timeframes)

# Global instance
ohlc_service = OHLCDataService()

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
from typing import List, Dict, Tuple, Optional
import logging
from scripts.TradingLog_db import FuturesDB
from config import config
from services.redis_cache_service import get_cache_service
from services.symbol_service import symbol_service

class BatchOptimizedRateLimiter:
    """Intelligent rate limiting for batch-optimized Yahoo Finance API requests"""
    
    def __init__(self, cache_service, config):
        self.logger = logging.getLogger(__name__)
        self.cache_service = cache_service
        self.config = config
        
        # Sliding window for success/failure tracking
        self.success_window = []
        self.failure_window = []
        self.window_size = 100  # Track last 100 requests
        
        # Concurrency control
        self.max_concurrent_requests = self.config.get('batch_processing', {}).get('max_concurrent_instruments', 3)
        
        # Per-endpoint rate limiting (future use)
        self.endpoint_delays = {}

    def _update_window(self, window: List, event_time: float):
        """Add event to sliding window and remove old entries"""
        window.append(event_time)
        cutoff = time.time() - 60  # 1-minute window
        while window and window[0] < cutoff:
            window.pop(0)

    def register_success(self):
        self._update_window(self.success_window, time.time())

    def register_failure(self):
        self._update_window(self.failure_window, time.time())

    def get_current_delay(self) -> float:
        """Calculate adaptive delay based on recent success/failure rates"""
        # This is a placeholder for a more sophisticated adaptive algorithm
        # For now, it will use the fixed delay from config
        return self.config.get('rate_limiting', {}).get('base_delay', 2.5)

    def enforce(self):
        """Enforce rate limit delay"""
        delay = self.get_current_delay()
        time.sleep(delay)

    def validate_cache_first(self, instrument: str, timeframes: List[str]) -> Tuple[List[str], Dict[str, List[Dict]]]:
        """Check cache for multiple timeframes to minimize API calls"""
        if not self.cache_service:
            return timeframes, {}
        
        cached_data = {}
        missing_timeframes = []
        
        for timeframe in timeframes:
            # This needs a method to get date ranges for each timeframe
            start_date, end_date = self._get_timeframe_specific_date_range(timeframe)
            start_ts = int(start_date.timestamp())
            end_ts = int(end_date.timestamp())
            
            data = self.cache_service.get_cached_ohlc_data(instrument, timeframe, start_ts, end_ts)
            if data:
                cached_data[timeframe] = data
            else:
                missing_timeframes.append(timeframe)
        
        return missing_timeframes, cached_data

    def _get_timeframe_specific_date_range(self, timeframe: str) -> Tuple[datetime, datetime]:
        """Helper to get date range for yfinance limitations"""
        end_date = datetime.now()
        if timeframe == '1m':
            start_date = end_date - timedelta(days=7)
        elif timeframe in ['3m', '5m', '15m', '1h', '4h']:
            start_date = end_date - timedelta(days=60)
        else:
            start_date = end_date - timedelta(days=365)
        return start_date, end_date

class OHLCDataService:
    """Service for managing OHLC market data with gap detection and backfilling"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.rate_limit_delay = 2.5  # 2.5 seconds between requests for reliability
        self.last_request_time = 0
        
        # Initialize cache service if enabled
        self.cache_service = get_cache_service() if config.cache_enabled else None
        if self.cache_service:
            self.logger.info("Redis cache service initialized")
        else:
            self.logger.info("Cache service disabled or unavailable")
        
        # Enhanced retry configuration for production reliability
        self.max_retries = 3
        self.retry_delays = [5, 15, 45]  # Exponential backoff in seconds
        
        # Use centralized symbol service for all symbol mappings
        # No need for local symbol_mapping - using symbol_service
        
        # Market hours (CME Group) - UTC times
        self.market_open_utc = {
            'sunday': 22,  # 10 PM Sunday UTC (3 PM PT Sunday) 
            'monday': 22,  # 10 PM Monday UTC
            'tuesday': 22,
            'wednesday': 22,
            'thursday': 22,
            'friday': 21   # 9 PM Friday UTC (2 PM PT Friday)
        }
        
        # Daily maintenance break: 21:00-22:00 UTC (2 PM - 3 PM PT)
        self.maintenance_break = (21, 22)
        
        # Run migration on initialization to ensure data consistency
        self._migrate_instrument_names()

    def _migrate_instrument_names(self):
        """Run database migration to normalize instrument names"""
        try:
            with FuturesDB() as db:
                results = db.migrate_instrument_names_to_base_symbols()
                if results:
                    self.logger.info(f"Migrated instrument names: {results}")
        except Exception as e:
            self.logger.error(f"Error during instrument name migration: {e}")

    def _enforce_rate_limit(self):
        """Enforce rate limiting between API requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()

    def _get_base_instrument(self, instrument: str) -> str:
        """Extract base instrument symbol (e.g., 'MNQ SEP25' -> 'MNQ')"""
        return symbol_service.get_base_symbol(instrument)
    
    def _get_yfinance_symbol(self, instrument: str) -> str:
        """Convert instrument symbol to yfinance symbol"""
        return symbol_service.get_yfinance_symbol(instrument)

    def _convert_timeframe_to_yfinance(self, timeframe: str) -> str:
        """Convert our timeframe format to yfinance interval"""
        timeframe_map = {
            '1m': '1m',
            '3m': '3m',
            '5m': '5m', 
            '15m': '15m',
            '1h': '1h',
            '4h': '4h',
            '1d': '1d'
        }
        return timeframe_map.get(timeframe, '1m')

    def _enforce_rate_limit_with_retry(self, func, *args, **kwargs):
        """Enhanced rate limiting with retry logic for production reliability"""
        for attempt in range(self.max_retries + 1):
            try:
                self._enforce_rate_limit()
                return func(*args, **kwargs)
            except Exception as e:
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ["429", "too many requests", "rate limit", "quota"]):
                    if attempt < self.max_retries:
                        wait_time = self.retry_delays[attempt]
                        self.logger.warning(f"Rate limited on attempt {attempt + 1}, retrying in {wait_time}s: {e}")
                        time.sleep(wait_time)
                        continue
                    else:
                        self.logger.error(f"Rate limited after {self.max_retries} retries, giving up: {e}")
                        raise e
                else:
                    # Non-rate limit error, don't retry
                    raise e
        return None

    def fetch_ohlc_data(self, instrument: str, timeframe: str, 
                       start_date: datetime, end_date: datetime) -> List[Dict]:
        """Fetch OHLC data from yfinance with enhanced retry logic"""
        return self._enforce_rate_limit_with_retry(
            self._fetch_ohlc_data_internal, instrument, timeframe, start_date, end_date
        )
    
    def _fetch_ohlc_data_internal(self, instrument: str, timeframe: str, 
                                 start_date: datetime, end_date: datetime) -> List[Dict]:
        """Internal method for fetching OHLC data (used by retry wrapper)"""
        try:
            
            yf_symbol = self._get_yfinance_symbol(instrument)
            yf_interval = self._convert_timeframe_to_yfinance(timeframe)
            
            self.logger.info(f"Fetching {instrument} ({yf_symbol}) {timeframe} data from {start_date} to {end_date}")
            
            # Fetch data from yfinance
            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(
                start=start_date,
                end=end_date,
                interval=yf_interval,
                prepost=True  # Include pre/post market for futures
            )
            
            if data.empty:
                self.logger.warning(f"No data returned for {instrument} {timeframe}")
                return []
            
            # Convert to our format
            ohlc_records = []
            for timestamp, row in data.iterrows():
                # Convert pandas timestamp to Unix timestamp
                unix_timestamp = int(timestamp.timestamp())
                
                record = {
                    'instrument': self._get_base_instrument(instrument),  # Store using base symbol
                    'timeframe': timeframe,
                    'timestamp': unix_timestamp,
                    'open_price': float(row['Open']),
                    'high_price': float(row['High']),
                    'low_price': float(row['Low']),
                    'close_price': float(row['Close']),
                    'volume': int(row['Volume']) if pd.notna(row['Volume']) else None
                }
                ohlc_records.append(record)
            
            self.logger.info(f"Successfully fetched {len(ohlc_records)} records for {instrument}")
            return ohlc_records
            
        except Exception as e:
            self.logger.error(f"Error fetching OHLC data for {instrument}: {e}")
            return []

    def is_market_open(self, timestamp: datetime) -> bool:
        """Check if market is open at given time (simplified version)"""
        # This is a basic implementation - could be enhanced with holiday calendar
        weekday = timestamp.weekday()  # 0=Monday, 6=Sunday
        hour_utc = timestamp.hour
        
        # Market closed on Saturday
        if weekday == 5:  # Saturday
            return False
        
        # Sunday: Opens at 10 PM UTC
        if weekday == 6:  # Sunday
            return hour_utc >= 22
        
        # Monday-Thursday: Closed during maintenance break
        if weekday <= 3:  # Monday-Thursday
            if self.maintenance_break[0] <= hour_utc < self.maintenance_break[1]:
                return False
            return True
        
        # Friday: Closes at 9 PM UTC
        if weekday == 4:  # Friday
            return hour_utc < 21
        
        return True

    def detect_and_fill_gaps(self, instrument: str, timeframe: str, 
                           start_date: datetime, end_date: datetime) -> bool:
        """Detect gaps in OHLC data and fill them intelligently"""
        try:
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            with FuturesDB() as db:
                # Find gaps in existing data
                gaps = db.find_ohlc_gaps(instrument, timeframe, start_timestamp, end_timestamp)
                
                if not gaps:
                    self.logger.info(f"No gaps found for {instrument} {timeframe}")
                    return True
                
                self.logger.info(f"Found {len(gaps)} gaps for {instrument} {timeframe}")
                
                # Fill each gap
                for gap_start_ts, gap_end_ts in gaps:
                    gap_start_dt = datetime.fromtimestamp(gap_start_ts)
                    gap_end_dt = datetime.fromtimestamp(gap_end_ts)
                    
                    # Skip gaps during market closure
                    if not self.is_market_open(gap_start_dt):
                        continue
                    
                    self.logger.info(f"Filling gap: {gap_start_dt} to {gap_end_dt}")
                    
                    # Fetch data for this gap
                    gap_data = self.fetch_ohlc_data(instrument, timeframe, gap_start_dt, gap_end_dt)
                    
                    # Insert data into database
                    for record in gap_data:
                        db.insert_ohlc_data(
                            record['instrument'],
                            record['timeframe'], 
                            record['timestamp'],
                            record['open_price'],
                            record['high_price'],
                            record['low_price'],
                            record['close_price'],
                            record['volume']
                        )
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error detecting/filling gaps: {e}")
            return False

    def get_chart_data(self, instrument: str, timeframe: str, 
                      start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get chart data with Redis caching and automatic gap filling"""
        try:
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            self.logger.info(f"DEBUG: get_chart_data called for {instrument} {timeframe}, timestamps {start_timestamp}-{end_timestamp}")
            
            # Try cache first if enabled
            if self.cache_service:
                self.logger.info(f"DEBUG: Cache service is enabled, checking cache...")
                cached_data = self.cache_service.get_cached_ohlc_data(
                    instrument, timeframe, start_timestamp, end_timestamp
                )
                self.logger.info(f"DEBUG: Cache returned {len(cached_data) if cached_data else 'None'} records")
                if cached_data:
                    self.logger.debug(f"Returning cached data for {instrument} {timeframe}")
                    return cached_data
            else:
                self.logger.info(f"DEBUG: Cache service is disabled")
            
            # Try to get data using exact instrument name first
            self.logger.info(f"DEBUG: Querying database for {instrument} {timeframe}...")
            with FuturesDB() as db:
                data = db.get_ohlc_data(instrument, timeframe, start_timestamp, end_timestamp, limit=None)
                self.logger.info(f"DEBUG: Database returned {len(data)} records for {instrument}")
                
                # If no data found with exact name, try base instrument name
                if not data:
                    base_instrument = self._get_base_instrument(instrument)
                    if base_instrument != instrument:
                        self.logger.debug(f"No data for {instrument}, trying base instrument {base_instrument}")
                        data = db.get_ohlc_data(base_instrument, timeframe, start_timestamp, end_timestamp, limit=None)
            
            # Cache the data if cache service is available
            if self.cache_service and data:
                self.cache_service.cache_ohlc_data(
                    instrument, timeframe, start_timestamp, end_timestamp, 
                    data, ttl_days=config.cache_ttl_days
                )
                self.logger.debug(f"Cached {len(data)} records for {instrument} {timeframe}")
            
            return data
                
        except Exception as e:
            self.logger.error(f"Error getting chart data: {e}")
            return []

    def update_recent_data(self, instrument: str, timeframes: List[str] = None) -> bool:
        """Update recent data for an instrument across multiple timeframes"""
        if timeframes is None:
            timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
        
        self.logger.info(f"Starting multi-timeframe update for {instrument} with {len(timeframes)} timeframes: {timeframes}")
        success_count = 0
        total_records = 0
        
        for i, timeframe in enumerate(timeframes, 1):
            try:
                self.logger.info(f"Processing timeframe {i}/{len(timeframes)}: {timeframe} for {instrument}")
                
                # Get appropriate date range for each timeframe based on yfinance limitations
                start_date, end_date = self.get_timeframe_specific_date_range(timeframe)
                self.logger.info(f"Using date range for {timeframe}: {start_date} to {end_date}")
                
                # Fetch and store recent data
                recent_data = self.fetch_ohlc_data(instrument, timeframe, start_date, end_date)
                self.logger.info(f"Fetched {len(recent_data)} records for {instrument} {timeframe}")
                
                if recent_data:
                    with FuturesDB() as db:
                        records_inserted = 0
                        for record in recent_data:
                            try:
                                db.insert_ohlc_data(
                                    record['instrument'],
                                    record['timeframe'],
                                    record['timestamp'], 
                                    record['open_price'],
                                    record['high_price'],
                                    record['low_price'],
                                    record['close_price'],
                                    record['volume']
                                )
                                records_inserted += 1
                            except Exception as insert_error:
                                self.logger.warning(f"Failed to insert record for {timeframe}: {insert_error}")
                                continue
                    
                    self.logger.info(f"Successfully stored {records_inserted}/{len(recent_data)} records for {instrument} {timeframe}")
                    total_records += records_inserted
                    success_count += 1
                else:
                    self.logger.warning(f"No data retrieved for {instrument} {timeframe}")
                
            except Exception as e:
                self.logger.error(f"Failed to process timeframe {timeframe} for {instrument}: {e}")
                # Continue processing other timeframes even if one fails
                continue
        
        self.logger.info(f"Multi-timeframe update completed: {success_count}/{len(timeframes)} timeframes successful, {total_records} total records inserted")
        
        # Return True if at least one timeframe was successful
        return success_count > 0

    def get_optimal_timeframe_order(self, timeframes: List[str]) -> List[str]:
        """Prioritize timeframes by data availability and reliability"""
        priority_order = {
            '1d': 1,   # Most reliable, longest history
            '1h': 2,   # Good balance of detail and availability  
            '4h': 3,   # Less frequent updates needed
            '15m': 4,  # Moderate intraday detail
            '5m': 5,   # Higher frequency, more prone to gaps
            '3m': 6,   # Higher frequency, limited by yfinance
            '1m': 7,   # Highest frequency, most limited history (7 days max)
        }
        return sorted(timeframes, key=lambda tf: priority_order.get(tf, 999))

    def get_timeframe_specific_date_range(self, timeframe: str) -> Tuple[datetime, datetime]:
        """Get optimal date range based on yfinance timeframe limitations"""
        end_date = datetime.now()
        
        # yfinance data availability constraints
        if timeframe == '1m':
            # 1-minute data: only last 7 days available
            start_date = end_date - timedelta(days=7)
        elif timeframe in ['3m', '5m', '15m', '1h', '4h']:
            # Intraday data: only last 60 days available
            start_date = end_date - timedelta(days=60)
        else:  # '1d'
            # Daily data: much longer history available
            start_date = end_date - timedelta(days=365)
        
        return start_date, end_date

    def batch_update_multiple_instruments(self, instruments: List[str], 
                                        timeframes: List[str] = None) -> Dict[str, Dict[str, bool]]:
        """
        Efficiently update multiple instruments across multiple timeframes
        
        Returns:
            Dict mapping instrument -> timeframe -> success_status
        """
        if timeframes is None:
            timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
        
        # Optimize timeframe order for best success rate
        optimized_timeframes = self.get_optimal_timeframe_order(timeframes)
        
        # Calculate estimated time and log progress info
        total_requests = len(instruments) * len(optimized_timeframes)
        estimated_time = total_requests * self.rate_limit_delay
        
        self.logger.info(f"Starting batch update:")
        self.logger.info(f"  - Instruments: {len(instruments)} ({', '.join(instruments)})")
        self.logger.info(f"  - Timeframes: {len(optimized_timeframes)} ({', '.join(optimized_timeframes)})")
        self.logger.info(f"  - Total requests: {total_requests}")
        self.logger.info(f"  - Estimated time: {estimated_time/60:.1f} minutes")
        
        results = {}
        start_time = time.time()
        
        for i, instrument in enumerate(instruments):
            results[instrument] = {}
            self.logger.info(f"\n📊 Processing instrument {i+1}/{len(instruments)}: {instrument}")
            
            for j, timeframe in enumerate(optimized_timeframes):
                request_num = i * len(optimized_timeframes) + j + 1
                progress = request_num / total_requests * 100
                
                self.logger.info(f"  🕐 [{progress:5.1f}%] Fetching {timeframe} data... (request {request_num}/{total_requests})")
                
                try:
                    # Get timeframe-specific date range
                    start_date, end_date = self.get_timeframe_specific_date_range(timeframe)
                    
                    # Fetch data with enhanced retry logic
                    data = self.fetch_ohlc_data(instrument, timeframe, start_date, end_date)
                    
                    if data:
                        # Store in database
                        with FuturesDB() as db:
                            records_inserted = 0
                            for record in data:
                                try:
                                    db.insert_ohlc_data(
                                        record['instrument'],
                                        record['timeframe'],
                                        record['timestamp'], 
                                        record['open_price'],
                                        record['high_price'],
                                        record['low_price'],
                                        record['close_price'],
                                        record['volume']
                                    )
                                    records_inserted += 1
                                except Exception as insert_error:
                                    # Likely duplicate, continue
                                    pass
                        
                        self.logger.info(f"    ✅ Success: {records_inserted} new records")
                        results[instrument][timeframe] = True
                    else:
                        self.logger.warning(f"    ⚠️ No data returned")
                        results[instrument][timeframe] = False
                
                except Exception as e:
                    self.logger.error(f"    ❌ Failed: {e}")
                    results[instrument][timeframe] = False
                
                # Extra delay between instruments to be respectful
                if j == len(optimized_timeframes) - 1 and i < len(instruments) - 1:
                    self.logger.info(f"  🔄 Completed {instrument}, pausing 1s before next instrument...")
                    time.sleep(1.0)
        
        # Summary statistics
        elapsed_time = time.time() - start_time
        total_success = sum(1 for inst_results in results.values() 
                          for success in inst_results.values() if success)
        success_rate = (total_success / total_requests) * 100 if total_requests > 0 else 0
        
        self.logger.info(f"\n🏁 Batch update completed!")
        self.logger.info(f"  - Total time: {elapsed_time/60:.1f} minutes")
        self.logger.info(f"  - Success rate: {success_rate:.1f}% ({total_success}/{total_requests})")
        self.logger.info(f"  - Average time per request: {elapsed_time/total_requests:.1f}s")
        
        return results

    def update_all_active_instruments(self, timeframes: List[str] = None) -> Dict[str, Dict[str, bool]]:
        """
        Update all instruments that have recent trade activity
        
        This is more efficient than updating all possible instruments
        """
        if timeframes is None:
            timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
        
        # Get instruments that have recent trade activity
        with FuturesDB() as db:
            # Get instruments with trades in last 30 days
            recent_date = datetime.now() - timedelta(days=30)
            instruments = db.get_active_instruments_since(recent_date)
        
        if not instruments:
            self.logger.warning("No active instruments found in the last 30 days")
            return {}
        
        self.logger.info(f"Found {len(instruments)} active instruments: {', '.join(instruments)}")
        
        return self.batch_update_multiple_instruments(instruments, timeframes)

# Global instance
ohlc_service = OHLCDataService()