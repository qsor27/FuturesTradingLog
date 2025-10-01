"""
Trade domain model - Core trade execution entity
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class MarketSide(Enum):
    BUY = "Buy"
    SELL = "Sell"
    BUY_TO_COVER = "BuyToCover"
    SELL_SHORT = "SellShort"
    LONG = "Long"
    SHORT = "Short"


@dataclass
class Trade:
    """Pure domain model for a trade execution"""
    
    # Core identification
    id: Optional[int] = None
    entry_execution_id: str = ""
    exit_execution_id: Optional[str] = None
    
    # Trade characteristics
    instrument: str = ""
    account: str = ""
    side_of_market: MarketSide = MarketSide.BUY
    quantity: int = 0
    
    # Pricing
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    
    # Timing
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    
    # P&L
    points_gain_loss: float = 0.0
    dollars_gain_loss: float = 0.0
    commission: float = 0.0
    
    # Link grouping for related trades
    link_group_id: Optional[str] = None
    
    # Metadata
    deleted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate trade data after initialization"""
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        if self.entry_price <= 0:
            raise ValueError("Entry price must be positive")
        
        if self.exit_price is not None and self.exit_price <= 0:
            raise ValueError("Exit price must be positive")
    
    def is_completed(self) -> bool:
        """Check if trade is completed (has exit data)"""
        return (self.exit_price is not None and 
                self.exit_time is not None and 
                self.exit_execution_id is not None)
    
    def is_buy_action(self) -> bool:
        """Check if this is a buy action"""
        return self.side_of_market in [MarketSide.BUY, MarketSide.BUY_TO_COVER, MarketSide.LONG]
    
    def is_sell_action(self) -> bool:
        """Check if this is a sell action"""
        return self.side_of_market in [MarketSide.SELL, MarketSide.SELL_SHORT, MarketSide.SHORT]
    
    def signed_quantity_change(self) -> int:
        """Get signed quantity change for position tracking"""
        if self.is_buy_action():
            return self.quantity
        else:
            return -self.quantity
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trade to dictionary for serialization"""
        return {
            'id': self.id,
            'entry_execution_id': self.entry_execution_id,
            'exit_execution_id': self.exit_execution_id,
            'instrument': self.instrument,
            'account': self.account,
            'side_of_market': self.side_of_market.value,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'points_gain_loss': self.points_gain_loss,
            'dollars_gain_loss': self.dollars_gain_loss,
            'commission': self.commission,
            'link_group_id': self.link_group_id,
            'deleted': self.deleted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Trade':
        """Create trade from dictionary"""
        return cls(
            id=data.get('id'),
            entry_execution_id=data.get('entry_execution_id', ''),
            exit_execution_id=data.get('exit_execution_id'),
            instrument=data.get('instrument', ''),
            account=data.get('account', ''),
            side_of_market=MarketSide(data.get('side_of_market', 'Buy')),
            quantity=data.get('quantity', 0),
            entry_price=data.get('entry_price', 0.0),
            exit_price=data.get('exit_price'),
            entry_time=datetime.fromisoformat(data['entry_time']) if data.get('entry_time') else None,
            exit_time=datetime.fromisoformat(data['exit_time']) if data.get('exit_time') else None,
            points_gain_loss=data.get('points_gain_loss', 0.0),
            dollars_gain_loss=data.get('dollars_gain_loss', 0.0),
            commission=data.get('commission', 0.0),
            link_group_id=data.get('link_group_id'),
            deleted=data.get('deleted', False),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None,
        )