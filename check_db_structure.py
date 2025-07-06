"""
Check database structure and sample data
"""

import sqlite3
from config import config


def check_database():
    """Check database structure and contents"""
    db_path = config.db_path
    print(f"Checking database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # List all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"Found {len(tables)} tables:")
        for table in tables:
            print(f"  - {table}")
        
        # Check each table's structure and row count
        for table in tables:
            print(f"\nTable: {table}")
            print("-" * 40)
            
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            print("Columns:")
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"Row count: {count}")
            
            # Get sample data if exists
            if count > 0:
                cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                rows = cursor.fetchall()
                print("Sample data:")
                for i, row in enumerate(rows):
                    print(f"  Row {i+1}: {row}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error checking database: {e}")


if __name__ == "__main__":
    check_database()