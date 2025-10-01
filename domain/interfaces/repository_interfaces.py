"""
Repository Interfaces - Data access contracts
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Tuple
from ..models.position import Position
from ..models.trade import Trade


class IBaseRepository(ABC):
    """
    Base repository interface with common operations
    """
    
    @abstractmethod
    def begin_transaction(self) -> None:
        """Begin database transaction"""
        pass
    
    @abstractmethod
    def commit_transaction(self) -> None:
        """Commit database transaction"""
        pass
    
    @abstractmethod
    def rollback_transaction(self) -> None:
        """Rollback database transaction"""
        pass
    
    @abstractmethod
    def get_connection_health(self) -> Dict[str, Any]:
        """Get database connection health status"""
        pass


class IPositionRepository(ABC):
    """
    Interface for position data access operations
    """
    
    @abstractmethod
    def get_by_id(self, position_id: int) -> Optional[Position]:
        """
        Get position by ID
        
        Args:
            position_id: Position ID
            
        Returns:
            Position object or None
        """
        pass
    
    @abstractmethod
    def get_all(self, page: int = 1, page_size: int = 50,
               account: Optional[str] = None,
               instrument: Optional[str] = None,
               status: Optional[str] = None,
               sort_by: str = 'entry_time',
               sort_order: str = 'DESC') -> Tuple[List[Position], int, int]:
        """
        Get positions with filtering and pagination
        
        Args:
            page: Page number
            page_size: Page size
            account: Account filter
            instrument: Instrument filter
            status: Status filter
            sort_by: Sort field
            sort_order: Sort order
            
        Returns:
            Tuple of (positions, total_count, total_pages)
        """
        pass
    
    @abstractmethod
    def create(self, position: Position) -> int:
        """
        Create new position
        
        Args:
            position: Position object to create
            
        Returns:
            Created position ID
        """
        pass
    
    @abstractmethod
    def update(self, position: Position) -> bool:
        """
        Update existing position
        
        Args:
            position: Position object to update
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def delete(self, position_id: int) -> bool:
        """
        Delete position
        
        Args:
            position_id: Position ID to delete
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def delete_multiple(self, position_ids: List[int]) -> int:
        """
        Delete multiple positions
        
        Args:
            position_ids: List of position IDs to delete
            
        Returns:
            Number of positions deleted
        """
        pass
    
    @abstractmethod
    def clear_all(self) -> bool:
        """
        Clear all positions
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_statistics(self, account: Optional[str] = None) -> Dict[str, Any]:
        """
        Get position statistics
        
        Args:
            account: Optional account filter
            
        Returns:
            Dictionary with statistics
        """
        pass


class ITradeRepository(ABC):
    """
    Interface for trade data access operations
    """
    
    @abstractmethod
    def get_by_id(self, trade_id: int) -> Optional[Trade]:
        """
        Get trade by ID
        
        Args:
            trade_id: Trade ID
            
        Returns:
            Trade object or None
        """
        pass
    
    @abstractmethod
    def get_all(self, page: int = 1, page_size: int = 50,
               account: Optional[str] = None,
               instrument: Optional[str] = None,
               deleted: bool = False) -> Tuple[List[Trade], int, int]:
        """
        Get trades with filtering and pagination
        
        Args:
            page: Page number
            page_size: Page size
            account: Account filter
            instrument: Instrument filter
            deleted: Include deleted trades
            
        Returns:
            Tuple of (trades, total_count, total_pages)
        """
        pass
    
    @abstractmethod
    def get_all_non_deleted(self) -> List[Trade]:
        """
        Get all non-deleted trades
        
        Returns:
            List of Trade objects
        """
        pass
    
    @abstractmethod
    def create(self, trade: Trade) -> int:
        """
        Create new trade
        
        Args:
            trade: Trade object to create
            
        Returns:
            Created trade ID
        """
        pass
    
    @abstractmethod
    def update(self, trade: Trade) -> bool:
        """
        Update existing trade
        
        Args:
            trade: Trade object to update
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def delete(self, trade_id: int) -> bool:
        """
        Soft delete trade
        
        Args:
            trade_id: Trade ID to delete
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def delete_multiple(self, trade_ids: List[int]) -> int:
        """
        Soft delete multiple trades
        
        Args:
            trade_ids: List of trade IDs to delete
            
        Returns:
            Number of trades deleted
        """
        pass
    
    @abstractmethod
    def get_linked_trades(self, link_group_id: str) -> List[Trade]:
        """
        Get trades linked by group ID
        
        Args:
            link_group_id: Link group ID
            
        Returns:
            List of linked trades
        """
        pass
    
    @abstractmethod
    def get_trades_by_account_instrument(self, account: str, instrument: str) -> List[Trade]:
        """
        Get trades for specific account and instrument
        
        Args:
            account: Account name
            instrument: Instrument name
            
        Returns:
            List of trades
        """
        pass


