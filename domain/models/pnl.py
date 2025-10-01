"""
P&L domain model - Profit and Loss calculation entity
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class PnLCalculation:
    """Pure domain model for P&L calculations"""
    
    # Core identification
    position_id: Optional[int] = None
    
    # P&L components
    points_pnl: float = 0.0
    dollars_pnl: float = 0.0
    commission: float = 0.0
    net_pnl: float = 0.0
    
    # Calculation details
    matched_quantity: int = 0
    average_entry_price: float = 0.0
    average_exit_price: float = 0.0
    multiplier: float = 1.0
    
    # Metadata
    calculation_time: Optional[datetime] = None
    method: str = "FIFO"  # FIFO, LIFO, etc.
    
    def __post_init__(self):
        """Calculate derived values after initialization"""
        self.net_pnl = self.dollars_pnl - self.commission
    
    def is_profitable(self) -> bool:
        """Check if the P&L is profitable"""
        return self.net_pnl > 0
    
    def profit_margin(self) -> float:
        """Calculate profit margin as percentage"""
        if self.average_entry_price == 0:
            return 0.0
        return (self.points_pnl / self.average_entry_price) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert P&L to dictionary for serialization"""
        return {
            'position_id': self.position_id,
            'points_pnl': self.points_pnl,
            'dollars_pnl': self.dollars_pnl,
            'commission': self.commission,
            'net_pnl': self.net_pnl,
            'matched_quantity': self.matched_quantity,
            'average_entry_price': self.average_entry_price,
            'average_exit_price': self.average_exit_price,
            'multiplier': self.multiplier,
            'calculation_time': self.calculation_time.isoformat() if self.calculation_time else None,
            'method': self.method,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PnLCalculation':
        """Create P&L calculation from dictionary"""
        return cls(
            position_id=data.get('position_id'),
            points_pnl=data.get('points_pnl', 0.0),
            dollars_pnl=data.get('dollars_pnl', 0.0),
            commission=data.get('commission', 0.0),
            net_pnl=data.get('net_pnl', 0.0),
            matched_quantity=data.get('matched_quantity', 0),
            average_entry_price=data.get('average_entry_price', 0.0),
            average_exit_price=data.get('average_exit_price', 0.0),
            multiplier=data.get('multiplier', 1.0),
            calculation_time=datetime.fromisoformat(data['calculation_time']) if data.get('calculation_time') else None,
            method=data.get('method', 'FIFO'),
        )


@dataclass
class FIFOMatch:
    """Represents a FIFO match between entry and exit"""
    
    entry_price: float
    exit_price: float
    quantity: int
    entry_time: datetime
    exit_time: datetime
    
    def calculate_pnl(self, position_type: str, multiplier: float = 1.0) -> float:
        """Calculate P&L for this match"""
        if position_type.lower() == 'long':
            points_pnl = self.exit_price - self.entry_price
        else:  # short
            points_pnl = self.entry_price - self.exit_price
        
        return points_pnl * self.quantity * multiplier
    
    def duration_minutes(self) -> int:
        """Get duration of this match in minutes"""
        duration = self.exit_time - self.entry_time
        return int(duration.total_seconds() / 60)


@dataclass
class FIFOCalculator:
    """FIFO P&L calculator for position entries and exits"""
    
    def calculate_pnl(self, entries: List[Dict], exits: List[Dict], position_type: str, multiplier: float = 1.0) -> PnLCalculation:
        """Calculate P&L using FIFO methodology"""
        if not entries or not exits:
            return PnLCalculation()
        
        # Sort by time for chronological matching
        sorted_entries = sorted(entries, key=lambda x: x.get('entry_time', ''))
        sorted_exits = sorted(exits, key=lambda x: x.get('entry_time', ''))
        
        matches = []
        total_pnl = 0.0
        matched_quantity = 0
        
        entry_idx = 0
        exit_idx = 0
        remaining_entry_qty = 0
        remaining_exit_qty = 0
        
        while entry_idx < len(sorted_entries) and exit_idx < len(sorted_exits):
            entry = sorted_entries[entry_idx]
            exit = sorted_exits[exit_idx]
            
            # Get remaining quantities
            if remaining_entry_qty == 0:
                remaining_entry_qty = int(entry.get('quantity', 0))
            if remaining_exit_qty == 0:
                remaining_exit_qty = int(exit.get('quantity', 0))
            
            # Match the smaller quantity
            match_qty = min(remaining_entry_qty, remaining_exit_qty)
            
            if match_qty > 0:
                entry_price = float(entry.get('entry_price', 0))
                exit_price = float(exit.get('exit_price', exit.get('entry_price', 0)))
                
                # Create match
                match = FIFOMatch(
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=match_qty,
                    entry_time=datetime.fromisoformat(entry.get('entry_time', '')),
                    exit_time=datetime.fromisoformat(exit.get('entry_time', ''))
                )
                
                matches.append(match)
                
                # Calculate P&L for this match
                match_pnl = match.calculate_pnl(position_type, multiplier)
                total_pnl += match_pnl
                matched_quantity += match_qty
                
                # Update remaining quantities
                remaining_entry_qty -= match_qty
                remaining_exit_qty -= match_qty
                
                # Move to next entry/exit if current one is fully matched
                if remaining_entry_qty == 0:
                    entry_idx += 1
                if remaining_exit_qty == 0:
                    exit_idx += 1
        
        # Calculate averages
        total_entry_quantity = sum(int(e.get('quantity', 0)) for e in entries)
        total_exit_quantity = sum(int(e.get('quantity', 0)) for e in exits)
        
        avg_entry_price = 0.0
        if total_entry_quantity > 0:
            weighted_entry = sum(float(e.get('entry_price', 0)) * int(e.get('quantity', 0)) for e in entries)
            avg_entry_price = weighted_entry / total_entry_quantity
        
        avg_exit_price = 0.0
        if total_exit_quantity > 0:
            weighted_exit = sum(float(e.get('exit_price', e.get('entry_price', 0))) * int(e.get('quantity', 0)) for e in exits)
            avg_exit_price = weighted_exit / total_exit_quantity
        
        return PnLCalculation(
            points_pnl=total_pnl / multiplier,  # Points P&L
            dollars_pnl=total_pnl,  # Dollar P&L
            matched_quantity=matched_quantity,
            average_entry_price=avg_entry_price,
            average_exit_price=avg_exit_price,
            multiplier=multiplier,
            calculation_time=datetime.now(),
            method="FIFO"
        )