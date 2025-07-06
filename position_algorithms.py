"""
Position Algorithms - Pure Functions for Position Calculations

Refactored position logic into smaller, testable pure functions.
Implements Gemini's recommendations for modular algorithm design.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
import logging

logger = logging.getLogger('position_algorithms')


class QuantityFlow:
    """Represents a single point in quantity flow with running totals"""
    
    def __init__(self, execution: Dict, running_quantity: int, previous_quantity: int = 0):
        self.execution = execution
        self.running_quantity = running_quantity
        self.previous_quantity = previous_quantity
        self.timestamp = execution['entry_time']
        self.quantity_change = execution['quantity']
        
        # Determine if this is opening or closing based on previous quantity
        if previous_quantity == 0:
            self.action_type = 'START'
        elif running_quantity == 0:
            self.action_type = 'CLOSE'
        elif (previous_quantity > 0 and execution['side_of_market'] == 'Sell') or \
             (previous_quantity < 0 and execution['side_of_market'] == 'Buy'):
            self.action_type = 'REDUCE'
        else:
            self.action_type = 'ADD'


def calculate_running_quantity(executions: List[Dict]) -> List[QuantityFlow]:
    """
    Calculate running quantity through executions to identify position boundaries.
    
    Args:
        executions: List of execution dictionaries sorted by time
        
    Returns:
        List of QuantityFlow objects showing position lifecycle
    """
    if not executions:
        return []
    
    quantity_flows = []
    running_quantity = 0
    
    for execution in executions:
        # Calculate signed quantity change
        side = execution['side_of_market']
        quantity = execution['quantity']
        
        if side == 'Buy':
            signed_change = quantity
        elif side == 'Sell':
            signed_change = -quantity
        else:
            logger.warning(f"Unknown side_of_market: {side} in execution {execution.get('id', 'unknown')}")
            continue
        
        # Update running quantity
        previous_quantity = running_quantity
        running_quantity += signed_change
        
        # Create quantity flow point
        flow = QuantityFlow(execution, running_quantity, previous_quantity)
        flow.signed_change = signed_change
        
        quantity_flows.append(flow)
    
    return quantity_flows


def group_executions_by_position(quantity_flows: List[QuantityFlow]) -> List[List[QuantityFlow]]:
    """
    Group quantity flows into discrete positions based on 0 → +/- → 0 lifecycle.
    
    Args:
        quantity_flows: List of QuantityFlow objects
        
    Returns:
        List of position groups, each containing QuantityFlow objects
    """
    if not quantity_flows:
        return []
    
    positions = []
    current_position = []
    
    for flow in quantity_flows:
        current_position.append(flow)
        
        # Check if position is closed (running quantity returns to 0)
        if flow.running_quantity == 0 and len(current_position) > 1:
            positions.append(current_position)
            current_position = []
    
    # Add any remaining open position
    if current_position and current_position[0].running_quantity != 0:
        positions.append(current_position)
    
    return positions


def calculate_position_pnl(position_flows: List[QuantityFlow], multiplier: Decimal = Decimal('1')) -> Dict[str, Any]:
    """
    Calculate P&L for a complete position using FIFO methodology.
    
    Args:
        position_flows: List of QuantityFlow objects for one position
        multiplier: Instrument multiplier for dollar conversion
        
    Returns:
        Dictionary with P&L calculations
    """
    if not position_flows:
        return {'error': 'No flows provided'}
    
    if len(position_flows) < 2:
        return {'error': 'Position must have at least entry and exit'}
    
    # Separate entry and exit flows based on side of market and position direction
    entry_flows = []
    exit_flows = []
    
    # Determine position direction from first flow
    first_flow = position_flows[0]
    is_long_position = first_flow.execution['side_of_market'] == 'Buy'
    
    for flow in position_flows:
        if is_long_position:
            # For long positions: Buy = entry, Sell = exit
            if flow.execution['side_of_market'] == 'Buy':
                entry_flows.append(flow)
            else:
                exit_flows.append(flow)
        else:
            # For short positions: Sell = entry, Buy = exit
            if flow.execution['side_of_market'] == 'Sell':
                entry_flows.append(flow)
            else:
                exit_flows.append(flow)
    
    if not entry_flows or not exit_flows:
        return {'error': 'Position must have both entries and exits'}
    
    # Calculate weighted average entry price
    total_entry_quantity = sum(flow.quantity_change for flow in entry_flows)
    total_entry_value = Decimal('0')
    
    for flow in entry_flows:
        # Use appropriate price field based on position direction
        if is_long_position:
            price = flow.execution.get('entry_price') or flow.execution.get('price', 0)
        else:
            price = flow.execution.get('entry_price') or flow.execution.get('price', 0)
        total_entry_value += Decimal(str(price)) * Decimal(str(flow.quantity_change))
    
    avg_entry_price = total_entry_value / Decimal(str(total_entry_quantity))
    
    # Calculate weighted average exit price
    total_exit_quantity = sum(flow.quantity_change for flow in exit_flows)
    total_exit_value = Decimal('0')
    
    for flow in exit_flows:
        # Use appropriate price field based on position direction
        if is_long_position:
            price = flow.execution.get('exit_price') or flow.execution.get('price', 0)
        else:
            price = flow.execution.get('exit_price') or flow.execution.get('price', 0)
        total_exit_value += Decimal(str(price)) * Decimal(str(flow.quantity_change))
    
    avg_exit_price = total_exit_value / Decimal(str(total_exit_quantity))
    
    # Determine position direction from first entry
    first_entry = entry_flows[0]
    is_long = first_entry.execution['side_of_market'] == 'Buy'
    
    # Calculate points P&L
    if is_long:
        points_pnl = avg_exit_price - avg_entry_price
    else:
        points_pnl = avg_entry_price - avg_exit_price
    
    # Calculate total commission
    total_commission = sum(
        Decimal(str(flow.execution.get('commission', 0)))
        for flow in position_flows
    )
    
    # Calculate dollar P&L
    position_size = min(total_entry_quantity, total_exit_quantity)
    gross_pnl = points_pnl * multiplier * Decimal(str(position_size))
    net_pnl = gross_pnl - total_commission
    
    return {
        'position_size': position_size,
        'is_long': is_long,
        'avg_entry_price': float(avg_entry_price),
        'avg_exit_price': float(avg_exit_price),
        'points_pnl': float(points_pnl),
        'gross_pnl': float(gross_pnl),
        'total_commission': float(total_commission),
        'net_pnl': float(net_pnl),
        'entry_time': entry_flows[0].timestamp,
        'exit_time': exit_flows[-1].timestamp,
        'entry_flows_count': len(entry_flows),
        'exit_flows_count': len(exit_flows)
    }


def validate_position_boundaries(quantity_flows: List[QuantityFlow]) -> List[str]:
    """
    Validate that position follows proper 0 → +/- → 0 lifecycle without direction changes.
    
    Args:
        quantity_flows: List of QuantityFlow objects for validation
        
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    
    if not quantity_flows:
        return ['No quantity flows to validate']
    
    # Check that position starts from 0
    if quantity_flows[0].previous_quantity != 0:
        errors.append('Position does not start from zero quantity')
    
    # Check for direction changes without reaching zero
    current_direction = None
    
    for i, flow in enumerate(quantity_flows):
        # Determine direction
        if flow.running_quantity > 0:
            direction = 'LONG'
        elif flow.running_quantity < 0:
            direction = 'SHORT'
        else:
            direction = 'FLAT'
        
        # Check for invalid direction changes
        if current_direction and direction != 'FLAT' and current_direction != 'FLAT':
            if current_direction != direction:
                errors.append(f'Invalid direction change from {current_direction} to {direction} at flow {i} without reaching flat')
        
        if direction != 'FLAT':
            current_direction = direction
        else:
            current_direction = None
    
    # Validate timestamps are in order
    for i in range(1, len(quantity_flows)):
        if quantity_flows[i].timestamp < quantity_flows[i-1].timestamp:
            errors.append(f'Timestamps out of order at flow {i}')
    
    return errors


