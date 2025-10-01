"""
Position Service - Dependency Injection Implementation
Preserves the CRITICAL position building algorithm while using modular architecture
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from .interfaces import IPositionService
from repositories.interfaces import IPositionRepository, ITradeRepository, TradeRecord, PositionRecord
from config.container import Injectable

logger = logging.getLogger('position_service')

class PositionService(IPositionService):
    """
    🚨 CRITICAL: This service contains the MOST IMPORTANT component of the application
    
    The position building algorithm transforms NinjaTrader executions into position records
    using Quantity Flow Analysis. Modifying this affects ALL historical data.
    """
    
    def __init__(self, position_repository: IPositionRepository, trade_repository: ITradeRepository):
        self.position_repository = position_repository
        self.trade_repository = trade_repository
    
    def build_positions_from_executions(self, executions: List[Dict[str, Any]]) -> List[PositionRecord]:
        """
        Build position records from execution data using the CRITICAL algorithm
        
        Core Algorithm - Never Modify Without Extreme Care:
        1. Position Lifecycle: 0 → +/- → 0 (never Long→Short without reaching 0)
        2. Quantity Flow: Track running quantity through all executions
        3. FIFO P&L: Weighted averages for entry/exit prices
        """
        if not executions:
            return []
        
        # Sort executions chronologically - CRITICAL for correct position building
        try:
            sorted_executions = sorted(executions, key=lambda ex: ex.get('entry_time', ''))
            logger.info(f"Sorted {len(sorted_executions)} executions by entry_time for correct order")
        except Exception as e:
            logger.warning(f"Could not sort executions by entry_time: {e}. Using original order.")
            sorted_executions = executions
        
        positions = []
        current_position = None
        running_quantity = 0
        
        logger.info(f"Starting quantity flow analysis for {len(sorted_executions)} executions")
        
        for i, execution in enumerate(sorted_executions):
            # Get raw execution data from NinjaTrader import
            quantity = abs(int(execution.get('quantity', 0)))
            
            # Determine the quantity change effect based on the stored side_of_market
            action = execution.get('side_of_market', '').strip()
            
            # Convert to signed quantity change effect based on market actions
            if action in ["Buy", "BuyToCover"]:
                signed_qty_change = quantity  # Buying contracts (+)
            elif action in ["Sell", "SellShort"]: 
                signed_qty_change = -quantity  # Selling contracts (-)
            elif action == "Short":
                signed_qty_change = -quantity  # Opening short position (-)
            elif action == "Long":
                signed_qty_change = quantity  # Opening long position (+)
            else:
                logger.warning(f"Unknown side_of_market '{action}' for execution {execution.get('entry_execution_id', 'Unknown')}")
                continue
            
            previous_quantity = running_quantity
            running_quantity += signed_qty_change
            
            logger.info(f"Execution {i+1}: {action} {quantity} contracts | Running: {previous_quantity} → {running_quantity}")
            
            # Position lifecycle logic - CRITICAL ALGORITHM
            if previous_quantity == 0 and running_quantity != 0:
                # Starting new position (0 → non-zero)
                current_position = {
                    'instrument': execution.get('instrument'),
                    'side': 'Long' if running_quantity > 0 else 'Short',
                    'start_time': datetime.fromisoformat(execution.get('entry_time')) if execution.get('entry_time') else None,
                    'end_time': None,
                    'executions': [execution],
                    'quantity': abs(running_quantity),
                    'entry_price': execution.get('entry_price'),
                    'exit_price': None,
                    'realized_pnl': 0.0,
                    'commission': execution.get('commission', 0.0),
                    'link_group_id': execution.get('link_group_id'),
                    'mae': None,
                    'mfe': None
                }
                logger.info(f"  → Started new {current_position['side']} position")
                
            elif current_position and previous_quantity * running_quantity < 0:
                # Position Reversal detected (e.g., from +10 to -5) - OVERLAP PREVENTION
                logger.info(f"  → REVERSAL DETECTED: Closing previous {current_position['side']} position")
                
                # Step 1: Close the old position
                current_position['executions'].append(execution)
                current_position['end_time'] = datetime.fromisoformat(execution.get('entry_time')) if execution.get('entry_time') else None
                self._calculate_position_totals_from_executions(current_position)
                
                # Convert to PositionRecord and add to positions
                position_record = self._dict_to_position_record(current_position)
                positions.append(position_record)
                
                # Step 2: Open new position in opposite direction
                new_side = 'Long' if running_quantity > 0 else 'Short'
                logger.info(f"  → Starting new {new_side} position from reversal")
                current_position = {
                    'instrument': execution.get('instrument'),
                    'side': new_side,
                    'start_time': datetime.fromisoformat(execution.get('entry_time')) if execution.get('entry_time') else None,
                    'end_time': None,
                    'executions': [execution],
                    'quantity': abs(running_quantity),
                    'entry_price': execution.get('entry_price'),
                    'exit_price': None,
                    'realized_pnl': 0.0,
                    'commission': execution.get('commission', 0.0),
                    'link_group_id': execution.get('link_group_id'),
                    'mae': None,
                    'mfe': None
                }
                
            elif current_position and running_quantity != 0:
                # Continuing existing position (non-zero → non-zero)
                current_position['executions'].append(execution)
                current_position['quantity'] = abs(running_quantity)
                current_position['commission'] += execution.get('commission', 0.0)
                logger.info(f"  → Added to existing {current_position['side']} position")
                
            elif current_position and running_quantity == 0:
                # Closing position (non-zero → 0)
                current_position['executions'].append(execution)
                current_position['end_time'] = datetime.fromisoformat(execution.get('entry_time')) if execution.get('entry_time') else None
                self._calculate_position_totals_from_executions(current_position)
                
                # Convert to PositionRecord and add to positions
                position_record = self._dict_to_position_record(current_position)
                positions.append(position_record)
                
                logger.info(f"  → Closed {current_position['side']} position with {len(current_position['executions'])} executions")
                current_position = None
        
        # Handle any remaining open position
        if current_position:
            self._calculate_position_totals_from_executions(current_position)
            position_record = self._dict_to_position_record(current_position)
            positions.append(position_record)
            logger.info(f"  → Saved open {current_position['side']} position")
        
        logger.info(f"Position building complete: Created {len(positions)} positions")
        return positions
    
    def _calculate_position_totals_from_executions(self, position: Dict[str, Any]):
        """Calculate position totals from executions using FIFO P&L calculation"""
        executions = position.get('executions', [])
        if not executions:
            return
        
        # Calculate weighted average entry price
        total_quantity = 0
        total_value = 0
        total_commission = 0
        total_pnl = 0
        
        for execution in executions:
            quantity = abs(int(execution.get('quantity', 0)))
            price = float(execution.get('entry_price', 0))
            commission = float(execution.get('commission', 0))
            pnl = float(execution.get('dollars_gain_loss', 0))
            
            total_quantity += quantity
            total_value += quantity * price
            total_commission += commission
            total_pnl += pnl
        
        position['entry_price'] = total_value / total_quantity if total_quantity > 0 else 0
        position['exit_price'] = position['entry_price']  # Will be recalculated for closed positions
        position['realized_pnl'] = total_pnl
        position['commission'] = total_commission
        
        # For closed positions, calculate proper exit price
        if position['end_time'] and len(executions) > 1:
            # Calculate weighted average exit price from closing executions
            closing_executions = executions[1:]  # All except first (entry)
            if closing_executions:
                exit_value = 0
                exit_quantity = 0
                for execution in closing_executions:
                    quantity = abs(int(execution.get('quantity', 0)))
                    price = float(execution.get('exit_price', execution.get('entry_price', 0)))
                    exit_value += quantity * price
                    exit_quantity += quantity
                
                position['exit_price'] = exit_value / exit_quantity if exit_quantity > 0 else position['entry_price']
    
    def _dict_to_position_record(self, position_dict: Dict[str, Any]) -> PositionRecord:
        """Convert position dictionary to PositionRecord"""
        return PositionRecord(
            instrument=position_dict.get('instrument'),
            side=position_dict.get('side'),
            start_time=position_dict.get('start_time'),
            end_time=position_dict.get('end_time'),
            quantity=position_dict.get('quantity'),
            entry_price=position_dict.get('entry_price'),
            exit_price=position_dict.get('exit_price'),
            realized_pnl=position_dict.get('realized_pnl'),
            commission=position_dict.get('commission'),
            link_group_id=position_dict.get('link_group_id'),
            mae=position_dict.get('mae'),
            mfe=position_dict.get('mfe')
        )
    
    def rebuild_positions(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        """
        Rebuild positions from existing trades
        
        ⚠️ Critical Warning: Always test with /positions/rebuild after any changes
        """
        try:
            # Get all trades for rebuilding
            if instrument:
                trades = self.trade_repository.get_trades_by_instrument(instrument)
            else:
                trades = self.trade_repository.get_all_trades()
            
            if not trades:
                return {'positions_created': 0, 'trades_processed': 0}
            
            # Convert TradeRecord to execution dict format
            executions = []
            for trade in trades:
                execution = {
                    'instrument': trade.instrument,
                    'quantity': trade.quantity,
                    'entry_price': trade.price,
                    'exit_price': trade.price,
                    'entry_time': trade.timestamp.isoformat() if trade.timestamp else None,
                    'side_of_market': trade.side,
                    'commission': trade.commission,
                    'dollars_gain_loss': trade.realized_pnl,
                    'link_group_id': trade.link_group_id,
                    'entry_execution_id': str(trade.id)
                }
                executions.append(execution)
            
            # Build positions using the critical algorithm
            positions = self.build_positions_from_executions(executions)
            
            # Save positions to database
            positions_created = 0
            for position in positions:
                position_id = self.position_repository.create_position(position)
                if position_id:
                    positions_created += 1
            
            return {
                'positions_created': positions_created,
                'trades_processed': len(trades)
            }
            
        except Exception as e:
            logger.error(f"Error rebuilding positions: {e}")
            return {'error': str(e)}
    
    def get_position_by_id(self, position_id: int) -> Optional[PositionRecord]:
        """Get a position by ID"""
        return self.position_repository.get_position(position_id)
    
    def get_positions_by_instrument(self, instrument: str, start_date: Optional[datetime] = None, 
                                   end_date: Optional[datetime] = None) -> List[PositionRecord]:
        """Get positions for a specific instrument"""
        return self.position_repository.get_positions_by_instrument(instrument, start_date, end_date)
    
    def validate_positions(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        """Validate position data integrity"""
        try:
            validation_results = {
                'total_positions': 0,
                'valid_positions': 0,
                'invalid_positions': 0,
                'issues': []
            }
            
            # Get positions to validate
            if instrument:
                positions = self.position_repository.get_positions_by_instrument(instrument)
            else:
                positions = self.position_repository.get_all_positions()
            
            validation_results['total_positions'] = len(positions)
            
            for position in positions:
                issues = []
                
                # Check for basic data integrity
                if not position.instrument:
                    issues.append("Missing instrument")
                
                if not position.start_time:
                    issues.append("Missing start time")
                
                if position.quantity <= 0:
                    issues.append("Invalid quantity")
                
                if position.entry_price <= 0:
                    issues.append("Invalid entry price")
                
                # Check for position overlap
                if position.end_time and position.start_time and position.end_time <= position.start_time:
                    issues.append("End time before start time")
                
                if issues:
                    validation_results['invalid_positions'] += 1
                    validation_results['issues'].append({
                        'position_id': position.id,
                        'instrument': position.instrument,
                        'issues': issues
                    })
                else:
                    validation_results['valid_positions'] += 1
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating positions: {e}")
            return {'error': str(e)}
    
    def check_position_overlaps(self, instrument: str) -> List[Dict[str, Any]]:
        """Check for position overlaps"""
        return self.position_repository.check_position_overlaps(instrument)
    
    def get_position_statistics(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        """Get position statistics"""
        try:
            if instrument:
                positions = self.position_repository.get_positions_by_instrument(instrument)
            else:
                positions = self.position_repository.get_all_positions()
            
            if not positions:
                return {'total_positions': 0}
            
            total_positions = len(positions)
            winning_positions = sum(1 for p in positions if p.realized_pnl and p.realized_pnl > 0)
            losing_positions = sum(1 for p in positions if p.realized_pnl and p.realized_pnl < 0)
            
            total_pnl = sum(p.realized_pnl for p in positions if p.realized_pnl)
            average_pnl = total_pnl / total_positions if total_positions > 0 else 0
            
            win_rate = (winning_positions / total_positions) * 100 if total_positions > 0 else 0
            
            return {
                'total_positions': total_positions,
                'winning_positions': winning_positions,
                'losing_positions': losing_positions,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'average_pnl': average_pnl
            }
            
        except Exception as e:
            logger.error(f"Error calculating position statistics: {e}")
            return {'error': str(e)}