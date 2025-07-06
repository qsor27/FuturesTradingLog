"""
Data Models Package

Type-safe data structures using Pydantic for validation and serialization.
"""

try:
    from .execution import Execution, ExecutionAction, ExecutionType
    from .position import Position, PositionStatus, PositionSide
    MODELS_AVAILABLE = True
    
    __all__ = [
        'Execution',
        'ExecutionAction', 
        'ExecutionType',
        'Position',
        'PositionStatus',
        'PositionSide'
    ]
except ImportError as e:
    print(f"Warning: Pydantic models not available: {e}")
    MODELS_AVAILABLE = False
    __all__ = []