def aggregate_position_statistics(positions_data: List[Dict]) -> Dict[str, Any]:
    """
    Aggregate statistics across multiple positions.
    
    Args:
        positions_data: List of position P&L dictionaries
        
    Returns:
        Aggregated statistics dictionary
    """
    if not positions_data:
        return {
            'total_positions': 0,
            'winning_positions': 0,
            'losing_positions': 0,
            'total_pnl': 0,
            'win_rate': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'largest_win': 0,
            'largest_loss': 0
        }
    
    total_positions = len(positions_data)
    winning_positions = sum(1 for pos in positions_data if pos.get('net_pnl', 0) > 0)
    losing_positions = sum(1 for pos in positions_data if pos.get('net_pnl', 0) < 0)
    
    total_pnl = sum(pos.get('net_pnl', 0) for pos in positions_data)
    
    wins = [pos['net_pnl'] for pos in positions_data if pos.get('net_pnl', 0) > 0]
    losses = [pos['net_pnl'] for pos in positions_data if pos.get('net_pnl', 0) < 0]
    
    return {
        'total_positions': total_positions,
        'winning_positions': winning_positions,
        'losing_positions': losing_positions,
        'total_pnl': round(total_pnl, 2),
        'win_rate': round((winning_positions / total_positions) * 100, 1) if total_positions > 0 else 0,
        'avg_win': round(sum(wins) / len(wins), 2) if wins else 0,
        'avg_loss': round(sum(losses) / len(losses), 2) if losses else 0,
        'largest_win': round(max(wins), 2) if wins else 0,
        'largest_loss': round(min(losses), 2) if losses else 0,
        'profit_factor': round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else float('inf') if wins else 0
    }


