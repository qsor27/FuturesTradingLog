#!/usr/bin/env python3
"""
Fix Chart Data - Corrects future timestamps in OHLC data
"""
import sqlite3
import time
from datetime import datetime, timedelta

def fix_ohlc_timestamps():
    """Fix future timestamps in OHLC data by adjusting them to current timeframe"""
    
    # Connect to database
    db_path = 'data/db/futures_trades.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get all OHLC records
        cursor.execute("SELECT id, timestamp FROM ohlc_data ORDER BY timestamp")
        records = cursor.fetchall()
        
        if not records:
            print("No OHLC records found")
            return
        
        print(f"Found {len(records)} OHLC records to fix")
        
        # Calculate adjustment needed
        future_start = records[0][1]  # First timestamp
        current_time = int(time.time())
        
        # Adjust to end the data series about 1 day ago
        end_time = current_time - (24 * 3600)  # 1 day ago
        
        # Calculate total time span of existing data
        future_end = records[-1][1]
        time_span = future_end - future_start
        
        # New start time = end_time - time_span
        new_start = end_time - time_span
        adjustment = new_start - future_start
        
        print(f"Original time range: {datetime.fromtimestamp(future_start)} to {datetime.fromtimestamp(future_end)}")
        print(f"Adjusting by {adjustment} seconds ({adjustment/3600:.1f} hours)")
        print(f"New time range: {datetime.fromtimestamp(new_start)} to {datetime.fromtimestamp(end_time)}")
        
        # Update all timestamps
        cursor.execute("""
            UPDATE ohlc_data 
            SET timestamp = timestamp + ?
        """, (adjustment,))
        
        rows_updated = cursor.rowcount
        conn.commit()
        
        print(f"Successfully updated {rows_updated} OHLC records")
        
        # Verify the fix
        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM ohlc_data")
        min_ts, max_ts = cursor.fetchone()
        print(f"Verification - New range: {datetime.fromtimestamp(min_ts)} to {datetime.fromtimestamp(max_ts)}")
        
    except Exception as e:
        print(f"Error fixing timestamps: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_ohlc_timestamps()