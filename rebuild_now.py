from services.enhanced_position_service_v2 import EnhancedPositionServiceV2 as PositionService

print("Rebuilding positions...")
with PositionService() as pos_service:
    result = pos_service.rebuild_positions_from_trades()
    print(f"Result: {result['positions_created']} positions from {result['trades_processed']} trades")
