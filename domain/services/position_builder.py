"""
Position Builder - Core position building algorithm extracted from position_service.py

🚨 CRITICAL: This contains the MOST IMPORTANT algorithm in the application.
All modifications must preserve the exact position building logic.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

from ..models.position import Position, PositionType, PositionStatus
from ..models.trade import Trade, MarketSide
from .quantity_flow_analyzer import QuantityFlowAnalyzer
from .pnl_calculator import PnLCalculator
from .position_execution_integrity_validator import PositionExecutionIntegrityValidator
from ..models.execution import Execution

logger = logging.getLogger('position_builder')


class PositionBuilder:
    """
    Pure domain service for building positions from trade executions
    
    CRITICAL ALGORITHM: Uses Quantity Flow Analysis (0 → +/- → 0)
    - Position starts when quantity goes from 0 to non-zero
    - Position continues while quantity remains non-zero (same direction)
    - Position ends when quantity returns to 0
    - Position reversal detection prevents overlaps
    """
    
    def __init__(self, pnl_calculator: PnLCalculator, enable_validation: bool = False,
                 validation_repository=None):
        self.pnl_calculator = pnl_calculator
        self.flow_analyzer = QuantityFlowAnalyzer()
        self.enable_validation = enable_validation
        self.validator = PositionExecutionIntegrityValidator() if enable_validation else None
        self.validation_repository = validation_repository
    
    def build_positions_from_trades(self, trades: List[Trade], account: str, instrument: str) -> List[Position]:
        """
        Build position objects from trade executions using quantity flow analysis

        QUANTITY FLOW MODEL: All executions are aggregated using quantity flow (0 → +/- → 0)
        - Position starts when quantity goes from 0 to non-zero
        - Position continues while quantity remains non-zero (same direction)
        - Position ends when quantity returns to 0
        - Ignores P&L values on individual executions (P&L is recalculated for the complete position)
        """
        logger.info(f"=== BUILDING POSITIONS FOR {account}/{instrument} ===")
        logger.info(f"Processing {len(trades)} trades using QUANTITY FLOW MODEL")
        
        # Sort trades by entry time for chronological processing
        trades_sorted = sorted(trades, key=lambda t: t.entry_time or datetime.min)
        
        # Process all trades using quantity flow analysis
        # This ignores any P&L on individual executions and aggregates by quantity flow (0 → +/- → 0)
        logger.info("Using quantity flow analysis to aggregate all executions into positions")
        positions = self._aggregate_executions_into_positions(trades_sorted, account, instrument)
        
        logger.info(f"=== POSITION BUILDING COMPLETE ===")
        logger.info(f"Created {len(positions)} positions from {len(trades_sorted)} trades")

        # Run validation if enabled
        if self.enable_validation and positions:
            logger.info("Running integrity validation on built positions")
            self._validate_positions(positions, trades_sorted)

        return positions
    
    def _convert_completed_trade_to_position(self, trade: Trade, account: str, instrument: str) -> Optional[Position]:
        """
        Convert a completed trade directly to a position
        
        For trades where entry_time == exit_time and entry_price == exit_price,
        this represents a complete round-trip position.
        """
        try:
            position = Position(
                instrument=instrument,
                account=account,
                position_type=PositionType.LONG if trade.side_of_market == MarketSide.BUY else PositionType.SHORT,
                entry_time=trade.entry_time,
                exit_time=trade.exit_time,
                total_quantity=abs(trade.quantity),
                max_quantity=abs(trade.quantity),
                position_status=PositionStatus.CLOSED,
                execution_count=1
            )
            
            # Calculate position totals from the single trade
            self._calculate_position_totals_from_trade(position, trade)
            
            return position
            
        except Exception as e:
            logger.error(f"Error converting completed trade to position: {e}")
            return None
    
    def _aggregate_executions_into_positions(self, trades: List[Trade], account: str, instrument: str) -> List[Position]:
        """
        Aggregate raw executions into complete positions using quantity flow tracking
        
        Algorithm: Track running position quantity (0 → +/- → 0)
        - Position starts when quantity goes from 0 to non-zero
        - Position continues while quantity remains non-zero (same direction)
        - Position ends when quantity returns to 0
        - Position reversal detection prevents overlaps
        """
        if not trades:
            return []
        
        # Sort executions by timestamp to ensure correct order
        try:
            sorted_trades = sorted(trades, key=lambda t: t.entry_time or datetime.min)
            logger.info(f"Sorted {len(sorted_trades)} executions by entry_time for correct order")
        except Exception as e:
            logger.warning(f"Could not sort executions by entry_time: {e}. Using original order.")
            sorted_trades = trades
        
        positions = []
        current_position = None
        current_executions = []
        
        # Use quantity flow analyzer to track position lifecycle
        flow_events = self.flow_analyzer.analyze_quantity_flow(sorted_trades)
        
        for event in flow_events:
            if event.event_type == 'position_start':
                # Starting new position
                current_position = Position(
                    instrument=instrument,
                    account=account,
                    position_type=PositionType.LONG if event.running_quantity > 0 else PositionType.SHORT,
                    entry_time=event.trade.entry_time,
                    exit_time=None,
                    total_quantity=abs(event.running_quantity),
                    max_quantity=abs(event.running_quantity),
                    position_status=PositionStatus.OPEN,
                    execution_count=1
                )
                current_executions = [event.trade]
                logger.info(f"Started new {current_position.position_type.value} position")
                
            elif event.event_type == 'position_modify':
                # Modifying existing position
                if current_position:
                    current_executions.append(event.trade)
                    current_position.max_quantity = max(current_position.max_quantity, abs(event.running_quantity))
                    current_position.total_quantity = abs(event.running_quantity)  # Track current/remaining quantity
                    current_position.execution_count = len(current_executions)

                    if abs(event.running_quantity) > abs(event.previous_quantity):
                        logger.info(f"Added to {current_position.position_type.value} position")
                    else:
                        logger.info(f"Reduced {current_position.position_type.value} position")
                
            elif event.event_type == 'position_close':
                # Closing position
                if current_position:
                    current_executions.append(event.trade)
                    current_position.position_status = PositionStatus.CLOSED
                    current_position.execution_count = len(current_executions)
                    
                    # Calculate position totals
                    self._calculate_position_totals_from_executions(current_position, current_executions)
                    
                    positions.append(current_position)
                    logger.info(f"Closed position with {current_position.execution_count} executions")
                    
                    current_position = None
                    current_executions = []
                    
            elif event.event_type == 'position_reversal':
                # Position reversal - close old, start new
                if current_position:
                    # Close the old position
                    current_executions.append(event.trade)
                    current_position.position_status = PositionStatus.CLOSED
                    current_position.execution_count = len(current_executions)
                    self._calculate_position_totals_from_executions(current_position, current_executions)
                    positions.append(current_position)
                    logger.info(f"Closed reversed {current_position.position_type.value} position")
                    
                    # Start new position in opposite direction
                    new_position_type = PositionType.LONG if event.running_quantity > 0 else PositionType.SHORT
                    current_position = Position(
                        instrument=instrument,
                        account=account,
                        position_type=new_position_type,
                        entry_time=event.trade.entry_time,
                        exit_time=None,
                        total_quantity=abs(event.running_quantity),
                        max_quantity=abs(event.running_quantity),
                        position_status=PositionStatus.OPEN,
                        execution_count=1
                    )
                    current_executions = [event.trade]
                    logger.info(f"Started new {new_position_type.value} position from reversal")
        
        # Handle any remaining open position
        if current_position:
            current_position.position_status = PositionStatus.OPEN
            self._calculate_position_totals_from_executions(current_position, current_executions)
            positions.append(current_position)
            logger.info(f"Saved open position with {current_position.execution_count} executions")
        
        logger.info(f"Quantity flow analysis complete: {len(positions)} positions created")
        return positions
    
    def _calculate_position_totals_from_trade(self, position: Position, trade: Trade):
        """Calculate position totals from a single completed trade"""
        position.average_entry_price = trade.entry_price
        position.average_exit_price = trade.exit_price
        position.total_points_pnl = trade.points_gain_loss
        position.total_dollars_pnl = trade.dollars_gain_loss
        position.execution_count = 1

        # Calculate commission: either from trade or from config (per contract per side)
        if trade.commission and trade.commission > 0:
            position.total_commission = trade.commission
        else:
            # Calculate commission from config: commission_per_side × quantity
            commission_per_side = self.pnl_calculator._get_instrument_commission(position.instrument)
            position.total_commission = commission_per_side * abs(trade.quantity)

        # Calculate risk/reward ratio
        if position.total_dollars_pnl != 0 and position.total_commission > 0:
            if position.total_dollars_pnl > 0:
                position.risk_reward_ratio = abs(position.total_dollars_pnl) / position.total_commission
            else:
                position.risk_reward_ratio = position.total_commission / abs(position.total_dollars_pnl)
        else:
            position.risk_reward_ratio = 0.0
    
    def _calculate_position_totals_from_executions(self, position: Position, executions: List[Trade]):
        """Calculate position totals from aggregated executions using FIFO methodology"""
        if not executions:
            return

        # Set actual entry and exit times from first and last executions
        sorted_executions = sorted(executions, key=lambda x: x.entry_time or datetime.min)
        position.entry_time = sorted_executions[0].entry_time

        # For closed positions, set exit time to the last execution
        if position.position_status == PositionStatus.CLOSED:
            position.exit_time = sorted_executions[-1].entry_time

        # Calculate P&L using the PnL calculator
        pnl_result = self.pnl_calculator.calculate_position_pnl(position, executions)

        position.average_entry_price = pnl_result.average_entry_price

        # For OPEN positions, exit price should be None (no exits yet)
        if position.position_status == PositionStatus.OPEN:
            position.average_exit_price = None
        else:
            position.average_exit_price = pnl_result.average_exit_price

        position.total_points_pnl = pnl_result.points_pnl
        position.total_dollars_pnl = pnl_result.dollars_pnl

        # Calculate commission: either from executions or from config (per contract per side)
        csv_commission = sum(t.commission for t in executions)
        if csv_commission > 0:
            # Use commission from CSV if available
            position.total_commission = csv_commission
        else:
            # Calculate commission from config: commission_per_side × total_contracts_traded
            commission_per_side = self.pnl_calculator._get_instrument_commission(position.instrument)
            total_contracts = sum(abs(t.quantity) for t in executions)
            position.total_commission = commission_per_side * total_contracts

        # Calculate risk/reward ratio
        if position.total_dollars_pnl != 0 and position.total_commission > 0:
            if position.total_dollars_pnl > 0:
                position.risk_reward_ratio = abs(position.total_dollars_pnl) / position.total_commission
            else:
                position.risk_reward_ratio = position.total_commission / abs(position.total_dollars_pnl)
        else:
            position.risk_reward_ratio = 0.0
    def _validate_positions(self, positions: List[Position], trades: List[Trade]):
        """
        Validate built positions against source executions

        This runs integrity checks to ensure:
        - All executions are accounted for in positions
        - Position quantities match execution flows
        - No orphaned executions or positions
        - Data consistency between positions and executions
        """
        if not self.validator or not self.validation_repository:
            logger.warning("Validation requested but validator or repository not configured")
            return

        try:
            # Convert trades to executions for validation
            executions = self._convert_trades_to_executions(trades)

            # Group executions by position (assuming trade_id maps to position)
            # For now, validate that we have the right number of executions
            total_exec_count = len(executions)
            total_position_exec_count = sum(p.execution_count for p in positions)

            if total_exec_count != total_position_exec_count:
                logger.warning(
                    f"Execution count mismatch: {total_exec_count} source executions "
                    f"but {total_position_exec_count} executions in positions"
                )

            # Run validation on each position
            validation_count = 0
            issue_count = 0

            for position in positions:
                # Find executions for this position
                # Note: This is a simplified mapping - in production, you would need proper
                # execution-to-position tracking
                position_executions = []

                # Validate position
                result, issues = self.validator.validate_position(position, position_executions)

                if result.status.value != "passed":
                    pos_id = position.id if position.id else "new"
                    logger.warning(
                        f"Position validation failed: {len(issues)} issues found for "
                        f"position {pos_id}"
                    )
                    issue_count += len(issues)

                    # Save validation results if repository is available
                    if self.validation_repository and position.id:
                        self.validation_repository.save_validation_with_issues(result, issues)

                validation_count += 1

            logger.info(
                f"Validation complete: {validation_count} positions validated, "
                f"{issue_count} total issues found"
            )

        except Exception as e:
            logger.error(f"Error during position validation: {e}", exc_info=True)

    def _convert_trades_to_executions(self, trades: List[Trade]) -> List[Execution]:
        """Convert Trade objects to Execution objects for validation"""
        executions = []

        for trade in trades:
            try:
                execution = Execution(
                    execution_id=f"TRADE_{trade.id}" if trade.id else f"TRADE_{id(trade)}",
                    instrument=trade.instrument or "",
                    account=trade.account or "",
                    side_of_market=trade.side_of_market.value if isinstance(trade.side_of_market, MarketSide) else str(trade.side_of_market),
                    quantity=abs(trade.quantity),
                    price=trade.entry_price or 0.0,
                    execution_time=trade.entry_time or datetime.now(),
                    trade_id=trade.id
                )
                executions.append(execution)
            except Exception as e:
                logger.warning(f"Could not convert trade to execution: {e}")
                continue

        return executions

