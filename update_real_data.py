#!/usr/bin/env python3
"""
Update OHLC data with real Yahoo Finance data for NASDAQ futures
This runs on the host system where Yahoo Finance access works
"""

import yfinance as yf
import sqlite3
import os
from datetime import datetime
import time

def update_mnq_data():
    """Fetch real NQ=F data and update the database"""
    
    print("Fetching real NASDAQ futures data from Yahoo Finance...")
    
    # Database path
    db_path = os.path.join('data', 'db', 'futures_trading.db')
    
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Clear existing MNQ data
        print("Clearing existing MNQ data...")
        cursor.execute("DELETE FROM ohlc_data WHERE instrument = 'MNQ'")
        conn.commit()
        
        # Fetch data from Yahoo Finance using NQ=F symbol
        symbol = 'NQ=F'  # NASDAQ E-mini futures
        print(f"Fetching data for {symbol}...")
        
        ticker = yf.Ticker(symbol)
        
        # Get multiple timeframes
        timeframes = {
            '1h': {'period': '30d', 'interval': '1h'},
            '4h': {'period': '90d', 'interval': '4h'}, 
            '1d': {'period': '2y', 'interval': '1d'}
        }
        
        total_records = 0
        
        for tf, params in timeframes.items():
            print(f"\\nFetching {tf} data...")
            
            try:
                # Add delay to avoid rate limiting
                time.sleep(1)
                
                data = ticker.history(period=params['period'], interval=params['interval'])
                
                if data.empty:
                    print(f"  No data returned for {tf}")
                    continue
                
                # Process the data
                records = []
                for timestamp, row in data.iterrows():
                    record = {
                        'timestamp': int(timestamp.timestamp()),
                        'instrument': 'MNQ',  # Store as MNQ (the symbol you're tracking)
                        'timeframe': tf,
                        'open_price': float(row['Open']),
                        'high_price': float(row['High']),
                        'low_price': float(row['Low']),
                        'close_price': float(row['Close']),
                        'volume': int(row['Volume']) if row['Volume'] > 0 else 0
                    }
                    records.append(record)
                
                # Insert into database
                if records:
                    cursor.executemany('''
                        INSERT OR REPLACE INTO ohlc_data 
                        (timestamp, instrument, timeframe, open_price, high_price, low_price, close_price, volume)
                        VALUES (:timestamp, :instrument, :timeframe, :open_price, :high_price, :low_price, :close_price, :volume)
                    ''', records)
                    
                    conn.commit()
                    total_records += len(records)
                    
                    # Show sample of latest data
                    latest = records[-1]
                    latest_time = datetime.fromtimestamp(latest['timestamp'])
                    print(f"  ✅ Inserted {len(records)} records for {tf}")
                    print(f"  Latest: {latest_time} - O={latest['open_price']:.2f}, C={latest['close_price']:.2f}")
                
            except Exception as e:
                print(f"  ❌ Error fetching {tf} data: {e}")
        
        # Show final summary
        print(f"\\n🎉 Update complete! Total records inserted: {total_records}")
        
        # Verify the data
        cursor.execute('''
            SELECT timeframe, COUNT(*) as count, MAX(timestamp) as latest_ts
            FROM ohlc_data 
            WHERE instrument = 'MNQ'
            GROUP BY timeframe
            ORDER BY timeframe
        ''')
        
        print("\\n📊 Updated MNQ data summary:")
        for row in cursor.fetchall():
            tf, count, latest_ts = row
            latest_time = datetime.fromtimestamp(latest_ts)
            days_old = (datetime.now() - latest_time).days
            print(f"  {tf}: {count} records, latest: {latest_time} ({days_old} days old)")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

if __name__ == "__main__":
    success = update_mnq_data()
    if success:
        print("\\n✅ Real Yahoo Finance data update successful!")
        print("You can now refresh your chart to see current price data.")
    else:
        print("\\n❌ Data update failed. Please check the error messages above.")