class IOHLCRepository(ABC):
    """
    Interface for OHLC data access operations
    """
    
    @abstractmethod
    def get_chart_data(self, instrument: str, timeframe: str,
                      start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Get OHLC chart data
        
        Args:
            instrument: Instrument symbol
            timeframe: Timeframe (1m, 5m, 1h, etc.)
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            
        Returns:
            List of OHLC data points
        """
        pass
    
    @abstractmethod
    def insert_ohlc_data(self, data: List[Dict[str, Any]]) -> int:
        """
        Insert OHLC data
        
        Args:
            data: List of OHLC data points
            
        Returns:
            Number of records inserted
        """
        pass
    
    @abstractmethod
    def get_available_instruments(self) -> List[str]:
        """
        Get list of available instruments
        
        Returns:
            List of instrument names
        """
        pass
    
    @abstractmethod
    def get_available_timeframes(self, instrument: str) -> List[str]:
        """
        Get available timeframes for instrument
        
        Args:
            instrument: Instrument symbol
            
        Returns:
            List of available timeframes
        """
        pass
    
    @abstractmethod
    def get_data_range(self, instrument: str, timeframe: str) -> Dict[str, Any]:
        """
        Get data range for instrument and timeframe
        
        Args:
            instrument: Instrument symbol
            timeframe: Timeframe
            
        Returns:
            Dictionary with min/max dates and record count
        """
        pass


class ISettingsRepository(ABC):
    """
    Interface for settings data access operations
    """
    
    @abstractmethod
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get setting value
        
        Args:
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value
        """
        pass
    
    @abstractmethod
    def set_setting(self, key: str, value: Any) -> bool:
        """
        Set setting value
        
        Args:
            key: Setting key
            value: Setting value
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get all settings
        
        Returns:
            Dictionary with all settings
        """
        pass
    
    @abstractmethod
    def delete_setting(self, key: str) -> bool:
        """
        Delete setting
        
        Args:
            key: Setting key to delete
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get user preferences
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with user preferences
        """
        pass
    
    @abstractmethod
    def set_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """
        Set user preferences
        
        Args:
            user_id: User ID
            preferences: User preferences dictionary
            
        Returns:
            True if successful
        """
        pass


class IMetadataRepository(ABC):
    """
    Interface for metadata operations
    """
    
    @abstractmethod
    def get_unique_accounts(self) -> List[str]:
        """
        Get unique account names
        
        Returns:
            List of unique account names
        """
        pass
    
    @abstractmethod
    def get_unique_instruments(self) -> List[str]:
        """
        Get unique instrument names
        
        Returns:
            List of unique instrument names
        """
        pass
    
    @abstractmethod
    def get_database_info(self) -> Dict[str, Any]:
        """
        Get database information
        
        Returns:
            Dictionary with database information
        """
        pass
    
    @abstractmethod
    def get_table_sizes(self) -> Dict[str, int]:
        """
        Get table sizes
        
        Returns:
            Dictionary with table names and row counts
        """
        pass