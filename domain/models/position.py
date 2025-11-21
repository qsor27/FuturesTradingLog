"""
Position domain model - Core position entity
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class PositionType(Enum):
    LONG = "Long"
    SHORT = "Short"


class PositionStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass
class Position:
    """Pure domain model for a trading position"""

    # Core identification
    id: Optional[int] = None
    instrument: str = ""
    account: str = ""

    # Position characteristics
    position_type: PositionType = PositionType.LONG
    position_status: PositionStatus = PositionStatus.OPEN

    # Timing
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None

    # Quantities
    total_quantity: int = 0
    max_quantity: int = 0

    # Pricing
    average_entry_price: float = 0.0
    average_exit_price: Optional[float] = None

    # P&L
    total_points_pnl: float = 0.0
    total_dollars_pnl: float = 0.0
    total_commission: float = 0.0

    # Metrics
    risk_reward_ratio: float = 0.0
    execution_count: int = 0

    # Integrity tracking
    last_validated_at: Optional[datetime] = None
    validation_status: str = "not_validated"  # not_validated, passed, failed, error
    integrity_score: float = 0.0  # 0.0 to 100.0

    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate position data after initialization"""
        if self.total_quantity < 0:
            raise ValueError("Total quantity cannot be negative")
        
        if self.max_quantity < self.total_quantity:
            self.max_quantity = self.total_quantity
        
        if self.average_entry_price < 0:
            raise ValueError("Average entry price cannot be negative")
    
    def is_open(self) -> bool:
        """Check if position is open"""
        return self.position_status == PositionStatus.OPEN
    
    def is_closed(self) -> bool:
        """Check if position is closed"""
        return self.position_status == PositionStatus.CLOSED
    
    def is_long(self) -> bool:
        """Check if position is long"""
        return self.position_type == PositionType.LONG
    
    def is_short(self) -> bool:
        """Check if position is short"""
        return self.position_type == PositionType.SHORT
    
    def is_profitable(self) -> bool:
        """Check if position is profitable"""
        return self.total_dollars_pnl > 0
    
    def duration_minutes(self) -> Optional[int]:
        """Get position duration in minutes"""
        if not self.entry_time:
            return None

        end_time = self.exit_time or datetime.now()
        duration = end_time - self.entry_time
        return int(duration.total_seconds() / 60)

    def validate_state(self) -> Dict[str, Any]:
        """
        Validate position state for consistency and data integrity.

        Returns:
            Dictionary with validation results:
            {
                'is_valid': bool,
                'errors': List[str],
                'warnings': List[str],
                'integrity_score': float (0-100)
            }
        """
        errors = []
        warnings = []

        # Check 1: Open position should not have exit_time
        if self.position_status == PositionStatus.OPEN and self.exit_time is not None:
            errors.append(f"Open position {self.id} has exit_time set")

        # Check 2: Closed position should have exit_time
        if self.position_status == PositionStatus.CLOSED and self.exit_time is None:
            errors.append(f"Closed position {self.id} missing exit_time")

        # Check 3: Average entry price should not be zero for closed positions
        if self.position_status == PositionStatus.CLOSED and self.average_entry_price == 0.0:
            errors.append(f"Closed position {self.id} has zero average_entry_price")

        # Check 4: Average exit price should be set for closed positions
        if self.position_status == PositionStatus.CLOSED and self.average_exit_price is None:
            warnings.append(f"Closed position {self.id} missing average_exit_price")

        # Check 5: Entry time should always be set
        if self.entry_time is None:
            errors.append(f"Position {self.id} missing entry_time")

        # Check 6: Exit time should be after entry time
        if self.entry_time and self.exit_time:
            if self.exit_time < self.entry_time:
                errors.append(f"Position {self.id} has exit_time before entry_time")

        # Check 7: Quantity should be positive
        if self.total_quantity <= 0:
            errors.append(f"Position {self.id} has non-positive total_quantity")

        # Check 8: Max quantity should be >= total quantity
        if self.max_quantity < self.total_quantity:
            warnings.append(f"Position {self.id} has max_quantity < total_quantity")

        # Check 9: Execution count should be positive for closed positions
        if self.position_status == PositionStatus.CLOSED and self.execution_count == 0:
            warnings.append(f"Closed position {self.id} has zero execution_count")

        # Check 10: Catastrophic P&L detection (likely data corruption)
        if abs(self.total_dollars_pnl) > 1000000:  # > $1M
            errors.append(f"Position {self.id} has catastrophic P&L: ${self.total_dollars_pnl:,.2f}")

        # Check 11: Instrument and account should be set
        if not self.instrument:
            errors.append(f"Position {self.id} missing instrument")
        if not self.account:
            errors.append(f"Position {self.id} missing account")

        # Calculate integrity score (0-100)
        total_checks = 11
        failed_checks = len(errors)
        warning_checks = len(warnings)
        integrity_score = max(0.0, 100.0 - (failed_checks * 10) - (warning_checks * 2))

        is_valid = len(errors) == 0

        return {
            'is_valid': is_valid,
            'errors': errors,
            'warnings': warnings,
            'integrity_score': integrity_score
        }

    def update_validation_status(self) -> None:
        """
        Update position validation status based on current state.

        This should be called after position creation or modification.
        """
        validation_result = self.validate_state()

        self.validation_status = 'passed' if validation_result['is_valid'] else 'failed'
        self.integrity_score = validation_result['integrity_score']
        self.last_validated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary for serialization"""
        return {
            'id': self.id,
            'instrument': self.instrument,
            'account': self.account,
            'position_type': self.position_type.value,
            'position_status': self.position_status.value,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'total_quantity': self.total_quantity,
            'max_quantity': self.max_quantity,
            'average_entry_price': self.average_entry_price,
            'average_exit_price': self.average_exit_price,
            'total_points_pnl': self.total_points_pnl,
            'total_dollars_pnl': self.total_dollars_pnl,
            'total_commission': self.total_commission,
            'risk_reward_ratio': self.risk_reward_ratio,
            'execution_count': self.execution_count,
            'last_validated_at': self.last_validated_at.isoformat() if self.last_validated_at else None,
            'validation_status': self.validation_status,
            'integrity_score': self.integrity_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Position':
        """Create position from dictionary"""
        return cls(
            id=data.get('id'),
            instrument=data.get('instrument', ''),
            account=data.get('account', ''),
            position_type=PositionType(data.get('position_type', 'Long')),
            position_status=PositionStatus(data.get('position_status', 'open')),
            entry_time=datetime.fromisoformat(data['entry_time']) if data.get('entry_time') else None,
            exit_time=datetime.fromisoformat(data['exit_time']) if data.get('exit_time') else None,
            total_quantity=data.get('total_quantity', 0),
            max_quantity=data.get('max_quantity', 0),
            average_entry_price=data.get('average_entry_price', 0.0),
            average_exit_price=data.get('average_exit_price'),
            total_points_pnl=data.get('total_points_pnl', 0.0),
            total_dollars_pnl=data.get('total_dollars_pnl', 0.0),
            total_commission=data.get('total_commission', 0.0),
            risk_reward_ratio=data.get('risk_reward_ratio', 0.0),
            execution_count=data.get('execution_count', 0),
            last_validated_at=datetime.fromisoformat(data['last_validated_at']) if data.get('last_validated_at') else None,
            validation_status=data.get('validation_status', 'not_validated'),
            integrity_score=data.get('integrity_score', 0.0),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None,
        )