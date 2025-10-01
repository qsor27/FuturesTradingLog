"""
Execution domain model - Raw execution data from trading platform
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class ExecutionType(Enum):
    MARKET = "Market"
    LIMIT = "Limit"
    STOP = "Stop"
    STOP_LIMIT = "StopLimit"


@dataclass
class Execution:
    """Pure domain model for a raw execution from trading platform"""
    
    # Core identification
    id: Optional[int] = None
    execution_id: str = ""
    
    # Execution characteristics
    instrument: str = ""
    account: str = ""
    side_of_market: str = ""
    quantity: int = 0
    price: float = 0.0
    
    # Timing
    execution_time: Optional[datetime] = None
    
    # Order information
    order_id: Optional[str] = None
    execution_type: ExecutionType = ExecutionType.MARKET
    
    # Fees
    commission: float = 0.0
    
    # Link to processed trade
    trade_id: Optional[int] = None
    
    # Metadata
    created_at: Optional[datetime] = None
    processed: bool = False
    
    def __post_init__(self):
        """Validate execution data after initialization"""
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        if self.price <= 0:
            raise ValueError("Price must be positive")
    
    def is_buy_action(self) -> bool:
        """Check if this is a buy action"""
        return self.side_of_market.lower() in ['buy', 'buytocover', 'long']
    
    def is_sell_action(self) -> bool:
        """Check if this is a sell action"""
        return self.side_of_market.lower() in ['sell', 'sellshort', 'short']
    
    def signed_quantity_change(self) -> int:
        """Get signed quantity change for position tracking"""
        if self.is_buy_action():
            return self.quantity
        else:
            return -self.quantity
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert execution to dictionary for serialization"""
        return {
            'id': self.id,
            'execution_id': self.execution_id,
            'instrument': self.instrument,
            'account': self.account,
            'side_of_market': self.side_of_market,
            'quantity': self.quantity,
            'price': self.price,
            'execution_time': self.execution_time.isoformat() if self.execution_time else None,
            'order_id': self.order_id,
            'execution_type': self.execution_type.value,
            'commission': self.commission,
            'trade_id': self.trade_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'processed': self.processed,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Execution':
        """Create execution from dictionary"""
        return cls(
            id=data.get('id'),
            execution_id=data.get('execution_id', ''),
            instrument=data.get('instrument', ''),
            account=data.get('account', ''),
            side_of_market=data.get('side_of_market', ''),
            quantity=data.get('quantity', 0),
            price=data.get('price', 0.0),
            execution_time=datetime.fromisoformat(data['execution_time']) if data.get('execution_time') else None,
            order_id=data.get('order_id'),
            execution_type=ExecutionType(data.get('execution_type', 'Market')),
            commission=data.get('commission', 0.0),
            trade_id=data.get('trade_id'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            processed=data.get('processed', False),
        )