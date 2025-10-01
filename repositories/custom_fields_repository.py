"""
Custom Fields repository for managing custom field definitions and values

Provides CRUD operations for:
- CustomField definitions
- CustomFieldOption for select fields
- PositionCustomFieldValue for storing field values per position
"""

import sqlite3
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

from .base_repository import BaseRepository

db_logger = logging.getLogger('database')


class CustomFieldsRepository(BaseRepository):
    """Repository for custom fields database operations"""

    def get_table_name(self) -> str:
        return 'custom_fields'

    # ========== CUSTOM FIELD CRUD OPERATIONS ==========

    def create_custom_field(self, field_data: Dict[str, Any]) -> int:
        """Create a new custom field definition"""
        query = """
            INSERT INTO custom_fields
            (name, label, field_type, description, is_required, default_value,
             sort_order, validation_rules, is_active, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            field_data['name'],
            field_data['label'],
            field_data['field_type'],
            field_data.get('description'),
            field_data.get('is_required', False),
            field_data.get('default_value'),
            field_data.get('sort_order', 0),
            field_data.get('validation_rules'),
            field_data.get('is_active', True),
            field_data.get('created_by', 1)
        )

        result = self._execute_with_monitoring(
            query, params,
            operation='insert',
            table=self.get_table_name()
        )

        field_id = result.lastrowid

        # If this is a select field with options in validation_rules, create options
        if (field_data['field_type'] == 'select' and
            field_data.get('validation_rules')):
            try:
                rules = json.loads(field_data['validation_rules'])
                if 'options' in rules:
                    self._create_field_options(field_id, rules['options'])
            except (json.JSONDecodeError, KeyError):
                pass

        db_logger.info(f"Created custom field: {field_data['name']} (ID: {field_id})")
        return field_id

    def get_custom_fields(self, active_only: bool = True,
                         include_options: bool = False) -> List[Dict[str, Any]]:
        """Get all custom field definitions"""
        conditions = []
        params = []

        if active_only:
            conditions.append("is_active = 1")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT * FROM custom_fields
            WHERE {where_clause}
            ORDER BY sort_order, label
        """

        result = self._execute_with_monitoring(
            query, tuple(params),
            operation='select',
            table=self.get_table_name()
        )

        fields = [dict(row) for row in result.fetchall()]

        # Include options for select fields if requested
        if include_options:
            for field in fields:
                if field['field_type'] == 'select':
                    field['options'] = self.get_field_options(field['id'])

        return fields

    def get_custom_field_by_id(self, field_id: int,
                              include_options: bool = False) -> Optional[Dict[str, Any]]:
        """Get a custom field by ID"""
        query = """
            SELECT * FROM custom_fields
            WHERE id = ?
        """

        result = self._execute_with_monitoring(
            query, (field_id,),
            operation='select',
            table=self.get_table_name()
        )

        row = result.fetchone()
        if not row:
            return None

        field = dict(row)

        # Include options for select fields if requested
        if include_options and field['field_type'] == 'select':
            field['options'] = self.get_field_options(field_id)

        return field

    def get_custom_field_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a custom field by name"""
        query = """
            SELECT * FROM custom_fields
            WHERE name = ? AND is_active = 1
        """

        result = self._execute_with_monitoring(
            query, (name,),
            operation='select',
            table=self.get_table_name()
        )

        row = result.fetchone()
        return dict(row) if row else None

    def update_custom_field(self, field_id: int, updates: Dict[str, Any]) -> bool:
        """Update a custom field definition"""
        # Build SET clause dynamically
        set_clauses = []
        params = []

        allowed_fields = [
            'label', 'description', 'is_required', 'default_value',
            'sort_order', 'validation_rules', 'is_active'
        ]

        for field, value in updates.items():
            if field in allowed_fields:
                set_clauses.append(f"{field} = ?")
                params.append(value)

        if not set_clauses:
            return False

        # Always update timestamp
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(field_id)

        query = f"""
            UPDATE custom_fields
            SET {', '.join(set_clauses)}
            WHERE id = ?
        """

        result = self._execute_with_monitoring(
            query, tuple(params),
            operation='update',
            table=self.get_table_name()
        )

        # If validation_rules changed for select field, update options
        if ('validation_rules' in updates and
            self.get_custom_field_by_id(field_id, include_options=False)):
            field = self.get_custom_field_by_id(field_id)
            if field and field['field_type'] == 'select':
                try:
                    rules = json.loads(updates['validation_rules'])
                    if 'options' in rules:
                        self._replace_field_options(field_id, rules['options'])
                except (json.JSONDecodeError, KeyError):
                    pass

        success = result.rowcount > 0
        if success:
            db_logger.info(f"Updated custom field ID: {field_id}")

        return success

    def delete_custom_field(self, field_id: int, soft_delete: bool = True) -> bool:
        """Delete a custom field (soft delete by default)"""
        if soft_delete:
            query = """
                UPDATE custom_fields
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """
        else:
            # Hard delete - will cascade to options and values
            query = "DELETE FROM custom_fields WHERE id = ?"

        result = self._execute_with_monitoring(
            query, (field_id,),
            operation='delete',
            table=self.get_table_name()
        )

        success = result.rowcount > 0
        if success:
            action = "soft deleted" if soft_delete else "deleted"
            db_logger.info(f"Custom field {action}: ID {field_id}")

        return success

    # ========== CUSTOM FIELD OPTIONS CRUD OPERATIONS ==========

    def _create_field_options(self, field_id: int, options: List[str]) -> None:
        """Create options for a select field"""
        for i, option in enumerate(options):
            self.create_field_option(field_id, option, option.capitalize(), i)

    def _replace_field_options(self, field_id: int, options: List[str]) -> None:
        """Replace all options for a select field"""
        # Delete existing options
        self._execute_with_monitoring(
            "DELETE FROM custom_field_options WHERE custom_field_id = ?",
            (field_id,),
            operation='delete',
            table='custom_field_options'
        )

        # Create new options
        self._create_field_options(field_id, options)

    def create_field_option(self, field_id: int, option_value: str,
                           option_label: str, sort_order: int = 0) -> int:
        """Create a new option for a select field"""
        query = """
            INSERT INTO custom_field_options
            (custom_field_id, option_value, option_label, sort_order)
            VALUES (?, ?, ?, ?)
        """

        result = self._execute_with_monitoring(
            query, (field_id, option_value, option_label, sort_order),
            operation='insert',
            table='custom_field_options'
        )

        return result.lastrowid

    def get_field_options(self, field_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get options for a select field"""
        conditions = ["custom_field_id = ?"]
        params = [field_id]

        if active_only:
            conditions.append("is_active = 1")

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT * FROM custom_field_options
            WHERE {where_clause}
            ORDER BY sort_order, option_label
        """

        result = self._execute_with_monitoring(
            query, tuple(params),
            operation='select',
            table='custom_field_options'
        )

        return [dict(row) for row in result.fetchall()]

    def update_field_option(self, option_id: int, updates: Dict[str, Any]) -> bool:
        """Update a field option"""
        set_clauses = []
        params = []

        allowed_fields = ['option_value', 'option_label', 'sort_order', 'is_active']

        for field, value in updates.items():
            if field in allowed_fields:
                set_clauses.append(f"{field} = ?")
                params.append(value)

        if not set_clauses:
            return False

        params.append(option_id)

        query = f"""
            UPDATE custom_field_options
            SET {', '.join(set_clauses)}
            WHERE id = ?
        """

        result = self._execute_with_monitoring(
            query, tuple(params),
            operation='update',
            table='custom_field_options'
        )

        return result.rowcount > 0

    def delete_field_option(self, option_id: int) -> bool:
        """Delete a field option"""
        query = "DELETE FROM custom_field_options WHERE id = ?"

        result = self._execute_with_monitoring(
            query, (option_id,),
            operation='delete',
            table='custom_field_options'
        )

        return result.rowcount > 0

    # ========== POSITION CUSTOM FIELD VALUES CRUD OPERATIONS ==========

    def set_position_field_value(self, position_id: int, field_id: int,
                                 value: str) -> bool:
        """Set/update a custom field value for a position"""
        # Use UPSERT (INSERT OR REPLACE) to handle both create and update
        query = """
            INSERT OR REPLACE INTO position_custom_field_values
            (position_id, custom_field_id, field_value, created_at, updated_at)
            VALUES (
                ?, ?, ?,
                COALESCE(
                    (SELECT created_at FROM position_custom_field_values
                     WHERE position_id = ? AND custom_field_id = ?),
                    CURRENT_TIMESTAMP
                ),
                CURRENT_TIMESTAMP
            )
        """

        params = (position_id, field_id, value, position_id, field_id)

        result = self._execute_with_monitoring(
            query, params,
            operation='upsert',
            table='position_custom_field_values'
        )

        success = result.rowcount > 0
        if success:
            db_logger.debug(f"Set custom field value: position {position_id}, field {field_id}")

        return success

    def get_position_field_values(self, position_id: int,
                                 include_field_definitions: bool = True) -> List[Dict[str, Any]]:
        """Get all custom field values for a position"""
        if include_field_definitions:
            query = """
                SELECT
                    pcfv.*,
                    cf.name as field_name,
                    cf.label as field_label,
                    cf.field_type,
                    cf.description as field_description,
                    cf.validation_rules
                FROM position_custom_field_values pcfv
                JOIN custom_fields cf ON pcfv.custom_field_id = cf.id
                WHERE pcfv.position_id = ? AND cf.is_active = 1
                ORDER BY cf.sort_order, cf.label
            """
        else:
            query = """
                SELECT * FROM position_custom_field_values
                WHERE position_id = ?
                ORDER BY custom_field_id
            """

        result = self._execute_with_monitoring(
            query, (position_id,),
            operation='select',
            table='position_custom_field_values'
        )

        return [dict(row) for row in result.fetchall()]

    def get_position_field_value(self, position_id: int, field_id: int) -> Optional[str]:
        """Get a specific custom field value for a position"""
        query = """
            SELECT field_value FROM position_custom_field_values
            WHERE position_id = ? AND custom_field_id = ?
        """

        result = self._execute_with_monitoring(
            query, (position_id, field_id),
            operation='select',
            table='position_custom_field_values'
        )

        row = result.fetchone()
        return row[0] if row else None

    def delete_position_field_value(self, position_id: int, field_id: int) -> bool:
        """Delete a custom field value for a position"""
        query = """
            DELETE FROM position_custom_field_values
            WHERE position_id = ? AND custom_field_id = ?
        """

        result = self._execute_with_monitoring(
            query, (position_id, field_id),
            operation='delete',
            table='position_custom_field_values'
        )

        return result.rowcount > 0

    def delete_all_position_field_values(self, position_id: int) -> bool:
        """Delete all custom field values for a position"""
        query = """
            DELETE FROM position_custom_field_values
            WHERE position_id = ?
        """

        result = self._execute_with_monitoring(
            query, (position_id,),
            operation='delete',
            table='position_custom_field_values'
        )

        return result.rowcount > 0

    def bulk_set_position_field_values(self, position_id: int,
                                      field_values: Dict[int, str]) -> bool:
        """Set multiple custom field values for a position in one transaction"""
        if not field_values:
            return True

        success = True
        for field_id, value in field_values.items():
            if not self.set_position_field_value(position_id, field_id, value):
                success = False

        return success

    # ========== UTILITY AND ANALYTICS OPERATIONS ==========

    def get_custom_field_usage_stats(self, field_id: int) -> Dict[str, Any]:
        """Get usage statistics for a custom field"""
        query = """
            SELECT
                COUNT(*) as total_positions,
                COUNT(CASE WHEN field_value IS NOT NULL AND field_value != ''
                          THEN 1 END) as positions_with_values,
                cf.name as field_name,
                cf.label as field_label
            FROM custom_fields cf
            LEFT JOIN position_custom_field_values pcfv ON cf.id = pcfv.custom_field_id
            WHERE cf.id = ?
            GROUP BY cf.id, cf.name, cf.label
        """

        result = self._execute_with_monitoring(
            query, (field_id,),
            operation='select',
            table='custom_fields'
        )

        row = result.fetchone()
        if not row:
            return {}

        stats = dict(row)
        stats['usage_percentage'] = (
            (stats['positions_with_values'] / stats['total_positions']) * 100
            if stats['total_positions'] > 0 else 0
        )

        return stats

    def get_field_value_distribution(self, field_id: int) -> List[Dict[str, Any]]:
        """Get value distribution for a custom field"""
        query = """
            SELECT
                field_value,
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
            FROM position_custom_field_values
            WHERE custom_field_id = ? AND field_value IS NOT NULL
            GROUP BY field_value
            ORDER BY count DESC
        """

        result = self._execute_with_monitoring(
            query, (field_id,),
            operation='select',
            table='position_custom_field_values'
        )

        return [dict(row) for row in result.fetchall()]

    def search_positions_by_custom_field(self, field_id: int, value: str,
                                        limit: int = 50) -> List[Dict[str, Any]]:
        """Search positions by custom field value"""
        query = """
            SELECT DISTINCT p.*
            FROM positions p
            JOIN position_custom_field_values pcfv ON p.id = pcfv.position_id
            WHERE pcfv.custom_field_id = ?
              AND pcfv.field_value = ?
              AND p.deleted = 0
            ORDER BY p.entry_time DESC
            LIMIT ?
        """

        result = self._execute_with_monitoring(
            query, (field_id, value, limit),
            operation='select',
            table='positions'
        )

        return [dict(row) for row in result.fetchall()]

    def validate_field_constraints(self, position_id: int) -> List[Dict[str, Any]]:
        """Validate all custom field constraints for a position"""
        query = """
            SELECT
                cf.name,
                cf.label,
                cf.is_required,
                cf.field_type,
                cf.validation_rules,
                pcfv.field_value
            FROM custom_fields cf
            LEFT JOIN position_custom_field_values pcfv
                ON cf.id = pcfv.custom_field_id AND pcfv.position_id = ?
            WHERE cf.is_active = 1
        """

        result = self._execute_with_monitoring(
            query, (position_id,),
            operation='select',
            table='custom_fields'
        )

        violations = []
        for row in result.fetchall():
            field_data = dict(row)

            # Check required field constraint
            if (field_data['is_required'] and
                (not field_data['field_value'] or field_data['field_value'].strip() == '')):
                violations.append({
                    'field_name': field_data['name'],
                    'field_label': field_data['label'],
                    'violation_type': 'required_field_missing',
                    'message': f"Required field '{field_data['label']}' is missing"
                })

            # Additional validation based on field type and rules can be added here

        return violations