"""
Position Data Model

Type-safe representation of trading positions with validation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, validator, root_validator


class PositionSide(str, Enum):
    """Valid position sides"""
    LONG = "Long"
    SHORT = "Short"


class PositionStatus(str, Enum):
    """Valid position statuses"""
    OPEN = "Open"
    CLOSED = "Closed"
    PARTIAL = "Partial"


class Position(BaseModel):
    """
    Validated position record built from executions.
    
    Represents a complete trading position with entry/exit details.
    """
    
    # Core position fields
    id: str = Field(..., description="Unique position ID")
    account: str = Field(..., min_length=1, description="Trading account name")
    instrument: str = Field(..., min_length=1, description="Instrument symbol")
    side: PositionSide = Field(..., description="Long or Short position")
    status: PositionStatus = Field(..., description="Position status")
    
    # Quantity and pricing
    quantity: int = Field(..., gt=0, description="Position size in contracts")
    entry_price: Decimal = Field(..., gt=0, description="Average entry price")
    exit_price: Optional[Decimal] = Field(None, gt=0, description="Average exit price")
    
    # Timing
    entry_time: datetime = Field(..., description="First entry timestamp")
    exit_time: Optional[datetime] = Field(None, description="Final exit timestamp")
    
    # P&L calculation
    points_pnl: Optional[Decimal] = Field(None, description="P&L in points")
    dollar_pnl: Optional[Decimal] = Field(None, description="P&L in dollars")
    commission: Decimal = Field(..., ge=0, description="Total commission")
    
    # Execution tracking
    entry_executions: List[str] = Field(default_factory=list, description="Entry execution IDs")
    exit_executions: List[str] = Field(default_factory=list, description="Exit execution IDs")
    
    # Optional fields
    strategy: Optional[str] = Field(None, description="Strategy name")
    notes: Optional[str] = Field(None, description="Position notes")
    
    class Config:
        """Pydantic configuration"""
        use_enum_values = True
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "id": "pos_12345",
                "account": "Sim101",
                "instrument": "ES 03-24",
                "side": "Long",
                "status": "Closed",
                "quantity": 2,
                "entry_price": "4500.25",
                "exit_price": "4510.50",
                "entry_time": "2024-01-15T09:30:00",
                "exit_time": "2024-01-15T10:15:00",
                "points_pnl": "10.25",
                "dollar_pnl": "512.50",
                "commission": "8.64",
                "entry_executions": ["12345", "12346"],
                "exit_executions": ["12347", "12348"]
            }
        }
    
    @validator('entry_price', 'exit_price', 'points_pnl', 'dollar_pnl', 'commission', pre=True)
    def parse_decimal_fields(cls, v):
        """Convert string values to Decimal"""
        if v is None:
            return v
        if isinstance(v, str):
            cleaned = v.replace('$', '').replace(',', '').strip()
            return Decimal(cleaned) if cleaned else None
        return Decimal(str(v))
    
    @validator('quantity', pre=True)
    def parse_quantity(cls, v):
        """Ensure quantity is a positive integer"""
        if isinstance(v, str):
            return int(v.strip())
        return int(v)
    
    @validator('instrument')
    def validate_instrument(cls, v):
        """Validate instrument format"""
        if not v or len(v.strip()) == 0:
            raise ValueError('Instrument cannot be empty')
        return v.strip()
    
    @validator('account')
    def validate_account(cls, v):
        """Validate account format"""
        if not v or len(v.strip()) == 0:
            raise ValueError('Account cannot be empty')
        return v.strip()
    
    @root_validator(skip_on_failure=True)
    def validate_position_logic(cls, values):
        """Cross-field validation for position logic"""
        status = values.get('status')
        exit_price = values.get('exit_price')
        exit_time = values.get('exit_time')
        points_pnl = values.get('points_pnl')
        dollar_pnl = values.get('dollar_pnl')
        
        # Closed positions must have exit data
        if status == PositionStatus.CLOSED:
            if exit_price is None:
                raise ValueError('Closed positions must have exit_price')
            if exit_time is None:
                raise ValueError('Closed positions must have exit_time')
            if points_pnl is None:
                raise ValueError('Closed positions must have points_pnl')
            if dollar_pnl is None:
                raise ValueError('Closed positions must have dollar_pnl')
        
        # Open positions should not have exit data
        elif status == PositionStatus.OPEN:
            if exit_price is not None:
                raise ValueError('Open positions should not have exit_price')
            if exit_time is not None:
                raise ValueError('Open positions should not have exit_time')
        
        # Entry time should be before exit time
        entry_time = values.get('entry_time')
        if entry_time and exit_time and entry_time >= exit_time:
            raise ValueError('Entry time must be before exit time')
        
        return values
    
    @property
    def duration_seconds(self) -> Optional[int]:
        """Get position duration in seconds"""
        if self.entry_time and self.exit_time:
            return int((self.exit_time - self.entry_time).total_seconds())
        return None
    
    @property
    def is_profitable(self) -> Optional[bool]:
        """Check if position is profitable"""
        if self.dollar_pnl is not None:
            return self.dollar_pnl > 0
        return None
    
    @property
    def is_long(self) -> bool:
        """Check if position is long"""
        return self.side == PositionSide.LONG
    
    @property
    def is_short(self) -> bool:
        """Check if position is short"""
        return self.side == PositionSide.SHORT
    
    @property
    def is_closed(self) -> bool:
        """Check if position is closed"""
        return self.status == PositionStatus.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if position is open"""
        return self.status == PositionStatus.OPEN
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database storage"""
        return {
            'id': self.id,
            'account': self.account,
            'instrument': self.instrument,
            'side': self.side.value,
            'status': self.status.value,
            'quantity': self.quantity,
            'entry_price': float(self.entry_price),
            'exit_price': float(self.exit_price) if self.exit_price else None,
            'entry_time': self.entry_time,
            'exit_time': self.exit_time,
            'points_pnl': float(self.points_pnl) if self.points_pnl else None,
            'dollar_pnl': float(self.dollar_pnl) if self.dollar_pnl else None,
            'commission': float(self.commission),
            'entry_executions': self.entry_executions,
            'exit_executions': self.exit_executions,
            'strategy': self.strategy,
            'notes': self.notes
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Position':
        """Create Position from dictionary"""
        return cls(**data)
    
    def add_entry_execution(self, execution_id: str) -> None:
        """Add an entry execution ID to tracking"""
        if execution_id not in self.entry_executions:
            self.entry_executions.append(execution_id)
    
    def add_exit_execution(self, execution_id: str) -> None:
        """Add an exit execution ID to tracking"""
        if execution_id not in self.exit_executions:
            self.exit_executions.append(execution_id)
    
    def calculate_pnl(self, multiplier: Decimal = Decimal('1')) -> None:
        """
        Calculate P&L for closed positions.
        
        Args:
            multiplier: Instrument multiplier for dollar conversion
        """
        if self.status != PositionStatus.CLOSED or self.exit_price is None:
            return
        
        # Calculate points P&L based on position side
        if self.side == PositionSide.LONG:
            self.points_pnl = self.exit_price - self.entry_price
        else:  # SHORT
            self.points_pnl = self.entry_price - self.exit_price
        
        # Calculate dollar P&L
        self.dollar_pnl = (self.points_pnl * multiplier * self.quantity) - self.commission