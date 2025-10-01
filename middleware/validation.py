"""
Validation Middleware for Custom Fields API

Provides request validation, error handling, and middleware functions
for custom fields REST API endpoints.
"""

import logging
import time
from functools import wraps
from flask import request, jsonify, g
from typing import Dict, Any, Optional, List, Callable
from pydantic import ValidationError as PydanticValidationError, BaseModel

from scripts.database_manager import create_database_manager
from services.custom_fields_service import CustomFieldsService

# Configure logging
logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base API error class"""
    def __init__(self, message: str, status_code: int = 400, details: Dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ValidationError(APIError):
    """Validation error class"""
    def __init__(self, message: str, errors: List[Dict] = None):
        super().__init__(message, 400)
        self.errors = errors or []


class NotFoundError(APIError):
    """Resource not found error"""
    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found", 404)


class ConflictError(APIError):
    """Resource conflict error"""
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message, 409)


def handle_api_errors(f):
    """Decorator to handle API errors consistently"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)

        except ValidationError as e:
            logger.warning(f"Validation error in {f.__name__}: {e.message}")
            return jsonify({
                'success': False,
                'error': 'Validation failed',
                'message': e.message,
                'errors': e.errors
            }), e.status_code

        except NotFoundError as e:
            logger.info(f"Not found error in {f.__name__}: {e.message}")
            return jsonify({
                'success': False,
                'error': 'Not found',
                'message': e.message
            }), e.status_code

        except ConflictError as e:
            logger.warning(f"Conflict error in {f.__name__}: {e.message}")
            return jsonify({
                'success': False,
                'error': 'Conflict',
                'message': e.message
            }), e.status_code

        except APIError as e:
            logger.error(f"API error in {f.__name__}: {e.message}")
            return jsonify({
                'success': False,
                'error': 'API error',
                'message': e.message,
                'details': e.details
            }), e.status_code

        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'error': 'Internal server error',
                'message': 'An unexpected error occurred'
            }), 500

    return decorated_function


def validate_json_request(required_fields: List[str] = None,
                         optional_fields: List[str] = None,
                         max_content_length: int = 1024 * 1024):  # 1MB default
    """
    Decorator to validate JSON request data

    Args:
        required_fields: List of required field names
        optional_fields: List of optional field names
        max_content_length: Maximum content length in bytes
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check content type
            if not request.is_json:
                raise ValidationError("Content-Type must be application/json")

            # Check content length
            if request.content_length and request.content_length > max_content_length:
                raise ValidationError(f"Request too large. Maximum size: {max_content_length} bytes")

            # Get JSON data
            try:
                data = request.get_json()
            except Exception as e:
                raise ValidationError(f"Invalid JSON: {str(e)}")

            if data is None:
                raise ValidationError("No JSON data provided")

            # Validate required fields
            if required_fields:
                missing_fields = []
                for field in required_fields:
                    if field not in data or data[field] is None:
                        missing_fields.append(field)

                if missing_fields:
                    raise ValidationError(
                        f"Missing required fields: {', '.join(missing_fields)}",
                        [{'field': field, 'error': 'required'} for field in missing_fields]
                    )

            # Check for unexpected fields
            if required_fields or optional_fields:
                allowed_fields = set((required_fields or []) + (optional_fields or []))
                unexpected_fields = set(data.keys()) - allowed_fields

                if unexpected_fields:
                    logger.warning(f"Unexpected fields in request: {unexpected_fields}")

            return f(*args, **kwargs)

        return decorated_function
    return decorator


def validate_pydantic_model(model_class: BaseModel):
    """
    Decorator to validate request data against a Pydantic model

    Args:
        model_class: Pydantic model class to validate against
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                data = request.get_json()
                if not data:
                    raise ValidationError("No data provided")

                # Validate with Pydantic model
                validated_data = model_class(**data)

                # Add validated data to g for use in the route
                g.validated_data = validated_data

                return f(*args, **kwargs)

            except PydanticValidationError as e:
                # Convert Pydantic ValidationError to our APIError
                errors = []
                for error in e.errors():
                    errors.append({
                        'field': '.'.join(str(x) for x in error['loc']),
                        'error': error['msg'],
                        'type': error['type']
                    })

                raise ValidationError("Validation failed", errors)

        return decorated_function
    return decorator


