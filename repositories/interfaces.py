from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
from config.container import Injectable

@dataclass
class TradeRecord:
    """Data class for trade records"""
    id: Optional[int] = None
    timestamp: Optional[datetime] = None
    instrument: Optional[str] = None
    quantity: Optional[int] = None
    price: Optional[float] = None
    side: Optional[str] = None
    commission: Optional[float] = None
    realized_pnl: Optional[float] = None
    link_group_id: Optional[str] = None
    
@dataclass
class PositionRecord:
    """Data class for position records"""
    id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    instrument: Optional[str] = None
    side: Optional[str] = None
    quantity: Optional[int] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    commission: Optional[float] = None
    link_group_id: Optional[str] = None
    mae: Optional[float] = None
    mfe: Optional[float] = None

@dataclass
class OHLCRecord:
    """Data class for OHLC records"""
    id: Optional[int] = None
    timestamp: Optional[datetime] = None
    instrument: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None

class ITradeRepository(Injectable, ABC):
    """Interface for trade data access"""
    
    @abstractmethod
    def create_trade(self, trade: TradeRecord) -> int:
        """Create a new trade record"""
        pass
    
    @abstractmethod
    def get_trade(self, trade_id: int) -> Optional[TradeRecord]:
        """Get a trade by ID"""
        pass
    
    @abstractmethod
    def get_trades_by_instrument(self, instrument: str, start_date: Optional[datetime] = None, 
                                end_date: Optional[datetime] = None) -> List[TradeRecord]:
        """Get trades for a specific instrument"""
        pass
    
    @abstractmethod
    def get_trades_by_link_group(self, link_group_id: str) -> List[TradeRecord]:
        """Get trades by link group ID"""
        pass
    
    @abstractmethod
    def update_trade(self, trade: TradeRecord) -> bool:
        """Update an existing trade record"""
        pass
    
    @abstractmethod
    def delete_trade(self, trade_id: int) -> bool:
        """Delete a trade record"""
        pass
    
    @abstractmethod
    def get_all_trades(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[TradeRecord]:
        """Get all trades with optional pagination"""
        pass

class IPositionRepository(Injectable, ABC):
    """Interface for position data access"""
    
    @abstractmethod
    def create_position(self, position: PositionRecord) -> int:
        """Create a new position record"""
        pass
    
    @abstractmethod
    def get_position(self, position_id: int) -> Optional[PositionRecord]:
        """Get a position by ID"""
        pass
    
    @abstractmethod
    def get_positions_by_instrument(self, instrument: str, start_date: Optional[datetime] = None, 
                                   end_date: Optional[datetime] = None) -> List[PositionRecord]:
        """Get positions for a specific instrument"""
        pass
    
    @abstractmethod
    def get_positions_by_link_group(self, link_group_id: str) -> List[PositionRecord]:
        """Get positions by link group ID"""
        pass
    
    @abstractmethod
    def update_position(self, position: PositionRecord) -> bool:
        """Update an existing position record"""
        pass
    
    @abstractmethod
    def delete_position(self, position_id: int) -> bool:
        """Delete a position record"""
        pass
    
    @abstractmethod
    def get_all_positions(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[PositionRecord]:
        """Get all positions with optional pagination"""
        pass
    
    @abstractmethod
    def check_position_overlaps(self, instrument: str) -> List[Dict[str, Any]]:
        """Check for position overlaps for validation"""
        pass

class IOHLCRepository(Injectable, ABC):
    """Interface for OHLC data access"""
    
    @abstractmethod
    def create_ohlc(self, ohlc: OHLCRecord) -> int:
        """Create a new OHLC record"""
        pass
    
    @abstractmethod
    def get_ohlc_data(self, instrument: str, start_date: datetime, end_date: datetime, 
                      resolution: str = '1m') -> List[OHLCRecord]:
        """Get OHLC data for charting"""
        pass
    
    @abstractmethod
    def update_ohlc(self, ohlc: OHLCRecord) -> bool:
        """Update an existing OHLC record"""
        pass
    
    @abstractmethod
    def delete_ohlc(self, ohlc_id: int) -> bool:
        """Delete an OHLC record"""
        pass
    
    @abstractmethod
    def get_latest_ohlc(self, instrument: str) -> Optional[OHLCRecord]:
        """Get the latest OHLC record for an instrument"""
        pass

class ISettingsRepository(Injectable, ABC):
    """Interface for settings data access"""
    
    @abstractmethod
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        pass
    
    @abstractmethod
    def set_setting(self, key: str, value: Any) -> bool:
        """Set a setting value"""
        pass
    
    @abstractmethod
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings"""
        pass
    
    @abstractmethod
    def delete_setting(self, key: str) -> bool:
        """Delete a setting"""
        pass

class IProfileRepository(Injectable, ABC):
    """Interface for user profile data access"""
    
    @abstractmethod
    def create_profile(self, profile_data: Dict[str, Any]) -> int:
        """Create a new profile"""
        pass
    
    @abstractmethod
    def get_profile(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get a profile by ID"""
        pass
    
    @abstractmethod
    def get_profile_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a profile by name"""
        pass
    
    @abstractmethod
    def update_profile(self, profile_id: int, profile_data: Dict[str, Any]) -> bool:
        """Update a profile"""
        pass
    
    @abstractmethod
    def delete_profile(self, profile_id: int) -> bool:
        """Delete a profile"""
        pass
    
    @abstractmethod
    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """Get all profiles"""
        pass

class IStatisticsRepository(Injectable, ABC):
    """Interface for statistics and analytics data access"""
    
    @abstractmethod
    def get_performance_metrics(self, instrument: Optional[str] = None, 
                               start_date: Optional[datetime] = None, 
                               end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get performance metrics"""
        pass
    
    @abstractmethod
    def get_trade_statistics(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        """Get trade statistics"""
        pass
    
    @abstractmethod
    def get_position_statistics(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        """Get position statistics"""
        pass
    
    @abstractmethod
    def get_daily_pnl(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get daily P&L data"""
        pass