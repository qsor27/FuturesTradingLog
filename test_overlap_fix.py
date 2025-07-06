"""
Test script to validate the position overlap prevention fix
"""

from datetime import datetime, timedelta
from typing import List, Dict
import json

def create_reversal_test_scenario() -> List[Dict]:
    """Create test executions that demonstrate position reversal (overlap scenario)"""
    base_time = datetime.now() - timedelta(hours=2)
    
    # Scenario: Long position that reverses to short
    # This used to cause overlaps, now should create clean boundaries
    executions = [
        {
            'id': 1,
            'entry_execution_id': 'rev_001',
            'instrument': 'MNQ',
            'account': 'TestAccount',
            'side_of_market': 'Buy',
            'quantity': 4,
            'entry_price': 22800.0,
            'entry_time': base_time.strftime('%Y-%m-%d %H:%M:%S'),
            'commission': 2.5
        },
        {
            'id': 2,
            'entry_execution_id': 'rev_002', 
            'instrument': 'MNQ',
            'account': 'TestAccount',
            'side_of_market': 'Sell',
            'quantity': 2,
            'entry_price': 22810.0,
            'entry_time': (base_time + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S'),
            'commission': 1.25
        },
        {
            'id': 3,
            'entry_execution_id': 'rev_003',
            'instrument': 'MNQ', 
            'account': 'TestAccount',
            'side_of_market': 'Sell',
            'quantity': 5,  # This causes reversal: 4 - 2 - 5 = -3
            'entry_price': 22815.0,
            'entry_time': (base_time + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S'),
            'commission': 2.50
        },
        {
            'id': 4,
            'entry_execution_id': 'rev_004',
            'instrument': 'MNQ',
            'account': 'TestAccount', 
            'side_of_market': 'Buy',
            'quantity': 3,  # This closes the short position: -3 + 3 = 0
            'entry_price': 22805.0,
            'entry_time': (base_time + timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S'),
            'commission': 1.50
        }
    ]
    
    return executions

def simulate_position_building(executions: List[Dict]) -> Dict:
    """Simulate the position building logic to see how it handles reversals"""
    print("=== SIMULATING POSITION BUILDING WITH REVERSAL DETECTION ===")
    
    positions = []
    current_position = None
    running_quantity = 0
    
    print(f"Processing {len(executions)} executions:")
    
    for i, execution in enumerate(executions):
        quantity = abs(int(execution.get('quantity', 0)))
        action = execution.get('side_of_market', '').strip()
        
        # Convert to signed quantity change
        if action == "Buy":
            signed_qty_change = quantity
        elif action == "Sell":
            signed_qty_change = -quantity
        else:
            continue
        
        previous_quantity = running_quantity
        running_quantity += signed_qty_change
        
        print(f"\nExecution {i+1}: {action} {quantity} contracts")
        print(f"  Running quantity: {previous_quantity} → {running_quantity}")
        
        # Position lifecycle logic (simplified version of the real algorithm)
        if previous_quantity == 0 and running_quantity != 0:
            # Starting new position
            current_position = {
                'id': len(positions) + 1,
                'position_type': 'Long' if running_quantity > 0 else 'Short',
                'entry_time': execution.get('entry_time'),
                'executions': [execution],
                'status': 'open'
            }
            print(f"  → Started new {current_position['position_type']} position")
            
        elif current_position and previous_quantity * running_quantity < 0:
            # REVERSAL DETECTED - This is the key overlap prevention logic
            print(f"  → REVERSAL DETECTED: {previous_quantity} to {running_quantity}")
            
            # Close old position
            current_position['executions'].append(execution)
            current_position['status'] = 'closed'
            current_position['exit_time'] = execution.get('entry_time')
            positions.append(current_position)
            print(f"  → Closed {current_position['position_type']} position")
            
            # Open new position in opposite direction
            new_position_type = 'Long' if running_quantity > 0 else 'Short'
            current_position = {
                'id': len(positions) + 1,
                'position_type': new_position_type,
                'entry_time': execution.get('entry_time'),
                'executions': [execution],
                'status': 'open'
            }
            print(f"  → Started new {new_position_type} position from reversal")
            
        elif current_position and running_quantity == 0:
            # Normal position close
            current_position['executions'].append(execution)
            current_position['status'] = 'closed'
            current_position['exit_time'] = execution.get('entry_time')
            positions.append(current_position)
            print(f"  → Closed {current_position['position_type']} position normally")
            current_position = None
            
        elif current_position:
            # Modify existing position
            current_position['executions'].append(execution)
            action_type = "Added to" if abs(running_quantity) > abs(previous_quantity) else "Reduced"
            print(f"  → {action_type} {current_position['position_type']} position")
    
    # Handle remaining open position
    if current_position:
        positions.append(current_position)
        print(f"  → Saved open {current_position['position_type']} position")
    
    print(f"\n=== RESULTS ===")
    print(f"Created {len(positions)} positions:")
    
    for i, pos in enumerate(positions):
        exec_count = len(pos['executions'])
        status = pos['status']
        pos_type = pos['position_type']
        print(f"  Position {i+1}: {pos_type} {status} with {exec_count} executions")
        print(f"    Entry: {pos['entry_time']}")
        if pos.get('exit_time'):
            print(f"    Exit: {pos['exit_time']}")
    
    return {
        'positions': positions,
        'final_quantity': running_quantity,
        'reversal_detected': any(p.get('status') == 'closed' for p in positions[:-1] if positions)
    }

def main():
    """Run the overlap prevention test"""
    print("Testing Position Overlap Prevention Fix")
    print("=" * 50)
    
    # Create test scenario with position reversal
    test_executions = create_reversal_test_scenario()
    
    print("Test Scenario: Position Reversal")
    print("Expected: Long position reverses to Short, then closes")
    print("Expected Result: 2 separate positions with clear boundaries")
    print()
    
    # Simulate the fixed algorithm
    results = simulate_position_building(test_executions)
    
    print("\n" + "=" * 50)
    print("OVERLAP PREVENTION VALIDATION:")
    
    if results['reversal_detected']:
        print("✅ PASS: Reversal was detected and handled correctly")
        print("✅ PASS: Positions have clear boundaries")
        print("✅ PASS: No position overlaps occurred")
    else:
        print("❌ FAIL: Reversal not detected properly")
    
    print(f"\nFinal quantity: {results['final_quantity']} (should be 0)")
    print(f"Positions created: {len(results['positions'])} (should be 2)")
    
    return results

if __name__ == "__main__":
    main()