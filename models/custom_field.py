"""
Custom Field Data Models

Type-safe representation of custom field definitions and values with validation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Union
from enum import Enum
import json

from pydantic import BaseModel, Field, field_validator, model_validator


class CustomFieldType(str, Enum):
    """Valid custom field types"""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    SELECT = "select"


class CustomField(BaseModel):
    """
    Validated custom field definition.

    Represents a user-configurable field that can be added to positions.
    """

    # Core fields
    id: Optional[int] = Field(None, description="Database ID (auto-generated)")
    name: str = Field(..., min_length=1, max_length=50, description="Unique field name")
    label: str = Field(..., min_length=1, max_length=100, description="Display label")
    field_type: CustomFieldType = Field(..., description="Field data type")
    description: Optional[str] = Field(None, max_length=500, description="Field description")

    # Configuration
    is_required: bool = Field(False, description="Whether field is required")
    default_value: Optional[str] = Field(None, description="Default field value")
    sort_order: int = Field(0, ge=0, description="Display sort order")
    validation_rules: Optional[str] = Field(None, description="JSON validation rules")

    # State management
    is_active: bool = Field(True, description="Whether field is active")
    created_by: int = Field(1, description="User who created the field")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    # Relationship data (populated when loading with options)
    options: Optional[List['CustomFieldOption']] = Field(None, description="Select field options")

    class Config:
        """Pydantic configuration"""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        json_schema_extra = {
            "example": {
                "name": "trade_reviewed",
                "label": "Trade Reviewed",
                "field_type": "boolean",
                "description": "Mark if trade has been reviewed",
                "is_required": False,
                "default_value": "false",
                "sort_order": 1,
                "validation_rules": '{"required": false}',
                "is_active": True,
                "created_by": 1
            }
        }

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate field name format"""
        if not v or len(v.strip()) == 0:
            raise ValueError('Field name cannot be empty')

        # Must be valid identifier-like (letters, numbers, underscores)
        if not all(c.isalnum() or c == '_' for c in v):
            raise ValueError('Field name must contain only letters, numbers, and underscores')

        # Cannot start with number
        if v[0].isdigit():
            raise ValueError('Field name cannot start with a number')

        return v.strip().lower()

    @field_validator('label')
    @classmethod
    def validate_label(cls, v):
        """Validate field label"""
        if not v or len(v.strip()) == 0:
            raise ValueError('Field label cannot be empty')
        return v.strip()

    @field_validator('validation_rules', mode='before')
    @classmethod
    def validate_validation_rules(cls, v):
        """Validate JSON format of validation rules"""
        if v is None or v == '':
            return None

        if isinstance(v, dict):
            v = json.dumps(v)

        if isinstance(v, str):
            try:
                json.loads(v)  # Validate JSON format
                return v
            except json.JSONDecodeError:
                raise ValueError('Validation rules must be valid JSON')

        raise ValueError('Validation rules must be JSON string or dict')

    @model_validator(mode='after')
    def validate_field_configuration(self):
        """Cross-field validation for field configuration"""
        # Validate default value format based on field type
        if self.default_value is not None and self.field_type:
            try:
                self._validate_field_value(self.field_type, self.default_value)
            except ValueError as e:
                raise ValueError(f'Invalid default value for {self.field_type} field: {e}')

        # Select fields should have options in validation rules
        if self.field_type == CustomFieldType.SELECT and self.validation_rules:
            try:
                rules = json.loads(self.validation_rules)
                if 'options' not in rules or not isinstance(rules['options'], list):
                    raise ValueError('Select fields must have options array in validation rules')
                if len(rules['options']) == 0:
                    raise ValueError('Select fields must have at least one option')
            except json.JSONDecodeError:
                raise ValueError('Invalid JSON in validation rules')

        return self

    @staticmethod
    def _validate_field_value(field_type: CustomFieldType, value: str) -> bool:
        """Validate a field value against its type"""
        if field_type == CustomFieldType.BOOLEAN:
            if value.lower() not in ['true', 'false', '1', '0']:
                raise ValueError('Boolean field must be true/false or 1/0')

        elif field_type == CustomFieldType.NUMBER:
            try:
                float(value)
            except ValueError:
                raise ValueError('Number field must be a valid number')

        elif field_type == CustomFieldType.DATE:
            try:
                datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError('Date field must be a valid ISO date string')

        # TEXT and SELECT are always valid as strings
        return True

    def get_validation_rules_dict(self) -> Dict[str, Any]:
        """Get validation rules as dictionary"""
        if not self.validation_rules:
            return {}
        try:
            return json.loads(self.validation_rules)
        except json.JSONDecodeError:
            return {}

    def validate_field_value(self, value: str) -> bool:
        """Validate a value against this field's type and rules"""
        try:
            # Type validation
            self._validate_field_value(self.field_type, value)

            # Rules validation
            rules = self.get_validation_rules_dict()

            # Required validation
            if self.is_required and (not value or value.strip() == ''):
                raise ValueError('Field is required')

            # Select field options validation
            if self.field_type == CustomFieldType.SELECT and 'options' in rules:
                if value not in rules['options']:
                    raise ValueError(f'Value must be one of: {", ".join(rules["options"])}')

            # Text length validation
            if self.field_type == CustomFieldType.TEXT and 'maxLength' in rules:
                if len(value) > rules['maxLength']:
                    raise ValueError(f'Text exceeds maximum length of {rules["maxLength"]}')

            return True

        except ValueError:
            return False

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage"""
        return {
            'id': self.id,
            'name': self.name,
            'label': self.label,
            'field_type': self.field_type.value,
            'description': self.description,
            'is_required': self.is_required,
            'default_value': self.default_value,
            'sort_order': self.sort_order,
            'validation_rules': self.validation_rules,
            'is_active': self.is_active,
            'created_by': self.created_by,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CustomField':
        """Create CustomField from dictionary"""
        return cls(**data)


class CustomFieldOption(BaseModel):
    """
    Option for select-type custom fields.

    Represents a selectable option for dropdown/select custom fields.
    """

    # Core fields
    id: Optional[int] = Field(None, description="Database ID (auto-generated)")
    custom_field_id: int = Field(..., description="Parent custom field ID")
    option_value: str = Field(..., min_length=1, max_length=100, description="Option value")
    option_label: str = Field(..., min_length=1, max_length=100, description="Display label")
    sort_order: int = Field(0, ge=0, description="Display sort order")

    # State management
    is_active: bool = Field(True, description="Whether option is active")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")

    class Config:
        """Pydantic configuration"""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        json_schema_extra = {
            "example": {
                "custom_field_id": 1,
                "option_value": "high",
                "option_label": "High Risk",
                "sort_order": 2,
                "is_active": True
            }
        }

    @field_validator('option_value')
    @classmethod
    def validate_option_value(cls, v):
        """Validate option value format"""
        if not v or len(v.strip()) == 0:
            raise ValueError('Option value cannot be empty')
        return v.strip()

    @field_validator('option_label')
    @classmethod
    def validate_option_label(cls, v):
        """Validate option label"""
        if not v or len(v.strip()) == 0:
            raise ValueError('Option label cannot be empty')
        return v.strip()

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage"""
        return {
            'id': self.id,
            'custom_field_id': self.custom_field_id,
            'option_value': self.option_value,
            'option_label': self.option_label,
            'sort_order': self.sort_order,
            'is_active': self.is_active,
            'created_at': self.created_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CustomFieldOption':
        """Create CustomFieldOption from dictionary"""
        return cls(**data)


class PositionCustomFieldValue(BaseModel):
    """
    Value of a custom field for a specific position.

    Represents the actual data stored for a custom field on a position.
    """

    # Core fields
    id: Optional[int] = Field(None, description="Database ID (auto-generated)")
    position_id: int = Field(..., description="Position ID")
    custom_field_id: int = Field(..., description="Custom field definition ID")
    field_value: Optional[str] = Field(None, description="Field value as string")

    # Timestamps
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    # Relationship data (populated when loading with field definition)
    custom_field: Optional[CustomField] = Field(None, description="Custom field definition")

    class Config:
        """Pydantic configuration"""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        json_schema_extra = {
            "example": {
                "position_id": 123,
                "custom_field_id": 1,
                "field_value": "true"
            }
        }

    @field_validator('field_value', mode='before')
    @classmethod
    def normalize_field_value(cls, v):
        """Normalize field value to string"""
        if v is None:
            return None
        if isinstance(v, bool):
            return 'true' if v else 'false'
        return str(v)

    def get_typed_value(self) -> Union[str, int, float, bool, datetime, None]:
        """Get field value converted to appropriate Python type"""
        if not self.field_value or not self.custom_field:
            return None

        field_type = self.custom_field.field_type

        try:
            if field_type == CustomFieldType.BOOLEAN:
                return self.field_value.lower() in ['true', '1']

            elif field_type == CustomFieldType.NUMBER:
                # Try int first, then float
                if '.' in self.field_value:
                    return float(self.field_value)
                else:
                    return int(self.field_value)

            elif field_type == CustomFieldType.DATE:
                return datetime.fromisoformat(self.field_value.replace('Z', '+00:00'))

            else:  # TEXT or SELECT
                return self.field_value

        except (ValueError, AttributeError):
            # If conversion fails, return as string
            return self.field_value

    def validate_value(self) -> bool:
        """Validate the field value against its custom field definition"""
        if not self.custom_field:
            return True  # Can't validate without field definition

        if self.field_value is None:
            return not self.custom_field.is_required

        return self.custom_field.validate_field_value(self.field_value)

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage"""
        return {
            'id': self.id,
            'position_id': self.position_id,
            'custom_field_id': self.custom_field_id,
            'field_value': self.field_value,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PositionCustomFieldValue':
        """Create PositionCustomFieldValue from dictionary"""
        return cls(**data)


# Update forward references
CustomField.update_forward_refs()