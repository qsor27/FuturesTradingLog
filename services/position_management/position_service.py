"""
Position Management Service - Business logic for position operations

Extracted from routes/positions.py to separate business logic from HTTP handling
Integrates with the new domain services for position building
"""

from typing import List, Dict, Optional, Any, Tuple
import logging
from datetime import datetime

from ...services.position_engine.position_engine import PositionEngine
from ...services.position_engine.position_orchestrator import PositionOrchestrator
from ...domain.models.position import Position
from ...domain.interfaces.position_service_interface import IPositionManagementService

logger = logging.getLogger('position_management_service')


class PositionManagementService(IPositionManagementService):
    """
    Application service for position management operations
    
    Handles position dashboard data, filtering, pagination, and statistics
    """
    
    def __init__(self, db_service=None, instrument_config_path: Optional[str] = None):
        self.db_service = db_service
        self.position_engine = PositionEngine(instrument_config_path)
        self.position_orchestrator = PositionOrchestrator(self.position_engine, db_service)
    
    def get_positions_dashboard_data(self, page: int = 1, page_size: int = 50,
                                   account_filter: Optional[str] = None,
                                   instrument_filter: Optional[str] = None,
                                   status_filter: Optional[str] = None,
                                   sort_by: str = 'entry_time',
                                   sort_order: str = 'DESC') -> Dict[str, Any]:
        """
        Get data for positions dashboard with filtering and pagination
        
        Args:
            page: Page number (1-based)
            page_size: Number of positions per page
            account_filter: Account filter
            instrument_filter: Instrument filter
            status_filter: Status filter ('open', 'closed', or None)
            sort_by: Sort field
            sort_order: Sort order ('ASC' or 'DESC')
            
        Returns:
            Dictionary with dashboard data
        """
        try:
            # Validate and sanitize parameters
            validation_result = self._validate_dashboard_parameters(
                page, page_size, sort_by, sort_order
            )
            
            if not validation_result['valid']:
                return {
                    'success': False,
                    'errors': validation_result['errors'],
                    'positions': [],
                    'total_count': 0,
                    'total_pages': 0
                }
            
            # Use validated parameters
            page = validation_result['page']
            page_size = validation_result['page_size']
            sort_by = validation_result['sort_by']
            sort_order = validation_result['sort_order']
            
            # Get positions from database with filtering
            positions_result = self._get_filtered_positions(
                page=page,
                page_size=page_size,
                account_filter=account_filter,
                instrument_filter=instrument_filter,
                status_filter=status_filter,
                sort_by=sort_by,
                sort_order=sort_order
            )
            
            # Get position statistics
            stats_result = self._get_position_statistics(account_filter)
            
            # Get filter options
            filter_options = self._get_filter_options()
            
            return {
                'success': True,
                'positions': positions_result['positions'],
                'total_count': positions_result['total_count'],
                'total_pages': positions_result['total_pages'],
                'current_page': page,
                'page_size': page_size,
                'statistics': stats_result,
                'filter_options': filter_options,
                'applied_filters': {
                    'account': account_filter,
                    'instrument': instrument_filter,
                    'status': status_filter,
                    'sort_by': sort_by,
                    'sort_order': sort_order
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting positions dashboard data: {e}")
            return {
                'success': False,
                'error': str(e),
                'positions': [],
                'total_count': 0,
                'total_pages': 0
            }
    
    def get_position_detail(self, position_id: int) -> Dict[str, Any]:
        """
        Get detailed information for a specific position
        
        Args:
            position_id: Position ID
            
        Returns:
            Dictionary with position details
        """
        try:
            if not self.db_service:
                raise ValueError("Database service not available")
            
            # Get position from database
            position_data = self.db_service.get_position_by_id(position_id)
            
            if not position_data:
                return {
                    'success': False,
                    'error': 'Position not found',
                    'position_id': position_id
                }
            
            # Convert to Position domain object
            position = Position.from_dict(position_data)
            
            # Get related executions
            executions = position_data.get('executions', [])
            
            # Calculate additional metrics
            additional_metrics = self._calculate_additional_metrics(position, executions)
            
            return {
                'success': True,
                'position': position.to_dict(),
                'executions': executions,
                'additional_metrics': additional_metrics
            }
            
        except Exception as e:
            logger.error(f"Error getting position detail for ID {position_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'position_id': position_id
            }
    
    def rebuild_positions(self) -> Dict[str, Any]:
        """
        Rebuild all positions from trade data
        
        Returns:
            Dictionary with rebuild results
        """
        try:
            logger.info("Starting position rebuild process")
            
            # Use position orchestrator to rebuild positions
            result = self.position_orchestrator.rebuild_all_positions()
            
            logger.info(f"Position rebuild complete: {result}")
            
            return {
                'success': True,
                'positions_created': result.get('positions_created', 0),
                'trades_processed': result.get('trades_processed', 0),
                'rebuild_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error rebuilding positions: {e}")
            return {
                'success': False,
                'error': str(e),
                'positions_created': 0,
                'trades_processed': 0
            }
    
    def delete_positions(self, position_ids: List[int]) -> Dict[str, Any]:
        """
        Delete multiple positions
        
        Args:
            position_ids: List of position IDs to delete
            
        Returns:
            Dictionary with deletion results
        """
        try:
            if not position_ids:
                return {
                    'success': False,
                    'error': 'No position IDs provided'
                }
            
            if not self.db_service:
                raise ValueError("Database service not available")
            
            deleted_count = self.db_service.delete_positions(position_ids)
            
            return {
                'success': True,
                'deleted_count': deleted_count,
                'position_ids': position_ids
            }
            
        except Exception as e:
            logger.error(f"Error deleting positions {position_ids}: {e}")
            return {
                'success': False,
                'error': str(e),
                'position_ids': position_ids
            }
    
    def validate_positions(self) -> Dict[str, Any]:
        """
        Validate position integrity
        
        Returns:
            Dictionary with validation results
        """
        try:
            # Use position orchestrator for validation
            validation_result = self.position_orchestrator.validate_position_integrity()
            
            return {
                'success': True,
                'validation_results': validation_result
            }
            
        except Exception as e:
            logger.error(f"Error validating positions: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _validate_dashboard_parameters(self, page: int, page_size: int, 
                                     sort_by: str, sort_order: str) -> Dict[str, Any]:
        """
        Validate dashboard parameters
        
        Args:
            page: Page number
            page_size: Page size
            sort_by: Sort field
            sort_order: Sort order
            
        Returns:
            Dictionary with validation results
        """
        errors = []
        
        # Validate page
        try:
            page = max(1, int(page))
        except (ValueError, TypeError):
            page = 1
        
        # Validate page_size
        allowed_page_sizes = [10, 25, 50, 100]
        try:
            page_size = int(page_size)
            if page_size not in allowed_page_sizes:
                page_size = 50
        except (ValueError, TypeError):
            page_size = 50
        
        # Validate sort_by
        allowed_sort_fields = {'entry_time', 'exit_time', 'instrument', 'total_dollars_pnl', 'account'}
        if sort_by not in allowed_sort_fields:
            sort_by = 'entry_time'
        
        # Validate sort_order
        sort_order = 'DESC' if sort_order.upper() == 'DESC' else 'ASC'
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'page': page,
            'page_size': page_size,
            'sort_by': sort_by,
            'sort_order': sort_order
        }
    
    def _get_filtered_positions(self, page: int, page_size: int,
                               account_filter: Optional[str],
                               instrument_filter: Optional[str],
                               status_filter: Optional[str],
                               sort_by: str, sort_order: str) -> Dict[str, Any]:
        """
        Get filtered positions from database
        
        Args:
            page: Page number
            page_size: Page size
            account_filter: Account filter
            instrument_filter: Instrument filter
            status_filter: Status filter
            sort_by: Sort field
            sort_order: Sort order
            
        Returns:
            Dictionary with filtered positions
        """
        if not self.db_service:
            return {
                'positions': [],
                'total_count': 0,
                'total_pages': 0
            }
        
        # Get positions from database
        positions, total_count, total_pages = self.db_service.get_positions(
            page_size=page_size,
            page=page,
            account=account_filter,
            instrument=instrument_filter,
            status=status_filter,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        return {
            'positions': positions,
            'total_count': total_count,
            'total_pages': total_pages
        }
    
    def _get_position_statistics(self, account_filter: Optional[str]) -> Dict[str, Any]:
        """
        Get position statistics
        
        Args:
            account_filter: Account filter
            
        Returns:
            Dictionary with position statistics
        """
        if not self.db_service:
            return {}
        
        return self.db_service.get_position_statistics(account=account_filter)
    
    def _get_filter_options(self) -> Dict[str, List[str]]:
        """
        Get available filter options
        
        Returns:
            Dictionary with filter options
        """
        if not self.db_service:
            return {
                'accounts': [],
                'instruments': []
            }
        
        return {
            'accounts': self.db_service.get_unique_accounts(),
            'instruments': self.db_service.get_unique_instruments()
        }
    
    def _calculate_additional_metrics(self, position: Position, 
                                    executions: List[Dict]) -> Dict[str, Any]:
        """
        Calculate additional metrics for position detail
        
        Args:
            position: Position object
            executions: List of execution dictionaries
            
        Returns:
            Dictionary with additional metrics
        """
        metrics = {}
        
        try:
            # Duration metrics
            duration_minutes = position.duration_minutes()
            if duration_minutes:
                metrics['duration_minutes'] = duration_minutes
                metrics['duration_hours'] = duration_minutes / 60
                metrics['duration_days'] = duration_minutes / (60 * 24)
            
            # Execution metrics
            metrics['total_executions'] = len(executions)
            metrics['entry_executions'] = sum(1 for ex in executions 
                                            if self._is_entry_execution(ex, position))
            metrics['exit_executions'] = sum(1 for ex in executions 
                                           if self._is_exit_execution(ex, position))
            
            # Performance metrics
            if position.total_commission > 0:
                metrics['pnl_to_commission_ratio'] = position.total_dollars_pnl / position.total_commission
            
            if position.average_entry_price > 0:
                metrics['price_change_percent'] = (
                    (position.average_exit_price - position.average_entry_price) / 
                    position.average_entry_price * 100
                ) if position.average_exit_price else 0
            
        except Exception as e:
            logger.error(f"Error calculating additional metrics: {e}")
        
        return metrics
    
    def _is_entry_execution(self, execution: Dict, position: Position) -> bool:
        """Check if execution is an entry execution"""
        side = execution.get('side_of_market', '').strip()
        
        if position.is_long():
            return side in ['Buy', 'Long']
        else:
            return side in ['Sell', 'Short']
    
    def _is_exit_execution(self, execution: Dict, position: Position) -> bool:
        """Check if execution is an exit execution"""
        side = execution.get('side_of_market', '').strip()
        
        if position.is_long():
            return side in ['Sell', 'Short']
        else:
            return side in ['Buy', 'Long']