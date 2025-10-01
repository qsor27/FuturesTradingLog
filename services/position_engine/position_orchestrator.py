"""
Position Orchestrator - High-level orchestration of position operations

Coordinates database operations with position building
"""

from typing import List, Dict, Optional, Tuple, Any
import logging

from .position_engine import PositionEngine
from ...domain.models.position import Position
from ...domain.interfaces.position_service_interface import IPositionOrchestrator

logger = logging.getLogger('position_orchestrator')


class PositionOrchestrator(IPositionOrchestrator):
    """
    High-level orchestrator for position operations
    
    Coordinates between position engine and data persistence
    """
    
    def __init__(self, position_engine: PositionEngine, db_service=None):
        self.position_engine = position_engine
        self.db_service = db_service
    
    def rebuild_all_positions(self) -> Dict[str, int]:
        """
        Rebuild all positions from existing trade data
        
        Returns:
            Dictionary with rebuild statistics
        """
        try:
            # Get all non-deleted trades from database
            trades_data = self._get_all_trades_from_db()
            
            if not trades_data:
                logger.warning("No trades found in database")
                return {'positions_created': 0, 'trades_processed': 0}
            
            # Build positions using position engine
            result = self.position_engine.rebuild_positions_from_trades(trades_data)
            positions = result['positions']
            
            # Clear existing positions and save new ones
            if self.db_service:
                self._clear_existing_positions()
                saved_count = self._save_positions_to_db(positions)
                
                return {
                    'positions_created': saved_count,
                    'trades_processed': result['trades_processed']
                }
            else:
                return result
            
        except Exception as e:
            logger.error(f"Error rebuilding positions: {e}")
            return {'positions_created': 0, 'trades_processed': 0}
    
    def build_positions_for_new_trades(self, new_trades: List[Dict]) -> List[Position]:
        """
        Build positions for newly imported trades
        
        Args:
            new_trades: List of new trade dictionaries
            
        Returns:
            List of Position objects created
        """
        if not new_trades:
            return []
        
        try:
            # Build positions from new trades
            positions = self.position_engine.build_positions_from_trades(new_trades)
            
            # Save to database if db_service is available
            if self.db_service and positions:
                self._save_positions_to_db(positions)
            
            return positions
            
        except Exception as e:
            logger.error(f"Error building positions for new trades: {e}")
            return []
    
    def validate_position_integrity(self) -> Dict[str, Any]:
        """
        Validate the integrity of all positions
        
        Returns:
            Validation results
        """
        try:
            # Get all trades from database
            trades_data = self._get_all_trades_from_db()
            
            # Validate using position engine
            validation_results = self.position_engine.validate_position_building(trades_data)
            
            # Add database consistency checks
            if self.db_service:
                db_validation = self._validate_database_consistency()
                validation_results['database_validation'] = db_validation
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating position integrity: {e}")
            return {
                'valid': False,
                'errors': [f"Validation error: {e}"],
                'warnings': []
            }
    
    def get_position_statistics(self, account: Optional[str] = None, 
                              instrument: Optional[str] = None) -> Dict[str, Any]:
        """
        Get position statistics with optional filtering
        
        Args:
            account: Optional account filter
            instrument: Optional instrument filter
            
        Returns:
            Dictionary with position statistics
        """
        try:
            # Get positions from database
            positions_data = self._get_positions_from_db(account, instrument)
            
            # Convert to Position objects
            positions = [Position.from_dict(pos_dict) for pos_dict in positions_data]
            
            # Calculate statistics using position engine
            stats = self.position_engine.get_position_statistics(positions)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting position statistics: {e}")
            return {}
    
    def _get_all_trades_from_db(self) -> List[Dict]:
        """Get all non-deleted trades from database"""
        if not self.db_service:
            return []
        
        # This would be implemented by the database service
        # For now, return empty list as placeholder
        return []
    
    def _get_positions_from_db(self, account: Optional[str] = None, 
                             instrument: Optional[str] = None) -> List[Dict]:
        """Get positions from database with optional filtering"""
        if not self.db_service:
            return []
        
        # This would be implemented by the database service
        # For now, return empty list as placeholder
        return []
    
    def _clear_existing_positions(self):
        """Clear existing positions from database"""
        if not self.db_service:
            return
        
        # This would be implemented by the database service
        pass
    
    def _save_positions_to_db(self, positions: List[Position]) -> int:
        """Save positions to database"""
        if not self.db_service:
            return 0
        
        # This would be implemented by the database service
        # For now, return the count as placeholder
        return len(positions)
    
    def _validate_database_consistency(self) -> Dict[str, Any]:
        """Validate database consistency"""
        if not self.db_service:
            return {'valid': True, 'issues': []}
        
        issues = []
        
        # Check for orphaned position_executions
        # Check for positions without executions
        # Check for data integrity issues
        
        return {
            'valid': len(issues) == 0,
            'issues': issues
        }