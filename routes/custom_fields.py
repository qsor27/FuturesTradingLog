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

        # Extract options if provided
        options_data = data.pop('options', [])

        # Create custom field model
        custom_field = CustomField(**data)

        # Create field options if provided
        options = []
        if options_data:
            for option_data in options_data:
                option_data['field_id'] = None  # Will be set after field creation
                options.append(CustomFieldOption(**option_data))

        service = get_custom_fields_service()
        created_field = service.create_field(custom_field, options)

        return jsonify({
            'success': True,
            'data': created_field.dict()
        }), 201

    except ValidationError as e:
        return handle_validation_error(e)
    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/<int:field_id>', methods=['GET'])
def get_custom_field(field_id: int):
    """Get a specific custom field by ID"""
    try:
        service = get_custom_fields_service()
        field = service.get_field_by_id(field_id)

        if not field:
            return jsonify({'error': 'Custom field not found'}), 404

        return jsonify({
            'success': True,
            'data': field.dict()
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

        # Ensure field_id is set correctly
        data['field_id'] = field_id

        # Extract options if provided
        options_data = data.pop('options', None)

        # Create custom field model
        custom_field = CustomField(**data)

        # Create field options if provided
        options = None
        if options_data is not None:
            options = []
            for option_data in options_data:
                option_data['field_id'] = field_id
                options.append(CustomFieldOption(**option_data))

        service = get_custom_fields_service()
        updated_field = service.update_field(custom_field, options)

        if not updated_field:
            return jsonify({'error': 'Custom field not found'}), 404

        return jsonify({
            'success': True,
            'data': updated_field.dict()
        })

    except ValidationError as e:
        return handle_validation_error(e)
    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/<int:field_id>', methods=['DELETE'])
def delete_custom_field(field_id: int):
    """Delete a custom field"""
    try:
        service = get_custom_fields_service()
        success = service.delete_field(field_id)

        if not success:
            return jsonify({'error': 'Custom field not found'}), 404

        return jsonify({
            'success': True,
            'message': 'Custom field deleted successfully'
        })

    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/<int:field_id>/toggle-status', methods=['POST'])
def toggle_field_status(field_id: int):
    """Toggle active status of a custom field"""
    try:
        service = get_custom_fields_service()
        updated_field = service.toggle_field_status(field_id)

        if not updated_field:
            return jsonify({'error': 'Custom field not found'}), 404

        return jsonify({
            'success': True,
            'data': updated_field.dict()
        })

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
            'data': [value.dict() for value in values]
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

        data['position_id'] = position_id
        field_value = PositionCustomFieldValue(**data)

        service = get_custom_fields_service()
        saved_value = service.set_position_field_value(field_value)

        return jsonify({
            'success': True,
            'data': saved_value.dict()
        })

    except ValidationError as e:
        return handle_validation_error(e)
    except Exception as e:
        return handle_service_error(e)


@custom_fields_bp.route('/positions/<int:position_id>/values/<int:field_id>', methods=['GET'])
def get_position_field_value(position_id: int, field_id: int):
    """Get a specific custom field value for a position"""
    try:
        service = get_custom_fields_service()
        value = service.get_position_field_value(position_id, field_id)

        if not value:
            return jsonify({'error': 'Field value not found'}), 404

        return jsonify({
            'success': True,
            'data': value.dict()
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

        data['position_id'] = position_id
        data['field_id'] = field_id
        field_value = PositionCustomFieldValue(**data)

        service = get_custom_fields_service()
        updated_value = service.set_position_field_value(field_value)

        return jsonify({
            'success': True,
            'data': updated_value.dict()
        })

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