#!/usr/bin/env python3

import sqlite3
import json
from config import config

def analyze_pnl_calculation():
    """Analyze how P&L is calculated and stored"""
    
    # Connect to database
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=== ANALYZING P&L CALCULATION ===\n")
    
    # Get sample trades
    cursor.execute("""
        SELECT instrument, side_of_market, quantity, entry_price, exit_price, 
               points_gain_loss, dollars_gain_loss, commission, account, entry_execution_id
        FROM trades 
        ORDER BY entry_time DESC
        LIMIT 10
    """)
    
    trades = cursor.fetchall()
    
    print("Sample Trade Data:")
    print("-" * 120)
    print(f"{'Instrument':<15} {'Side':<6} {'Qty':<4} {'Entry':<8} {'Exit':<8} {'Points P&L':<12} {'$ P&L':<10} {'Commission':<10}")
    print("-" * 120)
    
    for trade in trades:
        print(f"{trade['instrument']:<15} {trade['side_of_market']:<6} {trade['quantity']:<4} "
              f"{trade['entry_price']:<8.2f} {trade['exit_price']:<8.2f} "
              f"{trade['points_gain_loss']:<12.2f} ${trade['dollars_gain_loss']:<9.2f} ${trade['commission']:<9.2f}")
    
    print("\n=== ANALYZING POSITION AGGREGATION ===\n")
    
    # Get positions data
    cursor.execute("""
        SELECT instrument, position_type, total_quantity, average_entry_price, average_exit_price,
               total_points_pnl, total_dollars_pnl, total_commission, execution_count
        FROM positions 
        ORDER BY entry_time DESC
        LIMIT 5
    """)
    
    positions = cursor.fetchall()
    
    print("Position Data:")
    print("-" * 120)
    print(f"{'Instrument':<15} {'Type':<6} {'Qty':<4} {'Avg Entry':<10} {'Avg Exit':<10} {'Points P&L':<12} {'$ P&L':<10} {'Executions':<10}")
    print("-" * 120)
    
    for pos in positions:
        print(f"{pos['instrument']:<15} {pos['position_type']:<6} {pos['total_quantity']:<4} "
              f"{pos['average_entry_price']:<10.2f} {pos['average_exit_price'] or 0:<10.2f} "
              f"{pos['total_points_pnl']:<12.2f} ${pos['total_dollars_pnl']:<9.2f} {pos['execution_count']:<10}")
    
    print("\n=== CHECKING MULTIPLIERS ===\n")
    
    # Load multipliers
    multipliers_file = config.data_dir / 'config' / 'instrument_multipliers.json'
    if multipliers_file.exists():
        with open(multipliers_file, 'r') as f:
            multipliers = json.load(f)
        
        print("Current Instrument Multipliers:")
        for instrument, multiplier in multipliers.items():
            print(f"  {instrument}: {multiplier}")
    else:
        print("No multipliers file found!")
    
    print("\n=== MANUAL P&L VERIFICATION ===\n")
    
    # Let's manually verify the calculation for a few trades
    print("Manual verification of P&L calculations:")
    for i, trade in enumerate(trades[:3]):
        instrument = trade['instrument']
        side = trade['side_of_market']
        quantity = trade['quantity']
        entry_price = trade['entry_price']
        exit_price = trade['exit_price']
        stored_points = trade['points_gain_loss']
        stored_dollars = trade['dollars_gain_loss']
        commission = trade['commission']
        
        # Calculate points P&L manually
        if side == 'Long':
            calculated_points = exit_price - entry_price
        else:  # Short
            calculated_points = entry_price - exit_price
        
        # Get multiplier
        multiplier = multipliers.get(instrument, 1.0)
        
        # Calculate dollar P&L manually
        calculated_dollars = (calculated_points * multiplier * quantity) - commission
        
        print(f"\nTrade {i+1}: {instrument} {side} {quantity} contracts")
        print(f"  Entry: ${entry_price}, Exit: ${exit_price}")
        print(f"  Multiplier: {multiplier}")
        print(f"  Points P&L: Stored={stored_points:.2f}, Calculated={calculated_points:.2f}")
        print(f"  Dollar P&L: Stored=${stored_dollars:.2f}, Calculated=${calculated_dollars:.2f}")
        
        if abs(stored_points - calculated_points) > 0.01:
            print(f"  *** POINTS MISMATCH! ***")
        if abs(stored_dollars - calculated_dollars) > 0.01:
            print(f"  *** DOLLARS MISMATCH! ***")
    
    conn.close()

if __name__ == "__main__":
    analyze_pnl_calculation()