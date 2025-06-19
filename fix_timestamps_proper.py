#!/usr/bin/env python3
"""
Fix Chart Data - Adjust timestamps to recent past data
"""
import sqlite3
import time
from datetime import datetime, timedelta

def fix_to_recent_past():
    """Fix timestamps to be recent past data (last week)"""
    
    # Connect to database
    db_path = 'data/db/futures_trades.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get current time and target end time (2 days ago)
        current_time = int(time.time())
        target_end = current_time - (2 * 24 * 3600)  # 2 days ago
        
        # Get the current max timestamp in data
        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM ohlc_data")
        current_min, current_max = cursor.fetchone()
        
        print(f"Current range: {datetime.fromtimestamp(current_min)} to {datetime.fromtimestamp(current_max)}")
        print(f"Target end time: {datetime.fromtimestamp(target_end)}")
        
        # Calculate adjustment to move max timestamp to target_end
        adjustment = target_end - current_max
        
        print(f"Adjusting all timestamps by {adjustment} seconds ({adjustment/86400:.1f} days)")
        
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
        print(f"New range: {datetime.fromtimestamp(min_ts)} to {datetime.fromtimestamp(max_ts)}")
        
        # Show sample data
        cursor.execute("SELECT timestamp, open_price, high_price, low_price, close_price FROM ohlc_data ORDER BY timestamp LIMIT 5")
        sample_data = cursor.fetchall()
        print("\\nSample updated data:")
        for row in sample_data:
            ts, o, h, l, c = row
            print(f"  {datetime.fromtimestamp(ts)}: O={o:.2f} H={h:.2f} L={l:.2f} C={c:.2f}")
        
    except Exception as e:
        print(f"Error fixing timestamps: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_to_recent_past()