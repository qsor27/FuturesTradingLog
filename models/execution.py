"""
Execution Data Model

Type-safe representation of NinjaTrader executions with validation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field, validator, root_validator


class ExecutionAction(str, Enum):
    """Valid execution actions"""
    BUY = "Buy"
    SELL = "Sell"


class ExecutionType(str, Enum):
    """Valid execution types"""
    ENTRY = "Entry"
    EXIT = "Exit"


class Execution(BaseModel):
    """
    Validated execution record from NinjaTrader.
    
    Provides type safety and validation for all execution data.
    """
    
    # Core execution fields
    id: str = Field(..., description="Unique execution ID")
    account: str = Field(..., min_length=1, description="Trading account name")
    instrument: str = Field(..., min_length=1, description="Instrument symbol")
    timestamp: datetime = Field(..., description="Execution timestamp")
    action: ExecutionAction = Field(..., description="Buy or Sell action")
    execution_type: ExecutionType = Field(..., description="Entry or Exit type")
    quantity: int = Field(..., gt=0, description="Number of contracts")
    price: Decimal = Field(..., gt=0, description="Execution price")
    commission: Decimal = Field(..., ge=0, description="Commission paid")
    
    # Optional fields
    order_id: Optional[str] = Field(None, description="Order ID if available")
    strategy: Optional[str] = Field(None, description="Strategy name if available")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    class Config:
        """Pydantic configuration"""
        # Use enum values for serialization
        use_enum_values = True
        # Allow arbitrary precision for Decimal fields
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat()
        }
        # Example data for documentation
        schema_extra = {
            "example": {
                "id": "12345",
                "account": "Sim101",
                "instrument": "ES 03-24",
                "timestamp": "2024-01-15T09:30:00",
                "action": "Buy",
                "execution_type": "Entry",
                "quantity": 1,
                "price": "4500.25",
                "commission": "4.32"
            }
        }
    
    @validator('price', 'commission', pre=True)
    def parse_decimal_fields(cls, v):
        """Convert string values to Decimal, handling currency symbols"""
        if isinstance(v, str):
            # Remove currency symbols and convert to Decimal
            cleaned = v.replace('$', '').replace(',', '').strip()
            return Decimal(cleaned)
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
    def validate_execution_logic(cls, values):
        """Cross-field validation for execution logic"""
        action = values.get('action')
        execution_type = values.get('execution_type')
        
        # Add any business logic validation here
        # For example: certain combinations of action/type that are invalid
        
        return values
    
    @property
    def signed_quantity(self) -> int:
        """
        Get signed quantity based on action.
        
        Returns:
            Positive for Buy, negative for Sell
        """
        return self.quantity if self.action == ExecutionAction.BUY else -self.quantity
    
    @property
    def is_opening(self) -> bool:
        """Check if this is an opening execution"""
        return self.execution_type == ExecutionType.ENTRY
    
    @property
    def is_closing(self) -> bool:
        """Check if this is a closing execution"""
        return self.execution_type == ExecutionType.EXIT
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database storage"""
        return {
            'id': self.id,
            'account': self.account,
            'instrument': self.instrument,
            'timestamp': self.timestamp,
            'action': self.action.value,
            'execution_type': self.execution_type.value,
            'quantity': self.quantity,
            'price': float(self.price),
            'commission': float(self.commission),
            'order_id': self.order_id,
            'strategy': self.strategy,
            'notes': self.notes
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Execution':
        """Create Execution from dictionary"""
        return cls(**data)
    
    @classmethod
    def from_ninja_row(cls, row: dict) -> 'Execution':
        """
        Create Execution from NinjaTrader CSV row.
        
        Maps NinjaTrader column names to our model fields.
        """
        return cls(
            id=str(row['ID']),
            account=str(row['Account']),
            instrument=str(row['Instrument']),
            timestamp=row['Time'] if isinstance(row['Time'], datetime) else datetime.fromisoformat(str(row['Time'])),
            action=ExecutionAction(row['Action']),
            execution_type=ExecutionType(row['E/X']),
            quantity=int(row['Quantity']),
            price=row['Price'],
            commission=row['Commission'],
            order_id=row.get('Order'),
            strategy=row.get('Strategy'),
            notes=row.get('Notes')
        )