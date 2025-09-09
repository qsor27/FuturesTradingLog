#!/usr/bin/env python3
"""
Debug script to test cache_only_chart_service database queries
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
from scripts.TradingLog_db import FuturesDB
from services.cache_only_chart_service import cache_only_chart_service

def debug_database_query():
    """Test the database query directly"""
    
    print("🔍 Debug: Testing database queries directly")
    print("=" * 60)
    
    # Test parameters (same as API would use)
    instrument = "MNQ"
    timeframe = "1h"
    
    # Use the same date range as the browser API calls
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)
    
    print(f"📊 Testing with:")
    print(f"   Instrument: {instrument}")
    print(f"   Timeframe: {timeframe}")
    print(f"   Start Date: {start_date}")
    print(f"   End Date: {end_date}")
    print(f"   Start Timestamp: {int(start_date.timestamp())}")
    print(f"   End Timestamp: {int(end_date.timestamp())}")
    print()
    
    # Test 1: Direct database query
    print("🗄️  Test 1: Direct database query")
    try:
        with FuturesDB() as db:
            data = db.get_ohlc_data(
                instrument, 
                timeframe, 
                int(start_date.timestamp()), 
                int(end_date.timestamp())
            )
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
    
    # Test 2: Check what's actually in the database
    print("🗄️  Test 2: Raw database check")
    try:
        with FuturesDB() as db:
            db.cursor.execute("""
                SELECT instrument, timeframe, COUNT(*) as count, 
                       MIN(timestamp) as min_ts, MAX(timestamp) as max_ts
                FROM ohlc_data 
                GROUP BY instrument, timeframe
                ORDER BY instrument, timeframe
            """)
            
            rows = db.cursor.fetchall()
            print(f"   Found {len(rows)} instrument/timeframe combinations:")
            for row in rows:
                min_dt = datetime.fromtimestamp(row[3]) if row[3] else None
                max_dt = datetime.fromtimestamp(row[4]) if row[4] else None
                print(f"   - {row[0]} {row[1]}: {row[2]} records ({min_dt} to {max_dt})")
        print()
    except Exception as e:
        print(f"   ERROR: {e}")
        print()
    
    # Test 3: Query with database date range
    print("🗄️  Test 3: Query using database's actual date range")
    try:
        with FuturesDB() as db:
            # Get the actual date range for MNQ 1h data
            db.cursor.execute("""
                SELECT MIN(timestamp), MAX(timestamp) 
                FROM ohlc_data 
                WHERE instrument = ? AND timeframe = ?
            """, (instrument, timeframe))
            
            result = db.cursor.fetchone()
            if result and result[0] and result[1]:
                db_start_ts = result[0]
                db_end_ts = result[1]
                db_start_dt = datetime.fromtimestamp(db_start_ts)
                db_end_dt = datetime.fromtimestamp(db_end_ts)
                
                print(f"   Database date range: {db_start_dt} to {db_end_dt}")
                
                # Query with database range
                data = db.get_ohlc_data(instrument, timeframe, db_start_ts, db_end_ts)
                print(f"   Result with DB range: {len(data)} records")
                
                if data:
                    print(f"   First record: {data[0]}")
                    print(f"   Last record: {data[-1]}")
            else:
                print("   No timestamp data found")
        print()
    except Exception as e:
        print(f"   ERROR: {e}")
        print()
    
    # Test 4: Test cache service method directly
    print("📦 Test 4: Cache service _get_database_data method")
    try:
        data = cache_only_chart_service._get_database_data(
            instrument, timeframe, start_date, end_date
        )
        print(f"   Cache service result: {len(data)} records")
        if data:
            print(f"   First record: {data[0]}")
            print(f"   Last record: {data[-1]}")
        print()
    except Exception as e:
        print(f"   ERROR: {e}")
        print()
    
    # Test 5: Test full cache service method
    print("📦 Test 5: Full cache service get_chart_data method")
    try:
        result = cache_only_chart_service.get_chart_data(
            instrument, timeframe, start_date, end_date
        )
        print(f"   Success: {result.get('success')}")
        print(f"   Count: {result.get('count')}")
        print(f"   Has data: {result.get('has_data')}")
        print(f"   Data source: {result.get('metadata', {}).get('data_source')}")
        if result.get('data'):
            print(f"   First data point: {result['data'][0]}")
            print(f"   Last data point: {result['data'][-1]}")
        print()
    except Exception as e:
        print(f"   ERROR: {e}")
        print()

if __name__ == "__main__":
    debug_database_query()