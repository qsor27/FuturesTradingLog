#!/usr/bin/env python3
"""
Simple script to update chart data for a specific instrument
Run this to fetch missing market data
"""

import sys
from datetime import datetime, timedelta
sys.path.insert(0, '.')

from scripts.TradingLog_db import FuturesDB
from services.data_service import DataService

def update_instrument_data(instrument, days_back=7):
    """Update OHLC data for an instrument"""
    print(f"\n=== Updating market data for {instrument} ===")
    print(f"Fetching last {days_back} days of data...\n")

    # Initialize data service
    data_service = DataService()

    # Define timeframes to fetch
    timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']

    success_count = 0
    fail_count = 0

    for timeframe in timeframes:
        try:
            print(f"Fetching {timeframe} data... ", end='', flush=True)

            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            # Fetch data from Yahoo Finance
            result = data_service.fetch_ohlc_data(
                instrument=instrument,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )

            if result and 'count' in result and result['count'] > 0:
                print(f"✓ {result['count']} candles")
                success_count += 1
            else:
                print(f"✗ No data")
                fail_count += 1

        except Exception as e:
            print(f"✗ Error: {e}")
            fail_count += 1

    print(f"\n=== Update complete ===")
    print(f"Success: {success_count}/{len(timeframes)} timeframes")
    print(f"Failed: {fail_count}/{len(timeframes)} timeframes")

    # Show what we have in database now
    with FuturesDB() as db:
        for tf in timeframes:
            count = db.cursor.execute(
                'SELECT COUNT(*) FROM ohlc_data WHERE instrument = ? AND timeframe = ?',
                (instrument, tf)
            ).fetchone()[0]

            if count > 0:
                # Get date range
                db.cursor.execute(
                    'SELECT MIN(timestamp), MAX(timestamp) FROM ohlc_data WHERE instrument = ? AND timeframe = ?',
                    (instrument, tf)
                )
                min_ts, max_ts = db.cursor.fetchone()
                min_date = datetime.fromtimestamp(min_ts).strftime('%Y-%m-%d')
                max_date = datetime.fromtimestamp(max_ts).strftime('%Y-%m-%d')
                print(f"{tf:4s}: {count:5d} records ({min_date} to {max_date})")
            else:
                print(f"{tf:4s}: No data")

if __name__ == '__main__':
    instrument = sys.argv[1] if len(sys.argv) > 1 else 'MNQ MAR26'
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 7

    update_instrument_data(instrument, days)
