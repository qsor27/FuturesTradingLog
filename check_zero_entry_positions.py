"""
Quick script to check positions with zero entry price
"""
import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))
from config import config

conn = sqlite3.connect(str(config.db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get positions with zero entry price
cursor.execute("""
    SELECT
        id, instrument, account, position_type, position_status,
        total_quantity, average_entry_price, average_exit_price,
        total_dollars_pnl, entry_time, exit_time, execution_count
    FROM positions
    WHERE average_entry_price = 0
    ORDER BY id
""")

positions = cursor.fetchall()

print(f"\n{'='*80}")
print(f"POSITIONS WITH ZERO ENTRY PRICE: {len(positions)}")
print(f"{'='*80}\n")

for pos in positions:
    print(f"Position ID: {pos['id']}")
    print(f"  Instrument: {pos['instrument']}")
    print(f"  Account: {pos['account']}")
    print(f"  Type: {pos['position_type']}, Status: {pos['position_status']}")
    print(f"  Quantity: {pos['total_quantity']}")
    print(f"  Entry Price: ${pos['average_entry_price']:.2f}")
    exit_price_str = f"${pos['average_exit_price']:.2f}" if pos['average_exit_price'] else 'N/A'
    print(f"  Exit Price: {exit_price_str}")
    print(f"  P&L: ${pos['total_dollars_pnl']:.2f}")
    print(f"  Entry Time: {pos['entry_time']}")
    print(f"  Exit Time: {pos['exit_time'] or 'N/A'}")
    print(f"  Execution Count: {pos['execution_count']}")

    # Get associated trades
    cursor.execute("""
        SELECT t.id, t.action, t.entry_exit, t.quantity, t.entry_price, t.entry_time
        FROM trades t
        JOIN position_executions pe ON t.id = pe.trade_id
        WHERE pe.position_id = ?
        ORDER BY t.entry_time
        LIMIT 10
    """, (pos['id'],))

    trades = cursor.fetchall()
    print(f"  Associated Trades ({len(trades)}):")
    for trade in trades:
        trade_price = trade['entry_price'] if trade['entry_price'] is not None else 0
        print(f"    - Trade {trade['id']}: {trade['action']} {trade['entry_exit']}, "
              f"Qty: {trade['quantity']}, Price: ${trade_price:.2f}, "
              f"Time: {trade['entry_time']}")
    print()

conn.close()

print(f"{'='*80}")
print(f"TOTAL: {len(positions)} positions with zero entry price")
print(f"{'='*80}\n")
