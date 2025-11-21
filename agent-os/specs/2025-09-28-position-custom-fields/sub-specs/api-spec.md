# API Specification

This is the API specification for the spec detailed in @.agent-os/specs/2025-09-28-position-custom-fields/spec.md

> Created: 2025-09-28
> Version: 1.0.0

## Endpoints

### Custom Field Definition Management

#### GET /api/custom-fields
**Description:** Retrieve all custom field definitions
**Authentication:** Required
**Parameters:**
- `active_only` (query, boolean, optional): Filter to only active fields (default: false)
- `field_type` (query, string, optional): Filter by field type (text, number, date, boolean, select)

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "name": "risk_level",
      "display_name": "Risk Level",
      "field_type": "select",
      "options": ["Low", "Medium", "High"],
      "default_value": "Medium",
      "is_required": false,
      "is_active": true,
      "sort_order": 1,
      "created_at": "2025-09-28T10:00:00Z",
      "updated_at": "2025-09-28T10:00:00Z"
    }
  ],
  "meta": {
    "total": 1,
    "count": 1
  }
}
```

#### POST /api/custom-fields
**Description:** Create a new custom field definition
**Authentication:** Required
**Request Body:**
```json
{
  "name": "market_sentiment",
  "display_name": "Market Sentiment",
  "field_type": "select",
  "options": ["Bullish", "Neutral", "Bearish"],
  "default_value": "Neutral",
  "is_required": false,
  "is_active": true,
  "sort_order": 2
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": 2,
    "name": "market_sentiment",
    "display_name": "Market Sentiment",
    "field_type": "select",
    "options": ["Bullish", "Neutral", "Bearish"],
    "default_value": "Neutral",
    "is_required": false,
    "is_active": true,
    "sort_order": 2,
    "created_at": "2025-09-28T10:05:00Z",
    "updated_at": "2025-09-28T10:05:00Z"
  }
}
```

#### GET /api/custom-fields/{field_id}
**Description:** Retrieve a specific custom field definition
**Authentication:** Required
**Parameters:**
- `field_id` (path, integer, required): Custom field ID

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": 1,
    "name": "risk_level",
    "display_name": "Risk Level",
    "field_type": "select",
    "options": ["Low", "Medium", "High"],
    "default_value": "Medium",
    "is_required": false,
    "is_active": true,
    "sort_order": 1,
    "created_at": "2025-09-28T10:00:00Z",
    "updated_at": "2025-09-28T10:00:00Z"
  }
}
```

#### PUT /api/custom-fields/{field_id}
**Description:** Update a custom field definition
**Authentication:** Required
**Parameters:**
- `field_id` (path, integer, required): Custom field ID

**Request Body:**
```json
{
  "display_name": "Updated Risk Level",
  "options": ["Very Low", "Low", "Medium", "High", "Very High"],
  "default_value": "Low",
  "is_required": true,
  "sort_order": 1
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": 1,
    "name": "risk_level",
    "display_name": "Updated Risk Level",
    "field_type": "select",
    "options": ["Very Low", "Low", "Medium", "High", "Very High"],
    "default_value": "Low",
    "is_required": true,
    "is_active": true,
    "sort_order": 1,
    "created_at": "2025-09-28T10:00:00Z",
    "updated_at": "2025-09-28T10:30:00Z"
  }
}
```

#### DELETE /api/custom-fields/{field_id}
**Description:** Soft delete a custom field definition (sets is_active to false)
**Authentication:** Required
**Parameters:**
- `field_id` (path, integer, required): Custom field ID

**Response:**
```json
{
  "status": "success",
  "message": "Custom field deactivated successfully"
}
```

#### POST /api/custom-fields/{field_id}/reorder
**Description:** Update the sort order of custom fields
**Authentication:** Required
**Parameters:**
- `field_id` (path, integer, required): Custom field ID

**Request Body:**
```json
{
  "sort_order": 3
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": 1,
    "sort_order": 3,
    "updated_at": "2025-09-28T10:35:00Z"
  }
}
```

### Position Custom Field Values

#### GET /api/positions/{position_id}/custom-fields
**Description:** Retrieve all custom field values for a position
**Authentication:** Required
**Parameters:**
- `position_id` (path, integer, required): Position ID

**Response:**
```json
{
  "status": "success",
  "data": {
    "position_id": 123,
    "custom_fields": [
      {
        "field_id": 1,
        "field_name": "risk_level",
        "field_display_name": "Risk Level",
        "field_type": "select",
        "value": "High",
        "updated_at": "2025-09-28T10:00:00Z"
      },
      {
        "field_id": 2,
        "field_name": "market_sentiment",
        "field_display_name": "Market Sentiment",
        "field_type": "select",
        "value": "Bullish",
        "updated_at": "2025-09-28T10:00:00Z"
      }
    ]
  }
}
```