def detect_position_overlaps(positions_by_account: Dict[str, List[Dict]]) -> List[Dict]:
    """
    Detect overlapping positions that violate the 0 → +/- → 0 rule.
    
    Args:
        positions_by_account: Dictionary mapping accounts to position lists
        
    Returns:
        List of overlap detection results
    """
    overlaps = []
    
    for account, positions in positions_by_account.items():
        # Sort positions by entry time
        sorted_positions = sorted(positions, key=lambda p: p.get('entry_time', datetime.min))
        
        for i in range(len(sorted_positions) - 1):
            current_pos = sorted_positions[i]
            next_pos = sorted_positions[i + 1]
            
            # Check for time overlap
            current_exit = current_pos.get('exit_time')
            next_entry = next_pos.get('entry_time')
            
            if current_exit and next_entry:
                if next_entry < current_exit:
                    overlaps.append({
                        'account': account,
                        'instrument': current_pos.get('instrument'),
                        'overlap_type': 'time_overlap',
                        'position1_id': current_pos.get('id'),
                        'position2_id': next_pos.get('id'),
                        'position1_exit': current_exit,
                        'position2_entry': next_entry,
                        'overlap_duration': str(current_exit - next_entry)
                    })
    
    return overlaps


def create_position_summary(quantity_flows: List[QuantityFlow], pnl_data: Dict) -> Dict[str, Any]:
    """
    Create a comprehensive position summary combining flow analysis and P&L.
    
    Args:
        quantity_flows: Position quantity flows
        pnl_data: P&L calculation results
        
    Returns:
        Complete position summary dictionary
    """
    if not quantity_flows:
        return {'error': 'No quantity flows provided'}
    
    first_flow = quantity_flows[0]
    last_flow = quantity_flows[-1]
    
    # Basic position info
    summary = {
        'instrument': first_flow.execution.get('instrument'),
        'account': first_flow.execution.get('account'),
        'entry_time': first_flow.timestamp,
        'exit_time': last_flow.timestamp if last_flow.running_quantity == 0 else None,
        'status': 'closed' if last_flow.running_quantity == 0 else 'open',
        'execution_count': len(quantity_flows),
        'max_quantity': max(abs(flow.running_quantity) for flow in quantity_flows),
    }
    
    # Add P&L data if available
    if 'error' not in pnl_data:
        summary.update({
            'position_size': pnl_data['position_size'],
            'position_type': 'Long' if pnl_data['is_long'] else 'Short',
            'avg_entry_price': pnl_data['avg_entry_price'],
            'avg_exit_price': pnl_data['avg_exit_price'],
            'points_pnl': pnl_data['points_pnl'],
            'total_commission': pnl_data['total_commission'],
            'net_pnl': pnl_data['net_pnl']
        })
    
    # Flow analysis
    summary['flows'] = [
        {
            'timestamp': flow.timestamp,
            'action_type': flow.action_type,
            'quantity_change': flow.quantity_change,
            'running_quantity': flow.running_quantity,
            'execution_id': flow.execution.get('id')
        }
        for flow in quantity_flows
    ]
    
    return summary