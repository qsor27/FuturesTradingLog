"""
Trade Service Interface - Contract for trade management operations
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any


class ITradeService(ABC):
    """
    Interface for trade management operations
    
    Defines the contract for trade-related business operations
    """
    
    @abstractmethod
    def get_trade_detail(self, trade_id: int) -> Dict[str, Any]:
        """
        Get comprehensive trade details
        
        Args:
            trade_id: Trade ID to get details for
            
        Returns:
            Dictionary with trade details and related data
        """
        pass
    
    @abstractmethod
    def delete_trades(self, trade_ids: List[int]) -> Dict[str, Any]:
        """
        Delete multiple trades
        
        Args:
            trade_ids: List of trade IDs to delete
            
        Returns:
            Dictionary with deletion results
        """
        pass
    
    @abstractmethod
    def update_trade_notes(self, trade_id: int, notes: str = '', 
                          chart_url: str = '', validated: bool = False, 
                          reviewed: bool = False) -> Dict[str, Any]:
        """
        Update trade notes and metadata
        
        Args:
            trade_id: Trade ID to update
            notes: Trade notes
            chart_url: Chart URL
            validated: Whether trade is validated
            reviewed: Whether trade is reviewed
            
        Returns:
            Dictionary with update results
        """
        pass
    
    @abstractmethod
    def get_trade_filters(self) -> Dict[str, List[str]]:
        """
        Get available filter options for trades
        
        Returns:
            Dictionary with filter options
        """
        pass


class ITradeFilterService(ABC):
    """
    Interface for trade filtering operations
    """
    
    @abstractmethod
    def apply_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply filters to trades
        
        Args:
            filters: Dictionary with filter criteria
            
        Returns:
            Dictionary with filtered results
        """
        pass
    
    @abstractmethod
    def get_filter_statistics(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get statistics for filtered trades
        
        Args:
            filters: Dictionary with filter criteria
            
        Returns:
            Dictionary with filter statistics
        """
        pass