"""
Custom Fields API Routes

Flask blueprint providing REST API endpoints for managing custom fields
and their values on position pages.
"""

import logging
from flask import Blueprint, request, jsonify, g
from typing import Dict, Any, Optional, List
from pydantic import ValidationError

from services.custom_fields_service import CustomFieldsService
from models.custom_field import CustomField, CustomFieldOption, PositionCustomFieldValue
from scripts.database_manager import create_database_manager

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
custom_fields_bp = Blueprint('custom_fields', __name__, url_prefix='/api/custom-fields')


def get_custom_fields_service() -> CustomFieldsService:
    """Get or create custom fields service instance"""
    if not hasattr(g, 'custom_fields_service') or not hasattr(g, 'db_manager'):
        g.db_manager = create_database_manager()
        g.db_context = g.db_manager.__enter__()
        g.custom_fields_service = CustomFieldsService(g.db_context.custom_fields)
    return g.custom_fields_service


def handle_validation_error(e: ValidationError) -> tuple:
    """Handle Pydantic validation errors"""
    logger.warning(f"Validation error: {e}")
    return jsonify({
        'error': 'Validation failed',
        'details': e.errors()
    }), 400


def handle_service_error(e: Exception) -> tuple:
    """Handle service layer errors"""
    logger.error(f"Service error: {e}")
    return jsonify({
        'error': 'Internal server error',
        'message': str(e)
    }), 500


# Custom Field Management Endpoints

@custom_fields_bp.route('/', methods=['GET'])
def get_all_custom_fields():
    """Get all custom fields with their options"""
    try:
        service = get_custom_fields_service()
        fields = service.get_custom_fields()

        return jsonify({
            'success': True,
            'data': fields
        })

    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/', methods=['POST'])
