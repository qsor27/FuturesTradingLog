# Profile Import/Export API Implementation

## Overview

This document describes the implementation of the **Import/Export & Sharing** feature (MEDIUM COLLABORATION priority from TODO list) for the FuturesTradingLog application. This feature provides comprehensive API endpoints for managing user profiles, including import/export functionality for backup, migration, and sharing configurations.

## API Endpoints

### Base URL Pattern
All profile endpoints follow the pattern: `/api/v2/profiles/*`

### Authentication
- Currently uses default `user_id = 1` for single-user setup
- Can be extended to support multi-user authentication

## Endpoint Documentation

### 1. Get All Profiles
```
GET /api/v2/profiles
```

**Parameters:**
- `user_id` (optional, query): User ID (default: 1)

**Response:**
```json
{
  "success": true,
  "profiles": [
    {
      "id": 1,
      "profile_name": "Scalping Setup",
      "description": "Quick trades with 1m charts",
      "settings_snapshot": {...},
      "is_default": true,
      "created_at": "2025-01-01T10:00:00",
      "updated_at": "2025-01-01T10:00:00"
    }
  ],
  "count": 1
}
```

### 2. Get Single Profile
```
GET /api/v2/profiles/<profile_id>
```

**Response:**
```json
{
  "success": true,
  "profile": {
    "id": 1,
    "profile_name": "Scalping Setup",
    "settings_snapshot": {...}
  }
}
```

### 3. Export Profile (Download)
```
GET /api/v2/profiles/<profile_id>/export
```

**Features:**
- Downloads JSON file with proper Content-Disposition headers
- Filename format: `profile_{safe_name}_{timestamp}.json`
- Excludes database-specific fields (id, user_id, timestamps)
- Includes export metadata (exported_at, export_version)

**Response:** JSON file download

**Export Format:**
```json
{
  "profile_name": "Scalping Setup",
  "description": "Quick trades with 1m charts",
  "settings_snapshot": {
    "chart_settings": {
      "default_timeframe": "1m",
      "default_data_range": "3hours"
    }
  },
  "exported_at": "2025-01-01T10:00:00.000Z",
  "export_version": "1.0"
}
```

### 4. Import Profile (Upload)
```
POST /api/v2/profiles/import
```

**Request:**
- Form data with `file` field (JSON file)
- Optional `user_id` form field

**Features:**
- File validation (JSON only, max 5MB)
- JSON structure validation
- Automatic name conflict resolution with "(imported)" suffix
- UTF-8 encoding validation

**Response:**
```json
{
  "success": true,
  "message": "Profile imported successfully",
  "profile_id": 123,
  "profile_name": "Scalping Setup (imported)",
  "name_changed": true,
  "original_name": "Scalping Setup"
}
```

### 5. Create Profile
```
POST /api/v2/profiles
```

**Request Body:**
```json
{
  "profile_name": "New Profile",
  "settings_snapshot": {...},
  "description": "Optional description",
  "is_default": false,
  "user_id": 1
}
```

### 6. Update Profile
```
PUT /api/v2/profiles/<profile_id>
```

**Request Body:** (all fields optional)
```json
{
  "profile_name": "Updated Name",
  "settings_snapshot": {...},
  "description": "Updated description",
  "is_default": true
}
```

### 7. Delete Profile
```
DELETE /api/v2/profiles/<profile_id>
```

**Response:**
```json
{
  "success": true,
  "message": "Profile deleted successfully"
}
```

### 8. Get Default Profile
```
GET /api/v2/profiles/default
```

**Parameters:**
- `user_id` (optional, query): User ID (default: 1)

### 9. Bulk Export Profiles
```
POST /api/v2/profiles/bulk-export
```

**Request Body:**
```json
{
  "profile_ids": [1, 2, 3],
  "user_id": 1
}
```

**Features:**
- Downloads single JSON file containing multiple profiles
- Filename format: `profiles_bulk_export_{timestamp}.json`

**Export Format:**
```json
{
  "profiles": [
    {
      "profile_name": "Profile 1",
      "settings_snapshot": {...}
    }
  ],
  "exported_at": "2025-01-01T10:00:00.000Z",
  "export_version": "1.0",
  "export_type": "bulk",
  "profile_count": 3
}
```

### 10. Validate Import File
```
POST /api/v2/profiles/validate
```

**Request:**
- Form data with `file` field (JSON file)

**Features:**
- Validates file without importing
- Supports both single profile and bulk export formats
- Returns detailed validation results

**Response (Single Profile):**
```json
{
  "success": true,
  "file_type": "single",
  "profile_name": "Test Profile",
  "valid": true,
  "error": null
}
```

**Response (Bulk Export):**
```json
{
  "success": true,
  "file_type": "bulk",
  "total_profiles": 3,
  "valid_profiles": 2,
  "validation_results": [
    {
      "index": 0,
      "profile_name": "Profile 1",
      "valid": true,
      "error": null
    }
  ],
  "all_valid": false
}
```

## Security Features

