#!/usr/bin/env python3
"""
Normalize trade data to fix side_of_market values
"""

import sqlite3
import os

# Database path
db_path = "data/db/futures_trades_clean.db"

def normalize_trade_data():
    """Fix side_of_market values to be compatible with position algorithms"""
    
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current side_of_market values
        cursor.execute("SELECT DISTINCT side_of_market FROM trades")
        current_values = [row[0] for row in cursor.fetchall()]
        
        print("Current side_of_market values:")
        for value in current_values:
            print(f"  - {value}")
        
        # Normalize the values
        updates_made = 0
        
        # Map Long -> Buy (for futures, Long means bought to open)
        if 'Long' in current_values:
            cursor.execute("UPDATE trades SET side_of_market = 'Buy' WHERE side_of_market = 'Long'")
            updated_long = cursor.rowcount
            print(f"\n✅ Updated {updated_long} 'Long' trades to 'Buy'")
            updates_made += updated_long
        
        # Map Short -> Sell (for futures, Short means sold to open) 
        if 'Short' in current_values:
            cursor.execute("UPDATE trades SET side_of_market = 'Sell' WHERE side_of_market = 'Short'")
            updated_short = cursor.rowcount
            print(f"✅ Updated {updated_short} 'Short' trades to 'Sell'")
            updates_made += updated_short
        
        # Check final values
        cursor.execute("SELECT DISTINCT side_of_market FROM trades")
        final_values = [row[0] for row in cursor.fetchall()]
        
        print(f"\nFinal side_of_market values:")
        for value in final_values:
            cursor.execute("SELECT COUNT(*) FROM trades WHERE side_of_market = ?", (value,))
            count = cursor.fetchone()[0]
            print(f"  - {value}: {count} trades")
        
        conn.commit()
        conn.close()
        
        if updates_made > 0:
            print(f"\n🎉 Successfully normalized {updates_made} trade records!")
        else:
            print(f"\n✅ All trades already have correct side_of_market values")
        
        return True
        
    except Exception as e:
        print(f"❌ Error normalizing trade data: {e}")
        return False

if __name__ == "__main__":
    normalize_trade_data()