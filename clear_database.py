"""
Clear Database Script

Safely removes all data from the Futures Trading Log database while preserving schema.
This script will:
1. Delete all records from all tables
2. Reset any auto-increment counters
3. Preserve the database schema (tables, indexes, etc.)
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

def get_database_path():
    """Get database path from config"""
    try:
        from config import config
        return config.db_path
    except ImportError:
        # Fallback to default path
        return Path(__file__).parent / "data" / "db" / "futures_trades_clean.db"

def list_all_tables(cursor):
    """Get list of all tables in the database"""
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    return [row[0] for row in cursor.fetchall()]

def get_table_row_count(cursor, table_name):
    """Get row count for a table"""
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cursor.fetchone()[0]
    except Exception as e:
        print(f"Warning: Could not count rows in {table_name}: {e}")
        return 0

def clear_database(db_path, confirm=False):
    """Clear all data from the database"""

    if not Path(db_path).exists():
        print(f"Error: Database not found at {db_path}")
        return False

    print("=" * 80)
    print("DATABASE CLEAR OPERATION")
    print("=" * 80)
    print(f"Database: {db_path}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all tables
    tables = list_all_tables(cursor)

    if not tables:
        print("No tables found in database.")
        conn.close()
        return True

    print(f"Found {len(tables)} tables:")
    print()

    # Display current row counts
    total_rows = 0
    table_info = []
    for table in tables:
        count = get_table_row_count(cursor, table)
        total_rows += count
        table_info.append((table, count))
        print(f"  {table}: {count:,} rows")

    print()
    print(f"Total rows across all tables: {total_rows:,}")
    print()

    if total_rows == 0:
        print("[OK] Database is already empty. No data to clear.")
        conn.close()
        return True

    # Confirmation prompt
    if not confirm:
        print("WARNING: This will permanently delete ALL data from the database!")
        print("The schema (tables, indexes) will be preserved, but all records will be removed.")
        print()
        response = input("Are you sure you want to proceed? (yes/no): ").strip().lower()

        if response != 'yes':
            print("Operation cancelled.")
            conn.close()
            return False

    print()
    print("Clearing database...")
    print()

    # Delete data from all tables
    deleted_tables = 0
    failed_tables = []

    for table_name, row_count in table_info:
        if row_count > 0:
            try:
                cursor.execute(f"DELETE FROM {table_name}")
                deleted_count = cursor.rowcount
                print(f"[OK] Cleared {table_name}: {deleted_count:,} rows deleted")
                deleted_tables += 1
            except Exception as e:
                print(f"[FAIL] Failed to clear {table_name}: {e}")
                failed_tables.append(table_name)

    # Reset auto-increment sequences
    try:
        cursor.execute("DELETE FROM sqlite_sequence")
        print("[OK] Reset auto-increment counters")
    except Exception as e:
        print(f"Note: Could not reset auto-increment counters: {e}")

    # Commit changes
    conn.commit()

    # Verify deletion
    print()
    print("Verifying deletion...")
    remaining_rows = 0
    for table in tables:
        count = get_table_row_count(cursor, table)
        remaining_rows += count
        if count > 0:
            print(f"  Warning: {table} still has {count} rows")

    conn.close()

    print()
    print("=" * 80)
    print("OPERATION COMPLETE")
    print("=" * 80)
    print(f"Tables cleared: {deleted_tables}/{len(tables)}")
    if failed_tables:
        print(f"Failed tables: {', '.join(failed_tables)}")
    print(f"Remaining rows: {remaining_rows}")
    print()

    if remaining_rows == 0 and not failed_tables:
        print("[SUCCESS] Database successfully cleared. All data removed.")
        return True
    else:
        print("[WARNING] Database clear completed with warnings.")
        return False

if __name__ == "__main__":
    # Check for --confirm flag
    confirm = '--confirm' in sys.argv or '-y' in sys.argv

    # Get database path
    db_path = get_database_path()

    # Clear database
    success = clear_database(db_path, confirm=confirm)

    sys.exit(0 if success else 1)
