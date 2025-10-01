"""
Middleware package for FuturesDB application

Provides validation, error handling, and request processing middleware
for API endpoints.
"""

from .validation import (
    APIError,
    ValidationError,
    NotFoundError,
    ConflictError,
    handle_api_errors,
    validate_json_request,
    validate_pydantic_model,
    validate_integer_param,
    require_database_connection,
    validate_custom_field_type,
    validate_field_value_format,
    rate_limit,
    log_api_request,
    sanitize_html_input
)

__all__ = [
    'APIError',
    'ValidationError',
    'NotFoundError',
    'ConflictError',
    'handle_api_errors',
    'validate_json_request',
    'validate_pydantic_model',
    'validate_integer_param',
    'require_database_connection',
    'validate_custom_field_type',
    'validate_field_value_format',
    'rate_limit',
    'log_api_request',
    'sanitize_html_input'
]