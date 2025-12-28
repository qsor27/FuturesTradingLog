"""Verify P&L calculations after rebuild"""
import sqlite3

conn = sqlite3.connect("/app/data/db/futures_trades_clean.db")
cursor = conn.cursor()

cursor.execute("""
    SELECT id, instrument, position_type, total_quantity,
           total_points_pnl, total_dollars_pnl
    FROM positions
    WHERE total_points_pnl != 0 AND total_dollars_pnl != 0
    ORDER BY id DESC
    LIMIT 10
""")

print("Sample positions with P&L:")
print("ID | Instrument        | Type  | Qty | Points P&L |  Dollar P&L | Implied Mult")
print("-" * 85)
for row in cursor.fetchall():
    implied_mult = row[5] / row[4] if row[4] != 0 else 0
    print(f"{row[0]:3} | {row[1]:17} | {row[2]:5} | {row[3]:3} | {row[4]:10.2f} | {row[5]:11.2f} | {implied_mult:.1f}")

conn.close()
