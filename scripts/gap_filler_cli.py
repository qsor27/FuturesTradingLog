#!/usr/bin/env python3
"""
Gap Filler CLI Tool
Simple command-line interface to trigger gap filling for missing OHLC data
"""

import sys
import os
import sqlite3
from datetime import datetime, timedelta

def analyze_gaps():
    """Analyze current gaps in OHLC data"""
    print("🔍 GAP ANALYSIS")
    print("=" * 50)
    
    db_path = "data/db/futures_trades.db"
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get instruments with recent trades
    cursor.execute("""
        SELECT DISTINCT instrument 
        FROM trades 
        WHERE entry_time >= datetime('now', '-30 days')
    """)
    trade_instruments = [row[0] for row in cursor.fetchall()]
    
    print(f"Instruments with recent trades (30 days): {len(trade_instruments)}")
    for instrument in trade_instruments:
        print(f"  - {instrument}")
    
    print(f"\nOHLC Data Analysis:")
    print("-" * 30)
    
    for instrument in trade_instruments:
        base_instrument = instrument.split(' ')[0] if ' ' in instrument else instrument
        
        # Check OHLC data for this instrument
        cursor.execute("""
            SELECT timeframe, COUNT(*) as count,
                   datetime(MAX(timestamp), 'unixepoch') as latest_date
            FROM ohlc_data 
            WHERE instrument IN (?, ?)
            GROUP BY timeframe
            ORDER BY timeframe
        """, (instrument, base_instrument))
        
        ohlc_data = cursor.fetchall()
        
        print(f"\n{instrument} (base: {base_instrument}):")
        if ohlc_data:
            for row in ohlc_data:
                latest = datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S')
                days_behind = (datetime.now() - latest).days
                status = '🔴' if days_behind > 2 else '🟡' if days_behind > 0 else '🟢'
                print(f"  {status} {row[0]}: {row[1]} records, latest: {row[2]} ({days_behind} days behind)")
        else:
            print("  ❌ No OHLC data found!")
    
    # Check latest trade dates
    print(f"\nLatest Trade Activity:")
    print("-" * 30)
    cursor.execute("""
        SELECT instrument, MAX(entry_time) as latest_trade
        FROM trades 
        WHERE entry_time >= datetime('now', '-30 days')
        GROUP BY instrument
        ORDER BY latest_trade DESC
    """)
    
    trade_activity = cursor.fetchall()
    for instrument, latest_trade in trade_activity:
        latest = datetime.strptime(latest_trade, '%Y-%m-%d %H:%M:%S')
        days_ago = (datetime.now() - latest).days
        print(f"  {instrument}: {latest_trade} ({days_ago} days ago)")
    
    conn.close()

def print_usage():
    """Print usage instructions"""
    print("\n📋 GAP FILLING SOLUTION")
    print("=" * 50)
    print("Your MNQ trades from June 18th don't have corresponding candle data.")
    print("The OHLC data only goes to June 17th, missing 2-3 days.")
    print("\n🔧 SOLUTIONS:")
    print("\n1. 🚀 START THE FLASK APP (Recommended):")
    print("   docker restart futurestradinglog")
    print("   # Wait for container to start, then visit:")
    print("   # http://localhost:5000/api/gap-filling/force/MNQ")
    print("\n2. 🔄 USE BACKGROUND SERVICES:")
    print("   # The app has automatic gap filling every 15 minutes")
    print("   # Emergency gap filling for recent trades")
    print("\n3. 📊 MANUAL API TRIGGERS:")
    print("   curl -X POST http://localhost:5000/api/gap-filling/emergency")
    print("   curl http://localhost:5000/api/gap-filling/force/MNQ?days=7")
    print("\n4. 🛠️ VERIFY RESULTS:")
    print("   python3 gap_filler_cli.py --analyze")
    print("\n💡 The system is designed to automatically detect and fill")
    print("   gaps when instruments have recent trades but missing data.")

def main():
    """Main CLI function"""
    if len(sys.argv) > 1 and sys.argv[1] == '--analyze':
        analyze_gaps()
    else:
        analyze_gaps()
        print_usage()

if __name__ == "__main__":
    main()