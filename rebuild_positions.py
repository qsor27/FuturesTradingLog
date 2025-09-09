#!/usr/bin/env python3
"""
Rebuild positions from trades after fixing the schema
"""

import sys
import os

# Add the app directory to Python path
sys.path.insert(0, '/app')

from scripts.TradingLog_db import FuturesDB
from services.enhanced_position_service_v2 import EnhancedPositionServiceV2

def rebuild_positions():
    """Rebuild all positions from existing trade data"""
    
    print("🔄 Starting position rebuild...")
    
    try:
        # Use the position service to rebuild positions
        with EnhancedPositionServiceV2() as position_service:
            result = position_service.rebuild_positions_from_trades()
            
            if result:
                positions_created = result.get('positions_created', 0)
                trades_processed = result.get('trades_processed', 0)
                
                print(f"✅ Position rebuild completed successfully!")
                print(f"   - Trades processed: {trades_processed}")
                print(f"   - Positions created: {positions_created}")
                
                # Verify the positions were created
                with FuturesDB() as db:
                    cursor = db.cursor
                    cursor.execute("SELECT COUNT(*) FROM positions WHERE soft_deleted = 0")
                    total_positions = cursor.fetchone()[0]
                    
                    cursor.execute("""
                        SELECT account, COUNT(*) as count, 
                               MIN(entry_time) as earliest, 
                               MAX(entry_time) as latest
                        FROM positions 
                        WHERE soft_deleted = 0
                        GROUP BY account
                    """)
                    account_stats = cursor.fetchall()
                    
                    print(f"\n📊 Position Summary:")
                    print(f"   Total Positions: {total_positions}")
                    print(f"   Breakdown by Account:")
                    for account, count, earliest, latest in account_stats:
                        print(f"     {account}: {count} positions ({earliest} to {latest})")
                
                return True
            else:
                print("❌ Position rebuild failed - no result returned")
                return False
                
    except Exception as e:
        print(f"❌ Error rebuilding positions: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = rebuild_positions()
    sys.exit(0 if success else 1)