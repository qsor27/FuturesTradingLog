#!/usr/bin/env python3
"""
Simple test script to verify execution display functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.enhanced_position_service_v2 import EnhancedPositionServiceV2

def test_execution_display():
    """Test the execution display functionality"""
    print("Testing execution display functionality...")
    
    with EnhancedPositionServiceV2() as service:
        # Get available positions
        result = service.get_positions(page_size=10)
        positions = result['positions']
        
        print(f"\nFound {len(positions)} positions:")
        for pos in positions:
            print(f"  Position {pos['id']}: {pos['instrument']} - {pos['execution_count']} executions")
        
        if positions:
            # Test with the first position
            test_position = positions[0]
            position_id = test_position['id']
            
            print(f"\nTesting with Position {position_id}:")
            print(f"  Instrument: {test_position['instrument']}")
            print(f"  Expected executions: {test_position['execution_count']}")
            
            # Get executions for this position
            executions = service.get_position_executions(position_id)
            print(f"  Actual executions retrieved: {len(executions)}")
            
            if executions:
                print("\nExecution details:")
                for i, exec in enumerate(executions):
                    print(f"    {i+1}. ID: {exec.get('id')}, Side: {exec.get('side_of_market')}, "
                          f"Qty: {exec.get('quantity')}, Price: {exec.get('entry_price')}")
                
                # Simulate what the template would see
                test_position['executions'] = executions
                print(f"\nTemplate would receive:")
                print(f"  position['execution_count']: {test_position['execution_count']}")
                print(f"  len(position['executions']): {len(test_position['executions'])}")
                print(f"  Template iteration would show: {len(executions)} rows")
                
                return True
            else:
                print("  ❌ No executions found!")
                return False
        else:
            print("  ❌ No positions found to test!")
            return False

if __name__ == "__main__":
    success = test_execution_display()
    sys.exit(0 if success else 1)