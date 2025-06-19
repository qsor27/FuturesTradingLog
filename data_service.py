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
from TradingLog_db import FuturesDB
from config import config
from redis_cache_service import get_cache_service

class OHLCDataService:
    """Service for managing OHLC market data with gap detection and backfilling"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.rate_limit_delay = 1.0  # 1 second between requests to be respectful
        self.last_request_time = 0
        
        # Initialize cache service if enabled
        self.cache_service = get_cache_service() if config.cache_enabled else None
        if self.cache_service:
            self.logger.info("Redis cache service initialized")
        else:
            self.logger.info("Cache service disabled or unavailable")
        
        # Futures symbol mapping - yfinance symbols for major futures
        self.symbol_mapping = {
            'MNQ': 'NQ=F',     # Micro Nasdaq-100
            'NQ': 'NQ=F',      # Nasdaq-100  
            'MES': 'ES=F',     # Micro S&P 500
            'ES': 'ES=F',      # S&P 500
            'YM': 'YM=F',      # Dow Jones
            'MYM': 'YM=F',     # Micro Dow Jones
            'RTY': 'RTY=F',    # Russell 2000
            'M2K': 'RTY=F',    # Micro Russell 2000
            'CL': 'CL=F',      # Crude Oil
            'GC': 'GC=F',      # Gold
            'SI': 'SI=F',      # Silver
            'ZN': 'ZN=F',      # 10-Year Treasury Note
            'ZB': 'ZB=F',      # 30-Year Treasury Bond
        }
        
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
        return instrument.split()[0]
    
    def _get_yfinance_symbol(self, instrument: str) -> str:
        """Convert instrument symbol to yfinance symbol"""
        # Handle expiration dates (e.g., "MNQ SEP25" -> "MNQ")
        base_symbol = self._get_base_instrument(instrument)
        return self.symbol_mapping.get(base_symbol, f"{base_symbol}=F")

    def _convert_timeframe_to_yfinance(self, timeframe: str) -> str:
        """Convert our timeframe format to yfinance interval"""
        timeframe_map = {
            '1m': '1m',
            '5m': '5m', 
            '15m': '15m',
            '1h': '1h',
            '4h': '4h',
            '1d': '1d'
        }
        return timeframe_map.get(timeframe, '1m')

    def fetch_ohlc_data(self, instrument: str, timeframe: str, 
                       start_date: datetime, end_date: datetime) -> List[Dict]:
        """Fetch OHLC data from yfinance with rate limiting"""
        try:
            self._enforce_rate_limit()
            
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
            
            # Try cache first if enabled
            if self.cache_service:
                cached_data = self.cache_service.get_cached_ohlc_data(
                    instrument, timeframe, start_timestamp, end_timestamp
                )
                if cached_data:
                    self.logger.debug(f"Returning cached data for {instrument} {timeframe}")
                    return cached_data
            
            # Try to get data using exact instrument name first
            with FuturesDB() as db:
                data = db.get_ohlc_data(instrument, timeframe, start_timestamp, end_timestamp, limit=None)
                
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
            timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        
        try:
            # Get data for last 7 days to ensure we catch up
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            for timeframe in timeframes:
                self.logger.info(f"Updating {instrument} {timeframe} data")
                
                # Fetch and store recent data
                recent_data = self.fetch_ohlc_data(instrument, timeframe, start_date, end_date)
                
                with FuturesDB() as db:
                    for record in recent_data:
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
                
                self.logger.info(f"Updated {len(recent_data)} records for {instrument} {timeframe}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating recent data: {e}")
            return False

# Global instance
ohlc_service = OHLCDataService()