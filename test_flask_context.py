#!/usr/bin/env python3
"""
Test script to debug Flask context issue with ohlc_service
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime
from services.data_service import ohlc_service
from app import app

def test_with_flask_context():
    """Test ohlc_service within Flask context"""
    
    print("Testing ohlc_service within Flask application context")
    print("=" * 60)
    
    # Test parameters
    instrument = "MNQ"
    timeframe = "1h"
    start_date = datetime(2025, 6, 16, 23, 20, 51)
    end_date = datetime(2025, 6, 17, 23, 20, 51)
    
    print(f"Parameters:")
    print(f"   Instrument: {instrument}")
    print(f"   Timeframe: {timeframe}")
    print(f"   Start Date: {start_date}")
    print(f"   End Date: {end_date}")
    print()
    
    # Test without Flask context
    print("Test 1: Without Flask context")
    try:
        data = ohlc_service.get_chart_data(instrument, timeframe, start_date, end_date)
        print(f"   Result: {len(data)} records")
    except Exception as e:
        print(f"   ERROR: {e}")
    print()
    
    # Test with Flask context
    print("Test 2: With Flask context")
    try:
        with app.app_context():
            data = ohlc_service.get_chart_data(instrument, timeframe, start_date, end_date)
            print(f"   Result: {len(data)} records")
    except Exception as e:
        print(f"   ERROR: {e}")
    print()
    
    # Test with Flask request context
    print("Test 3: With Flask request context")
    try:
        with app.test_request_context():
            data = ohlc_service.get_chart_data(instrument, timeframe, start_date, end_date)
            print(f"   Result: {len(data)} records")
    except Exception as e:
        print(f"   ERROR: {e}")
    print()

def test_different_service_instances():
    """Test if different instances of ohlc_service behave differently"""
    
    print("Testing different ohlc_service instances")
    print("=" * 60)
    
    # Test parameters
    instrument = "MNQ"
    timeframe = "1h"
    start_date = datetime(2025, 6, 16, 23, 20, 51)
    end_date = datetime(2025, 6, 17, 23, 20, 51)
    
    # Test global instance
    print("Test 1: Global ohlc_service instance")
    try:
        data = ohlc_service.get_chart_data(instrument, timeframe, start_date, end_date)
        print(f"   Result: {len(data)} records")
        print(f"   Cache service: {ohlc_service.cache_service}")
    except Exception as e:
        print(f"   ERROR: {e}")
    print()
    
    # Test new instance
    print("Test 2: New OHLCDataService instance")
    try:
        from services.data_service import OHLCDataService
        new_service = OHLCDataService()
        data = new_service.get_chart_data(instrument, timeframe, start_date, end_date)
        print(f"   Result: {len(data)} records")
        print(f"   Cache service: {new_service.cache_service}")
    except Exception as e:
        print(f"   ERROR: {e}")
    print()

if __name__ == "__main__":
    test_with_flask_context()
    test_different_service_instances()