#### PUT /api/positions/{position_id}/custom-fields
**Description:** Update custom field values for a position (bulk update)
**Authentication:** Required
**Parameters:**
- `position_id` (path, integer, required): Position ID

**Request Body:**
```json
{
  "custom_fields": [
    {
      "field_id": 1,
      "value": "Medium"
    },
    {
      "field_id": 2,
      "value": "Neutral"
    }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "position_id": 123,
    "updated_fields": [
      {
        "field_id": 1,
        "field_name": "risk_level",
        "value": "Medium",
        "updated_at": "2025-09-28T10:40:00Z"
      },
      {
        "field_id": 2,
        "field_name": "market_sentiment",
        "value": "Neutral",
        "updated_at": "2025-09-28T10:40:00Z"
      }
    ]
  }
}
```

#### PUT /api/positions/{position_id}/custom-fields/{field_id}
**Description:** Update a specific custom field value for a position
**Authentication:** Required
**Parameters:**
- `position_id` (path, integer, required): Position ID
- `field_id` (path, integer, required): Custom field ID

**Request Body:**
```json
{
  "value": "High"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "position_id": 123,
    "field_id": 1,
    "field_name": "risk_level",
    "value": "High",
    "updated_at": "2025-09-28T10:45:00Z"
  }
}
```

#### DELETE /api/positions/{position_id}/custom-fields/{field_id}
**Description:** Remove a custom field value for a position
**Authentication:** Required
**Parameters:**
- `position_id` (path, integer, required): Position ID
- `field_id` (path, integer, required): Custom field ID

**Response:**
```json
{
  "status": "success",
  "message": "Custom field value removed successfully"
}
```

### Enhanced Notes Endpoints

#### GET /api/positions/{position_id}/notes
**Description:** Retrieve all notes for a position with enhanced metadata
**Authentication:** Required
**Parameters:**
- `position_id` (path, integer, required): Position ID
- `note_type` (query, string, optional): Filter by note type (general, analysis, alert, custom)

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "position_id": 123,
      "content": "Strong resistance at 4200 level",
      "note_type": "analysis",
      "tags": ["resistance", "technical"],
      "is_pinned": false,
      "created_at": "2025-09-28T10:00:00Z",
      "updated_at": "2025-09-28T10:00:00Z"
    }
  ],
  "meta": {
    "total": 1,
    "count": 1
  }
}
```

#### POST /api/positions/{position_id}/notes
**Description:** Create a new note for a position
**Authentication:** Required
**Parameters:**
- `position_id` (path, integer, required): Position ID

**Request Body:**
```json
{
  "content": "Market showing bullish momentum",
  "note_type": "analysis",
  "tags": ["momentum", "bullish"],
  "is_pinned": false
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": 2,
    "position_id": 123,
    "content": "Market showing bullish momentum",
    "note_type": "analysis",
    "tags": ["momentum", "bullish"],
    "is_pinned": false,
    "created_at": "2025-09-28T10:50:00Z",
    "updated_at": "2025-09-28T10:50:00Z"
  }
}
```

#### PUT /api/positions/{position_id}/notes/{note_id}
**Description:** Update a specific note
**Authentication:** Required
**Parameters:**
- `position_id` (path, integer, required): Position ID
- `note_id` (path, integer, required): Note ID

**Request Body:**
```json
{
  "content": "Updated: Market showing strong bullish momentum",
  "note_type": "analysis",
  "tags": ["momentum", "bullish", "strong"],
  "is_pinned": true
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": 2,
    "position_id": 123,
    "content": "Updated: Market showing strong bullish momentum",
    "note_type": "analysis",
    "tags": ["momentum", "bullish", "strong"],
    "is_pinned": true,
    "created_at": "2025-09-28T10:50:00Z",
    "updated_at": "2025-09-28T10:55:00Z"
  }
}
```

#### DELETE /api/positions/{position_id}/notes/{note_id}
**Description:** Delete a specific note
**Authentication:** Required
**Parameters:**
- `position_id` (path, integer, required): Position ID
- `note_id` (path, integer, required): Note ID

**Response:**
```json
{
  "status": "success",
  "message": "Note deleted successfully"
}
```

### Bulk Operations

#### GET /api/positions/custom-fields/summary
**Description:** Get summary of custom field usage across all positions
**Authentication:** Required
**Parameters:**
- `field_id` (query, integer, optional): Filter by specific field
- `date_from` (query, date, optional): Filter positions from date
- `date_to` (query, date, optional): Filter positions to date

**Response:**
```json
{
  "status": "success",
  "data": {
    "summary": [
      {
        "field_id": 1,
        "field_name": "risk_level",
        "field_display_name": "Risk Level",
        "value_counts": {
          "Low": 25,
          "Medium": 45,
          "High": 15
        },
        "total_positions": 85,
        "usage_percentage": 68.5
      }
    ],
    "meta": {
      "total_positions": 124,
      "positions_with_custom_fields": 85
    }
  }
}
```

#### POST /api/positions/custom-fields/bulk-update
**Description:** Bulk update custom field values across multiple positions
**Authentication:** Required
**Request Body:**
```json
{
  "position_ids": [123, 124, 125],
  "updates": [
    {
      "field_id": 1,
      "value": "High"
    }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "updated_positions": 3,
    "failed_positions": 0,
    "details": [
      {
        "position_id": 123,
        "status": "updated",
        "updated_fields": [1]
      },
      {
        "position_id": 124,
        "status": "updated",
        "updated_fields": [1]
      },
      {
        "position_id": 125,
        "status": "updated",
        "updated_fields": [1]
      }
    ]
  }
}
```

## Controllers

### CustomFieldController

**Location:** `routes/custom_fields.py`

**Responsibilities:**
- Handle CRUD operations for custom field definitions
- Validate field types and options
- Manage field ordering and activation status
- Handle field value operations for positions

**Key Methods:**
- `get_custom_fields()` - List all custom field definitions
- `create_custom_field()` - Create new custom field definition
- `get_custom_field(field_id)` - Get specific custom field
- `update_custom_field(field_id)` - Update custom field definition
- `delete_custom_field(field_id)` - Soft delete custom field
- `reorder_custom_field(field_id)` - Update field sort order

**Integration with Flask Routing:**
```python
from flask import Blueprint
from routes.custom_fields import CustomFieldController

