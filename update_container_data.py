#!/usr/bin/env python3
"""
Update OHLC data with real Yahoo Finance data for NASDAQ futures
This version works inside the Docker container
"""

import yfinance as yf
import os
from datetime import datetime
import time
import sys
sys.path.append('/app')
from scripts.TradingLog_db import FuturesDB

def update_mnq_data():
    """Fetch real NQ=F data and update the database"""
    
    print("Fetching real NASDAQ futures data from Yahoo Finance...")
    
    try:
        # Use FuturesDB class for proper database handling
        with FuturesDB() as db:
            # Clear existing MNQ data
            print("Clearing existing MNQ data...")
            db.cursor.execute("DELETE FROM ohlc_data WHERE instrument = 'MNQ'")
            db.conn.commit()
            
            # Fetch data from Yahoo Finance using NQ=F symbol
            symbol = 'NQ=F'  # NASDAQ E-mini futures
            print(f"Fetching data for {symbol}...")
            
            ticker = yf.Ticker(symbol)
            
            # Get multiple timeframes including 1-minute data
            timeframes = {
                '1m': {'period': '7d', 'interval': '1m'},    # 1 week of 1-minute data
                '5m': {'period': '30d', 'interval': '5m'},   # 30 days of 5-minute data
                '15m': {'period': '60d', 'interval': '15m'}, # 60 days of 15-minute data
                '1h': {'period': '90d', 'interval': '1h'},   # 90 days of hourly data
                '4h': {'period': '90d', 'interval': '4h'},   # 90 days of 4-hour data
                '1d': {'period': '2y', 'interval': '1d'}     # 2 years of daily data
            }
            
            total_records = 0
            
            for tf, params in timeframes.items():
                print(f"\\nFetching {tf} data...")
                
                try:
                    # Add delay to avoid rate limiting
                    time.sleep(2)  # Increased delay for more timeframes
                    
                    data = ticker.history(period=params['period'], interval=params['interval'])
                    
                    if data.empty:
                        print(f"  No data returned for {tf}")
                        continue
                    
                    # Process the data using proper format for database
                    records = []
                    for timestamp, row in data.iterrows():
                        record = {
                            'timestamp': int(timestamp.timestamp()),
                            'instrument': 'MNQ',  # Store as MNQ (the symbol you're tracking)
                            'timeframe': tf,
                            'open': float(row['Open']),
                            'high': float(row['High']),
                            'low': float(row['Low']),
                            'close': float(row['Close']),
                            'volume': int(row['Volume']) if row['Volume'] > 0 else 0
                        }
                        records.append(record)
                    
                    # Insert using the bulk insert method
                    if records:
                        if db.insert_ohlc_batch(records):
                            total_records += len(records)
                            
                            # Show sample of latest data
                            latest = records[-1]
                            latest_time = datetime.fromtimestamp(latest['timestamp'])
                            print(f"  ✓ Inserted {len(records)} records for {tf}")
                            print(f"  Latest: {latest_time} - O={latest['open']:.2f}, C={latest['close']:.2f}")
                        else:
                            print(f"  X Failed to insert {tf} data")
                    
                except Exception as e:
                    print(f"  X Error fetching {tf} data: {e}")
            
            # Show final summary
            print(f"\\n★ Update complete! Total records inserted: {total_records}")
            
            # Verify the data
            db.cursor.execute('''
                SELECT timeframe, COUNT(*) as count, MAX(timestamp) as latest_ts
                FROM ohlc_data 
                WHERE instrument = 'MNQ'
                GROUP BY timeframe
                ORDER BY timeframe
            ''')
            
            print("\\n★ Updated MNQ data summary:")
            for row in db.cursor.fetchall():
                tf, count, latest_ts = row
                latest_time = datetime.fromtimestamp(latest_ts)
                days_old = (datetime.now() - latest_time).days
                print(f"  {tf}: {count} records, latest: {latest_time} ({days_old} days old)")
            
        return True
        
    except Exception as e:
        print(f"X Database error: {e}")
        return False

if __name__ == "__main__":
    success = update_mnq_data()
    if success:
        print("\\n✓ Real Yahoo Finance data update successful!")
        print("You can now refresh your chart to see current price data.")
    else:
        print("\\nX Data update failed. Please check the error messages above.")