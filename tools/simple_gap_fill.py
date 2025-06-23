#!/usr/bin/env python3
"""
Simple Gap Filling Solution
Direct approach to fill missing MNQ data using basic HTTP requests
"""

import urllib.request
import json
import sqlite3
import time
from datetime import datetime, timedelta

def fetch_yahoo_data(symbol, period1, period2, interval='1h'):
    """Fetch data from Yahoo Finance using direct HTTP request"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = f"period1={period1}&period2={period2}&interval={interval}&includePrePost=true"
    full_url = f"{url}?{params}"
    
    try:
        with urllib.request.urlopen(full_url) as response:
            data = json.loads(response.read().decode())
        
        result = data['chart']['result'][0]
        timestamps = result['timestamp']
        quotes = result['indicators']['quote'][0]
        
        candles = []
        for i, ts in enumerate(timestamps):
            if all(quotes[field][i] is not None for field in ['open', 'high', 'low', 'close']):
                candles.append({
                    'timestamp': ts,
                    'open': quotes['open'][i],
                    'high': quotes['high'][i],
                    'low': quotes['low'][i],
                    'close': quotes['close'][i],
                    'volume': quotes['volume'][i] if quotes['volume'][i] else 0
                })
        
        return candles
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

def fill_mnq_gaps():
    """Fill MNQ gaps using direct Yahoo Finance API"""
    print("🚨 SIMPLE MNQ GAP FILLING")
    print("=" * 40)
    
    # Database setup
    db_path = "data/db/futures_trades.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # MNQ symbol for Yahoo Finance
    symbol = "NQ=F"  # NASDAQ futures
    
    # Time range: last 7 days
    end_time = int(time.time())
    start_time = int((datetime.now() - timedelta(days=7)).timestamp())
    
    print(f"Fetching {symbol} data for MNQ...")
    print(f"Time range: {datetime.fromtimestamp(start_time)} to {datetime.fromtimestamp(end_time)}")
    
    # Define timeframes
    intervals = {
        '1h': '1h',
        '1d': '1d'
    }
    
    total_inserted = 0
    
    for our_timeframe, yahoo_interval in intervals.items():
        print(f"\nProcessing {our_timeframe} timeframe...", end=" ")
        
        # Fetch data
        candles = fetch_yahoo_data(symbol, start_time, end_time, yahoo_interval)
        
        if not candles:
            print("❌ No data received")
            continue
        
        # Insert into database
        inserted = 0
        for candle in candles:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO ohlc_data 
                    (instrument, timeframe, timestamp, open_price, high_price, low_price, close_price, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "MNQ",
                    our_timeframe,
                    candle['timestamp'],
                    candle['open'],
                    candle['high'],
                    candle['low'],
                    candle['close'],
                    candle['volume']
                ))
                if cursor.rowcount > 0:
                    inserted += 1
            except Exception as e:
                pass  # Skip duplicates
        
        conn.commit()
        total_inserted += inserted
        print(f"✅ {inserted} new records")
    
    print(f"\n📊 TOTAL: {total_inserted} new records inserted")
    
    # Verification
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
    
    results = cursor.fetchall()
    for row in results:
        latest = datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S")
        hours_behind = (datetime.now() - latest).total_seconds() / 3600
        
        if hours_behind < 12:
            status = "🟢"
            behind_text = f"{hours_behind:.1f} hours behind"
        elif hours_behind < 48:
            status = "🟡"
            behind_text = f"{hours_behind/24:.1f} days behind"
        else:
            status = "🔴"
            behind_text = f"{hours_behind/24:.1f} days behind"
        
        print(f"{status} {row[0]}: {row[1]} records, latest: {row[2]} ({behind_text})")
    
    conn.close()
    print("\n✅ Simple gap filling completed!")

if __name__ == "__main__":
    fill_mnq_gaps()