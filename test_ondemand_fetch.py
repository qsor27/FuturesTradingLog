#!/usr/bin/env python3
"""Test script to simulate the on-demand fetch process"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_ondemand_fetch():
    """Test the on-demand fetch process that the API uses"""
    print("=== Testing On-Demand Fetch Process ===")
    
    try:
        from TradingLog_db import FuturesDB
        from services.ohlc_service import OHLCOnDemandService
        from utils.instrument_utils import get_root_symbol
        from config import SUPPORTED_TIMEFRAMES
        
        instrument = 'MNQ'
        root_symbol = get_root_symbol(instrument)
        print(f"Testing on-demand fetch for '{instrument}' -> '{root_symbol}'")
        
        with FuturesDB() as db:
            # Check current state
            current_count = db.get_ohlc_count(root_symbol)
            print(f"Current OHLC count for {root_symbol}: {current_count}")
            
            if current_count == 0:
                print(f"Triggering on-demand fetch for {instrument}...")
                
                # This is what the API does
                ohlc_service = OHLCOnDemandService(db)
                
                try:
                    success = ohlc_service.fetch_and_store_ohlc(instrument)
                    print(f"On-demand fetch success: {success}")
                    
                    if success:
                        # Check what was fetched
                        print(f"\n=== After fetch - checking available timeframes ===")
                        for tf in SUPPORTED_TIMEFRAMES:
                            count = db.get_ohlc_count(root_symbol, tf)
                            print(f"{root_symbol} {tf}: {count} records")
                    
                except Exception as fetch_error:
                    print(f"On-demand fetch failed: {fetch_error}")
                    print(f"Error type: {type(fetch_error).__name__}")
                    import traceback
                    traceback.print_exc()
            
            # Now test the available timeframes logic
            print(f"\n=== Testing Available Timeframes Logic ===")
            available_timeframes = []
            for timeframe in SUPPORTED_TIMEFRAMES:
                count = db.get_ohlc_count(root_symbol, timeframe)
                if count > 0:
                    available_timeframes.append({'timeframe': timeframe, 'count': count})
            
            # Convert to API response format
            available = {}
            for tf in available_timeframes:
                available[tf['timeframe']] = tf['count']
            
            print(f"Available timeframes: {available}")
            
            # Simulate API response
            result = {
                'success': True,
                'instrument': instrument,
                'available_timeframes': available,
                'best_timeframe': None,
                'total_timeframes': len(available)
            }
            
            if available_timeframes:
                from config import TIMEFRAME_PREFERENCE_ORDER
                for pref in TIMEFRAME_PREFERENCE_ORDER:
                    if any(tf['timeframe'] == pref for tf in available_timeframes):
                        result['best_timeframe'] = pref
                        break
            
            print(f"Final API response: {result}")
            
    except Exception as e:
        print(f"Test error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ondemand_fetch()