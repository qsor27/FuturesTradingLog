#!/usr/bin/env python3
"""
Test script to debug ohlc_service.get_chart_data() method
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime
from services.data_service import ohlc_service

def test_ohlc_service():
    """Test the ohlc_service.get_chart_data method directly"""
    
    print("Testing ohlc_service.get_chart_data method")
    print("=" * 60)
    
    # Test parameters
    instrument = "MNQ"
    timeframe = "1h"
    
    # Use database date range (June 2025)
    start_date = datetime(2025, 6, 16, 23, 20, 51)
    end_date = datetime(2025, 6, 17, 23, 20, 51)
    
    print(f"Parameters:")
    print(f"   Instrument: {instrument}")
    print(f"   Timeframe: {timeframe}")
    print(f"   Start Date: {start_date}")
    print(f"   End Date: {end_date}")
    print(f"   Start Timestamp: {int(start_date.timestamp())}")
    print(f"   End Timestamp: {int(end_date.timestamp())}")
    print()
    
    # Test ohlc_service.get_chart_data
    print("Testing ohlc_service.get_chart_data()...")
    try:
        data = ohlc_service.get_chart_data(instrument, timeframe, start_date, end_date)
        print(f"   Result: {len(data)} records")
        if data:
            print(f"   First record: {data[0]}")
            print(f"   Last record: {data[-1]}")
        else:
            print("   No data returned")
        print()
    except Exception as e:
        print(f"   ERROR: {e}")
        print()
    
    # Test cache service availability
    print("Testing cache service...")
    try:
        print(f"   ohlc_service.cache_service: {ohlc_service.cache_service}")
        if ohlc_service.cache_service:
            print("   Cache service is available")
        else:
            print("   Cache service is None")
        print()
    except Exception as e:
        print(f"   ERROR: {e}")
        print()
    
    # Test database access directly through ohlc_service
    print("Testing database access via ohlc_service...")
    try:
        from scripts.TradingLog_db import FuturesDB
        with FuturesDB() as db:
            start_ts = int(start_date.timestamp())
            end_ts = int(end_date.timestamp())
            data = db.get_ohlc_data(instrument, timeframe, start_ts, end_ts, limit=None)
            print(f"   Direct DB query result: {len(data)} records")
            if data:
                print(f"   First record: {data[0]}")
    except Exception as e:
        print(f"   ERROR: {e}")

if __name__ == "__main__":
    test_ohlc_service()