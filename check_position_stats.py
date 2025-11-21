"""Quick script to check position statistics"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import config

conn = sqlite3.connect(str(config.db_path))
cursor = conn.cursor()

# Overall statistics
cursor.execute("""
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN average_entry_price > 0 THEN 1 ELSE 0 END) as valid,
        SUM(CASE WHEN average_entry_price = 0 THEN 1 ELSE 0 END) as invalid
    FROM positions
""")
total, valid, invalid = cursor.fetchone()

cursor.execute("SELECT SUM(total_dollars_pnl) FROM positions")
total_pnl = cursor.fetchone()[0]

print(f"\n{'='*60}")
print(f"POSITION STATISTICS")
print(f"{'='*60}")
print(f"Total positions: {total}")
print(f"Valid entry price: {valid} ({valid/total*100:.1f}%)")
print(f"Zero entry price: {invalid} ({invalid/total*100:.1f}%)")
print(f"Total P&L: ${total_pnl:.2f}")
print(f"{'='*60}\n")

conn.close()
