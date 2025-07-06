"""
Simple Position Overlap Check
Direct SQL analysis without external dependencies
"""

import sqlite3
from datetime import datetime
from config import config


def check_position_overlaps():
    """Check for position overlaps using direct SQL"""
    db_path = config.db_path
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all positions ordered by account, instrument, and time
        cursor.execute("""
            SELECT id, instrument, account, position_type, entry_time, exit_time, 
                   position_status, total_quantity, execution_count
            FROM positions 
            ORDER BY account, instrument, entry_time
        """)
        positions = [dict(row) for row in cursor.fetchall()]
        
        if not positions:
            print("No positions found to analyze")
            return
        
        print(f"Analyzing {len(positions)} positions for overlaps...")
        
        # Group positions by account and instrument
        grouped = {}
        for pos in positions:
            key = (pos['account'], pos['instrument'])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(pos)
        
        print(f"Found {len(grouped)} account/instrument groups")
        
        overlaps_found = 0
        
        for (account, instrument), group in grouped.items():
            print(f"\nAnalyzing {account}/{instrument}: {len(group)} positions")
            
            if len(group) < 2:
                print(f"  Only one position, no overlaps possible")
                continue
            
            # Sort positions by entry time
            group_sorted = sorted(group, key=lambda p: p['entry_time'])
            
            for i in range(len(group_sorted) - 1):
                current = group_sorted[i]
                next_pos = group_sorted[i + 1]
                
                print(f"  Checking positions {current['id']} and {next_pos['id']}")
                print(f"    Position {current['id']}: {current['position_type']} {current['entry_time']} -> {current['exit_time']} ({current['position_status']})")
                print(f"    Position {next_pos['id']}: {next_pos['position_type']} {next_pos['entry_time']} -> {next_pos['exit_time']} ({next_pos['position_status']})")
                
                # Check for overlaps
                if current['position_status'] == 'open':
                    print(f"    ⚠️  OVERLAP: Position {current['id']} is still open when position {next_pos['id']} starts")
                    overlaps_found += 1
                
                elif current['exit_time'] and next_pos['entry_time']:
                    try:
                        # Simple string comparison for timestamps
                        if current['exit_time'] > next_pos['entry_time']:
                            print(f"    ⚠️  OVERLAP: Position {current['id']} ends after position {next_pos['id']} starts")
                            overlaps_found += 1
                        else:
                            print(f"    ✓ No overlap detected")
                    except:
                        print(f"    ⚠️  Could not compare timestamps")
                        overlaps_found += 1
                
                # Check for same position type (possible missing zero crossing)
                if current['position_type'] == next_pos['position_type']:
                    print(f"    ⚠️  CONSISTENCY: Both positions are {current['position_type']} - possible missing zero crossing")
                    overlaps_found += 1
        
        print(f"\n" + "="*80)
        print(f"ANALYSIS COMPLETE")
        print(f"Total overlaps/issues found: {overlaps_found}")
        print(f"="*80)
        
        conn.close()
        
    except Exception as e:
        print(f"Error analyzing positions: {e}")


def check_quantity_flow():
    """Check quantity flow consistency"""
    db_path = config.db_path
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all trades ordered by account, instrument, and time
        cursor.execute("""
            SELECT id, instrument, account, side_of_market, quantity, entry_time, 
                   entry_execution_id, deleted
            FROM trades 
            WHERE deleted = 0 OR deleted IS NULL
            ORDER BY account, instrument, entry_time
        """)
        trades = [dict(row) for row in cursor.fetchall()]
        
        if not trades:
            print("No trades found to analyze")
            return
        
        print(f"Analyzing quantity flow for {len(trades)} trades...")
        
        # Group trades by account and instrument
        grouped = {}
        for trade in trades:
            key = (trade['account'], trade['instrument'])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(trade)
        
        violations = 0
        
        for (account, instrument), group in grouped.items():
            print(f"\nAnalyzing quantity flow for {account}/{instrument}: {len(group)} trades")
            
            running_quantity = 0
            
            for i, trade in enumerate(group):
                try:
                    quantity = abs(int(trade['quantity']))
                    action = trade['side_of_market'].strip()
                    
                    # Calculate signed quantity change
                    if action == "Buy":
                        signed_qty_change = quantity
                    elif action == "Sell":
                        signed_qty_change = -quantity
                    else:
                        print(f"    ⚠️  Unknown action: {action} for trade {trade['id']}")
                        violations += 1
                        continue
                    
                    previous_quantity = running_quantity
                    running_quantity += signed_qty_change
                    
                    print(f"    Trade {i+1}: {action} {quantity} | Running: {previous_quantity} → {running_quantity}")
                    
                    # Check for direction change without zero crossing
                    if previous_quantity != 0 and running_quantity != 0:
                        if (previous_quantity > 0 and running_quantity < 0) or (previous_quantity < 0 and running_quantity > 0):
                            print(f"    ⚠️  VIOLATION: Direction change without zero crossing!")
                            violations += 1
                    
                except (ValueError, TypeError) as e:
                    print(f"    ⚠️  Error processing trade {trade['id']}: {e}")
                    violations += 1
            
            # Check final quantity
            if running_quantity != 0:
                print(f"    ⚠️  VIOLATION: Final quantity is {running_quantity}, expected 0")
                violations += 1
            else:
                print(f"    ✓ Quantity flow ends at zero")
        
        print(f"\n" + "="*80)
        print(f"QUANTITY FLOW ANALYSIS COMPLETE")
        print(f"Total violations found: {violations}")
        print(f"="*80)
        
        conn.close()
        
    except Exception as e:
        print(f"Error analyzing quantity flow: {e}")


def main():
    """Run the analysis"""
    print("POSITION OVERLAP ANALYSIS")
    print("=" * 80)
    print(f"Analysis started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print("1. CHECKING POSITION OVERLAPS")
    print("-" * 40)
    check_position_overlaps()
    
    print("\n2. CHECKING QUANTITY FLOW")
    print("-" * 40)
    check_quantity_flow()


if __name__ == "__main__":
    main()