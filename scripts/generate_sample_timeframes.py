#!/usr/bin/env python3
"""
Generate sample OHLC data for multiple timeframes from existing 1h data
This provides realistic data for testing timeframe switching functionality
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.TradingLog_db import FuturesDB

logger = logging.getLogger(__name__)

class TimeframeGenerator:
    """Generate sample timeframes from existing 1h data"""
    
    def __init__(self):
        self.db = None
        
    def generate_multiple_timeframes(self, instrument: str = 'MNQ') -> Dict[str, Any]:
        """
        Generate sample data for multiple timeframes based on existing 1h data
        
        Args:
            instrument: The instrument to generate data for
            
        Returns:
            Dict with operation results
        """
        results = {
            'success': False,
            'generated_timeframes': [],
            'total_records': 0,
            'errors': []
        }
        
        print(f"Generating sample timeframes for {instrument}")
        
        try:
            with FuturesDB() as db:
                self.db = db
                
                # Get existing 1h data to base other timeframes on
                base_data = self._get_existing_1h_data(instrument)
                if not base_data:
                    print("No existing 1h data found - cannot generate other timeframes")
                    return results
                
                print(f"Found {len(base_data)} 1h records to base generation on")
                
                # Generate data for different timeframes
                timeframes_to_generate = ['1m', '5m', '15m', '1d']
                
                for timeframe in timeframes_to_generate:
                    try:
                        records_added = self._generate_timeframe_data(instrument, timeframe, base_data)
                        if records_added > 0:
                            results['generated_timeframes'].append(timeframe)
                            results['total_records'] += records_added
                            print(f"Generated {records_added} records for {timeframe}")
                        else:
                            print(f"No data generated for {timeframe}")
                    except Exception as e:
                        error_msg = f"Failed to generate {timeframe}: {str(e)}"
                        print(error_msg)
                        results['errors'].append(error_msg)
                
                results['success'] = len(results['generated_timeframes']) > 0
                
                if results['success']:
                    print(f"Sample data generation completed successfully. "
                          f"Generated {len(results['generated_timeframes'])} timeframes "
                          f"with {results['total_records']} total records")
                else:
                    print("Sample data generation completed but no new data was added")
                
                return results
                
        except Exception as e:
            print(f"Sample data generation failed: {e}")
            results['success'] = False
            results['errors'].append(str(e))
            return results
    
    def _get_existing_1h_data(self, instrument: str) -> List[Dict]:
        """Get existing 1h data to base other timeframes on"""
        self.db.cursor.execute('''
            SELECT timestamp, open_price, high_price, low_price, close_price, volume
            FROM ohlc_data 
            WHERE instrument = ? AND timeframe = '1h'
            ORDER BY timestamp
        ''', (instrument,))
        
        data = []
        for row in self.db.cursor.fetchall():
            data.append({
                'timestamp': row[0],
                'open_price': row[1],
                'high_price': row[2],
                'low_price': row[3],
                'close_price': row[4],
                'volume': row[5]
            })
        
        return data
    
    def _generate_timeframe_data(self, instrument: str, timeframe: str, base_data: List[Dict]) -> int:
        """Generate data for a specific timeframe based on 1h data"""
        
        if timeframe == '1d':
            return self._generate_daily_data(instrument, base_data)
        elif timeframe in ['1m', '5m', '15m']:
            return self._generate_intraday_data(instrument, timeframe, base_data)
        else:
            print(f"Timeframe {timeframe} not supported for generation")
            return 0
    
    def _generate_daily_data(self, instrument: str, base_data: List[Dict]) -> int:
        """Generate daily data by aggregating 1h data"""
        
        # Group 1h data by day
        daily_groups = {}
        for record in base_data:
            day_start = datetime.fromtimestamp(record['timestamp']).replace(hour=0, minute=0, second=0, microsecond=0)
            day_key = int(day_start.timestamp())
            
            if day_key not in daily_groups:
                daily_groups[day_key] = []
            daily_groups[day_key].append(record)
        
        records_added = 0
        
        for day_timestamp, day_records in daily_groups.items():
            if len(day_records) < 3:  # Need at least a few hours of data
                continue
                
            # Aggregate the day's data
            open_price = day_records[0]['open_price']
            close_price = day_records[-1]['close_price']
            high_price = max(r['high_price'] for r in day_records)
            low_price = min(r['low_price'] for r in day_records)
            volume = sum(r['volume'] for r in day_records)
            
            # Insert daily record
            try:
                self.db.cursor.execute('''
                    INSERT OR REPLACE INTO ohlc_data 
                    (instrument, timeframe, timestamp, open_price, high_price, low_price, close_price, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (instrument, '1d', day_timestamp, open_price, high_price, low_price, close_price, volume))
                
                records_added += 1
            except Exception as e:
                print(f"Failed to insert daily record for {day_timestamp}: {e}")
        
        self.db.conn.commit()
        return records_added
    
    def _generate_intraday_data(self, instrument: str, timeframe: str, base_data: List[Dict]) -> int:
        """Generate intraday data by interpolating between 1h candles"""
        
        # Calculate how many sub-candles per hour
        minutes_per_candle = {
            '1m': 1,
            '5m': 5,
            '15m': 15
        }
        
        candles_per_hour = 60 // minutes_per_candle[timeframe]
        records_added = 0
        
        for i, hour_data in enumerate(base_data):
            if i == 0:
                continue  # Skip first record as we need previous for interpolation
                
            prev_data = base_data[i-1]
            
            # Generate sub-candles for this hour
            hour_start = hour_data['timestamp']
            price_range = hour_data['high_price'] - hour_data['low_price']
            
            for candle_index in range(candles_per_hour):
                # Calculate timestamp for this sub-candle
                candle_timestamp = hour_start - (3600 - (candle_index * minutes_per_candle[timeframe] * 60))
                
                # Generate realistic OHLC within the hour's range
                base_price = prev_data['close_price'] + (hour_data['close_price'] - prev_data['close_price']) * (candle_index / candles_per_hour)
                
                # Add some randomness but keep within realistic bounds
                volatility = price_range * 0.3  # 30% of hour's range
                
                open_price = base_price + random.uniform(-volatility/4, volatility/4)
                close_price = open_price + random.uniform(-volatility/2, volatility/2)
                
                high_price = max(open_price, close_price) + random.uniform(0, volatility/3)
                low_price = min(open_price, close_price) - random.uniform(0, volatility/3)
                
                # Ensure price constraints
                high_price = min(high_price, hour_data['high_price'])
                low_price = max(low_price, hour_data['low_price'])
                
                volume = hour_data['volume'] // candles_per_hour + random.randint(-10, 10)
                volume = max(1, volume)  # Ensure positive volume
                
                try:
                    self.db.cursor.execute('''
                        INSERT OR REPLACE INTO ohlc_data 
                        (instrument, timeframe, timestamp, open_price, high_price, low_price, close_price, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (instrument, timeframe, candle_timestamp, open_price, high_price, low_price, close_price, volume))
                    
                    records_added += 1
                except Exception as e:
                    print(f"Failed to insert {timeframe} record for {candle_timestamp}: {e}")
        
        self.db.conn.commit()
        return records_added

def run_timeframe_generation(instrument: str = 'MNQ') -> Dict[str, Any]:
    """
    Convenience function to run timeframe generation
    
    Args:
        instrument: The instrument to generate timeframes for
        
    Returns:
        Results dictionary
    """
    generator = TimeframeGenerator()
    return generator.generate_multiple_timeframes(instrument)

if __name__ == "__main__":
    print("=== SAMPLE TIMEFRAME GENERATION ===")
    print("Generating sample data for multiple timeframes...")
    
    results = run_timeframe_generation('MNQ')
    
    print(f"\nResults:")
    print(f"Success: {results['success']}")
    print(f"Generated timeframes: {results['generated_timeframes']}")
    print(f"Total records added: {results['total_records']}")
    
    if results['errors']:
        print(f"Errors encountered:")
        for error in results['errors']:
            print(f"  - {error}")
    
    print("\n=== GENERATION COMPLETE ===")