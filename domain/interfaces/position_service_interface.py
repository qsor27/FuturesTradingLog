"""
Position Service Interface - Contract for position management operations
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from ..models.position import Position


class IPositionManagementService(ABC):
    """
    Interface for position management operations
    
    Defines the contract for position-related business operations
    """
    
    @abstractmethod
    def get_positions_dashboard_data(self, page: int = 1, page_size: int = 50,
                                   account_filter: Optional[str] = None,
                                   instrument_filter: Optional[str] = None,
                                   status_filter: Optional[str] = None,
                                   sort_by: str = 'entry_time',
                                   sort_order: str = 'DESC') -> Dict[str, Any]:
        """
        Get data for positions dashboard
        
        Args:
            page: Page number
            page_size: Number of positions per page
            account_filter: Account filter
            instrument_filter: Instrument filter
            status_filter: Status filter
            sort_by: Sort field
            sort_order: Sort order
            
        Returns:
            Dictionary with dashboard data
        """
        pass
    
    @abstractmethod
    def get_position_detail(self, position_id: int) -> Dict[str, Any]:
        """
        Get detailed position information
        
        Args:
            position_id: Position ID
            
        Returns:
            Dictionary with position details
        """
        pass
    
    @abstractmethod
    def rebuild_positions(self) -> Dict[str, Any]:
        """
        Rebuild all positions from trade data
        
        Returns:
            Dictionary with rebuild results
        """
        pass
    
    @abstractmethod
    def delete_positions(self, position_ids: List[int]) -> Dict[str, Any]:
        """
        Delete multiple positions
        
        Args:
            position_ids: List of position IDs to delete
            
        Returns:
            Dictionary with deletion results
        """
        pass
    
    @abstractmethod
    def validate_positions(self) -> Dict[str, Any]:
        """
        Validate position integrity
        
        Returns:
            Dictionary with validation results
        """
        pass


class IPositionEngine(ABC):
    """
    Interface for position building engine
    """
    
    @abstractmethod
    def build_positions_from_trades(self, trades_data: List[Dict]) -> List[Position]:
        """
        Build positions from trade data
        
        Args:
            trades_data: List of trade dictionaries
            
        Returns:
            List of Position objects
        """
        pass
    
    @abstractmethod
    def rebuild_positions_from_trades(self, trades_data: List[Dict]) -> Dict[str, int]:
        """
        Rebuild all positions from trade data
        
        Args:
            trades_data: List of trade dictionaries
            
        Returns:
            Dictionary with rebuild statistics
        """
        pass
    
    @abstractmethod
    def validate_position_building(self, trades_data: List[Dict]) -> Dict[str, Any]:
        """
        Validate position building process
        
        Args:
            trades_data: List of trade dictionaries
            
        Returns:
            Dictionary with validation results
        """
        pass


class IPositionOrchestrator(ABC):
    """
    Interface for position orchestration
    """
    
    @abstractmethod
    def rebuild_all_positions(self) -> Dict[str, int]:
        """
        Rebuild all positions from existing trade data
        
        Returns:
            Dictionary with rebuild statistics
        """
        pass
    
    @abstractmethod
    def validate_position_integrity(self) -> Dict[str, Any]:
        """
        Validate position integrity
        
        Returns:
            Dictionary with validation results
        """
        pass
    
    @abstractmethod
    def get_position_statistics(self, account: Optional[str] = None,
                              instrument: Optional[str] = None) -> Dict[str, Any]:
        """
        Get position statistics
        
        Args:
            account: Optional account filter
            instrument: Optional instrument filter
            
        Returns:
            Dictionary with position statistics
        """
        pass