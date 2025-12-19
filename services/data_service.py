"""
OHLC Data Service for Futures Trading Log
Handles fetching, caching, and gap detection for market data
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, timezone
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
    """Intelligent rate limiting for batch-optimized Yahoo Finance API requests

    Features:
    - Exponential backoff for consecutive requests
    - Daily quota tracking to prevent hitting Yahoo limits
    - Adaptive delays based on success/failure rates
    """

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

        # Daily quota tracking
        self.daily_quota_key = "rate_limiter:daily_quota"
        self.daily_quota_limit = self.config.get('daily_quota_limit', 2000)  # Conservative Yahoo limit

        # Progressive backoff state with fixed delay steps
        self.request_count = 0  # Tracks consecutive requests for backoff
        # Delay sequence: 5s, 30s, 2min (120s), 60min (3600s), then cap at 60min
        self.backoff_delays = self.config.get('backoff_delays', [5, 30, 120, 3600])
        self.backoff_max_delay = 3600  # Maximum 60 minutes

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
        self._increment_daily_quota()

    def register_failure(self):
        self._update_window(self.failure_key, time.time())
        self._increment_daily_quota()

    def _increment_daily_quota(self):
        """Increment daily API call counter with automatic daily reset"""
        try:
            # Increment counter
            current_count = self.redis_client.incr(self.daily_quota_key)

            # Set expiration to end of day (UTC) on first increment
            if current_count == 1:
                # Calculate seconds until midnight UTC
                now = datetime.now(timezone.utc)
                midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                seconds_until_midnight = int((midnight - now).total_seconds())
                self.redis_client.expire(self.daily_quota_key, seconds_until_midnight)

            return current_count
        except Exception as e:
            self.logger.warning(f"Failed to update daily quota counter: {e}")
            return 0

    def get_daily_quota_remaining(self) -> int:
        """Get remaining API calls for today"""
        try:
            used = int(self.redis_client.get(self.daily_quota_key) or 0)
            return max(0, self.daily_quota_limit - used)
        except Exception as e:
            self.logger.warning(f"Failed to get daily quota: {e}")
            return self.daily_quota_limit  # Fail open

    def check_daily_quota(self) -> bool:
        """Check if daily quota has been exceeded"""
        remaining = self.get_daily_quota_remaining()
        if remaining <= 0:
            self.logger.error(f"Daily quota exceeded! Limit: {self.daily_quota_limit}")
            return False
        elif remaining < 100:
            self.logger.warning(f"Daily quota running low: {remaining} remaining out of {self.daily_quota_limit}")
        return True

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

    def get_exponential_backoff_delay(self) -> float:
        """Calculate progressive backoff delay based on consecutive request count

        Fixed delay sequence to avoid rate limiting:
          Request 0: 5 seconds
          Request 1: 30 seconds
          Request 2: 2 minutes (120 seconds)
          Request 3+: 60 minutes (3600 seconds)

        This aggressive backoff strategy prevents hitting Yahoo Finance rate limits.
        """
        if self.request_count >= len(self.backoff_delays):
            # Cap at maximum delay for all subsequent requests
            return self.backoff_max_delay
        return self.backoff_delays[self.request_count]

    def enforce(self, use_exponential_backoff: bool = True):
        """Enforce rate limit delay with optional progressive backoff

        Args:
            use_exponential_backoff: If True, uses progressive backoff (5s, 30s, 2m, 60m).
                                    If False, uses standard adaptive delay.
        """
        if use_exponential_backoff:
            delay = self.get_exponential_backoff_delay()
            self.request_count += 1
            delay_display = f"{delay:.0f}s" if delay < 60 else f"{delay/60:.1f}m"
            self.logger.debug(f"Progressive backoff delay: {delay_display} (request #{self.request_count})")
        else:
            delay = self.get_current_delay()

        time.sleep(delay)

    def reset_backoff(self):
        """Reset progressive backoff counter (call after completing a batch of requests)"""
        if self.request_count > 0:
            self.logger.debug(f"Resetting progressive backoff (was at request #{self.request_count})")
        self.request_count = 0

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

    # All 18 Yahoo Finance supported timeframes
    ALL_YAHOO_TIMEFRAMES = [
        '1m', '2m', '5m', '15m', '30m', '60m', '90m',
        '1h', '2h', '4h', '6h', '8h', '12h',
        '1d', '5d', '1wk', '1mo', '3mo'
    ]

    # Priority timeframes (reduces API calls by 67%: from 18 to 6 per instrument)
    # These cover all major trading styles: scalping (1m), day trading (5m, 15m),
    # swing trading (1h, 4h), and long-term analysis (1d)
    PRIORITY_TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d']

    # Historical data retention limits by Yahoo Finance
    HISTORICAL_LIMITS = {
        '1m': 7,      # 7 days
        '2m': 60,     # 60 days
        '5m': 60,
        '15m': 60,
        '30m': 60,
        '60m': 60,
        '90m': 60,
        '1h': 60,
        '2h': 60,
        '4h': 60,
        '6h': 60,
        '8h': 60,
        '12h': 60,
        '1d': 365,    # 365 days
        '5d': 365,
        '1wk': 365,
        '1mo': 365,
        '3mo': 365
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Load configuration for timeframe strategy
        self.use_priority_timeframes = config.use_priority_timeframes
        if self.use_priority_timeframes:
            self.logger.info("Using PRIORITY timeframes (6) - reduces API calls by 67%")
        else:
            self.logger.info("Using ALL timeframes (18) - maximum data coverage")

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

        # REMOVED: self._migrate_instrument_names()
        # Contract-specific OHLC data must be preserved for accurate rollover handling.
        # Different contract months (MNQ SEP25 vs MNQ DEC25) have completely different prices.

    def _migrate_instrument_names(self):
        """DEPRECATED: Do not call - destroys contract-specific data.

        Previously normalized instrument names to base symbols, but this breaks
        contract rollover handling where different months have different prices.
        """
        import warnings
        warnings.warn(
            "_migrate_instrument_names is deprecated - contract-specific OHLC data must be preserved",
            DeprecationWarning
        )
        # Do nothing - preserve contract-specific data

    def _enforce_rate_limit(self):
        """Enforce rate limiting between API requests with progressive backoff (5s, 30s, 2m, 60m)"""
        self.rate_limiter.enforce(use_exponential_backoff=True)

    def _get_base_instrument(self, instrument: str) -> str:
        return symbol_service.get_base_symbol(instrument)

    def _get_yfinance_symbol(self, instrument: str) -> str:
        """Get continuous contract symbol (e.g., MNQ=F) - for backward compatibility"""
        return symbol_service.get_yfinance_symbol(instrument)

    def _get_yfinance_contract_symbol(self, instrument: str) -> str:
        """Get contract-specific symbol (e.g., MNQU25.CME) or continuous if no expiration"""
        return symbol_service.get_yfinance_contract_symbol(instrument)

    def _normalize_for_ohlc_storage(self, instrument: str) -> str:
        """Normalize instrument for OHLC storage - preserves full contract name"""
        return symbol_service.normalize_for_ohlc_storage(instrument)

    def _get_smart_cache_ttl(self, timeframe: str) -> int:
        """Calculate smart cache TTL based on timeframe to reduce API calls

        Longer timeframes get longer cache TTLs since historical data changes less frequently:
        - Intraday (1m-90m): 1 day TTL (data is constantly updating)
        - Hourly (1h-12h): 7 days TTL (moderate update frequency)
        - Daily+ (1d-3mo): 90 days TTL (very stable historical data)

        This aggressive caching significantly reduces Yahoo Finance API calls.
        """
        # Minute timeframes: very short-lived cache
        if timeframe in ['1m', '2m', '5m', '15m', '30m', '60m', '90m']:
            return 1  # 1 day
        # Hourly timeframes: moderate cache
        elif timeframe in ['1h', '2h', '4h', '6h', '8h', '12h']:
            return 7  # 1 week
        # Daily and longer: very long cache
        else:  # 1d, 5d, 1wk, 1mo, 3mo
            return 90  # 90 days (historical data rarely changes)

    def _convert_timeframe_to_yfinance(self, timeframe: str) -> str:
        """Convert internal timeframe to Yahoo Finance interval format

        Supports all 18 Yahoo Finance timeframes:
        - Minute: 1m, 2m, 5m, 15m, 30m, 60m, 90m
        - Hourly: 1h, 2h, 4h, 6h, 8h, 12h
        - Daily+: 1d, 5d, 1wk, 1mo, 3mo
        """
        timeframe_map = {
            '1m': '1m', '2m': '2m', '5m': '5m', '15m': '15m', '30m': '30m',
            '60m': '60m', '90m': '90m',
            '1h': '1h', '2h': '2h', '4h': '4h', '6h': '6h', '8h': '8h', '12h': '12h',
            '1d': '1d', '5d': '5d', '1wk': '1wk', '1mo': '1mo', '3mo': '3mo',
            # Backward compatibility for old '3m' timeframe
            '3m': '5m'
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
            # Use contract-specific symbol (e.g., MNQU25.CME) if expiration present
            yf_symbol = self._get_yfinance_contract_symbol(instrument)
            yf_interval = self._convert_timeframe_to_yfinance(timeframe)

            # Comprehensive API call logging
            self.logger.info(f"═══ Yahoo Finance API Call ═══")
            self.logger.info(f"Instrument: {instrument} → Yahoo Symbol: {yf_symbol}")
            self.logger.info(f"Timeframe: {timeframe} → YF Interval: {yf_interval}")
            self.logger.info(f"Date Range: {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"Request URL: https://query2.finance.yahoo.com/v8/finance/chart/{yf_symbol}")

            # Make API call
            import time
            start_time = time.time()

            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(
                start=start_date, end=end_date, interval=yf_interval, prepost=True
            )

            elapsed_time = time.time() - start_time

            # Log API response details
            self.logger.info(f"═══ Yahoo Finance API Response ═══")
            self.logger.info(f"Response Time: {elapsed_time:.2f}s")
            self.logger.info(f"Response Type: {type(data).__name__}")
            self.logger.info(f"Response Shape: {data.shape if hasattr(data, 'shape') else 'N/A'}")
            self.logger.info(f"Is Empty: {data.empty}")

            if not data.empty:
                self.logger.info(f"Columns: {list(data.columns)}")
                self.logger.info(f"Date Range in Response: {data.index[0]} to {data.index[-1]}")
                self.logger.info(f"Sample Data (first row): Open={data.iloc[0]['Open']:.2f}, Close={data.iloc[0]['Close']:.2f}, Volume={data.iloc[0]['Volume']:.0f}")

            if data.empty:
                self.logger.warning(f"❌ No data returned for {instrument} {timeframe}")
                self.logger.warning(f"Possible reasons: Symbol delisted, incorrect format, API rate limit, or market closed")
                return []
            
            ohlc_records = []
            # Store with full contract name (e.g., "MNQ SEP25") to keep contract-specific data separate
            # This is critical for contract rollover - different months have different prices
            storage_instrument = symbol_service.normalize_for_ohlc_storage(instrument)
            for timestamp, row in data.iterrows():
                unix_timestamp = int(timestamp.timestamp())
                record = {
                    'instrument': storage_instrument,
                    'timeframe': timeframe,
                    'timestamp': unix_timestamp,
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': int(row['Volume']) if pd.notna(row['Volume']) else None
                }
                ohlc_records.append(record)
            
            # Validate the fetched data quality
            validated_records = self.validate_ohlc_data(ohlc_records)

            if len(validated_records) != len(ohlc_records):
                self.logger.warning(f"Data validation filtered {len(ohlc_records) - len(validated_records)} invalid records")

            self.logger.info(f"✅ Successfully fetched and validated {len(validated_records)} records for {instrument}")
            self.logger.info(f"═══════════════════════════════")
            return validated_records

        except Exception as e:
            self.logger.error(f"═══ Yahoo Finance API Error ═══")
            self.logger.error(f"Exception Type: {type(e).__name__}")
            self.logger.error(f"Exception Message: {str(e)}")
            self.logger.error(f"Instrument: {instrument} ({yf_symbol if 'yf_symbol' in locals() else 'N/A'})")
            self.logger.error(f"Timeframe: {timeframe} ({yf_interval if 'yf_interval' in locals() else 'N/A'})")

            # Log traceback for debugging
            import traceback
            self.logger.error(f"Traceback:\n{traceback.format_exc()}")
            self.logger.error(f"═══════════════════════════════")
            return []

    def get_market_holidays(self, year: int) -> List[datetime]:
        """Get major US market holidays that affect futures trading"""
        import calendar

        holidays = []

        # New Year's Day
        holidays.append(datetime(year, 1, 1))

        # Martin Luther King Jr. Day (3rd Monday in January)
        jan_1 = datetime(year, 1, 1)
        days_to_monday = (7 - jan_1.weekday()) % 7
        first_monday_jan = jan_1 + timedelta(days=days_to_monday)
        mlk_day = first_monday_jan + timedelta(weeks=2)
        holidays.append(mlk_day)

        # Presidents Day (3rd Monday in February)
        feb_1 = datetime(year, 2, 1)
        days_to_monday = (7 - feb_1.weekday()) % 7
        first_monday_feb = feb_1 + timedelta(days=days_to_monday)
        presidents_day = first_monday_feb + timedelta(weeks=2)
        holidays.append(presidents_day)

        # Good Friday (Friday before Easter)
        easter = self._calculate_easter(year)
        good_friday = easter - timedelta(days=2)
        holidays.append(good_friday)

        # Memorial Day (last Monday in May)
        may_31 = datetime(year, 5, 31)
        days_back_to_monday = (may_31.weekday() - 0) % 7
        memorial_day = may_31 - timedelta(days=days_back_to_monday)
        holidays.append(memorial_day)

        # Independence Day
        july_4 = datetime(year, 7, 4)
        if july_4.weekday() == 5:  # Saturday
            holidays.append(july_4 - timedelta(days=1))  # Friday
        elif july_4.weekday() == 6:  # Sunday
            holidays.append(july_4 + timedelta(days=1))  # Monday
        else:
            holidays.append(july_4)

        # Labor Day (1st Monday in September)
        sep_1 = datetime(year, 9, 1)
        days_to_monday = (7 - sep_1.weekday()) % 7
        labor_day = sep_1 + timedelta(days=days_to_monday)
        holidays.append(labor_day)

        # Thanksgiving (4th Thursday in November)
        nov_1 = datetime(year, 11, 1)
        days_to_thursday = (3 - nov_1.weekday()) % 7
        first_thursday_nov = nov_1 + timedelta(days=days_to_thursday)
        thanksgiving = first_thursday_nov + timedelta(weeks=3)
        holidays.append(thanksgiving)

        # Christmas
        christmas = datetime(year, 12, 25)
        if christmas.weekday() == 5:  # Saturday
            holidays.append(christmas - timedelta(days=1))  # Friday
        elif christmas.weekday() == 6:  # Sunday
            holidays.append(christmas + timedelta(days=1))  # Monday
        else:
            holidays.append(christmas)

        return holidays

    def _calculate_easter(self, year: int) -> datetime:
        """Calculate Easter date using simple algorithm"""
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        return datetime(year, month, day)

    def is_market_holiday(self, timestamp: datetime) -> bool:
        """Check if the given date is a market holiday"""
        date_only = timestamp.date()
        year = timestamp.year

        holidays = self.get_market_holidays(year)
        if timestamp.month == 12:  # Also check next year's holidays
            holidays.extend(self.get_market_holidays(year + 1))

        holiday_dates = [h.date() for h in holidays]
        return date_only in holiday_dates

    def is_market_open(self, timestamp: datetime) -> bool:
        """Check if market is open at given time with holiday awareness"""
        if self.is_market_holiday(timestamp):
            return False

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

    def is_trading_session_active(self, timestamp: datetime) -> bool:
        """More granular check for active trading sessions including pre/post market"""
        if self.is_market_holiday(timestamp):
            return False

        weekday = timestamp.weekday()
        hour_utc = timestamp.hour

        # Extended trading hours for futures (almost 24/5)
        if weekday == 5:  # Saturday - closed
            return False
        elif weekday == 6:  # Sunday - opens at 5 PM ET (22 UTC)
            return hour_utc >= 22
        elif weekday <= 3:  # Monday-Thursday
            # Closed only during brief maintenance window
            return not (21 <= hour_utc < 22)
        elif weekday == 4:  # Friday - closes at 4 PM ET (21 UTC)
            return hour_utc < 21

        return True

    def get_expected_freshness_window(self, timeframe: str) -> int:
        """Get expected data freshness window in seconds for different timeframes

        Supports all 18 Yahoo Finance timeframes
        """
        freshness_windows = {
            '1m': 300,      # 5 minutes
            '2m': 600,      # 10 minutes
            '3m': 600,      # 10 minutes (backward compatibility)
            '5m': 900,      # 15 minutes
            '15m': 1800,    # 30 minutes
            '30m': 3600,    # 1 hour
            '60m': 7200,    # 2 hours
            '90m': 7200,    # 2 hours
            '1h': 7200,     # 2 hours
            '2h': 14400,    # 4 hours
            '4h': 14400,    # 4 hours
            '6h': 21600,    # 6 hours
            '8h': 28800,    # 8 hours
            '12h': 43200,   # 12 hours
            '1d': 86400,    # 1 day
            '5d': 432000,   # 5 days
            '1wk': 604800,  # 1 week
            '1mo': 2592000, # 30 days
            '3mo': 7776000  # 90 days
        }
        return freshness_windows.get(timeframe, 1800)  # Default 30 minutes

    def detect_missing_recent_data(self, instrument: str, timeframe: str) -> bool:
        """Detect if recent data is missing or stale beyond expected freshness window"""
        try:
            current_time = datetime.now()
            freshness_window = self.get_expected_freshness_window(timeframe)

            with FuturesDB() as db:
                # Get the latest timestamp for this instrument/timeframe
                latest_data = db.get_latest_ohlc_timestamp(instrument, timeframe)

                if not latest_data:
                    self.logger.warning(f"No existing data found for {instrument} {timeframe}")
                    return True  # Missing all data

                latest_timestamp = latest_data
                latest_datetime = datetime.fromtimestamp(latest_timestamp)
                time_since_last = (current_time - latest_datetime).total_seconds()

                # Only consider it stale if market should be open
                if self.is_trading_session_active(current_time) and time_since_last > freshness_window:
                    self.logger.warning(f"Stale data detected for {instrument} {timeframe}: "
                                      f"Latest data from {latest_datetime}, {time_since_last/60:.1f} minutes ago")
                    return True

                return False

        except Exception as e:
            self.logger.error(f"Error detecting missing recent data for {instrument} {timeframe}: {e}")
            return False

    def check_data_health(self, instruments: List[str], timeframes: List[str] = None) -> Dict[str, Dict[str, Dict]]:
        """Check overall data health for instruments and timeframes"""
        if timeframes is None:
            timeframes = ['1m', '5m', '15m', '1h', '1d']

        health_report = {}

        for instrument in instruments:
            health_report[instrument] = {}

            for timeframe in timeframes:
                try:
                    with FuturesDB() as db:
                        # Get latest timestamp
                        latest_timestamp = db.get_latest_ohlc_timestamp(instrument, timeframe)

                        if not latest_timestamp:
                            health_report[instrument][timeframe] = {
                                'status': 'no_data',
                                'latest_data': None,
                                'staleness_minutes': None,
                                'is_stale': True
                            }
                            continue

                        latest_datetime = datetime.fromtimestamp(latest_timestamp)
                        current_time = datetime.now()
                        staleness_seconds = (current_time - latest_datetime).total_seconds()
                        staleness_minutes = staleness_seconds / 60

                        # Check if data is stale
                        freshness_window = self.get_expected_freshness_window(timeframe)
                        is_stale = staleness_seconds > freshness_window and self.is_market_open(current_time)

                        if is_stale:
                            status = 'stale'
                        elif staleness_minutes < 60:
                            status = 'healthy'
                        else:
                            status = 'aging'

                        health_report[instrument][timeframe] = {
                            'status': status,
                            'latest_data': latest_datetime.isoformat(),
                            'staleness_minutes': round(staleness_minutes, 1),
                            'is_stale': is_stale
                        }

                except Exception as e:
                    health_report[instrument][timeframe] = {
                        'status': 'error',
                        'error': str(e),
                        'is_stale': True
                    }

        return health_report

    def validate_ohlc_data(self, ohlc_records: List[Dict]) -> List[Dict]:
        """Validate OHLC data quality and filter out invalid records"""
        if not ohlc_records:
            return []

        valid_records = []
        validation_errors = []

        for i, record in enumerate(ohlc_records):
            errors = []

            # Basic OHLC validation
            open_price = record.get('open')
            high_price = record.get('high')
            low_price = record.get('low')
            close_price = record.get('close')
            volume = record.get('volume')

            # Check for None or invalid prices
            if any(price is None or price <= 0 for price in [open_price, high_price, low_price, close_price]):
                errors.append("Invalid or missing OHLC prices")

            # Check OHLC relationships
            if open_price and high_price and low_price and close_price:
                if high_price < max(open_price, close_price):
                    errors.append(f"High ({high_price}) < max(Open({open_price}), Close({close_price}))")

                if low_price > min(open_price, close_price):
                    errors.append(f"Low ({low_price}) > min(Open({open_price}), Close({close_price}))")

                if high_price < low_price:
                    errors.append(f"High ({high_price}) < Low ({low_price})")

            # Volume validation
            if volume is not None and volume < 0:
                errors.append(f"Negative volume: {volume}")

            # Price continuity check (if not first record)
            if i > 0 and valid_records:
                prev_record = valid_records[-1]
                prev_close = prev_record.get('close')

                if prev_close and open_price:
                    # Check for unrealistic price gaps (>20% change)
                    price_change_pct = abs(open_price - prev_close) / prev_close * 100
                    if price_change_pct > 20:
                        errors.append(f"Large price gap: {price_change_pct:.1f}% from previous close")

            # Outlier detection (basic)
            if open_price and high_price and low_price and close_price:
                # Check for unrealistic intraday volatility (>15%)
                daily_range = (high_price - low_price) / ((high_price + low_price) / 2) * 100
                if daily_range > 15:
                    errors.append(f"Extreme intraday volatility: {daily_range:.1f}%")

            if errors:
                validation_errors.append({
                    'index': i,
                    'timestamp': record.get('timestamp'),
                    'errors': errors,
                    'record': record
                })
                self.logger.warning(f"OHLC validation failed for record {i}: {'; '.join(errors)}")
            else:
                valid_records.append(record)

        if validation_errors:
            self.logger.warning(f"Filtered out {len(validation_errors)} invalid records from {len(ohlc_records)} total")

        return valid_records

    def validate_data_consistency(self, instrument: str, timeframe: str,
                                 new_records: List[Dict]) -> Dict[str, any]:
        """Validate consistency of new data with existing database records"""
        validation_results = {
            'is_valid': True,
            'warnings': [],
            'errors': [],
            'duplicate_count': 0,
            'gap_count': 0
        }

        if not new_records:
            return validation_results

        try:
            with FuturesDB() as db:
                # Check for duplicates
                duplicates = 0
                for record in new_records:
                    timestamp = record.get('timestamp')
                    existing = db.execute_query(
                        "SELECT COUNT(*) FROM ohlc_data WHERE instrument = ? AND timeframe = ? AND timestamp = ?",
                        (instrument, timeframe, timestamp)
                    )
                    if existing and existing[0][0] > 0:
                        duplicates += 1

                validation_results['duplicate_count'] = duplicates
                if duplicates > 0:
                    validation_results['warnings'].append(f"{duplicates} duplicate timestamps detected")

                # Check for temporal consistency
                sorted_records = sorted(new_records, key=lambda x: x['timestamp'])

                # Get expected interval in seconds
                interval_seconds = self._get_timeframe_seconds(timeframe)

                gaps = 0
                for i in range(1, len(sorted_records)):
                    time_diff = sorted_records[i]['timestamp'] - sorted_records[i-1]['timestamp']
                    expected_diff = interval_seconds

                    # Allow some tolerance for irregular intervals
                    if time_diff > expected_diff * 1.5:
                        gaps += 1

                validation_results['gap_count'] = gaps
                if gaps > 0:
                    validation_results['warnings'].append(f"{gaps} temporal gaps detected in new data")

                # Price consistency check with existing data
                if sorted_records:
                    first_timestamp = sorted_records[0]['timestamp']

                    # Get the last record before our new data
                    previous_record = db.execute_query("""
                        SELECT open_price, high_price, low_price, close_price, timestamp
                        FROM ohlc_data
                        WHERE instrument = ? AND timeframe = ? AND timestamp < ?
                        ORDER BY timestamp DESC LIMIT 1
                    """, (instrument, timeframe, first_timestamp))

                    if previous_record and previous_record[0]:
                        prev_close = previous_record[0][3]  # close_price
                        first_open = sorted_records[0]['open_price']

                        if prev_close and first_open:
                            price_gap_pct = abs(first_open - prev_close) / prev_close * 100
                            if price_gap_pct > 10:
                                validation_results['warnings'].append(
                                    f"Large price gap: {price_gap_pct:.1f}% between existing and new data"
                                )

        except Exception as e:
            validation_results['is_valid'] = False
            validation_results['errors'].append(f"Validation error: {str(e)}")

        return validation_results

    def _get_timeframe_seconds(self, timeframe: str) -> int:
        """Convert timeframe to seconds

        Supports all 18 Yahoo Finance timeframes
        """
        timeframe_map = {
            '1m': 60,
            '2m': 120,
            '5m': 300,
            '15m': 900,
            '30m': 1800,
            '60m': 3600,
            '90m': 5400,
            '1h': 3600,
            '2h': 7200,
            '4h': 14400,
            '6h': 21600,
            '8h': 28800,
            '12h': 43200,
            '1d': 86400,
            '5d': 432000,
            '1wk': 604800,
            '1mo': 2592000,  # Approximate (30 days)
            '3mo': 7776000,  # Approximate (90 days)
            # Backward compatibility
            '3m': 180
        }
        return timeframe_map.get(timeframe, 3600)

    def detect_and_fill_gaps(self, instrument: str, timeframe: str,
                           start_date: datetime, end_date: datetime) -> bool:
        """Detect gaps in OHLC data and fill them intelligently with recent data prioritization"""
        try:
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())

            # First check for missing recent data
            has_stale_data = self.detect_missing_recent_data(instrument, timeframe)

            with FuturesDB() as db:
                # Find historical gaps in existing data
                gaps = db.find_ohlc_gaps(instrument, timeframe, start_timestamp, end_timestamp)

                # If we have stale recent data, add a gap from latest data to now
                if has_stale_data:
                    latest_timestamp = db.get_latest_ohlc_timestamp(instrument, timeframe)
                    if latest_timestamp:
                        current_timestamp = int(datetime.now().timestamp())
                        # Add gap from latest data to current time
                        gaps.append((latest_timestamp, current_timestamp))
                        self.logger.info(f"Added recent data gap for {instrument} {timeframe}: "
                                       f"{datetime.fromtimestamp(latest_timestamp)} to {datetime.fromtimestamp(current_timestamp)}")

                if not gaps:
                    self.logger.info(f"No gaps found for {instrument} {timeframe}")
                    return True

                self.logger.info(f"Found {len(gaps)} gaps for {instrument} {timeframe}")

                # Sort gaps by priority (recent gaps first)
                gaps_with_priority = []
                current_time = datetime.now().timestamp()
                for gap_start_ts, gap_end_ts in gaps:
                    # Priority: recent gaps get higher priority (lower number)
                    priority = current_time - gap_end_ts
                    gaps_with_priority.append((priority, gap_start_ts, gap_end_ts))

                # Sort by priority (recent gaps first)
                gaps_with_priority.sort()

                for priority, gap_start_ts, gap_end_ts in gaps_with_priority:
                    gap_start_dt = datetime.fromtimestamp(gap_start_ts)
                    gap_end_dt = datetime.fromtimestamp(gap_end_ts)

                    # Skip gaps during market closure
                    if not self.is_market_open(gap_start_dt):
                        continue

                    self.logger.info(f"Filling gap: {gap_start_dt} to {gap_end_dt}")

                    gap_data = self.fetch_ohlc_data(instrument, timeframe, gap_start_dt, gap_end_dt)

                    if gap_data:
                        # Validate data consistency before insertion
                        consistency_check = self.validate_data_consistency(instrument, timeframe, gap_data)

                        if consistency_check['errors']:
                            self.logger.error(f"Data consistency validation failed: {consistency_check['errors']}")
                            continue

                        if consistency_check['warnings']:
                            for warning in consistency_check['warnings']:
                                self.logger.warning(f"Data consistency warning: {warning}")

                        # Insert validated data
                        inserted_count = 0
                        for record in gap_data:
                            try:
                                db.insert_ohlc_data(
                                    record['instrument'], record['timeframe'], record['timestamp'],
                                    record['open_price'], record['high_price'], record['low_price'],
                                    record['close_price'], record['volume']
                                )
                                inserted_count += 1
                            except Exception as e:
                                self.logger.warning(f"Failed to insert record: {e}")

                        self.logger.info(f"Inserted {inserted_count} validated records for gap {gap_start_dt} to {gap_end_dt}")

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

            # Check for stale data and trigger automatic gap filling if needed
            if self.detect_missing_recent_data(instrument, timeframe):
                self.logger.info(f"Triggering automatic gap fill for stale data: {instrument} {timeframe}")
                # Fill gaps for the last day to catch up
                gap_start = datetime.now() - timedelta(days=1)
                gap_end = datetime.now()
                self.detect_and_fill_gaps(instrument, timeframe, gap_start, gap_end)

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
        # Priority order: 1m FIRST since it has only 7 days of availability from Yahoo Finance
        # If we don't fetch it early, aggressive backoff may prevent it from being fetched at all
        priority_order = {'1m': 1, '5m': 2, '15m': 3, '1h': 4, '4h': 5, '1d': 6, '3m': 7}
        return sorted(timeframes, key=lambda tf: priority_order.get(tf, 999))

    def get_timeframe_specific_date_range(self, timeframe: str) -> Tuple[datetime, datetime]:
        """Get date range based on Yahoo Finance timeframe limits

        Applies appropriate historical limits for each timeframe
        """
        end_date = datetime.now()
        days_limit = self.HISTORICAL_LIMITS.get(timeframe, 365)
        start_date = end_date - timedelta(days=days_limit)
        return start_date, end_date

    def batch_update_multiple_instruments(self, instruments: List[str],
                                        timeframes: List[str] = None) -> Dict[str, Dict[str, bool]]:
        if timeframes is None:
            timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']

        # Filter out expired contracts
        instruments = symbol_service.filter_active_contracts(instruments)
        if not instruments:
            self.logger.info("No active contracts to update after filtering expired ones")
            return {}

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

        # Filter out expired contracts (batch_update also filters, but log here for visibility)
        original_count = len(instruments)
        instruments = symbol_service.filter_active_contracts(instruments)
        if original_count > len(instruments):
            self.logger.info(f"Filtered {original_count - len(instruments)} expired contracts from active instruments")

        if not instruments:
            self.logger.info("No active non-expired contracts to update")
            return {}

        return self.batch_update_multiple_instruments(instruments, timeframes)

    def get_all_yahoo_timeframes(self) -> List[str]:
        """Get list of all supported Yahoo Finance timeframes

        Returns:
            List of all 18 Yahoo Finance timeframe strings
        """
        return self.ALL_YAHOO_TIMEFRAMES.copy()

    def get_priority_timeframes(self) -> List[str]:
        """Get list of priority timeframes (reduces API calls by 67%)

        Priority timeframes cover all major trading styles while minimizing Yahoo Finance API calls:
        - 1m: Scalping and tick analysis
        - 5m: Day trading standard
        - 15m: Swing trading entries
        - 1h: Position building
        - 4h: Trend analysis
        - 1d: Long-term charting

        Returns:
            List of 6 priority timeframe strings
        """
        return self.PRIORITY_TIMEFRAMES.copy()

    def _get_fetch_window(self, timeframe: str) -> Tuple[datetime, datetime]:
        """Calculate appropriate fetch window based on Yahoo Finance limits

        Args:
            timeframe: Timeframe string (e.g., '1m', '1h', '1d')

        Returns:
            Tuple of (start_date, end_date) for fetching data
        """
        end_date = datetime.now()
        days_limit = self.HISTORICAL_LIMITS.get(timeframe, 365)
        start_date = end_date - timedelta(days=days_limit)
        return start_date, end_date

    def _sync_instrument(self, instrument: str, timeframes: List[str]) -> Dict[str, any]:
        """Sync all timeframes for a single instrument with automatic 365-day backfill

        Detects zero-record instruments and triggers automatic backfill for up to 365 days
        of historical data (respecting Yahoo Finance API limits per timeframe).

        Args:
            instrument: Yahoo Finance symbol (e.g., 'NQ=F')
            timeframes: List of timeframes to sync

        Returns:
            Dictionary with sync statistics including backfill metrics
        """
        stats = {
            'instrument': instrument,
            'timeframes_synced': 0,
            'timeframes_failed': 0,
            'candles_added': 0,
            'api_calls': 0,
            'errors': [],
            'backfilled_timeframes': []
        }

        self.logger.info(f"Syncing {instrument} for {len(timeframes)} timeframes...")
        base_instrument = self._get_base_instrument(instrument)

        for timeframe in timeframes:
            try:
                # Check if zero records exist for this instrument/timeframe (triggers backfill)
                with FuturesDB() as db:
                    record_count = db.get_ohlc_count(base_instrument, timeframe)

                is_backfill = record_count == 0

                if is_backfill:
                    # BACKFILL MODE: Zero records detected - fetch 365 days (respecting API limits)
                    days_limit = self.HISTORICAL_LIMITS.get(timeframe, 365)
                    actual_backfill_days = min(365, days_limit)
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=actual_backfill_days)

                    self.logger.info(
                        f"BACKFILL: Zero records detected for {base_instrument} {timeframe} - "
                        f"fetching {actual_backfill_days} days (API limit: {days_limit}d)"
                    )
                    self.logger.info(
                        f"BACKFILL: Date range {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
                    )

                    stats['backfilled_timeframes'].append(timeframe)
                else:
                    # NORMAL SYNC MODE: Records exist - use standard fetch window
                    start_date, end_date = self._get_fetch_window(timeframe)
                    self.logger.debug(f"  {timeframe}: Normal sync ({record_count} existing records)")

                # Fetch OHLC data (same flow for both backfill and normal sync)
                data = self.fetch_ohlc_data(instrument, timeframe, start_date, end_date)
                stats['api_calls'] += 1

                if data:
                    # Insert into database using batch optimization
                    inserted_count = 0
                    with FuturesDB() as db:
                        for record in data:
                            try:
                                db.insert_ohlc_data(
                                    record['instrument'], record['timeframe'], record['timestamp'],
                                    record['open_price'], record['high_price'], record['low_price'],
                                    record['close_price'], record['volume']
                                )
                                inserted_count += 1
                            except Exception as e:
                                # Skip duplicates silently
                                pass

                        # Update cache if cache service available with smart TTL
                        if self.cache_service and data:
                            start_ts = int(start_date.timestamp())
                            end_ts = int(end_date.timestamp())
                            smart_ttl = self._get_smart_cache_ttl(timeframe)
                            self.cache_service.cache_ohlc_data(
                                base_instrument, timeframe, start_ts, end_ts,
                                data, ttl_days=smart_ttl
                            )

                    stats['candles_added'] += inserted_count
                    stats['timeframes_synced'] += 1

                    if is_backfill:
                        self.logger.info(
                            f"BACKFILL COMPLETE: {inserted_count} candles added for {base_instrument} {timeframe}"
                        )
                    else:
                        self.logger.debug(f"  {timeframe}: {inserted_count} candles added")
                else:
                    log_msg = f"  {timeframe}: No data returned"
                    if is_backfill:
                        log_msg = f"BACKFILL: No data available for {base_instrument} {timeframe}"
                    self.logger.warning(log_msg)
                    stats['timeframes_failed'] += 1

                # Exponential backoff between timeframe requests to avoid rate limiting
                # This increases delay progressively: 2s, 3s, 4.5s, 6.75s, etc.
                # No delay needed - enforce() is called in fetch_ohlc_data before each API call

            except Exception as e:
                error_msg = f"{timeframe}: {str(e)}"
                stats['errors'].append(error_msg)
                stats['timeframes_failed'] += 1
                self.logger.error(f"  Failed to sync {instrument} {timeframe}: {e}")

        return stats

    def sync_instruments(self, instruments: List[str], timeframes: List[str] = None,
                        reason: str = "manual", use_priority_timeframes: bool = None) -> Dict[str, any]:
        """Sync OHLC data for multiple instruments across timeframes

        Args:
            instruments: List of Yahoo Finance symbols (e.g., ['NQ=F', 'ES=F'])
            timeframes: List of timeframes to sync (defaults based on configuration)
            reason: Reason for sync (for logging)
            use_priority_timeframes: If True, use 6 priority timeframes; if False, use all 18;
                                   if None (default), read from config (OHLC_USE_PRIORITY_TIMEFRAMES)

        Returns:
            Dictionary with comprehensive sync statistics
        """
        # Filter out expired contracts to avoid wasting API calls
        original_count = len(instruments)
        instruments = symbol_service.filter_active_contracts(instruments)
        expired_count = original_count - len(instruments)

        if expired_count > 0:
            self.logger.info(f"Skipped {expired_count} expired contracts (keeping historical data, no new syncs)")

        if not instruments:
            self.logger.info("No active contracts to sync after filtering expired ones")
            return {
                'reason': reason,
                'instruments_total': original_count,
                'instruments_expired': expired_count,
                'instruments_synced': 0,
                'candles_added': 0,
                'message': 'All contracts have expired'
            }

        # Determine which timeframes to use
        if timeframes is None:
            # Use parameter if provided, otherwise fall back to config
            should_use_priority = use_priority_timeframes if use_priority_timeframes is not None else self.use_priority_timeframes
            timeframes = self.get_priority_timeframes() if should_use_priority else self.get_all_yahoo_timeframes()

        # Check daily quota before starting sync
        if not self.rate_limiter.check_daily_quota():
            quota_remaining = self.rate_limiter.get_daily_quota_remaining()
            return {
                'reason': reason,
                'error': 'Daily quota exceeded',
                'quota_remaining': quota_remaining,
                'instruments_total': len(instruments),
                'instruments_synced': 0,
                'timeframes_synced': 0,
                'candles_added': 0
            }

        sync_start = datetime.now()
        self.logger.info(f"=== Starting OHLC Sync ===")
        self.logger.info(f"Reason: {reason}")
        self.logger.info(f"Instruments: {len(instruments)} ({', '.join(instruments)})")
        self.logger.info(f"Timeframes: {len(timeframes)} ({', '.join(timeframes)})")
        if len(timeframes) == 6:
            self.logger.info(f"Using PRIORITY timeframes (67% fewer API calls than all 18)")
        else:
            self.logger.info(f"Using {'CUSTOM' if len(timeframes) not in [6, 18] else 'ALL'} timeframes")

        # Log quota status
        quota_remaining = self.rate_limiter.get_daily_quota_remaining()
        self.logger.info(f"Daily quota remaining: {quota_remaining} / {self.rate_limiter.daily_quota_limit}")

        overall_stats = {
            'reason': reason,
            'start_time': sync_start.isoformat(),
            'instruments_total': original_count,
            'instruments_expired': expired_count,
            'instruments_active': len(instruments),
            'instruments_synced': 0,
            'instruments_failed': 0,
            'timeframes_synced': 0,
            'timeframes_failed': 0,
            'candles_added': 0,
            'api_calls': 0,
            'duration_seconds': 0,
            'instrument_details': []
        }

        for instrument in instruments:
            try:
                instrument_stats = self._sync_instrument(instrument, timeframes)
                overall_stats['instrument_details'].append(instrument_stats)
                overall_stats['instruments_synced'] += 1
                overall_stats['timeframes_synced'] += instrument_stats['timeframes_synced']
                overall_stats['timeframes_failed'] += instrument_stats['timeframes_failed']
                overall_stats['candles_added'] += instrument_stats['candles_added']
                overall_stats['api_calls'] += instrument_stats['api_calls']

                if instrument_stats['timeframes_failed'] > 0:
                    self.logger.warning(f"Completed {instrument} with {instrument_stats['timeframes_failed']} failures")
                else:
                    self.logger.info(f"Completed {instrument}: {instrument_stats['candles_added']} candles")

                # Reset exponential backoff counter after completing an instrument
                self.rate_limiter.reset_backoff()

            except Exception as e:
                overall_stats['instruments_failed'] += 1
                self.logger.error(f"Failed to sync instrument {instrument}: {e}")
                # Reset backoff even on failure to start fresh for next instrument
                self.rate_limiter.reset_backoff()

        sync_end = datetime.now()
        overall_stats['duration_seconds'] = (sync_end - sync_start).total_seconds()
        overall_stats['end_time'] = sync_end.isoformat()

        # Log comprehensive summary
        self._log_sync_summary(overall_stats)

        return overall_stats

    def _log_sync_summary(self, stats: Dict[str, any]):
        """Log comprehensive sync summary

        Args:
            stats: Statistics dictionary from sync_instruments()
        """
        self.logger.info("=== OHLC Sync Complete ===")
        self.logger.info(f"Reason: {stats['reason']}")
        self.logger.info(f"Duration: {stats['duration_seconds']:.1f}s")
        self.logger.info(f"Instruments: {stats['instruments_synced']}/{stats['instruments_total']} succeeded, "
                        f"{stats['instruments_failed']} failed")
        self.logger.info(f"Timeframes: {stats['timeframes_synced']} succeeded, "
                        f"{stats['timeframes_failed']} failed")
        self.logger.info(f"Candles Added: {stats['candles_added']}")
        self.logger.info(f"API Calls: {stats['api_calls']}")

        if stats['instruments_failed'] > 0 or stats['timeframes_failed'] > 0:
            self.logger.warning("⚠️  Sync completed with failures - check logs for details")
        else:
            self.logger.info("✓ Sync completed successfully")

# Global instance
ohlc_service = OHLCDataService()

