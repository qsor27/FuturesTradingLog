"""
Chart Service Interface - Contract for chart data operations
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class IChartDataService(ABC):
    """
    Interface for chart data operations
    
    Defines the contract for chart-related business operations
    """
    
    @abstractmethod
    def get_chart_data(self, instrument: str, timeframe: str = '1m', 
                      days: int = 1) -> Dict[str, Any]:
        """
        Get chart data for instrument
        
        Args:
            instrument: Trading instrument symbol
            timeframe: Chart timeframe
            days: Number of days of data
            
        Returns:
            Dictionary with chart data
        """
        pass
    
    @abstractmethod
    def get_adaptive_chart_data(self, instrument: str, timeframe: str = '1h',
                               days: int = 1) -> Dict[str, Any]:
        """
        Get chart data with automatic resolution adaptation
        
        Args:
            instrument: Trading instrument symbol
            timeframe: Requested timeframe
            days: Number of days of data
            
        Returns:
            Dictionary with adaptive chart data
        """
        pass
    
    @abstractmethod
    def get_chart_data_with_trades(self, instrument: str, timeframe: str = '1m',
                                  days: int = 1, account: Optional[str] = None) -> Dict[str, Any]:
        """
        Get chart data with trade markers
        
        Args:
            instrument: Trading instrument symbol
            timeframe: Chart timeframe
            days: Number of days of data
            account: Optional account filter
            
        Returns:
            Dictionary with chart data and trade markers
        """
        pass
    
    @abstractmethod
    def validate_chart_request(self, instrument: str, timeframe: str,
                             days: int) -> Dict[str, Any]:
        """
        Validate chart data request parameters
        
        Args:
            instrument: Trading instrument symbol
            timeframe: Chart timeframe
            days: Number of days of data
            
        Returns:
            Dictionary with validation results
        """
        pass


class IChartPerformanceService(ABC):
    """
    Interface for chart performance monitoring
    """
    
    @abstractmethod
    def track_request_performance(self, instrument: str, timeframe: str,
                                 days: int, response_time: float,
                                 candle_count: int) -> None:
        """
        Track performance metrics for chart requests
        
        Args:
            instrument: Trading instrument
            timeframe: Chart timeframe
            days: Number of days requested
            response_time: Response time in seconds
            candle_count: Number of candles returned
        """
        pass
    
    @abstractmethod
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics
        
        Returns:
            Dictionary with performance statistics
        """
        pass