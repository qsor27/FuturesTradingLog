#!/usr/bin/env python3
"""
Direct 1-minute data fetcher using yfinance
Bypasses Redis rate limiting
Uses InstrumentMapper for proper contract naming
"""

import yfinance as yf
from datetime import datetime, timedelta
from scripts.TradingLog_db import FuturesDB
from services.instrument_mapper import InstrumentMapper

def fetch_and_store_1m_data(instrument, days=7):
    """
    Fetch 1-minute data and store in database

    Args:
        instrument: NinjaTrader format (e.g., "MNQ MAR26") or Yahoo format (e.g., "MNQ=F")
        days: Number of days to fetch
    """

    # Initialize mapper
    mapper = InstrumentMapper()

    # Get Yahoo symbol and storage instrument
    yahoo_symbol, storage_instrument = mapper.get_yahoo_for_contract(instrument)

    print(f"\nFetching 1-minute data for {instrument}")
    print("=" * 60)
    print(f"Yahoo symbol: {yahoo_symbol}")
    print(f"Storage name: {storage_instrument}")

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Downloading from Yahoo Finance...")

    # Fetch data using yfinance
    ticker = yf.Ticker(yahoo_symbol)
    df = ticker.history(
        start=start_date,
        end=end_date,
        interval='1m',
        prepost=True  # Include pre/post market data
    )

    if df.empty:
        print(f"No data returned from Yahoo Finance for {yahoo_symbol}")
        return 0

    print(f"Downloaded {len(df)} candles")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")

    # Store in database using storage instrument name
    print(f"\nStoring in database as '{storage_instrument}'...")

    with FuturesDB() as db:
        inserted_count = 0
        skipped_count = 0

        for timestamp, row in df.iterrows():
            # Convert timestamp to Unix epoch
            unix_ts = int(timestamp.timestamp())

            # Check if this candle already exists
            db.cursor.execute('''
                SELECT COUNT(*) FROM ohlc_data
                WHERE instrument = ? AND timeframe = ? AND timestamp = ?
            ''', (storage_instrument, '1m', unix_ts))

            if db.cursor.fetchone()[0] > 0:
                skipped_count += 1
                continue

            # Insert new candle using storage instrument name
            db.cursor.execute('''
                INSERT INTO ohlc_data
                (instrument, timeframe, timestamp, open_price, high_price, low_price, close_price, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                storage_instrument,
                '1m',
                unix_ts,
                float(row['Open']),
                float(row['High']),
                float(row['Low']),
                float(row['Close']),
                int(row['Volume']) if row['Volume'] > 0 else 0
            ))
            inserted_count += 1

        # Commit is automatic with FuturesDB context manager

        print(f"Inserted: {inserted_count} new candles")
        print(f"Skipped: {skipped_count} existing candles")
        print(f"Total: {len(df)} candles processed")

        return inserted_count

if __name__ == '__main__':
    import sys

    # Get instrument from command line or use default
    instrument = sys.argv[1] if len(sys.argv) > 1 else 'MNQ MAR26'
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 7

    # Fetch 1-minute data
    count = fetch_and_store_1m_data(instrument, days=days)

    if count > 0:
        print(f"\nSuccess! Added {count} 1-minute candles to database")
    else:
        print(f"\nNo new data added (may already exist in database)")
