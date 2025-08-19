#!/usr/bin/env python3
"""
Test script for instrument mapping solution
Validates that charts work regardless of instrument name format
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from TradingLog_db import FuturesDB
from data_service import ohlc_service
from datetime import datetime, timedelta
import json

def test_instrument_mapping():
    """Test the instrument mapping solution"""
    print("=== TESTING INSTRUMENT MAPPING SOLUTION ===")
    
    # Test instruments with different formats
    test_cases = [
        "MNQ SEP25",   # With expiration
        "MNQ",         # Base symbol
        "ES DEC24",    # Another with expiration
        "ES"           # Another base symbol
    ]
    
    results = {}
    
    for instrument in test_cases:
        print(f"\nTesting instrument: {instrument}")
        
        try:
            # Test base symbol extraction
            base_symbol = ohlc_service._get_base_instrument(instrument)
            print(f"  Base symbol: {base_symbol}")
            
            # Check OHLC data availability
            with FuturesDB() as db:
                count = db.get_ohlc_count(base_symbol)
                print(f"  OHLC records for {base_symbol}: {count}")
            
            # Test chart data retrieval
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            chart_data = ohlc_service.get_chart_data(instrument, '1h', start_date, end_date)
            print(f"  Chart data returned: {len(chart_data)} records")
            
            results[instrument] = {
                'base_symbol': base_symbol,
                'ohlc_count': count,
                'chart_data_count': len(chart_data),
                'success': len(chart_data) > 0
            }
            
        except Exception as e:
            print(f"  ERROR: {e}")
            results[instrument] = {
                'error': str(e),
                'success': False
            }
    
    return results

def test_chart_api():
    """Test the chart API endpoints"""
    print("\n=== TESTING CHART API ===")
    
    try:
        import requests
        
        test_instruments = ["MNQ SEP25", "MNQ"]
        
        for instrument in test_instruments:
            url = f"http://localhost:5000/api/chart-data/{instrument}?timeframe=1h&days=7"
            print(f"\nTesting API: {url}")
            
            try:
                response = requests.get(url, timeout=30)
                print(f"  Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"  Success: {data.get('success')}")
                    print(f"  Count: {data.get('count', 0)}")
                    
                    if data.get('error'):
                        print(f"  Error: {data['error']}")
                        
                else:
                    print(f"  HTTP Error: {response.text[:200]}")
                    
            except Exception as e:
                print(f"  Request failed: {e}")
                
    except ImportError:
        print("requests package not available - skipping API tests")

def validate_migration():
    """Validate the migration worked correctly"""
    print("\n=== VALIDATING MIGRATION ===")
    
    with FuturesDB() as db:
        # Check for any remaining instruments with expiration dates
        db.cursor.execute("""
            SELECT DISTINCT instrument 
            FROM ohlc_data 
            WHERE instrument LIKE '% %'
        """)
        
        remaining_expiry_instruments = [row[0] for row in db.cursor.fetchall()]
        
        if remaining_expiry_instruments:
            print(f"WARNING: Found instruments with expiration dates: {remaining_expiry_instruments}")
        else:
            print("✓ All OHLC data uses base instrument symbols")
        
        # Show current instrument distribution
        db.cursor.execute("""
            SELECT instrument, COUNT(*) as record_count
            FROM ohlc_data 
            GROUP BY instrument
            ORDER BY record_count DESC
        """)
        
        instrument_counts = db.cursor.fetchall()
        print("\nOHLC data distribution:")
        for instrument, count in instrument_counts:
            print(f"  {instrument}: {count} records")

def main():
    """Main test function"""
    print("Instrument Mapping Solution Test")
    print("=" * 50)
    
    # Run tests
    mapping_results = test_instrument_mapping()
    test_chart_api()
    validate_migration()
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    success_count = sum(1 for result in mapping_results.values() if result.get('success', False))
    total_count = len(mapping_results)
    
    print(f"Instrument mapping tests: {success_count}/{total_count} passed")
    
    for instrument, result in mapping_results.items():
        status = "✓" if result.get('success', False) else "✗"
        print(f"  {status} {instrument}: {result.get('chart_data_count', 0)} chart records")
    
    if success_count == total_count:
        print("\n✓ ALL TESTS PASSED - Chart data available for all instrument formats")
    else:
        print(f"\n✗ {total_count - success_count} tests failed")

if __name__ == "__main__":
    main()