#!/usr/bin/env python3

import sqlite3
from config import config

def check_database():
    """Check what tables exist in the database"""
    
    # Connect to database
    db_path = config.data_dir / 'db' / 'TradingLog.db'
    print(f"Checking TradingLog.db at: {db_path}")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    print(f"Database path: {db_path}")
    
    # Check if database file exists
    import os
    print(f"Database file exists: {os.path.exists(str(db_path))}")
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print(f"Tables found: {[table[0] for table in tables]}")
    
    # If trades table exists, check its structure
    for table_name in [table[0] for table in tables]:
        print(f"\nTable: {table_name}")
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Get count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  Records: {count}")
    
    conn.close()

if __name__ == "__main__":
    check_database()