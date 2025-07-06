#!/usr/bin/env python3
"""Debug script to test the available timeframes API issue"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
from config import SUPPORTED_TIMEFRAMES, TIMEFRAME_PREFERENCE_ORDER

def test_database_directly():
    """Test the database directly without using the ORM"""
    print("=== Testing Database Directly ===")
    
    # Connect to database
    db_path = "/home/qadmin/Projects/FuturesTradingLog/data/db/futures_trades.db"
    print(f"Connecting to: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if ohlc_data table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ohlc_data'")
        table_exists = cursor.fetchone()
        print(f"ohlc_data table exists: {table_exists is not None}")
        
        if table_exists:
            # Get all instruments
            cursor.execute("SELECT DISTINCT instrument FROM ohlc_data ORDER BY instrument")
            instruments = [row[0] for row in cursor.fetchall()]
            print(f"Available instruments: {instruments}")
            
            # Get all timeframes
            cursor.execute("SELECT DISTINCT timeframe FROM ohlc_data ORDER BY timeframe")
            timeframes = [row[0] for row in cursor.fetchall()]
            print(f"Available timeframes: {timeframes}")
            
            # Test for MNQ specifically
            print(f"\n=== Testing MNQ (from config: {SUPPORTED_TIMEFRAMES}) ===")
            for tf in SUPPORTED_TIMEFRAMES:
                cursor.execute("SELECT COUNT(*) FROM ohlc_data WHERE instrument = ? AND timeframe = ?", ('MNQ', tf))
                count = cursor.fetchone()[0]
                print(f"MNQ {tf}: {count} records")
            
            # Test available timeframes logic for MNQ
            print(f"\n=== Testing Available Timeframes Logic for MNQ ===")
            available_timeframes = []
            for timeframe in SUPPORTED_TIMEFRAMES:
                cursor.execute("SELECT COUNT(*) FROM ohlc_data WHERE instrument = ? AND timeframe = ?", ('MNQ', timeframe))
                count = cursor.fetchone()[0]
                if count > 0:
                    available_timeframes.append({'timeframe': timeframe, 'count': count})
            
            print(f"Available timeframes for MNQ: {available_timeframes}")
            
            # Determine best timeframe 
            best_timeframe = None
            if available_timeframes:
                for pref in TIMEFRAME_PREFERENCE_ORDER:
                    if any(tf['timeframe'] == pref for tf in available_timeframes):
                        best_timeframe = pref
                        break
            
            print(f"Best timeframe: {best_timeframe}")
            
            # Convert to old format
            available = {}
            for tf in available_timeframes:
                available[tf['timeframe']] = tf['count']
            
            print(f"API response format: {available}")
            
        conn.close()
        
    except Exception as e:
        print(f"Database error: {e}")

def test_symbol_mapping():
    """Test the symbol mapping logic"""
    print("\n=== Testing Symbol Mapping ===")
    
    try:
        from utils.instrument_utils import get_root_symbol
        from symbol_service import symbol_service
        
        test_instruments = ['MNQ', 'MNQ SEP25', 'ES', 'ES DEC24']
        
        for instrument in test_instruments:
            root = get_root_symbol(instrument)
            yf_symbol = symbol_service.get_yfinance_symbol(instrument)
            print(f"{instrument} -> root: {root}, yfinance: {yf_symbol}")
            
    except Exception as e:
        print(f"Symbol mapping error: {e}")

def test_api_endpoint_logic():
    """Test the available timeframes API endpoint logic"""
    print("\n=== Testing API Endpoint Logic ===")
    
    try:
        # Simulate the API call logic
        from utils.instrument_utils import get_root_symbol
        
        instrument = 'MNQ'
        root_symbol = get_root_symbol(instrument)
        print(f"API call for '{instrument}' -> root symbol: '{root_symbol}'")
        
        # Connect to database
        db_path = "/home/qadmin/Projects/FuturesTradingLog/data/db/futures_trades.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if any data exists for the root symbol (like the API does)
        cursor.execute("SELECT COUNT(*) FROM ohlc_data WHERE instrument = ?", (root_symbol,))
        total_count = cursor.fetchone()[0]
        print(f"Total OHLC records for '{root_symbol}': {total_count}")
        
        if total_count == 0:
            print("API would trigger on-demand fetch here")
        else:
            print("API would return available timeframes")
        
        conn.close()
        
    except Exception as e:
        print(f"API logic error: {e}")

if __name__ == "__main__":
    test_database_directly()
    test_symbol_mapping() 
    test_api_endpoint_logic()