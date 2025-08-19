"""
Position Engine - Pure Function Implementation

Isolated, bulletproof position building algorithm following 0→+/-→0 lifecycle.
Separates business logic from database concerns for easier testing and reliability.
"""

from typing import Dict, List, Any, Optional, Tuple, NamedTuple
from datetime import datetime
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger('position_engine')


class PositionSide(Enum):
    """Position direction enumeration"""
    LONG = "Long"
    SHORT = "Short"


class ExecutionAction(Enum):
    """Execution action enumeration"""
    BUY = "Buy"
    SELL = "Sell"


@dataclass
class Execution:
    """Immutable execution data structure"""
    id: str
    instrument: str
    account: str
    action: ExecutionAction  # Buy or Sell
    quantity: int  # Always positive
    price: float
    timestamp: str
    commission: float = 0.0
    
    def __post_init__(self):
        """Validate execution data"""
        if self.quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {self.quantity}")
        if self.price <= 0:
            raise ValueError(f"Price must be positive, got {self.price}")


@dataclass
class Position:
    """Immutable position data structure"""
    instrument: str
    account: str
    side: PositionSide
    entry_time: str
    exit_time: Optional[str]
    executions: List[Execution]
    total_quantity: int
    max_quantity: int
    average_entry_price: float
    average_exit_price: Optional[float]
    total_points_pnl: Optional[float]
    total_dollars_pnl: Optional[float]
    total_commission: float
    is_closed: bool
    
    def __post_init__(self):
        """Validate position data"""
        if self.total_quantity <= 0:
            raise ValueError(f"Total quantity must be positive, got {self.total_quantity}")
        if len(self.executions) == 0:
            raise ValueError("Position must have at least one execution")


