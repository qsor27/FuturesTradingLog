"""
Emergency OHLC Data Fix
Populates missing OHLC data to resolve candle display issues
"""

import logging
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
import pandas as pd
from scripts.TradingLog_db import FuturesDB
from utils.instrument_utils import get_root_symbol

logger = logging.getLogger(__name__)

class EmergencyDataFix:
    """Emergency fix for missing OHLC data that prevents candle display"""
    
    def __init__(self):
        self.db = None
        self.results = {
            'success': False,
            'populated_timeframes': [],
            'total_records': 0,
            'errors': []
        }
    
    def populate_missing_ohlc_data(self, instrument: str = 'MNQ') -> Dict[str, Any]:
        """
        Populate critical timeframes for immediate chart functionality
        
        Args:
            instrument: The futures instrument to populate data for
            
        Returns:
            Dict with operation results
        """
        logger.info(f"Starting emergency OHLC data population for {instrument}")
        
        try:
            # Target timeframes for full functionality (all supported timeframes)
            timeframes = ['1m', '5m', '15m', '1h', '1d']
            
            # Get last 3 days of data for immediate needs (fresher data)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=3)
            
            logger.info(f"Fetching data from {start_date} to {end_date}")
            
            with FuturesDB() as db:
                self.db = db
                
                # Check current data status
                current_status = self._check_current_data_status(instrument, timeframes)
                logger.info(f"Current data status: {current_status}")
                
                # Populate each timeframe (force populate all for immediate fix)
                for timeframe in timeframes:
                    current_count = current_status.get(timeframe, 0)
                    logger.info(f"Current {timeframe} records: {current_count}")
                    
                    # Always try to add fresh data, even if we have some records
                    if current_count < 200:  # Less than 200 records = needs more data
                        try:
                            records_added = self._fetch_and_store_timeframe(
                                instrument, timeframe, start_date, end_date
                            )
                            
                            if records_added > 0:
                                self.results['populated_timeframes'].append(timeframe)
                                self.results['total_records'] += records_added
                                logger.info(f"Added {records_added} records for {timeframe}")
                            else:
                                logger.warning(f"No data retrieved for {timeframe}")
                                
                        except Exception as e:
                            error_msg = f"Failed to populate {timeframe}: {str(e)}"
                            logger.error(error_msg)
                            self.results['errors'].append(error_msg)
                    else:
                        logger.info(f"Skipping {timeframe} - already has {current_status[timeframe]} records")
                
                self.results['success'] = len(self.results['populated_timeframes']) > 0
                
                if self.results['success']:
                    logger.info(f"Emergency data fix completed successfully. "
                              f"Populated {len(self.results['populated_timeframes'])} timeframes "
                              f"with {self.results['total_records']} total records")
                else:
                    logger.warning("Emergency data fix completed but no new data was added")
                
                return self.results
                
        except Exception as e:
            logger.error(f"Emergency data fix failed: {e}")
            self.results['success'] = False
            self.results['errors'].append(str(e))
            return self.results
    
    def _check_current_data_status(self, instrument: str, timeframes: List[str]) -> Dict[str, int]:
        """Check how many records exist for each timeframe"""
        status = {}
        
        for timeframe in timeframes:
            self.db.cursor.execute(
                "SELECT COUNT(*) FROM ohlc_data WHERE instrument = ? AND timeframe = ?",
                (instrument, timeframe)
            )
            count = self.db.cursor.fetchone()[0]
            status[timeframe] = count
            
        return status
    
    def _fetch_and_store_timeframe(self, instrument: str, timeframe: str, 
                                 start_date: datetime, end_date: datetime) -> int:
        """
        Fetch and store data for specific timeframe
        
        Returns:
            Number of records added
        """
        try:
            # Get Yahoo Finance symbol mapping
            yahoo_symbol = self._get_yahoo_symbol(instrument)
            if not yahoo_symbol:
                logger.error(f"Could not map {instrument} to Yahoo Finance symbol")
                return 0
            
            logger.info(f"Fetching {timeframe} data for {yahoo_symbol} ({instrument})")
            
            # Convert timeframe to Yahoo Finance format
            yahoo_interval = self._convert_timeframe_to_yahoo(timeframe)
            if not yahoo_interval:
                logger.error(f"Could not convert timeframe {timeframe} to Yahoo format")
                return 0
            
            # Fetch data from Yahoo Finance
            ticker = yf.Ticker(yahoo_symbol)
            data = ticker.history(
                start=start_date,
                end=end_date,
                interval=yahoo_interval,
                auto_adjust=True,
                prepost=True
            )
            
            if data.empty:
                logger.warning(f"No data returned from Yahoo Finance for {yahoo_symbol}")
                return 0
            
            logger.info(f"Retrieved {len(data)} records from Yahoo Finance")
            
            # Store data in database
            records_added = 0
            for timestamp, row in data.iterrows():
                try:
                    # Convert timestamp to Unix timestamp
                    unix_timestamp = int(timestamp.timestamp())
                    
                    # Prepare OHLC data
                    ohlc_data = {
                        'instrument': instrument,
                        'timeframe': timeframe,
                        'timestamp': unix_timestamp,
                        'open_price': float(row['Open']),
                        'high_price': float(row['High']),
                        'low_price': float(row['Low']),
                        'close_price': float(row['Close']),
                        'volume': int(row['Volume']) if 'Volume' in row and not pd.isna(row['Volume']) else 0
                    }
                    
                    # Insert or update record
                    self.db.cursor.execute('''
                        INSERT OR REPLACE INTO ohlc_data 
                        (instrument, timeframe, timestamp, open_price, high_price, low_price, close_price, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        ohlc_data['instrument'],
                        ohlc_data['timeframe'],
                        ohlc_data['timestamp'],
                        ohlc_data['open_price'],
                        ohlc_data['high_price'],
                        ohlc_data['low_price'],
                        ohlc_data['close_price'],
                        ohlc_data['volume']
                    ))
                    
                    records_added += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to store record for {timestamp}: {e}")
                    continue
            
            # Commit the transaction
            self.db.conn.commit()
            logger.info(f"Successfully stored {records_added} records for {timeframe}")
            
            return records_added
            
        except Exception as e:
            logger.error(f"Failed to fetch and store {timeframe} data: {e}")
            return 0
    
    def _get_yahoo_symbol(self, instrument: str) -> str:
        """Map futures instrument to Yahoo Finance symbol"""
        
        # Common futures mapping to Yahoo Finance symbols
        symbol_mapping = {
            'MNQ': 'NQ=F',    # Micro E-mini NASDAQ-100
            'MES': 'ES=F',    # Micro E-mini S&P 500
            'NQ': 'NQ=F',     # E-mini NASDAQ-100
            'ES': 'ES=F',     # E-mini S&P 500
            'YM': 'YM=F',     # E-mini Dow Jones
            'RTY': 'RTY=F',   # E-mini Russell 2000
            'CL': 'CL=F',     # Crude Oil
            'GC': 'GC=F',     # Gold
            'SI': 'SI=F',     # Silver
        }
        
        # Get root symbol
        root_symbol = get_root_symbol(instrument)
        
        # Return mapped symbol or try with =F suffix
        return symbol_mapping.get(root_symbol, f"{root_symbol}=F")
    
    def _convert_timeframe_to_yahoo(self, timeframe: str) -> str:
        """Convert our timeframe format to Yahoo Finance interval format"""
        
        timeframe_mapping = {
            '1m': '1m',
            '3m': '3m',    # Added 3m support
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',  # Added 30m support  
            '1h': '1h',
            '4h': '4h',
            '1d': '1d'
        }
        
        return timeframe_mapping.get(timeframe)

def run_emergency_fix(instrument: str = 'MNQ') -> Dict[str, Any]:
    """
    Convenience function to run emergency data fix
    
    Args:
        instrument: The instrument to fix data for
        
    Returns:
        Results dictionary
    """
    fix = EmergencyDataFix()
    return fix.populate_missing_ohlc_data(instrument)

if __name__ == "__main__":
    # Run emergency fix for MNQ
    import pandas as pd  # Import here to avoid module issues
    
    print("=== EMERGENCY OHLC DATA FIX ===")
    print("Populating missing data for MNQ instrument...")
    
    results = run_emergency_fix('MNQ')
    
    print(f"\nResults:")
    print(f"Success: {results['success']}")
    print(f"Populated timeframes: {results['populated_timeframes']}")
    print(f"Total records added: {results['total_records']}")
    
    if results['errors']:
        print(f"Errors encountered:")
        for error in results['errors']:
            print(f"  - {error}")
    
    print("\n=== FIX COMPLETE ===")