"""Check position_executions table data"""
from scripts.TradingLog_db import FuturesDB

with FuturesDB() as db:
    # Check if position_executions table exists
    db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='position_executions'")
    table_exists = db.cursor.fetchone()
    print(f"position_executions table exists: {table_exists is not None}")

    if table_exists:
        # Count total records
        db.cursor.execute("SELECT COUNT(*) FROM position_executions")
        total_count = db.cursor.fetchone()[0]
        print(f"Total records in position_executions: {total_count}")

        # Count for position 35
        db.cursor.execute("SELECT COUNT(*) FROM position_executions WHERE position_id = 35")
        pos35_count = db.cursor.fetchone()[0]
        print(f"Records for position 35: {pos35_count}")

        # Check what position IDs exist
        db.cursor.execute("SELECT DISTINCT position_id FROM position_executions ORDER BY position_id LIMIT 20")
        position_ids = [row[0] for row in db.cursor.fetchall()]
        print(f"Sample position IDs in table: {position_ids}")

        # Check position 35 in positions table
        db.cursor.execute("SELECT id, instrument, execution_count FROM positions WHERE id = 35")
        pos_data = db.cursor.fetchone()
        if pos_data:
            print(f"\nPosition 35 in positions table: id={pos_data[0]}, instrument={pos_data[1]}, execution_count={pos_data[2]}")
        else:
            print("\nPosition 35 NOT FOUND in positions table")