class PositionEngine:
    """
    Pure function position building engine
    
    Transforms raw executions into position lifecycle tracking using quantity flow analysis.
    Implements the critical 0→+/-→0 algorithm without any database dependencies.
    """
    
    @staticmethod
    def build_positions_from_executions(executions: List[Dict[str, Any]]) -> List[Position]:
        """
        Main entry point: Build positions from raw execution data
        
        Args:
            executions: List of execution dictionaries from database
            
        Returns:
            List of Position objects representing complete position lifecycles
            
        Raises:
            ValueError: If execution data is invalid
        """
        if not executions:
            return []
        
        # Convert raw data to typed execution objects
        typed_executions = PositionEngine._convert_raw_executions(executions)
        
        # Group by account and instrument
        groups = PositionEngine._group_executions(typed_executions)
        
        # Build positions for each group
        all_positions = []
        for (account, instrument), group_executions in groups.items():
            positions = PositionEngine._build_positions_for_group(group_executions)
            all_positions.extend(positions)
        
        return all_positions
    
    @staticmethod
    def _convert_raw_executions(raw_executions: List[Dict[str, Any]]) -> List[Execution]:
        """Convert raw database records to typed Execution objects"""
        typed_executions = []
        
        for i, raw in enumerate(raw_executions):
            try:
                # Parse action
                side_str = raw.get('side_of_market', '').strip()
                if side_str == 'Buy':
                    action = ExecutionAction.BUY
                elif side_str == 'Sell':
                    action = ExecutionAction.SELL
                else:
                    raise ValueError(f"Invalid side_of_market: '{side_str}'")
                
                execution = Execution(
                    id=str(raw.get('entry_execution_id', f'exec_{i}')),
                    instrument=raw.get('instrument', '').strip(),
                    account=raw.get('account', '').strip(),
                    action=action,
                    quantity=abs(int(raw.get('quantity', 0))),
                    price=float(raw.get('entry_price', 0)),
                    timestamp=raw.get('entry_time', ''),
                    commission=float(raw.get('commission', 0))
                )
                
                # Validate required fields
                if not execution.instrument:
                    raise ValueError("Missing instrument")
                if not execution.account:
                    raise ValueError("Missing account")
                if not execution.timestamp:
                    raise ValueError("Missing timestamp")
                
                typed_executions.append(execution)
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid execution {i}: {e}")
                continue
        
        return typed_executions
    
    @staticmethod
    def _group_executions(executions: List[Execution]) -> Dict[Tuple[str, str], List[Execution]]:
        """Group executions by account and instrument"""
        groups = {}
        
        for execution in executions:
            key = (execution.account, execution.instrument)
            if key not in groups:
                groups[key] = []
            groups[key].append(execution)
        
        # Sort each group by timestamp for chronological processing
        for key, group in groups.items():
            try:
                groups[key] = sorted(group, key=lambda e: e.timestamp)
            except Exception as e:
                logger.warning(f"Could not sort executions for {key}: {e}")
        
        return groups
    
    @staticmethod
    def _build_positions_for_group(executions: List[Execution]) -> List[Position]:
        """
        Build positions for a single account-instrument group using quantity flow analysis
        
        Core Algorithm: Track running quantity through all executions
        - Position lifecycle: 0 → +/- → 0 (never Long→Short without reaching 0)
        - Position starts when quantity moves from 0 to non-zero
        - Position continues while quantity remains non-zero (same direction)
        - Position closes when quantity returns to 0
        - Position reversal: Long→Short or Short→Long creates separate positions
        """
        if not executions:
            return []
        
        positions = []
        current_position_executions = []
        running_quantity = 0
        
        logger.debug(f"Processing {len(executions)} executions for {executions[0].account}/{executions[0].instrument}")
        
        for i, execution in enumerate(executions):
            # Calculate signed quantity change
            if execution.action == ExecutionAction.BUY:
                signed_qty_change = execution.quantity
            else:  # SELL
                signed_qty_change = -execution.quantity
            
            previous_quantity = running_quantity
            running_quantity += signed_qty_change
            
            logger.debug(f"Execution {i+1}: {execution.action.value} {execution.quantity} @ {execution.price} | "
                        f"Quantity: {previous_quantity} → {running_quantity}")
            
            # Position lifecycle logic
            if previous_quantity == 0 and running_quantity != 0:
                # START: New position (0 → non-zero)
                current_position_executions = [execution]
                logger.debug(f"POSITION START: {PositionEngine._get_side_from_quantity(running_quantity).value} position")
                
            elif previous_quantity != 0 and running_quantity == 0:
                # CLOSE: Position complete (non-zero → 0)
                current_position_executions.append(execution)
                position = PositionEngine._create_position_from_executions(current_position_executions)
                positions.append(position)
                logger.debug(f"POSITION CLOSE: Completed position with {len(current_position_executions)} executions")
                current_position_executions = []
                
            elif PositionEngine._is_position_reversal(previous_quantity, running_quantity):
                # REVERSAL: Position direction change without reaching 0
                # Close current position and start new one
                
                # Calculate the quantity needed to close the current position
                close_quantity = abs(previous_quantity)
                
                # Split the execution: part closes old position, part starts new position
                close_execution = PositionEngine._create_partial_execution(execution, close_quantity)
                remaining_quantity = execution.quantity - close_quantity
                
                # Close current position
                current_position_executions.append(close_execution)
                position = PositionEngine._create_position_from_executions(current_position_executions)
                positions.append(position)
                logger.debug(f"POSITION REVERSAL: Closed {position.side.value} position, starting new position")
                
                # Start new position with remaining quantity
                if remaining_quantity > 0:
                    new_execution = PositionEngine._create_partial_execution(execution, remaining_quantity)
                    current_position_executions = [new_execution]
                    # Update running quantity for the new position
                    running_quantity = signed_qty_change + previous_quantity  # This should equal new position quantity
                else:
                    current_position_executions = []
                
            elif previous_quantity != 0 and running_quantity != 0:
                # MODIFY: Position size change (same direction or partial close)
                current_position_executions.append(execution)
                logger.debug(f"POSITION MODIFY: Added execution to existing position")
                
            else:
                # Edge case: Should not happen with valid data
                logger.warning(f"Unexpected quantity transition: {previous_quantity} → {running_quantity}")
                if running_quantity != 0:
                    current_position_executions.append(execution)
        
        # Handle any remaining open position
        if current_position_executions and running_quantity != 0:
            logger.warning(f"Open position detected with {len(current_position_executions)} executions. "
                          f"Final quantity: {running_quantity}")
            # Create open position (no exit time/price)
            position = PositionEngine._create_position_from_executions(current_position_executions, is_open=True)
            positions.append(position)
        
        logger.debug(f"Built {len(positions)} positions from {len(executions)} executions")
        return positions
    
    @staticmethod
    def _is_position_reversal(prev_qty: int, new_qty: int) -> bool:
        """Detect if position direction changed without reaching zero"""
        if prev_qty == 0 or new_qty == 0:
            return False
        return (prev_qty > 0 and new_qty < 0) or (prev_qty < 0 and new_qty > 0)
    
    @staticmethod
    def _get_side_from_quantity(quantity: int) -> PositionSide:
        """Determine position side from quantity"""
        return PositionSide.LONG if quantity > 0 else PositionSide.SHORT
    
    @staticmethod
    def _create_partial_execution(original: Execution, quantity: int) -> Execution:
        """Create a partial execution with specified quantity"""
        return Execution(
            id=f"{original.id}_partial_{quantity}",
            instrument=original.instrument,
            account=original.account,
            action=original.action,
            quantity=quantity,
            price=original.price,
            timestamp=original.timestamp,
            commission=original.commission * (quantity / original.quantity)  # Proportional commission
        )
    
    @staticmethod
    def _create_position_from_executions(executions: List[Execution], is_open: bool = False) -> Position:
        """Create a Position object from a list of executions"""
        if not executions:
            raise ValueError("Cannot create position from empty executions")
        
        # Calculate position metrics
        total_quantity = sum(e.quantity for e in executions)
        max_quantity = max(e.quantity for e in executions)
        total_commission = sum(e.commission for e in executions)
        
        # Calculate weighted average entry/exit prices
        entry_executions = []
        exit_executions = []
        
        # First execution determines position side
        position_side = PositionEngine._get_side_from_quantity(
            executions[0].quantity if executions[0].action == ExecutionAction.BUY else -executions[0].quantity
        )
        
        # Classify executions as entry or exit based on position side
        for execution in executions:
            if position_side == PositionSide.LONG:
                if execution.action == ExecutionAction.BUY:
                    entry_executions.append(execution)
                else:
                    exit_executions.append(execution)
            else:  # SHORT
                if execution.action == ExecutionAction.SELL:
                    entry_executions.append(execution)
                else:
                    exit_executions.append(execution)
        
        # Calculate weighted averages
        if entry_executions:
            total_entry_value = sum(e.quantity * e.price for e in entry_executions)
            total_entry_quantity = sum(e.quantity for e in entry_executions)
            avg_entry_price = total_entry_value / total_entry_quantity
        else:
            avg_entry_price = executions[0].price  # Fallback
        
        avg_exit_price = None
        if exit_executions and not is_open:
            total_exit_value = sum(e.quantity * e.price for e in exit_executions)
            total_exit_quantity = sum(e.quantity for e in exit_executions)
            avg_exit_price = total_exit_value / total_exit_quantity
        
        # Calculate P&L if position is closed
        total_points_pnl = None
        total_dollars_pnl = None
        
        if avg_exit_price is not None and not is_open:
            if position_side == PositionSide.LONG:
                points_pnl = avg_exit_price - avg_entry_price
            else:  # SHORT
                points_pnl = avg_entry_price - avg_exit_price
            
            total_points_pnl = points_pnl
            total_dollars_pnl = points_pnl * total_quantity  # Simplified - should use contract multiplier
        
        return Position(
            instrument=executions[0].instrument,
            account=executions[0].account,
            side=position_side,
            entry_time=executions[0].timestamp,
            exit_time=executions[-1].timestamp if not is_open else None,
            executions=executions,
            total_quantity=total_quantity,
            max_quantity=max_quantity,
            average_entry_price=avg_entry_price,
            average_exit_price=avg_exit_price,
            total_points_pnl=total_points_pnl,
            total_dollars_pnl=total_dollars_pnl,
            total_commission=total_commission,
            is_closed=not is_open
        )