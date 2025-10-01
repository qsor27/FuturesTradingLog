"""
Quantity Flow Analyzer - Core algorithm for tracking position lifecycle

Extracted from position_service.py to isolate quantity flow analysis logic
"""

from typing import List, NamedTuple, Optional
from datetime import datetime
import logging

from ..models.trade import Trade, MarketSide

logger = logging.getLogger('quantity_flow_analyzer')


class FlowEvent(NamedTuple):
    """Represents a position lifecycle event"""
    event_type: str  # 'position_start', 'position_modify', 'position_close', 'position_reversal'
    trade: Trade
    previous_quantity: int
    running_quantity: int
    timestamp: datetime


class QuantityFlowAnalyzer:
    """
    Pure domain service for analyzing quantity flow in trade executions
    
    CORE ALGORITHM: Track running position quantity (0 → +/- → 0)
    - Position starts when quantity goes from 0 to non-zero
    - Position continues while quantity remains non-zero (same direction)
    - Position ends when quantity returns to 0
    - Position reversal detection prevents overlaps
    """
    
    def analyze_quantity_flow(self, trades: List[Trade]) -> List[FlowEvent]:
        """
        Analyze quantity flow through trade executions
        
        Returns a list of position lifecycle events that can be used
        to construct position records.
        """
        if not trades:
            return []
        
        # Sort trades by entry time for chronological processing
        sorted_trades = sorted(trades, key=lambda t: t.entry_time or datetime.min)
        
        events = []
        running_quantity = 0
        
        logger.info(f"Starting quantity flow analysis for {len(sorted_trades)} trades")
        
        for i, trade in enumerate(sorted_trades):
            # Calculate signed quantity change
            signed_qty_change = self._get_signed_quantity_change(trade)
            
            previous_quantity = running_quantity
            running_quantity += signed_qty_change
            
            logger.info(f"Trade {i+1}: {trade.side_of_market.value} {trade.quantity} | "
                       f"Running: {previous_quantity} → {running_quantity}")
            
            # Determine event type based on position lifecycle
            event_type = self._determine_event_type(previous_quantity, running_quantity)
            
            if event_type:
                event = FlowEvent(
                    event_type=event_type,
                    trade=trade,
                    previous_quantity=previous_quantity,
                    running_quantity=running_quantity,
                    timestamp=trade.entry_time or datetime.now()
                )
                events.append(event)
                
                logger.info(f"  → {event_type.upper()}")
        
        logger.info(f"Quantity flow analysis complete: {len(events)} events generated")
        return events
    
    def _get_signed_quantity_change(self, trade: Trade) -> int:
        """
        Get signed quantity change for a trade
        
        Buy actions: +quantity (increase position)
        Sell actions: -quantity (decrease position)
        """
        quantity = abs(trade.quantity)
        
        if trade.side_of_market in [MarketSide.BUY, MarketSide.BUY_TO_COVER, MarketSide.LONG]:
            return quantity  # Buying contracts (+)
        elif trade.side_of_market in [MarketSide.SELL, MarketSide.SELL_SHORT, MarketSide.SHORT]:
            return -quantity  # Selling contracts (-)
        else:
            logger.warning(f"Unknown side_of_market '{trade.side_of_market.value}' for trade {trade.id}")
            return 0
    
    def _determine_event_type(self, previous_quantity: int, running_quantity: int) -> Optional[str]:
        """
        Determine the type of position lifecycle event based on quantity changes
        
        Position Lifecycle Rules:
        - START: 0 → non-zero
        - MODIFY: non-zero → non-zero (same sign)
        - CLOSE: non-zero → 0
        - REVERSAL: positive → negative or negative → positive
        """
        
        # Position start: 0 → non-zero
        if previous_quantity == 0 and running_quantity != 0:
            return 'position_start'
        
        # Position reversal: sign change (e.g., +10 → -5)
        elif previous_quantity != 0 and running_quantity != 0 and previous_quantity * running_quantity < 0:
            return 'position_reversal'
        
        # Position close: non-zero → 0
        elif previous_quantity != 0 and running_quantity == 0:
            return 'position_close'
        
        # Position modify: non-zero → non-zero (same sign)
        elif previous_quantity != 0 and running_quantity != 0 and previous_quantity * running_quantity > 0:
            return 'position_modify'
        
        # No significant event
        return None
    
    def validate_quantity_flow(self, trades: List[Trade]) -> List[str]:
        """
        Validate quantity flow for potential issues
        
        Returns list of validation warnings/errors
        """
        warnings = []
        events = self.analyze_quantity_flow(trades)
        
        # Check for orphaned trades (trades that don't create events)
        total_trades = len(trades)
        total_events = len(events)
        
        if total_events == 0 and total_trades > 0:
            warnings.append(f"No position events generated from {total_trades} trades")
        
        # Check for open positions (positions that start but never close)
        position_starts = sum(1 for e in events if e.event_type == 'position_start')
        position_closes = sum(1 for e in events if e.event_type == 'position_close')
        position_reversals = sum(1 for e in events if e.event_type == 'position_reversal')
        
        # Each reversal closes one position and opens another
        effective_closes = position_closes + position_reversals
        effective_opens = position_starts + position_reversals
        
        open_positions = effective_opens - effective_closes
        
        if open_positions > 0:
            warnings.append(f"{open_positions} position(s) remain open")
        elif open_positions < 0:
            warnings.append(f"Invalid flow: more closes than opens ({abs(open_positions)})")
        
        # Check for quantity inconsistencies
        final_quantity = 0
        for event in events:
            final_quantity = event.running_quantity
        
        if final_quantity != 0:
            warnings.append(f"Final quantity is {final_quantity}, expected 0 for closed positions")
        
        return warnings
    
    def get_flow_summary(self, trades: List[Trade]) -> dict:
        """Get summary of quantity flow analysis"""
        events = self.analyze_quantity_flow(trades)
        
        event_counts = {}
        for event in events:
            event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
        
        return {
            'total_trades': len(trades),
            'total_events': len(events),
            'event_counts': event_counts,
            'validation_warnings': self.validate_quantity_flow(trades)
        }