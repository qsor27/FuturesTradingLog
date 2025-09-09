#!/usr/bin/env python3
"""
Debug script to test database queries directly
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
from scripts.TradingLog_db import FuturesDB

def debug_database_query():
    """Test the database query directly"""
    
    print("Debug: Testing database queries directly")
    print("=" * 60)
    
    # Test parameters (same as API would use)
    instrument = "MNQ"
    timeframe = "1h"
    
    # Use the same date range as the browser API calls
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)
    
    print(f"Testing with:")
    print(f"   Instrument: {instrument}")
    print(f"   Timeframe: {timeframe}")
    print(f"   Start Date: {start_date}")
    print(f"   End Date: {end_date}")
    print(f"   Start Timestamp: {int(start_date.timestamp())}")
    print(f"   End Timestamp: {int(end_date.timestamp())}")
    print()
    
    # Test 1: Direct database query
    print("Test 1: Direct database query with current date range")
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
    print("Test 2: Raw database inventory")
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
    print("Test 3: Query using database's actual date range")
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
                    print(f"   First record timestamp: {data[0].get('timestamp')} -> {datetime.fromtimestamp(data[0].get('timestamp'))}")
                    print(f"   Last record timestamp: {data[-1].get('timestamp')} -> {datetime.fromtimestamp(data[-1].get('timestamp'))}")
            else:
                print("   No timestamp data found")
        print()
    except Exception as e:
        print(f"   ERROR: {e}")
        print()
    
    # Test 4: Query without date filtering
    print("Test 4: Query without date filtering (get all MNQ 1h data)")
    try:
        with FuturesDB() as db:
            data = db.get_ohlc_data(instrument, timeframe)
        print(f"   Result: {len(data)} records")
        if data:
            print(f"   First record: {data[0]}")
            print(f"   Last record: {data[-1]}")
        print()
    except Exception as e:
        print(f"   ERROR: {e}")
        print()
    
    # Test 5: Test base instrument logic
    print("Test 5: Test base instrument extraction")
    test_instruments = ["MNQ", "MNQ SEP25", "MNQ DEC25", "ES", "ES SEP25"]
    for test_inst in test_instruments:
        base_inst = test_inst.split(' ')[0] if ' ' in test_inst else test_inst
        print(f"   '{test_inst}' -> base: '{base_inst}'")
        
        try:
            with FuturesDB() as db:
                data = db.get_ohlc_data(base_inst, timeframe)
            print(f"      Base instrument has {len(data)} records")
        except Exception as e:
            print(f"      ERROR querying base instrument: {e}")
    print()

if __name__ == "__main__":
    debug_database_query()