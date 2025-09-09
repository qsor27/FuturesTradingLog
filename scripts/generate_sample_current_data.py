#!/usr/bin/env python3
"""
Generate current sample OHLC data for testing chart functionality.
This creates realistic-looking price data with current timestamps.
"""

import random
import math
from datetime import datetime, timedelta
from scripts.TradingLog_db import FuturesDB

def generate_realistic_ohlc(start_price=22000, num_candles=200, timeframe_minutes=60):
    """Generate realistic OHLC data with trending patterns"""
    data = []
    current_price = start_price
    trend_strength = 0.0  # Overall trend bias
    volatility = 0.02     # Price volatility factor
    
    # Start from current time and go backwards
    end_time = datetime.now()
    current_time = end_time - timedelta(minutes=timeframe_minutes * num_candles)
    
    for i in range(num_candles):
        # Add some trending behavior
        trend_change = random.uniform(-0.001, 0.001)
        trend_strength = max(-0.01, min(0.01, trend_strength + trend_change))
        
        # Generate the open price (close of previous becomes open of current)
        if i == 0:
            open_price = current_price
        else:
            open_price = data[-1]['close']
        
        # Add trend and random movement
        trend_move = open_price * trend_strength
        random_move = open_price * volatility * random.uniform(-1, 1)
        close_price = open_price + trend_move + random_move
        
        # Generate high and low around open/close
        high_low_range = abs(close_price - open_price) * random.uniform(1.5, 3.0)
        if high_low_range < open_price * 0.001:  # Minimum range
            high_low_range = open_price * 0.001
            
        high_price = max(open_price, close_price) + high_low_range * random.uniform(0.2, 1.0)
        low_price = min(open_price, close_price) - high_low_range * random.uniform(0.2, 1.0)
        
        # Generate volume (higher volume during price moves)
        price_change_pct = abs(close_price - open_price) / open_price
        base_volume = random.randint(2000, 5000)
        volume_multiplier = 1 + (price_change_pct * 10)  # Higher volume on bigger moves
        volume = int(base_volume * volume_multiplier)
        
        data.append({
            'timestamp': int(current_time.timestamp()),
            'instrument': 'MNQ',
            'timeframe': '1h',
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': volume
        })
        
        current_time += timedelta(minutes=timeframe_minutes)
    
    return data

def generate_multiple_timeframes():
    """Generate data for multiple timeframes"""
    print("Generating current sample OHLC data...")
    
    with FuturesDB() as db:
        # Clear existing MNQ data first
        print("Clearing existing MNQ data...")
        db.cursor.execute("DELETE FROM ohlc_data WHERE instrument = 'MNQ'")
        
        # Generate 1h data (7 days worth)
        print("Generating 1h data...")
        hourly_data = generate_realistic_ohlc(start_price=22100, num_candles=168, timeframe_minutes=60)
        for record in hourly_data:
            record['timeframe'] = '1h'
        
        # Generate 4h data (30 days worth) 
        print("Generating 4h data...")
        four_hour_data = generate_realistic_ohlc(start_price=22100, num_candles=180, timeframe_minutes=240)
        for record in four_hour_data:
            record['timeframe'] = '4h'
            
        # Generate 1d data (90 days worth)
        print("Generating 1d data...")
        daily_data = generate_realistic_ohlc(start_price=22100, num_candles=90, timeframe_minutes=1440)
        for record in daily_data:
            record['timeframe'] = '1d'
        
        # Insert all data
        all_data = hourly_data + four_hour_data + daily_data
        print(f"Inserting {len(all_data)} records...")
        
        if db.insert_ohlc_batch(all_data):
            print(f"✅ Successfully inserted {len(all_data)} OHLC records")
            
            # Show summary
            for timeframe in ['1h', '4h', '1d']:
                count = len([r for r in all_data if r['timeframe'] == timeframe])
                latest_record = max([r for r in all_data if r['timeframe'] == timeframe], key=lambda x: x['timestamp'])
                latest_time = datetime.fromtimestamp(latest_record['timestamp'])
                print(f"  {timeframe}: {count} records, latest: {latest_time}")
        else:
            print("❌ Failed to insert OHLC data")

if __name__ == "__main__":
    generate_multiple_timeframes()