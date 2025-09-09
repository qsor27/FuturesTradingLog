#!/usr/bin/env python3
"""
Test script to verify multi-timeframe OHLC data downloads work correctly.
This tests the enhanced update_recent_data method with detailed logging.
"""
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scripts.TradingLog_db import FuturesDB
from services.data_service import DataService
from config import config

def setup_test_logging():
    """Setup detailed logging for the test"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set data service logger to debug level
    data_service_logger = logging.getLogger('services.data_service')
    data_service_logger.setLevel(logging.DEBUG)

def check_database_before():
    """Check current database state before test"""
    print("=== DATABASE STATE BEFORE TEST ===")
    try:
        with FuturesDB() as db:
            db.cursor.execute("""
                SELECT instrument, timeframe, COUNT(*) as count 
                FROM ohlc_data 
                GROUP BY instrument, timeframe 
                ORDER BY instrument, timeframe
            """)
            results = db.cursor.fetchall()
            
            if results:
                for row in results:
                    print(f"  {row[0]} | {row[1]} | {row[2]} records")
            else:
                print("  No OHLC data found in database")
    except Exception as e:
        print(f"  Error checking database: {e}")

def check_database_after():
    """Check database state after test"""
    print("\n=== DATABASE STATE AFTER TEST ===")
    try:
        with FuturesDB() as db:
            db.cursor.execute("""
                SELECT instrument, timeframe, COUNT(*) as count 
                FROM ohlc_data 
                GROUP BY instrument, timeframe 
                ORDER BY instrument, timeframe
            """)
            results = db.cursor.fetchall()
            
            if results:
                for row in results:
                    print(f"  {row[0]} | {row[1]} | {row[2]} records")
                    
                # Show summary
                print(f"\nSummary:")
                timeframes = set(row[1] for row in results)
                instruments = set(row[0] for row in results)
                total_records = sum(row[2] for row in results)
                
                print(f"  Instruments: {len(instruments)} ({', '.join(sorted(instruments))})")
                print(f"  Timeframes: {len(timeframes)} ({', '.join(sorted(timeframes))})")
                print(f"  Total records: {total_records}")
            else:
                print("  No OHLC data found in database")
    except Exception as e:
        print(f"  Error checking database: {e}")

def test_multi_timeframe_download():
    """Test the enhanced multi-timeframe download functionality"""
    print("=== TESTING MULTI-TIMEFRAME DOWNLOAD ===")
    print(f"Testing with instrument: MNQ")
    print(f"Database path: {config.db_path}")
    
    setup_test_logging()
    check_database_before()
    
    # Create data service instance
    try:
        data_service = DataService()
        print(f"\nDataService created successfully")
        
        # Test with MNQ and all supported timeframes
        instrument = "MNQ"
        timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
        
        print(f"\nStarting multi-timeframe download for {instrument}")
        print(f"Timeframes to download: {timeframes}")
        
        # Call the enhanced update_recent_data method
        success = data_service.update_recent_data(instrument, timeframes)
        
        print(f"\n=== DOWNLOAD COMPLETED ===")
        print(f"Overall success: {success}")
        
        check_database_after()
        
        return success
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Multi-Timeframe Download Test")
    print("=" * 50)
    print(f"Started at: {datetime.now()}")
    
    success = test_multi_timeframe_download()
    
    print(f"\nTest completed at: {datetime.now()}")
    print(f"Test result: {'SUCCESS' if success else 'FAILURE'}")
    
    sys.exit(0 if success else 1)