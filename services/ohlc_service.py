"""
OHLC Data Service for on-demand data fetching
"""
import yfinance as yf
import pandas as pd
import logging
from datetime import datetime
from typing import List, Dict
from TradingLog_db import FuturesDB
from config import SUPPORTED_TIMEFRAMES, YFINANCE_TIMEFRAME_MAP
from utils.instrument_utils import get_root_symbol
from symbol_service import symbol_service

logger = logging.getLogger(__name__)

class OHLCOnDemandService:
    """Service for fetching OHLC data on-demand when not available in database"""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.logger = logger

    def fetch_and_store_ohlc(self, instrument: str) -> bool:
        """
        Fetches OHLC data for all supported timeframes for a given instrument,
        normalizes its symbol, and stores the data in the database.
        
        Returns True if any data was successfully fetched and stored.
        """
        root_symbol = get_root_symbol(instrument)
        yf_symbol = symbol_service.get_yfinance_symbol(root_symbol)
        
        self.logger.info(f"Starting OHLC data fetch for instrument '{instrument}' -> '{root_symbol}' (yfinance: '{yf_symbol}')")
        
        success_count = 0
        total_records = 0
        
        for timeframe in SUPPORTED_TIMEFRAMES:
            yf_interval = YFINANCE_TIMEFRAME_MAP.get(timeframe)
            if not yf_interval:
                continue

            try:
                # Determine appropriate period based on timeframe
                if 'm' in timeframe:
                    period = "60d"  # 60 days for minute data
                elif 'h' in timeframe:
                    period = "730d"  # 2 years for hourly data
                else:
                    period = "5y"   # 5 years for daily data
                
                self.logger.info(f"Fetching {yf_symbol} data for {timeframe} with period {period}")
                
                # Fetch data from yfinance
                ticker = yf.Ticker(yf_symbol)
                data = ticker.history(period=period, interval=yf_interval, auto_adjust=True)

                if data.empty:
                    self.logger.warning(f"No OHLC data returned for {yf_symbol} with timeframe {timeframe}")
                    continue

                # Prepare data for database insertion
                data.reset_index(inplace=True)
                
                # Handle different index column names
                if 'Datetime' in data.columns:
                    data.rename(columns={'Datetime': 'timestamp'}, inplace=True)
                elif 'Date' in data.columns:
                    data.rename(columns={'Date': 'timestamp'}, inplace=True)
                
                # Rename price columns to match database schema
                data.rename(columns={
                    'Open': 'open',
                    'High': 'high', 
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                }, inplace=True)
                
                # Convert timestamp to unix timestamp
                data['timestamp'] = data['timestamp'].astype(int) // 10**9
                
                # Add instrument and timeframe
                data['instrument'] = root_symbol  # Store by root symbol
                data['timeframe'] = timeframe
                
                # Select only required columns
                records_to_store = data[['timestamp', 'instrument', 'timeframe', 'open', 'high', 'low', 'close', 'volume']].copy()
                
                # Convert to dict records for bulk insert
                records_dict = records_to_store.to_dict('records')
                
                # Use bulk insert method for efficiency
                if self.db.insert_ohlc_batch(records_dict):
                    success_count += 1
                    total_records += len(records_dict)
                    self.logger.info(f"Successfully stored {len(records_dict)} OHLC records for {root_symbol} {timeframe}")
                else:
                    self.logger.error(f"Failed to store OHLC data for {root_symbol} {timeframe}")

            except Exception as e:
                self.logger.error(f"Failed to fetch or store OHLC for {yf_symbol} {timeframe}: {e}")
                continue
        
        if success_count > 0:
            self.logger.info(f"Successfully fetched {success_count}/{len(SUPPORTED_TIMEFRAMES)} timeframes for {root_symbol}, total {total_records} records")
            return True
        else:
            self.logger.warning(f"No data could be fetched for {root_symbol}")
            return False

    def check_data_availability(self, instrument: str) -> Dict[str, int]:
        """
        Check what timeframes are available for an instrument.
        Returns dict mapping timeframe to record count.
        """
        root_symbol = get_root_symbol(instrument)
        availability = {}
        
        for timeframe in SUPPORTED_TIMEFRAMES:
            count = self.db.get_ohlc_count(root_symbol, timeframe)
            if count > 0:
                availability[timeframe] = count
        
        return availability