"""Check which positions have execution mappings"""
from scripts.TradingLog_db import FuturesDB

with FuturesDB() as db:
    # Get sample positions with their execution counts
    db.cursor.execute("""
        SELECT p.id, p.instrument, p.execution_count,
               (SELECT COUNT(*) FROM position_executions WHERE position_id = p.id) as actual_mappings
        FROM positions p
        ORDER BY p.id
        LIMIT 40
    """)
    
    print("Position ID | Instrument | Expected Execs | Actual Mappings")
    print("-" * 70)
    for row in db.cursor.fetchall():
        print(f"{row[0]:11} | {row[1]:10} | {row[2]:14} | {row[3]:15}")
        
    # Check total counts
    db.cursor.execute("SELECT COUNT(*) FROM positions WHERE id >= 35")
    recent_positions = db.cursor.fetchone()[0]
    print(f"\nPositions with ID >= 35: {recent_positions}")