custom_fields_bp = Blueprint('custom_fields', __name__, url_prefix='/api/custom-fields')
controller = CustomFieldController()

custom_fields_bp.add_url_rule('', 'list', controller.get_custom_fields, methods=['GET'])
custom_fields_bp.add_url_rule('', 'create', controller.create_custom_field, methods=['POST'])
custom_fields_bp.add_url_rule('/<int:field_id>', 'get', controller.get_custom_field, methods=['GET'])
custom_fields_bp.add_url_rule('/<int:field_id>', 'update', controller.update_custom_field, methods=['PUT'])
custom_fields_bp.add_url_rule('/<int:field_id>', 'delete', controller.delete_custom_field, methods=['DELETE'])
custom_fields_bp.add_url_rule('/<int:field_id>/reorder', 'reorder', controller.reorder_custom_field, methods=['POST'])
```

### PositionCustomFieldController

**Location:** `routes/position_custom_fields.py`

**Responsibilities:**
- Handle custom field values for specific positions
- Validate field values against field definitions
- Manage bulk operations for custom fields
- Provide summary and analytics endpoints

**Key Methods:**
- `get_position_custom_fields(position_id)` - Get all custom field values for position
- `update_position_custom_fields(position_id)` - Bulk update custom field values
- `update_position_custom_field(position_id, field_id)` - Update specific field value
- `delete_position_custom_field(position_id, field_id)` - Remove field value
- `get_custom_fields_summary()` - Get usage summary across positions
- `bulk_update_custom_fields()` - Bulk update across multiple positions

**Integration with Flask Routing:**
```python
from flask import Blueprint
from routes.position_custom_fields import PositionCustomFieldController

position_custom_fields_bp = Blueprint('position_custom_fields', __name__)
controller = PositionCustomFieldController()

# Position-specific custom field routes
position_custom_fields_bp.add_url_rule('/api/positions/<int:position_id>/custom-fields',
                                     'get_position_fields', controller.get_position_custom_fields, methods=['GET'])
position_custom_fields_bp.add_url_rule('/api/positions/<int:position_id>/custom-fields',
                                     'update_position_fields', controller.update_position_custom_fields, methods=['PUT'])
position_custom_fields_bp.add_url_rule('/api/positions/<int:position_id>/custom-fields/<int:field_id>',
                                     'update_position_field', controller.update_position_custom_field, methods=['PUT'])
position_custom_fields_bp.add_url_rule('/api/positions/<int:position_id>/custom-fields/<int:field_id>',
                                     'delete_position_field', controller.delete_position_custom_field, methods=['DELETE'])

# Bulk operations
position_custom_fields_bp.add_url_rule('/api/positions/custom-fields/summary',
                                     'get_summary', controller.get_custom_fields_summary, methods=['GET'])
position_custom_fields_bp.add_url_rule('/api/positions/custom-fields/bulk-update',
                                     'bulk_update', controller.bulk_update_custom_fields, methods=['POST'])