def create_custom_field():
    """Create a new custom field"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Clean up empty strings - convert to None
        for key in ['default_value', 'description', 'validation_rules']:
            if key in data and data[key] == '':
                data[key] = None

        # Extract options for select fields - store in validation_rules
        options_data = data.pop('options', [])
        if options_data and data.get('field_type') == 'select':
            import json
            data['validation_rules'] = json.dumps({'options': options_data})

        service = get_custom_fields_service()
        success, message, field_id = service.create_custom_field(data)

        if success:
            # Fetch the created field to return full data
            created_field = service.get_custom_field_by_id(field_id, include_options=True)
            return jsonify({
                'success': True,
                'data': created_field,
                'message': message
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400

    except ValidationError as e:
        return handle_validation_error(e)
    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/<int:field_id>', methods=['GET'])
def get_custom_field(field_id: int):
    """Get a specific custom field by ID"""
    try:
        service = get_custom_fields_service()
        field = service.get_custom_field_by_id(field_id, include_options=True)

        if not field:
            return jsonify({'error': 'Custom field not found'}), 404

        return jsonify({
            'success': True,
            'data': field
        })

    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/<int:field_id>', methods=['PUT'])
def update_custom_field(field_id: int):
    """Update an existing custom field"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Extract options for select fields - store in validation_rules
        options_data = data.pop('options', None)
        if options_data is not None and data.get('field_type') == 'select':
            import json
            data['validation_rules'] = json.dumps({'options': options_data})

        # Remove field_id from updates if present (it's in the URL)
        data.pop('field_id', None)
        data.pop('id', None)

        service = get_custom_fields_service()
        success, message = service.update_custom_field(field_id, data)

        if success:
            updated_field = service.get_custom_field_by_id(field_id, include_options=True)
            return jsonify({
                'success': True,
                'data': updated_field,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400

    except ValidationError as e:
        return handle_validation_error(e)
    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/<int:field_id>', methods=['DELETE'])
def delete_custom_field(field_id: int):
    """Delete a custom field (soft delete by default)"""
    try:
        service = get_custom_fields_service()
        success, message = service.delete_custom_field(field_id, soft_delete=True)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400

    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/<int:field_id>/toggle-status', methods=['POST'])
def toggle_field_status(field_id: int):
    """Toggle active status of a custom field"""
    try:
        service = get_custom_fields_service()

        # Get current field status
        field = service.get_custom_field_by_id(field_id)
        if not field:
            return jsonify({'error': 'Custom field not found'}), 404

        # Toggle the is_active status
        new_status = not field.get('is_active', True)
        success, message = service.update_custom_field(field_id, {'is_active': new_status})

        if success:
            updated_field = service.get_custom_field_by_id(field_id)
            return jsonify({
                'success': True,
                'data': updated_field,
                'message': f"Field {'activated' if new_status else 'deactivated'} successfully"
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400

    except Exception as e:
        return handle_service_error(e)


# Custom Field Options Management

@custom_fields_bp.route('/<int:field_id>/options', methods=['GET'])
def get_field_options(field_id: int):
    """Get all options for a custom field"""
    try:
        service = get_custom_fields_service()
        options = service.get_field_options(field_id)

        return jsonify({
            'success': True,
            'data': [option.dict() for option in options]
        })

    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/<int:field_id>/options', methods=['POST'])
def create_field_option(field_id: int):
    """Create a new option for a custom field"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        data['field_id'] = field_id
        option = CustomFieldOption(**data)

        service = get_custom_fields_service()
        created_option = service.create_field_option(option)

        return jsonify({
            'success': True,
            'data': created_option.dict()
        }), 201

    except ValidationError as e:
        return handle_validation_error(e)
    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/options/<int:option_id>', methods=['PUT'])
def update_field_option(option_id: int):
    """Update a field option"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        data['option_id'] = option_id
        option = CustomFieldOption(**data)

        service = get_custom_fields_service()
        updated_option = service.update_field_option(option)

        if not updated_option:
            return jsonify({'error': 'Field option not found'}), 404

        return jsonify({
            'success': True,
            'data': updated_option.dict()
        })

    except ValidationError as e:
        return handle_validation_error(e)
    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/options/<int:option_id>', methods=['DELETE'])
def delete_field_option(option_id: int):
    """Delete a field option"""
    try:
        service = get_custom_fields_service()
        success = service.delete_field_option(option_id)

        if not success:
            return jsonify({'error': 'Field option not found'}), 404

        return jsonify({
            'success': True,
            'message': 'Field option deleted successfully'
        })

    except Exception as e:
        return handle_service_error(e)


# Position Custom Field Values Endpoints

@custom_fields_bp.route('/positions/<int:position_id>/values', methods=['GET'])
def get_position_field_values(position_id: int):
    """Get all custom field values for a specific position"""
    try:
        service = get_custom_fields_service()
        values = service.get_position_field_values(position_id)

        return jsonify({
            'success': True,
            'data': values  # Already a list of dicts from the service
        })

    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/positions/<int:position_id>/values', methods=['POST'])
def set_position_field_value(position_id: int):
    """Set a custom field value for a position"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        field_id = data.get('custom_field_id') or data.get('field_id')
        field_value = data.get('field_value') or data.get('value', '')

        if not field_id:
            return jsonify({'error': 'custom_field_id is required'}), 400

        service = get_custom_fields_service()
        success, message = service.set_position_field_value(position_id, field_id, field_value)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400

    except ValidationError as e:
        return handle_validation_error(e)
    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/positions/<int:position_id>/values/<int:field_id>', methods=['GET'])
def get_position_field_value(position_id: int, field_id: int):
    """Get a specific custom field value for a position"""
    try:
        service = get_custom_fields_service()
        # Get all values and filter for the specific field
        all_values = service.get_position_field_values(position_id)
        value = next((v for v in all_values if v.get('custom_field_id') == field_id), None)

        if not value:
            return jsonify({'error': 'Field value not found'}), 404

        return jsonify({
            'success': True,
            'data': value
        })

    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/positions/<int:position_id>/values/<int:field_id>', methods=['PUT'])
def update_position_field_value(position_id: int, field_id: int):
    """Update a custom field value for a position"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        field_value = data.get('field_value') or data.get('value', '')

        service = get_custom_fields_service()
        success, message = service.set_position_field_value(position_id, field_id, field_value)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400

    except ValidationError as e:
        return handle_validation_error(e)
    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/positions/<int:position_id>/values/<int:field_id>', methods=['DELETE'])
def delete_position_field_value(position_id: int, field_id: int):
    """Delete a custom field value for a position"""
    try:
        service = get_custom_fields_service()
        success = service.delete_position_field_value(position_id, field_id)

        if not success:
            return jsonify({'error': 'Field value not found'}), 404

        return jsonify({
            'success': True,
            'message': 'Field value deleted successfully'
        })

    except Exception as e:
        return handle_service_error(e)


# Analytics and Utility Endpoints

@custom_fields_bp.route('/analytics/usage', methods=['GET'])
def get_field_usage_analytics():
    """Get analytics on custom field usage"""
    try:
        service = get_custom_fields_service()
        analytics = service.get_field_usage_analytics()

        return jsonify({
            'success': True,
            'data': analytics
        })

    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/validate', methods=['POST'])
def validate_field_value():
    """Validate a field value against field constraints"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        field_id = data.get('field_id')
        value = data.get('value')

        if field_id is None or value is None:
            return jsonify({'error': 'field_id and value are required'}), 400

        service = get_custom_fields_service()
        is_valid, error_message = service.validate_field_value(field_id, value)

        return jsonify({
            'success': True,
            'valid': is_valid,
            'error_message': error_message
        })

    except Exception as e:
        return handle_service_error(e)


# Error handlers for the blueprint

@custom_fields_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@custom_fields_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405


@custom_fields_bp.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500