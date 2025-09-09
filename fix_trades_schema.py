#!/usr/bin/env python3
"""
Fix the trades table schema by adding the missing soft_deleted column
"""

import sqlite3
import os
from pathlib import Path

# Database path
db_path = "data/db/futures_trades_clean.db"

def fix_trades_schema():
    """Add the missing soft_deleted column to trades table"""
    
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current schema
        cursor.execute("PRAGMA table_info(trades)")
        columns = cursor.fetchall()
        
        print("Current trades table columns:")
        for col in columns:
            print(f"  {col[1]} {col[2]}")
        
        # Check if soft_deleted column exists
        column_names = [col[1] for col in columns]
        
        if 'soft_deleted' not in column_names:
            print("\nAdding missing 'soft_deleted' column to trades table...")
            cursor.execute("ALTER TABLE trades ADD COLUMN soft_deleted INTEGER DEFAULT 0")
            print("✅ Added 'soft_deleted' column to trades table successfully")
        else:
            print("\n✅ 'soft_deleted' column already exists in trades table")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(trades)")
        columns = cursor.fetchall()
        
        print("\nUpdated trades table columns:")
        for col in columns:
            print(f"  {col[1]} {col[2]}")
        
        conn.commit()
        conn.close()
        
        print("\n🎉 Trades table schema fix completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing trades schema: {e}")
        return False

if __name__ == "__main__":
    fix_trades_schema()