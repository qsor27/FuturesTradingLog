from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from repositories.interfaces import TradeRecord, PositionRecord, OHLCRecord
from config.container import Injectable

class IPositionService(Injectable, ABC):
    """Interface for position service operations"""
    
    @abstractmethod
    def build_positions_from_executions(self, executions: List[Dict[str, Any]]) -> List[PositionRecord]:
        """Build position records from execution data"""
        pass
    
    @abstractmethod
    def rebuild_positions(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        """Rebuild positions from existing trades"""
        pass
    
    @abstractmethod
    def get_position_by_id(self, position_id: int) -> Optional[PositionRecord]:
        """Get a position by ID"""
        pass
    
    @abstractmethod
    def get_positions_by_instrument(self, instrument: str, start_date: Optional[datetime] = None, 
                                   end_date: Optional[datetime] = None) -> List[PositionRecord]:
        """Get positions for a specific instrument"""
        pass
    
    @abstractmethod
    def validate_positions(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        """Validate position data integrity"""
        pass
    
    @abstractmethod
    def check_position_overlaps(self, instrument: str) -> List[Dict[str, Any]]:
        """Check for position overlaps"""
        pass
    
    @abstractmethod
    def get_position_statistics(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        """Get position statistics"""
        pass

class ITradeService(Injectable, ABC):
    """Interface for trade service operations"""
    
    @abstractmethod
    def create_trade(self, trade_data: Dict[str, Any]) -> int:
        """Create a new trade"""
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
    def update_trade(self, trade_id: int, trade_data: Dict[str, Any]) -> bool:
        """Update a trade"""
        pass
    
    @abstractmethod
    def delete_trade(self, trade_id: int) -> bool:
        """Delete a trade"""
        pass
    
    @abstractmethod
    def import_executions(self, executions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Import execution data"""
        pass
    
    @abstractmethod
    def get_trade_statistics(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        """Get trade statistics"""
        pass

class IChartService(Injectable, ABC):
    """Interface for chart service operations"""
    
    @abstractmethod
    def get_chart_data(self, instrument: str, start_date: datetime, end_date: datetime,
                       resolution: str = '1m') -> Dict[str, Any]:
        """Get chart data for an instrument"""
        pass
    
    @abstractmethod
    def get_ohlc_data(self, instrument: str, start_date: datetime, end_date: datetime) -> List[OHLCRecord]:
        """Get OHLC data for charting"""
        pass
    
    @abstractmethod
    def update_chart_data(self, instrument: str, data: List[Dict[str, Any]]) -> bool:
        """Update chart data"""
        pass
    
    @abstractmethod
    def get_chart_settings(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get chart settings"""
        pass
    
    @abstractmethod
    def save_chart_settings(self, settings: Dict[str, Any], user_id: Optional[str] = None) -> bool:
        """Save chart settings"""
        pass

class IValidationService(Injectable, ABC):
    """Interface for validation service operations"""
    
    @abstractmethod
    def validate_trade_data(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate trade data"""
        pass
    
    @abstractmethod
    def validate_position_data(self, position_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate position data"""
        pass
    
    @abstractmethod
    def check_data_integrity(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        """Check overall data integrity"""
        pass
    
    @abstractmethod
    def get_validation_report(self) -> Dict[str, Any]:
        """Get comprehensive validation report"""
        pass
    
    @abstractmethod
    def fix_validation_issues(self, issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fix validation issues"""
        pass

class IAnalyticsService(Injectable, ABC):
    """Interface for analytics service operations"""
    
    @abstractmethod
    def get_performance_metrics(self, instrument: Optional[str] = None,
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get performance metrics"""
        pass
    
    @abstractmethod
    def get_daily_pnl(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get daily P&L data"""
        pass
    
    @abstractmethod
    def get_instrument_analysis(self, instrument: str) -> Dict[str, Any]:
        """Get analysis for a specific instrument"""
        pass
    
    @abstractmethod
    def get_risk_metrics(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        """Get risk metrics"""
        pass
    
    @abstractmethod
    def generate_report(self, report_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate various types of reports"""
        pass

class IUserService(Injectable, ABC):
    """Interface for user service operations"""
    
    @abstractmethod
    def create_profile(self, profile_data: Dict[str, Any]) -> int:
        """Create a new user profile"""
        pass
    
    @abstractmethod
    def get_profile(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get a user profile"""
        pass
    
    @abstractmethod
    def get_profile_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a user profile by name"""
        pass
    
    @abstractmethod
    def update_profile(self, profile_id: int, profile_data: Dict[str, Any]) -> bool:
        """Update a user profile"""
        pass
    
    @abstractmethod
    def delete_profile(self, profile_id: int) -> bool:
        """Delete a user profile"""
        pass
    
    @abstractmethod
    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """Get all user profiles"""
        pass
    
    @abstractmethod
    def get_user_settings(self, user_id: str) -> Dict[str, Any]:
        """Get user settings"""
        pass
    
    @abstractmethod
    def save_user_settings(self, user_id: str, settings: Dict[str, Any]) -> bool:
        """Save user settings"""
        pass

class IDataService(Injectable, ABC):
    """Interface for data service operations"""
    
    @abstractmethod
    def get_market_data(self, instrument: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get market data for an instrument"""
        pass
    
    @abstractmethod
    def update_market_data(self, instrument: str) -> bool:
        """Update market data for an instrument"""
        pass
    
    @abstractmethod
    def get_instrument_info(self, instrument: str) -> Dict[str, Any]:
        """Get instrument information"""
        pass
    
    @abstractmethod
    def get_available_instruments(self) -> List[str]:
        """Get list of available instruments"""
        pass
    
    @abstractmethod
    def cache_data(self, key: str, data: Any, ttl: int = 3600) -> bool:
        """Cache data with TTL"""
        pass
    
    @abstractmethod
    def get_cached_data(self, key: str) -> Any:
        """Get cached data"""
        pass
    
    @abstractmethod
    def clear_cache(self, pattern: Optional[str] = None) -> bool:
        """Clear cache"""
        pass

class INotificationService(Injectable, ABC):
    """Interface for notification service operations"""
    
    @abstractmethod
    def send_notification(self, notification_type: str, message: str, 
                         metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send a notification"""
        pass
    
    @abstractmethod
    def get_notifications(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get notifications"""
        pass
    
    @abstractmethod
    def mark_notification_read(self, notification_id: int) -> bool:
        """Mark notification as read"""
        pass
    
    @abstractmethod
    def subscribe_to_alerts(self, user_id: str, alert_types: List[str]) -> bool:
        """Subscribe to alert types"""
        pass
    
    @abstractmethod
    def unsubscribe_from_alerts(self, user_id: str, alert_types: List[str]) -> bool:
        """Unsubscribe from alert types"""
        pass