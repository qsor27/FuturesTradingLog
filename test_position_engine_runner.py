"""
Test runner for position engine without pytest dependency
"""

import sys
import traceback
from position_engine import PositionEngine, PositionSide, ExecutionAction


def create_raw_execution(execution_id: str, instrument: str, account: str,
                       side: str, quantity: int, price: float, 
                       timestamp: str, commission: float = 0.0):
    """Helper to create raw execution dictionary"""
    return {
        'entry_execution_id': execution_id,
        'instrument': instrument,
        'account': account,
        'side_of_market': side,
        'quantity': quantity,
        'entry_price': price,
        'entry_time': timestamp,
        'commission': commission
    }


def test_simple_long_position():
    """Test basic long position: Buy → Sell"""
    print("Testing simple long position...")
    
    executions = [
        create_raw_execution('1', 'ES', 'Test', 'Buy', 2, 4000.0, '2023-01-01 09:00:00'),
        create_raw_execution('2', 'ES', 'Test', 'Sell', 2, 4010.0, '2023-01-01 10:00:00'),
    ]
    
    positions = PositionEngine.build_positions_from_executions(executions)
    
    assert len(positions) == 1
    position = positions[0]
    
    assert position.side == PositionSide.LONG
    assert position.total_quantity == 4  # 2 + 2 for entry and exit
    assert position.average_entry_price == 4000.0
    assert position.average_exit_price == 4010.0
    assert position.total_points_pnl == 10.0  # 4010 - 4000
    assert position.is_closed is True
    assert len(position.executions) == 2
    
    print("✓ Simple long position test passed")


def test_position_reversal():
    """Test position reversal: Long → Short without touching zero"""
    print("Testing position reversal...")
    
    executions = [
        create_raw_execution('1', 'ES', 'Test', 'Buy', 2, 4000.0, '2023-01-01 09:00:00'),  # Long 2
        create_raw_execution('2', 'ES', 'Test', 'Sell', 5, 4010.0, '2023-01-01 10:00:00'), # Sell 5: Close 2, Short 3
    ]
    
    positions = PositionEngine.build_positions_from_executions(executions)
    
    assert len(positions) == 2
    
    # First position: Long position that was closed
    long_position = positions[0]
    assert long_position.side == PositionSide.LONG
    assert long_position.is_closed is True
    
    # Second position: Short position that was opened
    short_position = positions[1]
    assert short_position.side == PositionSide.SHORT
    assert short_position.is_closed is False  # Still open
    
    print("✓ Position reversal test passed")


def test_multiple_round_trips():
    """Test multiple complete round trips"""
    print("Testing multiple round trips...")
    
    executions = [
        # First round trip: Long
        create_raw_execution('1', 'ES', 'Test', 'Buy', 1, 4000.0, '2023-01-01 09:00:00'),
        create_raw_execution('2', 'ES', 'Test', 'Sell', 1, 4010.0, '2023-01-01 09:30:00'),
        
        # Second round trip: Short
        create_raw_execution('3', 'ES', 'Test', 'Sell', 2, 4020.0, '2023-01-01 10:00:00'),
        create_raw_execution('4', 'ES', 'Test', 'Buy', 2, 4005.0, '2023-01-01 10:30:00'),
        
        # Third round trip: Long
        create_raw_execution('5', 'ES', 'Test', 'Buy', 3, 4015.0, '2023-01-01 11:00:00'),
        create_raw_execution('6', 'ES', 'Test', 'Sell', 3, 4025.0, '2023-01-01 11:30:00'),
    ]
    
    positions = PositionEngine.build_positions_from_executions(executions)
    
    assert len(positions) == 3
    
    # All positions should be closed
    for position in positions:
        assert position.is_closed is True
    
    # Check position sides
    assert positions[0].side == PositionSide.LONG
    assert positions[1].side == PositionSide.SHORT
    assert positions[2].side == PositionSide.LONG
    
    print("✓ Multiple round trips test passed")


def test_empty_executions():
    """Test handling of empty execution list"""
    print("Testing empty executions...")
    
    positions = PositionEngine.build_positions_from_executions([])
    assert positions == []
    
    print("✓ Empty executions test passed")


def test_invalid_execution_data():
    """Test handling of invalid execution data"""
    print("Testing invalid execution data...")
    
    invalid_executions = [
        # Missing required fields
        {'instrument': 'ES', 'quantity': 1},
        # Invalid side_of_market
        {'instrument': 'ES', 'account': 'Test', 'side_of_market': 'Invalid', 'quantity': 1, 'entry_price': 100, 'entry_time': '2023-01-01'},
        # Zero quantity
        {'instrument': 'ES', 'account': 'Test', 'side_of_market': 'Buy', 'quantity': 0, 'entry_price': 100, 'entry_time': '2023-01-01'},
    ]
    
    positions = PositionEngine.build_positions_from_executions(invalid_executions)
    assert positions == []
    
    print("✓ Invalid execution data test passed")


def run_all_tests():
    """Run all tests"""
    tests = [
        test_empty_executions,
        test_invalid_execution_data,
        test_simple_long_position,
        test_position_reversal,
        test_multiple_round_trips
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            traceback.print_exc()
            failed += 1
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print("❌ Some tests failed!")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)