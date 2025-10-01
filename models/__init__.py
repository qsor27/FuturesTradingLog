"""
Data Models Package

Type-safe data structures using Pydantic for validation and serialization.
"""

try:
    from .execution import Execution, ExecutionAction, ExecutionType
    from .position import Position, PositionStatus, PositionSide
    from .custom_field import (
        CustomField,
        CustomFieldType,
        CustomFieldOption,
        PositionCustomFieldValue
    )
    MODELS_AVAILABLE = True

    __all__ = [
        'Execution',
        'ExecutionAction',
        'ExecutionType',
        'Position',
        'PositionStatus',
        'PositionSide',
        'CustomField',
        'CustomFieldType',
        'CustomFieldOption',
        'PositionCustomFieldValue'
    ]
except ImportError as e:
    print(f"Warning: Pydantic models not available: {e}")
    MODELS_AVAILABLE = False
    __all__ = []