def validate_integer_param(param_name: str, min_value: int = None, max_value: int = None):
    """
    Decorator to validate integer URL parameters

    Args:
        param_name: Name of the parameter to validate
        min_value: Minimum allowed value
        max_value: Maximum allowed value
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if param_name in kwargs:
                value = kwargs[param_name]

                try:
                    int_value = int(value)
                    kwargs[param_name] = int_value

                    if min_value is not None and int_value < min_value:
                        raise ValidationError(f"{param_name} must be at least {min_value}")

                    if max_value is not None and int_value > max_value:
                        raise ValidationError(f"{param_name} must be at most {max_value}")

                except ValueError:
                    raise ValidationError(f"{param_name} must be a valid integer")

            return f(*args, **kwargs)

        return decorated_function
    return decorator


def require_database_connection(f):
    """
    Decorator to ensure database connection exists
    Initializes custom fields service in Flask g context
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'db_manager'):
            try:
                g.db_manager = create_database_manager()
                g.db_context = g.db_manager.__enter__()
                g.custom_fields_service = CustomFieldsService(g.db_context.custom_fields)

                # Register cleanup function
                @g.db_manager.__exit__
                def cleanup_db(exc_type, exc_val, exc_tb):
                    if hasattr(g, 'db_manager'):
                        g.db_manager.__exit__(exc_type, exc_val, exc_tb)

            except Exception as e:
                logger.error(f"Failed to initialize database connection: {e}")
                raise APIError("Database connection failed", 503)

        return f(*args, **kwargs)

    return decorated_function


def validate_custom_field_type(field_type: str) -> bool:
    """
    Validate custom field type against allowed values

    Args:
        field_type: Field type to validate

    Returns:
        bool: True if valid
    """
    allowed_types = {'text', 'number', 'date', 'boolean', 'select'}
    return field_type in allowed_types


def validate_field_value_format(field_type: str, value: Any) -> tuple[bool, str]:
    """
    Validate field value format based on field type

    Args:
        field_type: Type of the custom field
        value: Value to validate

    Returns:
        tuple: (is_valid, error_message)
    """
    if value is None:
        return True, ""  # Allow null values

    try:
        if field_type == 'text':
            if not isinstance(value, str):
                return False, "Value must be a string"
            if len(value) > 1000:  # Reasonable text limit
                return False, "Text value too long (max 1000 characters)"

        elif field_type == 'number':
            if not isinstance(value, (int, float, str)):
                return False, "Value must be a number"
            try:
                float(value)  # Test conversion
            except ValueError:
                return False, "Invalid number format"

        elif field_type == 'date':
            if not isinstance(value, str):
                return False, "Date must be a string"
            # Add more specific date validation as needed

        elif field_type == 'boolean':
            if not isinstance(value, (bool, int, str)):
                return False, "Boolean value must be true/false, 1/0, or string"

        elif field_type == 'select':
            if not isinstance(value, (str, int)):
                return False, "Select value must be string or integer"

        else:
            return False, f"Unknown field type: {field_type}"

        return True, ""

    except Exception as e:
        return False, f"Validation error: {str(e)}"


def rate_limit(max_requests: int = 100, window_seconds: int = 3600):
    """
    Simple rate limiting decorator (in-memory, for basic protection)

    Args:
        max_requests: Maximum requests allowed
        window_seconds: Time window in seconds
    """
    import time
    from collections import defaultdict, deque

    request_history = defaultdict(deque)

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            now = time.time()

            # Clean old requests
            while (request_history[client_ip] and
                   request_history[client_ip][0] < now - window_seconds):
                request_history[client_ip].popleft()

            # Check rate limit
            if len(request_history[client_ip]) >= max_requests:
                raise APIError("Rate limit exceeded", 429)

            # Add current request
            request_history[client_ip].append(now)

            return f(*args, **kwargs)

        return decorated_function
    return decorator


# Middleware for common validations

def validate_position_exists(position_id: int) -> bool:
    """
    Validate that a position exists

    Args:
        position_id: Position ID to check

    Returns:
        bool: True if position exists
    """
    # This would need to check against the positions table
    # For now, we'll assume it exists and let foreign key constraints handle it
    return True


def sanitize_html_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize HTML content in request data

    Args:
        data: Request data dictionary

    Returns:
        Dict: Sanitized data
    """
    import html

    def sanitize_value(value):
        if isinstance(value, str):
            return html.escape(value)
        elif isinstance(value, dict):
            return {k: sanitize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [sanitize_value(item) for item in value]
        return value

    return sanitize_value(data)


# Request logging middleware

def log_api_request(f):
    """Decorator to log API requests for debugging"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()

        logger.info(f"API Request: {request.method} {request.path}")
        logger.debug(f"Request args: {dict(request.args)}")
        logger.debug(f"Request data: {request.get_json() if request.is_json else 'No JSON'}")

        try:
            response = f(*args, **kwargs)
            duration = time.time() - start_time

            logger.info(f"API Response: {request.method} {request.path} - "
                       f"Status: {getattr(response, 'status_code', 'Unknown')} - "
                       f"Duration: {duration:.3f}s")

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"API Error: {request.method} {request.path} - "
                        f"Error: {str(e)} - Duration: {duration:.3f}s")
            raise

    return decorated_function