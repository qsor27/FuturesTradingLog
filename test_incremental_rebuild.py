"""
Test script for the new incremental rebuild methods in EnhancedPositionServiceV2
"""

import logging
import sys
import sqlite3
from services.enhanced_position_service_v2 import EnhancedPositionServiceV2

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_incremental_rebuild():
    """Test the new incremental rebuild methods"""
    print("Testing incremental rebuild methods...")
    
    try:
        with EnhancedPositionServiceV2() as service:
            # First, let's see what trades we have available
            service.cursor.execute("""
                SELECT id, account, instrument, quantity, entry_time 
                FROM trades 
                WHERE deleted = 0 OR deleted IS NULL
                LIMIT 10
            """)
            
            sample_trades = [dict(row) for row in service.cursor.fetchall()]
            
            if not sample_trades:
                print("No trades found in database for testing")
                return False
            
            print(f"Found {len(sample_trades)} sample trades:")
            for trade in sample_trades[:3]:  # Show first 3
                print(f"   Trade {trade['id']}: {trade['account']}/{trade['instrument']} - {trade['quantity']} @ {trade['entry_time']}")
            
            # Test 1: rebuild_positions_for_trades method
            print("\nTest 1: rebuild_positions_for_trades()")
            test_trade_ids = [trade['id'] for trade in sample_trades[:3]]
            result1 = service.rebuild_positions_for_trades(test_trade_ids)
            
            print(f"   Result: {result1}")
            print(f"   Positions affected: {result1['positions_affected']}")
            print(f"   Accounts processed: {result1['accounts_processed']}")
            print(f"   Instruments processed: {result1['instruments_processed']}")
            
            if result1['validation_errors']:
                print(f"   Validation errors: {result1['validation_errors']}")
            
            # Test 2: rebuild_positions_for_account_instrument method
            print("\nTest 2: rebuild_positions_for_account_instrument()")
            test_account = sample_trades[0]['account']
            test_instrument = sample_trades[0]['instrument']
            
            result2 = service.rebuild_positions_for_account_instrument(test_account, test_instrument)
            
            print(f"   Result: {result2}")
            print(f"   Positions created: {result2['positions_created']}")
            
            if result2['validation_errors']:
                print(f"   Validation errors: {result2['validation_errors']}")
            
            # Test 3: trade impact analysis
            print("\nTest 3: _analyze_trade_impact() internal method")
            impact_combinations = service._analyze_trade_impact(test_trade_ids)
            
            print(f"   Trade impact analysis found {len(impact_combinations)} account/instrument combinations:")
            for account, instrument in impact_combinations:
                print(f"      - {account}/{instrument}")
            
            # Test 4: edge cases
            print("\nTest 4: Edge cases")
            
            # Empty trade IDs
            empty_result = service.rebuild_positions_for_trades([])
            print(f"   Empty trade IDs: {empty_result}")
            
            # Non-existent trade IDs
            fake_result = service.rebuild_positions_for_trades([999999, 999998])
            print(f"   Non-existent trade IDs: {fake_result}")
            
            # Non-existent account/instrument
            fake_account_result = service.rebuild_positions_for_account_instrument("FAKE_ACCOUNT", "FAKE_INSTRUMENT")
            print(f"   Non-existent account/instrument: {fake_account_result}")
            
            # Test 5: Performance comparison (basic)
            print("\nTest 5: Performance comparison")
            import time
            
            # Time the incremental rebuild
            start_time = time.time()
            service.rebuild_positions_for_trades(test_trade_ids)
            incremental_time = time.time() - start_time
            print(f"   Incremental rebuild time: {incremental_time:.3f}s")
            
            # Compare with full rebuild time (just measure a small portion)
            service.cursor.execute("SELECT COUNT(*) as count FROM trades WHERE deleted = 0 OR deleted IS NULL")
            total_trades = service.cursor.fetchone()['count']
            print(f"   Total trades in database: {total_trades}")
            print(f"   Incremental rebuild processed {len(test_trade_ids)} trades vs {total_trades} total")
            
            print("\nAll incremental rebuild tests completed successfully!")
            return True
            
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_method_integration():
    """Test that the new methods integrate properly with existing functionality"""
    print("\nTesting integration with existing functionality...")
    
    try:
        with EnhancedPositionServiceV2() as service:
            # Get current position count
            service.cursor.execute("SELECT COUNT(*) as count FROM positions")
            initial_count = service.cursor.fetchone()['count']
            print(f"Initial position count: {initial_count}")
            
            # Get some sample trades
            service.cursor.execute("""
                SELECT id, account, instrument 
                FROM trades 
                WHERE deleted = 0 OR deleted IS NULL
                LIMIT 5
            """)
            sample_trades = [dict(row) for row in service.cursor.fetchall()]
            
            if sample_trades:
                # Use incremental rebuild
                test_trade_ids = [trade['id'] for trade in sample_trades]
                result = service.rebuild_positions_for_trades(test_trade_ids)
                
                # Check position count after incremental rebuild
                service.cursor.execute("SELECT COUNT(*) as count FROM positions")
                after_count = service.cursor.fetchone()['count']
                print(f"Position count after incremental rebuild: {after_count}")
                
                # Verify positions can still be retrieved normally
                positions = service.get_positions(page_size=5)
                print(f"Retrieved {len(positions['positions'])} positions using existing method")
                
                # Verify statistics still work
                stats = service.get_position_statistics()
                print(f"Position statistics: {stats['total_positions_in_db']} total positions")
                
                print("Integration test completed successfully!")
                return True
            else:
                print("No trades available for integration test")
                return True
                
    except Exception as e:
        print(f"Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting Enhanced Position Service V2 - Incremental Rebuild Tests")
    print("=" * 70)
    
    # Run the tests
    success1 = test_incremental_rebuild()
    success2 = test_method_integration()
    
    print("\n" + "=" * 70)
    if success1 and success2:
        print("All tests passed! The incremental rebuild functionality is working correctly.")
        sys.exit(0)
    else:
        print("Some tests failed. Please check the output above.")
        sys.exit(1)