### File Upload Security
- **File Type Validation**: Only `.json` files allowed
- **File Size Limits**: Maximum 5MB upload size
- **Encoding Validation**: UTF-8 encoding required
- **Filename Sanitization**: Uses `secure_filename()` for safe file handling

### Data Validation
- **Required Fields**: Validates presence of `profile_name` and `settings_snapshot`
- **Data Types**: Ensures correct data types for all fields
- **Name Uniqueness**: Prevents duplicate profile names per user
- **JSON Structure**: Validates settings_snapshot is valid JSON object

### Error Handling
- **Comprehensive Error Messages**: Clear, actionable error descriptions
- **HTTP Status Codes**: Proper status codes for different error types
- **Logging**: All operations logged for debugging and auditing

## Integration with Existing System

### Database Integration
- Uses existing `FuturesDB` class and user profile methods
- Follows established database connection patterns
- Integrates with monitoring and metrics collection

### Flask Blueprint Pattern
- Follows existing route organization with `profiles_bp` blueprint
- Registered in `app.py` with other blueprints
- Uses consistent error handling and response formats

### API Versioning
- Uses `/api/v2/` prefix for versioning
- Maintains compatibility with existing v1 APIs
- Allows for future API evolution

## Usage Examples

### Export a Profile
```bash
curl -X GET "http://localhost:5000/api/v2/profiles/1/export" \
  -H "Accept: application/json" \
  -o "my_profile.json"
```

### Import a Profile
```bash
curl -X POST "http://localhost:5000/api/v2/profiles/import" \
  -F "file=@my_profile.json" \
  -F "user_id=1"
```

### Validate Before Import
```bash
curl -X POST "http://localhost:5000/api/v2/profiles/validate" \
  -F "file=@my_profile.json"
```

### Bulk Export
```bash
curl -X POST "http://localhost:5000/api/v2/profiles/bulk-export" \
  -H "Content-Type: application/json" \
  -d '{"profile_ids": [1, 2, 3]}' \
  -o "bulk_profiles.json"
```

## Error Response Format

All endpoints return errors in consistent format:

```json
{
  "success": false,
  "error": "Detailed error message"
}
```

### Common HTTP Status Codes
- `200`: Success
- `400`: Bad Request (validation errors, missing data)
- `404`: Not Found (profile doesn't exist)
- `500`: Internal Server Error (database errors, unexpected failures)

## Implementation Details

### File Structure
- **Route File**: `/routes/profiles.py`
- **Blueprint Registration**: Added to `app.py`
- **Database Methods**: Uses existing methods in `TradingLog_db.py`

### Dependencies
- **Flask**: Web framework and utilities
- **werkzeug**: File handling and security utilities
- **json**: JSON parsing and generation
- **logging**: Error logging and debugging

### Performance Considerations
- **File Size Limits**: Prevents memory issues with large uploads
- **JSON Parsing**: Efficient parsing with error handling
- **Database Queries**: Uses existing optimized database methods
- **Memory Management**: File processing in memory with size limits

## Testing

### Validation Testing
- Valid JSON profile import/export
- Invalid JSON handling
- File size limit enforcement
- Name conflict resolution
- Bulk operations

### Security Testing
- File type restrictions
- Encoding validation
- SQL injection prevention (via parameterized queries)
- File path traversal prevention

### Integration Testing
- Database operations
- Blueprint registration
- Error handling
- Response formats

## Future Enhancements

### Possible Extensions
1. **Multi-User Support**: Extend authentication and user isolation
2. **Profile Sharing URLs**: Generate shareable links for profiles
3. **Profile Templates**: System-provided template profiles
4. **Import Preview**: UI preview before importing profiles
5. **Batch Import**: Support importing multiple profiles from one file
6. **Profile Versioning**: Track changes to profiles over time

### Frontend Integration
The API is designed to support a comprehensive frontend interface with:
- Profile management dashboard
- Drag-and-drop file upload
- Import validation preview
- Bulk selection and export
- Profile sharing interface

## Implementation Status

✅ **Complete**: All API endpoints implemented
✅ **Complete**: File upload and validation
✅ **Complete**: Security and error handling
✅ **Complete**: JSON export/import functionality
✅ **Complete**: Name conflict resolution
✅ **Complete**: Bulk operations support
✅ **Complete**: Blueprint registration
✅ **Complete**: Documentation and examples

## Files Modified

1. **`/routes/profiles.py`**: New file containing all profile API endpoints
2. **`/app.py`**: Added import and registration for profiles blueprint

## Key Features Implemented

1. **Single Profile Export**: Download individual profiles as JSON
2. **Profile Import**: Upload and validate JSON profile files
3. **Name Conflict Resolution**: Automatic handling with "(imported)" suffix
4. **Bulk Export**: Export multiple profiles in single file
5. **Validation API**: Validate files before importing
6. **Comprehensive CRUD**: Full create, read, update, delete operations
7. **Security**: File type, size, and content validation
8. **Error Handling**: Detailed error messages and proper HTTP status codes

This implementation provides a robust foundation for profile management and sharing, following the existing codebase patterns and supporting the collaboration use case described in the original requirements.