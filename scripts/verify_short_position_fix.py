"""
Verify short position P&L calculation fix for position #241

This script rebuilds position #241 and verifies that:
1. Average entry price is correctly calculated (not 0.00)
2. P&L is realistic (not millions of dollars in losses)
3. Short position logic works correctly
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.TradingLog_db import FuturesDB
from services.enhanced_position_service_v2 import EnhancedPositionServiceV2


def verify_short_position_fix():
    """Verify the short position P&L fix works on real data"""

    print("=" * 80)
    print("VERIFYING SHORT POSITION P&L FIX")
    print("=" * 80)

    # Connect to database using context manager
    with FuturesDB() as db:
        # Query position #241 BEFORE rebuild
        print("\n--- Position #241 BEFORE Fix ---")
        db.cursor.execute("""
            SELECT
                id,
                instrument,
                account,
                position_type,
                average_entry_price,
                average_exit_price,
                total_points_pnl,
                total_dollars_pnl,
                execution_count
            FROM positions
            WHERE id = 241
        """)
        pos_before = db.cursor.fetchone()

        if pos_before:
            print(f"ID: {pos_before[0]}")
            print(f"Instrument: {pos_before[1]}")
            print(f"Account: {pos_before[2]}")
            print(f"Type: {pos_before[3]}")
            print(f"Average Entry Price: {pos_before[4]}")
            print(f"Average Exit Price: {pos_before[5]}")
            print(f"Points P&L: {pos_before[6]}")
            print(f"Dollars P&L: ${pos_before[7]:,.2f}")
            print(f"Execution Count: {pos_before[8]}")
        else:
            print("Position #241 not found!")
            return

        # Query executions for position #241
        print("\n--- Executions for Position #241 ---")
        db.cursor.execute("""
            SELECT
                t.id,
                t.side_of_market,
                t.quantity,
                t.entry_price,
                t.exit_price,
                t.entry_time
            FROM position_executions pe
            JOIN trades t ON pe.trade_id = t.id
            WHERE pe.position_id = 241
            ORDER BY pe.execution_order
        """)
        executions = db.cursor.fetchall()

        for exec in executions:
            print(f"Trade {exec[0]}: {exec[1]} {exec[2]} @ "
                  f"entry:{exec[3] or 'N/A'} exit:{exec[4] or 'N/A'} "
                  f"time:{exec[5]}")

        # Rebuild positions for this account/instrument
        print("\n--- Rebuilding Positions ---")
        account = pos_before[2]
        instrument = pos_before[1]

        # Use context manager for position service with same db path
        with EnhancedPositionServiceV2(db.db_path) as position_service:
            result = position_service.rebuild_positions_for_account_instrument(account, instrument)
            print(f"Rebuild result: {result}")

        # Query position AFTER rebuild (position ID may have changed)
        print("\n--- Position AFTER Fix ---")
        db.cursor.execute("""
            SELECT
                id,
                instrument,
                account,
                position_type,
                average_entry_price,
                average_exit_price,
                total_points_pnl,
                total_dollars_pnl,
                execution_count
            FROM positions
            WHERE account = ? AND instrument = ?
            ORDER BY id DESC
            LIMIT 1
        """, (account, instrument))
        pos_after = db.cursor.fetchone()

        if pos_after:
            print(f"ID: {pos_after[0]}")
            print(f"Instrument: {pos_after[1]}")
            print(f"Account: {pos_after[2]}")
            print(f"Type: {pos_after[3]}")
            print(f"Average Entry Price: {pos_after[4]}")
            print(f"Average Exit Price: {pos_after[5]}")
            print(f"Points P&L: {pos_after[6]}")
            print(f"Dollars P&L: ${pos_after[7]:,.2f}")
            print(f"Execution Count: {pos_after[8]}")
        else:
            print("Position not found after rebuild!")
            return

        # Verify the fix
        print("\n" + "=" * 80)
        print("VERIFICATION RESULTS")
        print("=" * 80)

        checks = []

        # Check 1: Average entry price is not 0.00
        if pos_after[4] != 0.00:
            print(f"✓ PASS: Average entry price is {pos_after[4]} (not 0.00)")
            checks.append(True)
        else:
            print(f"✗ FAIL: Average entry price is still 0.00")
            checks.append(False)

        # Check 2: P&L is realistic (not millions)
        if abs(pos_after[7]) < 1000:  # Less than $1000 loss
            print(f"✓ PASS: P&L is realistic (${pos_after[7]:,.2f})")
            checks.append(True)
        else:
            print(f"✗ FAIL: P&L is still unrealistic (${pos_after[7]:,.2f})")
            checks.append(False)

        # Check 3: P&L is negative (short position lost money)
        if pos_after[7] < 0:
            print(f"✓ PASS: P&L is negative as expected for losing short position")
            checks.append(True)
        else:
            print(f"✗ FAIL: P&L should be negative for this losing short position")
            checks.append(False)

        # Check 4: P&L matches expected value
        # Short: Sell @ 25561.50, Buy @ 25565.50 = -4 points
        # -4 points * 6 contracts = -24 points
        # -24 points * $2 multiplier = -$48
        expected_points = -24.0
        expected_dollars = -48.0

        if abs(pos_after[6] - expected_points) < 1.0:
            print(f"✓ PASS: Points P&L ({pos_after[6]}) matches expected ({expected_points})")
            checks.append(True)
        else:
            print(f"⚠ WARNING: Points P&L ({pos_after[6]}) differs from expected ({expected_points})")
            checks.append(False)

        if abs(pos_after[7] - expected_dollars) < 5.0:
            print(f"✓ PASS: Dollars P&L (${pos_after[7]}) matches expected (${expected_dollars})")
            checks.append(True)
        else:
            print(f"⚠ WARNING: Dollars P&L (${pos_after[7]}) differs from expected (${expected_dollars})")
            checks.append(False)

        # Summary
        print("\n" + "=" * 80)
        if all(checks):
            print("✓ ALL CHECKS PASSED - Short position fix is working correctly!")
        else:
            passed = sum(checks)
            total = len(checks)
            print(f"⚠ {passed}/{total} CHECKS PASSED - Review results above")
        print("=" * 80)

        # Query all short positions to see if others have the same issue
        print("\n--- Checking Other Short Positions ---")
        db.cursor.execute("""
            SELECT
                COUNT(*) as total_short,
                COUNT(CASE WHEN average_entry_price = 0 OR average_entry_price IS NULL THEN 1 END) as zero_entry
            FROM positions
            WHERE position_type = 'Short'
        """)
        short_stats = db.cursor.fetchone()

        print(f"Total short positions: {short_stats[0]}")
        print(f"Short positions with entry_price = 0: {short_stats[1]}")

        if short_stats[1] > 0:
            print(f"\n⚠ WARNING: {short_stats[1]} other short positions have zero entry price!")
            print("   Run full position rebuild to fix all affected positions.")


if __name__ == "__main__":
    verify_short_position_fix()
