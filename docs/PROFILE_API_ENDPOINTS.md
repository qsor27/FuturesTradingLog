# Profile API Endpoints Quick Reference

## Testing Commands

Use these curl commands to test the Profile Import/Export API endpoints:

### 1. Get All Profiles
```bash
curl -X GET "http://localhost:5000/api/v2/profiles" \
  -H "Accept: application/json"
```

### 2. Get Single Profile
```bash
curl -X GET "http://localhost:5000/api/v2/profiles/1" \
  -H "Accept: application/json"
```

### 3. Create New Profile
```bash
curl -X POST "http://localhost:5000/api/v2/profiles" \
  -H "Content-Type: application/json" \
  -d '{
    "profile_name": "Test Scalping Profile",
    "description": "Quick trades with 1m charts",
    "settings_snapshot": {
      "chart_settings": {
        "default_timeframe": "1m",
        "default_data_range": "3hours",
        "volume_visibility": true
      },
      "instrument_multipliers": {
        "NQ": 20,
        "ES": 50
      }
    },
    "is_default": false
  }'
```

### 4. Export Profile (Download)
```bash
curl -X GET "http://localhost:5000/api/v2/profiles/1/export" \
  -H "Accept: application/json" \
  -o "exported_profile.json"
```

### 5. Import Profile (Upload)
First create a test profile file:
```bash
cat > test_profile.json << 'EOF'
{
  "profile_name": "Imported Swing Profile",
  "description": "Swing trading setup",
  "settings_snapshot": {
    "chart_settings": {
      "default_timeframe": "4h",
      "default_data_range": "1month",
      "volume_visibility": false
    }
  },
  "exported_at": "2025-01-01T10:00:00.000Z",
  "export_version": "1.0"
}
EOF
```

Then import it:
```bash
curl -X POST "http://localhost:5000/api/v2/profiles/import" \
  -F "file=@test_profile.json" \
  -F "user_id=1"
```

### 6. Validate Import File
```bash
curl -X POST "http://localhost:5000/api/v2/profiles/validate" \
  -F "file=@test_profile.json"
```

### 7. Update Profile
```bash
curl -X PUT "http://localhost:5000/api/v2/profiles/1" \
  -H "Content-Type: application/json" \
  -d '{
    "profile_name": "Updated Profile Name",
    "description": "Updated description"
  }'
```

### 8. Get Default Profile
```bash
curl -X GET "http://localhost:5000/api/v2/profiles/default" \
  -H "Accept: application/json"
```

### 9. Bulk Export Profiles
```bash
curl -X POST "http://localhost:5000/api/v2/profiles/bulk-export" \
  -H "Content-Type: application/json" \
  -d '{"profile_ids": [1, 2, 3]}' \
  -o "bulk_profiles.json"
```

### 10. Delete Profile
```bash
curl -X DELETE "http://localhost:5000/api/v2/profiles/1" \
  -H "Accept: application/json"
```

## Sample Profile JSON Structure

### Single Profile Export Format
```json
{
  "profile_name": "Scalping Setup",
  "description": "Quick trades with 1m charts",
  "settings_snapshot": {
    "chart_settings": {
      "default_timeframe": "1m",
      "default_data_range": "3hours",
      "volume_visibility": true
    },
    "instrument_multipliers": {
      "NQ": 20,
      "ES": 50,
      "YM": 5,
      "RTY": 50
    },
    "theme_settings": {
      "dark_mode": true,
      "chart_background": "#000000",
      "grid_color": "#333333"
    },
    "display_preferences": {
      "show_pnl": true,
      "show_volume": true,
      "decimal_places": 2
    }
  },
  "exported_at": "2025-01-01T10:00:00.000Z",
  "export_version": "1.0"
}
```

### Bulk Export Format
```json
{
  "profiles": [
    {
      "profile_name": "Scalping Setup",
      "description": "Quick trades",
      "settings_snapshot": {
        "chart_settings": {
          "default_timeframe": "1m"
        }
      }
    },
    {
      "profile_name": "Swing Trading",
      "description": "Long-term positions",
      "settings_snapshot": {
        "chart_settings": {
          "default_timeframe": "4h"
        }
      }
    }
  ],
  "exported_at": "2025-01-01T10:00:00.000Z",
  "export_version": "1.0",
  "export_type": "bulk",
  "profile_count": 2
}
```

## Expected Response Formats

### Success Response
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "profile_id": 123,
  "profile_name": "New Profile Name"
}
```

### Error Response
```json
{
  "success": false,
  "error": "Detailed error message describing what went wrong"
}
```

### Validation Response
```json
{
  "success": true,
  "file_type": "single",
  "profile_name": "Test Profile",
  "valid": true,
  "error": null
}
```

## HTTP Status Codes

- `200`: Success
- `400`: Bad Request (validation errors, missing data)
- `404`: Not Found (profile doesn't exist)
- `500`: Internal Server Error (database errors, unexpected failures)

## Testing Workflow

1. **Create a test profile** using the create endpoint
2. **Export the profile** to get a JSON file
3. **Validate the exported file** using the validation endpoint
4. **Import the profile** with a different name to test name conflict resolution
5. **Bulk export multiple profiles** to test bulk functionality
6. **Update and delete profiles** to test full CRUD operations

## Error Testing

### Invalid File Upload
```bash
# Test with non-JSON file
echo "not json" > invalid.txt
curl -X POST "http://localhost:5000/api/v2/profiles/import" \
  -F "file=@invalid.txt"
```

### Invalid JSON Structure
```bash
# Test with invalid JSON structure
cat > invalid_profile.json << 'EOF'
{
  "invalid_field": "missing required fields"
}
EOF

curl -X POST "http://localhost:5000/api/v2/profiles/validate" \
  -F "file=@invalid_profile.json"
```

### Large File Test
```bash
# Create a large file (over 5MB) to test size limits
dd if=/dev/zero of=large_file.json bs=1M count=6
curl -X POST "http://localhost:5000/api/v2/profiles/import" \
  -F "file=@large_file.json"
```

This provides a comprehensive test suite for validating the Profile Import/Export API implementation.