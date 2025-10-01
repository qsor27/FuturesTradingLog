"""
Position Engine - Application service for position management

Orchestrates position building using domain services
"""

from typing import List, Dict, Optional, Tuple
import logging
from datetime import datetime

from domain.models.position import Position
from domain.models.trade import Trade
from domain.services.position_builder import PositionBuilder
from domain.services.pnl_calculator import PnLCalculator
from domain.interfaces.position_service_interface import IPositionEngine

logger = logging.getLogger('position_engine')


class PositionEngine(IPositionEngine):
    """
    Application service for position management
    
    Coordinates position building operations using domain services
    """
    
    def __init__(self, instrument_config_path: Optional[str] = None):
        self.pnl_calculator = PnLCalculator(instrument_config_path)
        self.position_builder = PositionBuilder(self.pnl_calculator)
    
    def build_positions_from_trades(self, trades_data: List[Dict]) -> List[Position]:
        """
        Build positions from trade data
        
        Args:
            trades_data: List of trade dictionaries (from database)
            
        Returns:
            List of Position objects
        """
        if not trades_data:
            return []
        
        logger.info(f"Building positions from {len(trades_data)} trades")
        
        # Group trades by account and instrument
        account_instrument_groups = self._group_trades_by_account_instrument(trades_data)
        
        all_positions = []
        
        for (account, instrument), group_trades in account_instrument_groups.items():
            logger.info(f"Processing {len(group_trades)} trades for {account}/{instrument}")
            
            # Convert trade dictionaries to Trade objects
            trade_objects = [Trade.from_dict(trade_dict) for trade_dict in group_trades]
            
            # Build positions for this account/instrument group
            positions = self.position_builder.build_positions_from_trades(
                trade_objects, account, instrument
            )
            
            all_positions.extend(positions)
        
        logger.info(f"Built {len(all_positions)} positions from {len(trades_data)} trades")
        return all_positions
    
    def rebuild_positions_from_trades(self, trades_data: List[Dict]) -> Dict[str, int]:
        """
        Rebuild all positions from trade data
        
        Args:
            trades_data: List of trade dictionaries (from database)
            
        Returns:
            Dictionary with rebuild statistics
        """
        try:
            positions = self.build_positions_from_trades(trades_data)
            
            return {
                'positions_created': len(positions),
                'trades_processed': len(trades_data),
                'positions': positions
            }
            
        except Exception as e:
            logger.error(f"Error rebuilding positions: {e}")
            return {
                'positions_created': 0,
                'trades_processed': 0,
                'positions': []
            }
    
    def validate_position_building(self, trades_data: List[Dict]) -> Dict[str, any]:
        """
        Validate position building process
        
        Args:
            trades_data: List of trade dictionaries
            
        Returns:
            Validation results
        """
        results = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'statistics': {}
        }
        
        try:
            # Group trades by account and instrument
            account_instrument_groups = self._group_trades_by_account_instrument(trades_data)
            
            for (account, instrument), group_trades in account_instrument_groups.items():
                # Convert to Trade objects
                trade_objects = [Trade.from_dict(trade_dict) for trade_dict in group_trades]
                
                # Validate using quantity flow analyzer
                from ...domain.services.quantity_flow_analyzer import QuantityFlowAnalyzer
                analyzer = QuantityFlowAnalyzer()
                
                warnings = analyzer.validate_quantity_flow(trade_objects)
                flow_summary = analyzer.get_flow_summary(trade_objects)
                
                if warnings:
                    results['warnings'].extend([
                        f"{account}/{instrument}: {warning}" for warning in warnings
                    ])
                
                results['statistics'][f"{account}/{instrument}"] = flow_summary
            
            results['valid'] = len(results['errors']) == 0
            
        except Exception as e:
            results['valid'] = False
            results['errors'].append(f"Validation error: {e}")
            logger.error(f"Position validation error: {e}")
        
        return results
    
    def _group_trades_by_account_instrument(self, trades_data: List[Dict]) -> Dict[Tuple[str, str], List[Dict]]:
        """
        Group trades by account and instrument for position building
        
        Args:
            trades_data: List of trade dictionaries
            
        Returns:
            Dictionary with (account, instrument) as key and list of trades as value
        """
        groups = {}
        
        for trade in trades_data:
            # Normalize account and instrument for consistent grouping
            account = (trade.get('account') or '').strip()
            instrument = (trade.get('instrument') or '').strip()
            
            # Skip trades with missing critical fields
            if not account or not instrument:
                logger.warning(f"Skipping trade with missing account/instrument: {trade.get('entry_execution_id', 'Unknown')}")
                continue
            
            key = (account, instrument)
            if key not in groups:
                groups[key] = []
            groups[key].append(trade)
        
        return groups
    
    def get_position_statistics(self, positions: List[Position]) -> Dict[str, any]:
        """
        Calculate statistics for a list of positions
        
        Args:
            positions: List of Position objects
            
        Returns:
            Dictionary with position statistics
        """
        if not positions:
            return {
                'total_positions': 0,
                'closed_positions': 0,
                'open_positions': 0,
                'winning_positions': 0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'total_commission': 0.0,
                'avg_executions_per_position': 0.0,
                'win_rate': 0.0
            }
        
        closed_positions = [p for p in positions if p.is_closed()]
        open_positions = [p for p in positions if p.is_open()]
        winning_positions = [p for p in closed_positions if p.is_profitable()]
        
        total_pnl = sum(p.total_dollars_pnl for p in positions)
        total_commission = sum(p.total_commission for p in positions)
        avg_executions = sum(p.execution_count for p in positions) / len(positions)
        
        win_rate = 0.0
        if closed_positions:
            win_rate = (len(winning_positions) / len(closed_positions)) * 100
        
        return {
            'total_positions': len(positions),
            'closed_positions': len(closed_positions),
            'open_positions': len(open_positions),
            'winning_positions': len(winning_positions),
            'total_pnl': total_pnl,
            'avg_pnl': total_pnl / len(positions),
            'total_commission': total_commission,
            'avg_executions_per_position': avg_executions,
            'win_rate': win_rate,
            'instruments_traded': len(set(p.instrument for p in positions)),
            'accounts_traded': len(set(p.account for p in positions))
        }