```

### Enhanced NotesController

**Location:** `routes/notes.py` (enhanced)

**Responsibilities:**
- Handle CRUD operations for position notes
- Support enhanced note features (types, tags, pinning)
- Integrate with custom fields for comprehensive position metadata

**Key Methods:**
- `get_position_notes(position_id)` - Get all notes for position
- `create_position_note(position_id)` - Create new note
- `update_position_note(position_id, note_id)` - Update existing note
- `delete_position_note(position_id, note_id)` - Delete note

**Enhanced Integration:**
```python
from flask import Blueprint
from routes.notes import NotesController

notes_bp = Blueprint('notes', __name__)
controller = NotesController()

notes_bp.add_url_rule('/api/positions/<int:position_id>/notes',
                     'get_notes', controller.get_position_notes, methods=['GET'])
notes_bp.add_url_rule('/api/positions/<int:position_id>/notes',
                     'create_note', controller.create_position_note, methods=['POST'])
notes_bp.add_url_rule('/api/positions/<int:position_id>/notes/<int:note_id>',
                     'update_note', controller.update_position_note, methods=['PUT'])
notes_bp.add_url_rule('/api/positions/<int:position_id>/notes/<int:note_id>',
                     'delete_note', controller.delete_position_note, methods=['DELETE'])
```

## Error Handling

### Standard Error Response Format

```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Field validation failed",
    "details": {
      "field": "field_type",
      "reason": "Invalid field type. Must be one of: text, number, date, boolean, select"
    }
  }
}
```

### Common Error Codes

- `VALIDATION_ERROR` - Input validation failed
- `NOT_FOUND` - Resource not found
- `DUPLICATE_ERROR` - Attempting to create duplicate resource
- `DEPENDENCY_ERROR` - Cannot delete resource due to dependencies
- `PERMISSION_ERROR` - Insufficient permissions
- `SERVER_ERROR` - Internal server error

### Field-Specific Validations

#### Custom Field Definitions
- `name`: Required, unique, alphanumeric with underscores
- `display_name`: Required, string, max 100 characters
- `field_type`: Required, must be valid type (text, number, date, boolean, select)
- `options`: Required for select fields, array of strings
- `default_value`: Must be valid for field type
- `sort_order`: Integer, auto-assigned if not provided

#### Custom Field Values
- Value must match field type requirements
- Select field values must be in predefined options
- Number fields must be valid numbers
- Date fields must be valid ISO date strings
- Boolean fields must be true/false

### Error Examples

#### Invalid Field Type
```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid field type",
    "details": {
      "field": "field_type",
      "value": "invalid_type",
      "allowed_values": ["text", "number", "date", "boolean", "select"]
    }
  }
}
```

#### Field Not Found
```json
{
  "status": "error",
  "error": {
    "code": "NOT_FOUND",
    "message": "Custom field not found",
    "details": {
      "field_id": 999
    }
  }
}
```

#### Duplicate Field Name
```json
{
  "status": "error",
  "error": {
    "code": "DUPLICATE_ERROR",
    "message": "Custom field with this name already exists",
    "details": {
      "field": "name",
      "value": "risk_level"
    }
  }
}
```

#### Invalid Select Value
```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid value for select field",
    "details": {
      "field": "value",
      "value": "Invalid",
      "allowed_values": ["Low", "Medium", "High"]
    }
  }
}
```

## Integration with Existing Flask Routing Structure

### Blueprint Registration

In `app.py` or main application file:

```python
from routes.custom_fields import custom_fields_bp
from routes.position_custom_fields import position_custom_fields_bp
from routes.notes import notes_bp

# Register blueprints
app.register_blueprint(custom_fields_bp)
app.register_blueprint(position_custom_fields_bp)
app.register_blueprint(notes_bp)
```

### Middleware Integration

```python
from functools import wraps
from flask import request, jsonify

def validate_json(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.content_type != 'application/json':
            return jsonify({
                "status": "error",
                "error": {
                    "code": "INVALID_CONTENT_TYPE",
                    "message": "Content-Type must be application/json"
                }
            }), 400
        return f(*args, **kwargs)
    return decorated_function

def authenticate_request(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Add authentication logic here
        return f(*args, **kwargs)
    return decorated_function
```

### Service Layer Integration

Controllers will integrate with existing service classes:

```python
from services.custom_field_service import CustomFieldService
from services.position_service import PositionService
from services.data_service import DataService

class CustomFieldController:
    def __init__(self):
        self.custom_field_service = CustomFieldService()
        self.position_service = PositionService()
        self.data_service = DataService()
```

This API specification provides comprehensive endpoints for managing custom fields and enhanced notes while integrating seamlessly with the existing Flask routing structure and maintaining consistency with current application patterns.