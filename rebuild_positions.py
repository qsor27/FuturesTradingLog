"""Rebuild positions to populate position_executions table"""
from services.enhanced_position_service_v2 import EnhancedPositionServiceV2 as PositionService

with PositionService() as pos_service:
    # Clear existing positions
    pos_service.cursor.execute("DELETE FROM position_executions")
    pos_service.cursor.execute("DELETE FROM positions")
    pos_service.conn.commit()
    print("Cleared existing positions and position_executions")

    # Rebuild
    result = pos_service.rebuild_positions_from_trades()
    print(f"Rebuild complete: {result['positions_created']} positions from {result['trades_processed']} trades")

    # Check position_executions
    pos_service.cursor.execute("SELECT COUNT(*) FROM position_executions")
    pe_count = pos_service.cursor.fetchone()[0]
    print(f"position_executions records: {pe_count}")

    # Check position 35 specifically
    pos_service.cursor.execute("SELECT COUNT(*) FROM position_executions WHERE position_id = 35")
    pos35_count = pos_service.cursor.fetchone()[0]
    print(f"position_executions for position 35: {pos35_count}")
