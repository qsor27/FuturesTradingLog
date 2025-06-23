#!/usr/bin/env python3
"""
Manual Gap Filling Script for MNQ Data
Direct yfinance API calls to fill missing OHLC data
"""

import requests
import json
from datetime import datetime, timedelta
import sqlite3
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fill_mnq_gaps():
    """Fill gaps for MNQ using manual API approach"""
    
    print("🚨 MANUAL GAP FILLING FOR MNQ")
    print("=" * 50)
    
    # Use the existing Flask API endpoints to trigger gap filling
    base_url = "http://localhost:5000"
    
    # Try to trigger gap filling via API
    try:
        # Check if the Flask app is running
        health_response = requests.get(f"{base_url}/health", timeout=5)
        if health_response.status_code == 200:
            print("✅ Flask app is running, using API endpoints")
            
            # Trigger gap filling for MNQ
            instruments = ["MNQ"]
            
            for instrument in instruments:
                print(f"\n📊 Triggering gap fill for {instrument}...")
                
                # Use the manual gap filling API endpoint
                gap_fill_response = requests.post(
                    f"{base_url}/api/gap-filling/force/{instrument}",
                    timeout=120  # 2 minute timeout for gap filling
                )
                
                if gap_fill_response.status_code == 200:
                    result = gap_fill_response.json()
                    print(f"✅ Gap filling result: {result}")
                else:
                    print(f"⚠️ Gap filling API returned status {gap_fill_response.status_code}")
                    print(f"Response: {gap_fill_response.text}")
                
                # Also trigger a manual data update
                print(f"📈 Triggering data update for {instrument}...")
                update_response = requests.get(
                    f"{base_url}/api/update-data/{instrument}",
                    timeout=120
                )
                
                if update_response.status_code == 200:
                    result = update_response.json()
                    print(f"✅ Data update result: {result}")
                else:
                    print(f"⚠️ Data update API returned status {update_response.status_code}")
            
            # Verify the results
            print("\n🔍 VERIFICATION")
            print("-" * 30)
            
            chart_response = requests.get(
                f"{base_url}/api/chart-data/MNQ?timeframe=1h&days=7",
                timeout=30
            )
            
            if chart_response.status_code == 200:
                data = chart_response.json()
                if data.get('data'):
                    latest_timestamp = max([candle['time'] for candle in data['data']])
                    latest_date = datetime.fromtimestamp(latest_timestamp)
                    days_behind = (datetime.now() - latest_date).days
                    
                    status = "🟢" if days_behind <= 1 else "🟡" if days_behind <= 2 else "🔴"
                    print(f"{status} MNQ 1h data: {len(data['data'])} records")
                    print(f"   Latest: {latest_date.strftime('%Y-%m-%d %H:%M')} ({days_behind} days behind)")
                else:
                    print("❌ No chart data returned")
            else:
                print(f"⚠️ Chart data API returned status {chart_response.status_code}")
        
        else:
            print("❌ Flask app not responding, falling back to direct database approach")
            fill_via_database()
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to Flask app: {e}")
        print("Falling back to direct database approach...")
        fill_via_database()

def fill_via_database():
    """Fill gaps using direct database and yfinance calls"""
    print("\n🔧 DIRECT DATABASE APPROACH")
    print("-" * 30)
    
    try:
        import yfinance as yf
        import pandas as pd
        
        # Connect to database
        db_path = "data/db/futures_trades.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # MNQ symbol mapping for yfinance
        yf_symbol = "NQ=F"  # NASDAQ futures symbol
        
        # Get data for the last 7 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        print(f"Fetching {yf_symbol} data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Fetch data from yfinance
        ticker = yf.Ticker(yf_symbol)
        
        timeframes = {
            '1h': '1h',
            '1d': '1d',
            '5m': '5m',
            '15m': '15m'
        }
        
        for our_tf, yf_tf in timeframes.items():
            print(f"\nProcessing {our_tf} timeframe...", end=" ")
            
            try:
                data = ticker.history(
                    start=start_date,
                    end=end_date,
                    interval=yf_tf,
                    prepost=True
                )
                
                if data.empty:
                    print("❌ No data returned")
                    continue
                
                # Insert data into database
                inserted = 0
                for timestamp, row in data.iterrows():
                    unix_timestamp = int(timestamp.timestamp())
                    
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO ohlc_data 
                            (instrument, timeframe, timestamp, open_price, high_price, low_price, close_price, volume)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            "MNQ",
                            our_tf,
                            unix_timestamp,
                            float(row['Open']),
                            float(row['High']),
                            float(row['Low']),
                            float(row['Close']),
                            int(row['Volume']) if pd.notna(row['Volume']) else None
                        ))
                        inserted += 1
                    except sqlite3.IntegrityError:
                        pass  # Duplicate, skip
                
                conn.commit()
                print(f"✅ {inserted} new records inserted")
                
            except Exception as e:
                print(f"❌ Error: {e}")
        
        # Verify results
        print("\n🔍 VERIFICATION")
        print("-" * 20)
        
        cursor.execute("""
            SELECT timeframe, COUNT(*) as count,
                   datetime(MAX(timestamp), 'unixepoch') as latest_date
            FROM ohlc_data 
            WHERE instrument = 'MNQ'
            GROUP BY timeframe
            ORDER BY timeframe
        """)
        
        updated_data = cursor.fetchall()
        for row in updated_data:
            latest = datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S')
            days_behind = (datetime.now() - latest).days
            status = "🟢" if days_behind <= 1 else "🟡" if days_behind <= 2 else "🔴"
            print(f"{status} {row[0]}: {row[1]} records, latest: {row[2]} ({days_behind} days behind)")
        
        conn.close()
        print("\n✅ Manual gap filling completed!")
        
    except ImportError:
        print("❌ yfinance not available, cannot fill gaps directly")
        print("Please install with: pip install yfinance pandas")
    except Exception as e:
        print(f"❌ Error in direct database approach: {e}")

if __name__ == "__main__":
    fill_mnq_gaps()