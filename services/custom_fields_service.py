"""
Custom Fields Service Layer

Provides business logic for custom field management including:
- Field definition CRUD operations with validation
- Position custom field values management
- Field validation and type conversion
- Analytics and reporting
- Integration with existing services
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from repositories.custom_fields_repository import CustomFieldsRepository
from models.custom_field import CustomField, CustomFieldType, CustomFieldOption, PositionCustomFieldValue
from config.container import Injectable

# Setup logging
logger = logging.getLogger(__name__)


@dataclass
class FieldValidationError:
    """Represents a field validation error"""
    field_name: str
    field_label: str
    error_type: str
    message: str


@dataclass
class CustomFieldStats:
    """Statistics for a custom field"""
    field_id: int
    field_name: str
    field_label: str
    total_positions: int
    positions_with_values: int
    usage_percentage: float
    value_distribution: List[Dict[str, Any]]


class CustomFieldsService(Injectable):
    """Service class for custom field business logic"""

    def __init__(self, custom_fields_repo: CustomFieldsRepository):
        """Initialize service with repository dependency"""
        self.repo = custom_fields_repo
        logger.info("CustomFieldsService initialized")

    # ========== FIELD DEFINITION MANAGEMENT ==========

    def create_custom_field(self, field_data: Dict[str, Any]) -> Tuple[bool, str, Optional[int]]:
        """
        Create a new custom field with business logic validation

        Returns:
            Tuple of (success, message, field_id)
        """
        try:
            # Validate field data using Pydantic model
            field_model = CustomField(**field_data)

            # Business logic validation
            validation_errors = self._validate_field_business_rules(field_model)
            if validation_errors:
                error_messages = [error.message for error in validation_errors]
                return False, "; ".join(error_messages), None

            # Check for name uniqueness
            existing_field = self.repo.get_custom_field_by_name(field_model.name)
            if existing_field:
                return False, f"Field with name '{field_model.name}' already exists", None

            # Create field in repository
            field_id = self.repo.create_custom_field(field_model.to_dict())

            logger.info(f"Created custom field: {field_model.name} (ID: {field_id})")
            return True, f"Field '{field_model.label}' created successfully", field_id

        except ValueError as e:
            logger.error(f"Validation error creating field: {e}")
            return False, f"Validation error: {str(e)}", None
        except Exception as e:
            logger.error(f"Error creating custom field: {e}")
            return False, f"Failed to create field: {str(e)}", None

    def get_custom_fields(self, active_only: bool = True,
                         include_options: bool = False) -> List[Dict[str, Any]]:
        """Get list of custom field definitions"""
        try:
            fields = self.repo.get_custom_fields(active_only=active_only,
                                               include_options=include_options)
            logger.debug(f"Retrieved {len(fields)} custom fields")
            return fields
        except Exception as e:
            logger.error(f"Error retrieving custom fields: {e}")
            return []

    def get_custom_field_by_id(self, field_id: int,
                              include_options: bool = False) -> Optional[Dict[str, Any]]:
        """Get a specific custom field by ID"""
        try:
            field = self.repo.get_custom_field_by_id(field_id, include_options=include_options)
            if field:
                logger.debug(f"Retrieved custom field: {field['name']}")
            else:
                logger.warning(f"Custom field not found: ID {field_id}")
            return field
        except Exception as e:
            logger.error(f"Error retrieving custom field {field_id}: {e}")
            return None

    def update_custom_field(self, field_id: int,
                           updates: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Update a custom field with validation

        Returns:
            Tuple of (success, message)
        """
        try:
            # Get existing field
            existing_field = self.repo.get_custom_field_by_id(field_id)
            if not existing_field:
                return False, f"Field with ID {field_id} not found"

            # Merge updates with existing data for validation
            updated_data = existing_field.copy()
            updated_data.update(updates)

            # Validate updated data
            field_model = CustomField(**updated_data)

            # Business logic validation
            validation_errors = self._validate_field_business_rules(field_model)
            if validation_errors:
                error_messages = [error.message for error in validation_errors]
                return False, "; ".join(error_messages)

            # Update in repository
            success = self.repo.update_custom_field(field_id, updates)

            if success:
                logger.info(f"Updated custom field: ID {field_id}")
                return True, "Field updated successfully"
            else:
                return False, "Failed to update field"

        except ValueError as e:
            logger.error(f"Validation error updating field {field_id}: {e}")
            return False, f"Validation error: {str(e)}"
        except Exception as e:
            logger.error(f"Error updating custom field {field_id}: {e}")
            return False, f"Failed to update field: {str(e)}"

    def delete_custom_field(self, field_id: int,
                           soft_delete: bool = True) -> Tuple[bool, str]:
        """
        Delete a custom field

        Returns:
            Tuple of (success, message)
        """
        try:
            # Check if field exists
            existing_field = self.repo.get_custom_field_by_id(field_id)
            if not existing_field:
                return False, f"Field with ID {field_id} not found"

            # Check if field has values (for business logic warning)
            if not soft_delete:
                stats = self.repo.get_custom_field_usage_stats(field_id)
                if stats.get('positions_with_values', 0) > 0:
                    return False, (
                        f"Cannot delete field '{existing_field['label']}' because it has "
                        f"{stats['positions_with_values']} position values. "
                        f"Use soft delete instead."
                    )

            # Delete field
            success = self.repo.delete_custom_field(field_id, soft_delete=soft_delete)

            if success:
                action = "deactivated" if soft_delete else "deleted"
                logger.info(f"Custom field {action}: {existing_field['name']} (ID: {field_id})")
                return True, f"Field '{existing_field['label']}' {action} successfully"
            else:
                return False, "Failed to delete field"

        except Exception as e:
            logger.error(f"Error deleting custom field {field_id}: {e}")
            return False, f"Failed to delete field: {str(e)}"

    # ========== POSITION FIELD VALUES MANAGEMENT ==========

    def set_position_field_value(self, position_id: int, field_id: int,
                                value: str) -> Tuple[bool, str]:
        """
        Set a custom field value for a position with validation

        Returns:
            Tuple of (success, message)
        """
        try:
            # Get field definition for validation
            field_def = self.repo.get_custom_field_by_id(field_id)
            if not field_def:
                return False, f"Field with ID {field_id} not found"

            if not field_def['is_active']:
                return False, f"Field '{field_def['label']}' is inactive"

            # Validate value using field definition
            field_model = CustomField(**field_def)
            if not field_model.validate_field_value(value):
                return False, f"Invalid value for field '{field_def['label']}'"

            # Set value in repository
            success = self.repo.set_position_field_value(position_id, field_id, value)

            if success:
                logger.debug(f"Set field value: position {position_id}, field {field_id}")
                return True, "Field value set successfully"
            else:
                return False, "Failed to set field value"

        except Exception as e:
            logger.error(f"Error setting field value: {e}")
            return False, f"Failed to set field value: {str(e)}"

    def get_position_field_values(self, position_id: int,
                                 active_fields_only: bool = True) -> List[Dict[str, Any]]:
        """Get all custom field values for a position"""
        try:
            values = self.repo.get_position_field_values(
                position_id,
                include_field_definitions=True
            )

            if active_fields_only:
                # Filter out inactive fields
                values = [v for v in values if v.get('field_is_active', True)]

            logger.debug(f"Retrieved {len(values)} field values for position {position_id}")
            return values

        except Exception as e:
            logger.error(f"Error retrieving field values for position {position_id}: {e}")
            return []

    def get_position_field_values_typed(self, position_id: int) -> Dict[str, Any]:
        """
        Get position field values with proper type conversion

        Returns:
            Dictionary with field names as keys and typed values
        """
        try:
            raw_values = self.get_position_field_values(position_id)
            typed_values = {}

            for value_data in raw_values:
                field_name = value_data['field_name']
                field_type = value_data['field_type']
                field_value = value_data['field_value']

                if field_value is None or field_value == '':
                    typed_values[field_name] = None
                    continue

                # Convert based on field type
                try:
                    if field_type == 'boolean':
                        typed_values[field_name] = field_value.lower() in ['true', '1']
                    elif field_type == 'number':
                        if '.' in field_value:
                            typed_values[field_name] = float(field_value)
                        else:
                            typed_values[field_name] = int(field_value)
                    elif field_type == 'date':
                        typed_values[field_name] = datetime.fromisoformat(
                            field_value.replace('Z', '+00:00')
                        )
                    else:  # text, select
                        typed_values[field_name] = field_value
                except (ValueError, AttributeError):
                    # If conversion fails, store as string
                    typed_values[field_name] = field_value

            return typed_values

        except Exception as e:
            logger.error(f"Error getting typed values for position {position_id}: {e}")
            return {}

    def bulk_set_position_field_values(self, position_id: int,
                                     field_values: Dict[int, str]) -> Tuple[bool, List[str]]:
        """
        Set multiple field values for a position

        Returns:
            Tuple of (success, error_messages)
        """
        errors = []
        success_count = 0

        for field_id, value in field_values.items():
            success, message = self.set_position_field_value(position_id, field_id, value)
            if success:
                success_count += 1
            else:
                errors.append(f"Field {field_id}: {message}")

        overall_success = len(errors) == 0
        logger.info(f"Bulk set field values: {success_count} successful, {len(errors)} errors")

        return overall_success, errors

    def delete_position_field_value(self, position_id: int,
                                   field_id: int) -> Tuple[bool, str]:
        """Delete a field value for a position"""
        try:
            success = self.repo.delete_position_field_value(position_id, field_id)

            if success:
                logger.debug(f"Deleted field value: position {position_id}, field {field_id}")
                return True, "Field value deleted successfully"
            else:
                return False, "Field value not found"

        except Exception as e:
            logger.error(f"Error deleting field value: {e}")
            return False, f"Failed to delete field value: {str(e)}"

    # ========== VALIDATION AND ANALYTICS ==========

    def validate_position_field_values(self, position_id: int) -> List[FieldValidationError]:
        """Validate all field values for a position"""
        try:
            violations = self.repo.validate_field_constraints(position_id)
            errors = []

            for violation in violations:
                error = FieldValidationError(
                    field_name=violation['field_name'],
                    field_label=violation['field_label'],
                    error_type=violation['violation_type'],
                    message=violation['message']
                )
                errors.append(error)

            return errors

        except Exception as e:
            logger.error(f"Error validating position field values: {e}")
            return []

    def get_field_statistics(self, field_id: int) -> Optional[CustomFieldStats]:
        """Get comprehensive statistics for a custom field"""
        try:
            # Get usage stats
            usage_stats = self.repo.get_custom_field_usage_stats(field_id)
            if not usage_stats:
                return None

            # Get value distribution
            distribution = self.repo.get_field_value_distribution(field_id)

            stats = CustomFieldStats(
                field_id=field_id,
                field_name=usage_stats.get('field_name', ''),
                field_label=usage_stats.get('field_label', ''),
                total_positions=usage_stats.get('total_positions', 0),
                positions_with_values=usage_stats.get('positions_with_values', 0),
                usage_percentage=usage_stats.get('usage_percentage', 0.0),
                value_distribution=distribution
            )

            return stats

        except Exception as e:
            logger.error(f"Error getting field statistics: {e}")
            return None

    def search_positions_by_field_value(self, field_id: int, value: str,
                                       limit: int = 50) -> List[Dict[str, Any]]:
        """Search positions by custom field value"""
        try:
            positions = self.repo.search_positions_by_custom_field(field_id, value, limit)
            logger.debug(f"Found {len(positions)} positions with field {field_id} = '{value}'")
            return positions

        except Exception as e:
            logger.error(f"Error searching positions by field value: {e}")
            return []

    # ========== FIELD OPTIONS MANAGEMENT (FOR SELECT FIELDS) ==========

    def create_field_option(self, field_id: int, option_value: str,
                           option_label: str, sort_order: int = 0) -> Tuple[bool, str]:
        """Create a new option for a select field"""
        try:
            # Validate field exists and is select type
            field = self.repo.get_custom_field_by_id(field_id)
            if not field:
                return False, f"Field with ID {field_id} not found"

            if field['field_type'] != 'select':
                return False, "Options can only be added to select fields"

            # Create option
            option_id = self.repo.create_field_option(
                field_id, option_value, option_label, sort_order
            )

            if option_id:
                logger.info(f"Created option for field {field_id}: {option_value}")
                return True, "Option created successfully"
            else:
                return False, "Failed to create option"

        except Exception as e:
            logger.error(f"Error creating field option: {e}")
            return False, f"Failed to create option: {str(e)}"

    def get_field_options(self, field_id: int) -> List[Dict[str, Any]]:
        """Get options for a select field"""
        try:
            options = self.repo.get_field_options(field_id)
            logger.debug(f"Retrieved {len(options)} options for field {field_id}")
            return options

        except Exception as e:
            logger.error(f"Error retrieving field options: {e}")
            return []

    # ========== PRIVATE HELPER METHODS ==========

    def _validate_field_business_rules(self, field: CustomField) -> List[FieldValidationError]:
        """Validate business rules for custom fields"""
        errors = []

        # Select fields must have options
        if field.field_type == CustomFieldType.SELECT:
            if not field.validation_rules:
                errors.append(FieldValidationError(
                    field_name=field.name,
                    field_label=field.label,
                    error_type="missing_options",
                    message="Select fields must have options defined in validation rules"
                ))
            else:
                try:
                    rules = json.loads(field.validation_rules)
                    if 'options' not in rules or not rules['options']:
                        errors.append(FieldValidationError(
                            field_name=field.name,
                            field_label=field.label,
                            error_type="empty_options",
                            message="Select fields must have at least one option"
                        ))
                except json.JSONDecodeError:
                    errors.append(FieldValidationError(
                        field_name=field.name,
                        field_label=field.label,
                        error_type="invalid_validation_rules",
                        message="Invalid JSON in validation rules"
                    ))

        # Field name length restrictions
        if len(field.name) > 50:
            errors.append(FieldValidationError(
                field_name=field.name,
                field_label=field.label,
                error_type="name_too_long",
                message="Field name cannot exceed 50 characters"
            ))

        # Label length restrictions
        if len(field.label) > 100:
            errors.append(FieldValidationError(
                field_name=field.name,
                field_label=field.label,
                error_type="label_too_long",
                message="Field label cannot exceed 100 characters"
            ))

        return errors

    def get_fields_summary(self) -> Dict[str, Any]:
        """Get summary information about all custom fields"""
        try:
            fields = self.get_custom_fields(active_only=False)

            active_count = sum(1 for f in fields if f['is_active'])
            inactive_count = len(fields) - active_count

            # Count by type
            type_counts = {}
            for field in fields:
                field_type = field['field_type']
                type_counts[field_type] = type_counts.get(field_type, 0) + 1

            summary = {
                'total_fields': len(fields),
                'active_fields': active_count,
                'inactive_fields': inactive_count,
                'fields_by_type': type_counts,
                'created_at': datetime.now().isoformat()
            }

            return summary

        except Exception as e:
            logger.error(f"Error getting fields summary: {e}")
            return {
                'total_fields': 0,
                'active_fields': 0,
                'inactive_fields': 0,
                'fields_by_type': {},
                'error': str(e)
            }