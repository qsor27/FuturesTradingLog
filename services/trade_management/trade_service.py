"""
Trade Service - Business logic for trade operations

Extracted from routes/trades.py to separate business logic from HTTP handling
"""

from typing import List, Dict, Optional, Any
import logging
from datetime import datetime

from ...domain.interfaces.trade_service_interface import ITradeService, ITradeFilterService

logger = logging.getLogger('trade_service')


class TradeService(ITradeService):
    """
    Application service for trade management operations
    
    Handles trade filtering, details, updates, and related operations
    """
    
    def __init__(self, db_service=None):
        self.db_service = db_service
    
    def get_trade_detail(self, trade_id: int) -> Dict[str, Any]:
        """
        Get comprehensive trade details including position data and linked trades
        
        Args:
            trade_id: Trade ID to get details for
            
        Returns:
            Dictionary with trade details, position data, and linked trades
        """
        try:
            if not self.db_service:
                raise ValueError("Database service not available")
            
            # Get basic trade data
            trade = self.db_service.get_trade_by_id(trade_id)
            if not trade:
                return {
                    'success': False,
                    'error': 'Trade not found',
                    'trade_id': trade_id
                }
            
            # Get comprehensive position data
            position_data = self._get_position_data(trade_id)
            
            # Get linked trades if part of a group
            linked_data = self._get_linked_trades_data(trade)
            
            return {
                'success': True,
                'trade': trade,
                'position_data': position_data,
                'linked_trades': linked_data['trades'],
                'group_total_pnl': linked_data['total_pnl'],
                'group_total_commission': linked_data['total_commission']
            }
            
        except Exception as e:
            logger.error(f"Error getting trade detail for ID {trade_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'trade_id': trade_id
            }
    
    def delete_trades(self, trade_ids: List[int]) -> Dict[str, Any]:
        """
        Delete multiple trades
        
        Args:
            trade_ids: List of trade IDs to delete
            
        Returns:
            Dictionary with success status and results
        """
        try:
            if not trade_ids:
                return {
                    'success': False,
                    'error': 'No trade IDs provided'
                }
            
            if not self.db_service:
                raise ValueError("Database service not available")
            
            success = self.db_service.delete_trades(trade_ids)
            
            return {
                'success': success,
                'deleted_count': len(trade_ids) if success else 0,
                'trade_ids': trade_ids
            }
            
        except Exception as e:
            logger.error(f"Error deleting trades {trade_ids}: {e}")
            return {
                'success': False,
                'error': str(e),
                'trade_ids': trade_ids
            }
    
    def update_trade_notes(self, trade_id: int, notes: str = '', chart_url: str = '', 
                          validated: bool = False, reviewed: bool = False) -> Dict[str, Any]:
        """
        Update trade notes and metadata
        
        Args:
            trade_id: Trade ID to update
            notes: Trade notes
            chart_url: Chart URL
            validated: Whether trade is validated
            reviewed: Whether trade is reviewed
            
        Returns:
            Dictionary with success status
        """
        try:
            if not self.db_service:
                raise ValueError("Database service not available")
            
            success = self.db_service.update_trade_details(
                trade_id=trade_id,
                chart_url=chart_url,
                notes=notes,
                confirmed_valid=validated,
                reviewed=reviewed
            )
            
            return {
                'success': success,
                'trade_id': trade_id,
                'updated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error updating trade notes for ID {trade_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'trade_id': trade_id
            }
    
    def get_trade_filters(self) -> Dict[str, List[str]]:
        """
        Get available filter options for trades
        
        Returns:
            Dictionary with filter options (accounts, instruments, etc.)
        """
        try:
            if not self.db_service:
                raise ValueError("Database service not available")
            
            accounts = self.db_service.get_unique_accounts()
            instruments = self.db_service.get_unique_instruments()
            
            return {
                'success': True,
                'accounts': accounts,
                'instruments': instruments
            }
            
        except Exception as e:
            logger.error(f"Error getting trade filters: {e}")
            return {
                'success': False,
                'error': str(e),
                'accounts': [],
                'instruments': []
            }
    
    def _get_position_data(self, trade_id: int) -> Dict[str, Any]:
        """
        Get position data for a trade
        
        Args:
            trade_id: Trade ID
            
        Returns:
            Dictionary with position data
        """
        try:
            # Try to get comprehensive position data
            position_data = self.db_service.get_position_executions(trade_id)
            
            if position_data:
                return position_data
            
            # Fallback: create position data from trade
            trade = self.db_service.get_trade_by_id(trade_id)
            if not trade:
                return {}
            
            return self._create_fallback_position_data(trade)
            
        except Exception as e:
            logger.error(f"Error getting position data for trade {trade_id}: {e}")
            return {}
    
    def _create_fallback_position_data(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create fallback position data from trade
        
        Args:
            trade: Trade dictionary
            
        Returns:
            Dictionary with fallback position data
        """
        return {
            'primary_trade': trade,
            'related_executions': [trade],
            'execution_analysis': {
                'executions': [],
                'total_fills': 2,
                'entry_fills': 1,
                'exit_fills': 1,
                'position_lifecycle': 'closed'
            },
            'position_summary': {
                'total_pnl': trade.get('dollars_gain_loss', 0),
                'total_commission': trade.get('commission', 0),
                'total_points': trade.get('points_gain_loss', 0),
                'total_quantity': trade.get('quantity', 0),
                'average_entry_price': trade.get('entry_price', 0),
                'average_exit_price': trade.get('exit_price', 0),
                'net_pnl': (trade.get('dollars_gain_loss', 0) - 
                           (trade.get('commission', 0) or 0)),
                'first_entry': trade.get('entry_time'),
                'last_exit': trade.get('exit_time'),
                'number_of_fills': 2
            }
        }
    
    def _get_linked_trades_data(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get linked trades data for a trade
        
        Args:
            trade: Trade dictionary
            
        Returns:
            Dictionary with linked trades data
        """
        linked_data = {
            'trades': None,
            'total_pnl': 0,
            'total_commission': 0
        }
        
        if not trade.get('link_group_id'):
            return linked_data
        
        try:
            linked_trades = self.db_service.get_linked_trades(trade['link_group_id'])
            group_stats = self.db_service.get_group_statistics(trade['link_group_id'])
            
            if linked_trades and group_stats:
                linked_data['trades'] = linked_trades
                linked_data['total_pnl'] = group_stats.get('total_pnl', 0)
                linked_data['total_commission'] = group_stats.get('total_commission', 0)
                
        except Exception as e:
            logger.error(f"Error getting linked trades for group {trade['link_group_id']}: {e}")
        
        return linked_data


class TradeFilterService(ITradeFilterService):
    """
    Service for trade filtering operations
    """
    
    def __init__(self, db_service=None):
        self.db_service = db_service
    
    def apply_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply filters to trades
        
        Args:
            filters: Dictionary with filter criteria
            
        Returns:
            Dictionary with filtered results
        """
        try:
            # Extract filter parameters
            account_filter = filters.get('account')
            instrument_filter = filters.get('instrument')
            date_from = filters.get('date_from')
            date_to = filters.get('date_to')
            min_pnl = filters.get('min_pnl')
            max_pnl = filters.get('max_pnl')
            
            # Apply filters through database service
            filtered_trades = self.db_service.get_filtered_trades(
                account=account_filter,
                instrument=instrument_filter,
                date_from=date_from,
                date_to=date_to,
                min_pnl=min_pnl,
                max_pnl=max_pnl
            )
            
            return {
                'success': True,
                'trades': filtered_trades,
                'count': len(filtered_trades),
                'filters_applied': filters
            }
            
        except Exception as e:
            logger.error(f"Error applying trade filters: {e}")
            return {
                'success': False,
                'error': str(e),
                'trades': [],
                'count': 0
            }
    
    def get_filter_statistics(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get statistics for filtered trades
        
        Args:
            filters: Dictionary with filter criteria
            
        Returns:
            Dictionary with filter statistics
        """
        try:
            # Get filtered trades
            result = self.apply_filters(filters)
            if not result['success']:
                return result
            
            trades = result['trades']
            
            # Calculate statistics
            total_pnl = sum(trade.get('dollars_gain_loss', 0) for trade in trades)
            total_commission = sum(trade.get('commission', 0) for trade in trades)
            winning_trades = [t for t in trades if t.get('dollars_gain_loss', 0) > 0]
            
            return {
                'success': True,
                'total_trades': len(trades),
                'winning_trades': len(winning_trades),
                'win_rate': (len(winning_trades) / len(trades) * 100) if trades else 0,
                'total_pnl': total_pnl,
                'total_commission': total_commission,
                'net_pnl': total_pnl - total_commission,
                'average_pnl': total_pnl / len(trades) if trades else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting filter statistics: {e}")
            return {
                'success': False,
                'error': str(e)
            }