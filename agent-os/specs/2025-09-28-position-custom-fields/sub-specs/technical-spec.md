# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-09-28-position-custom-fields/spec.md

> Created: 2025-09-28
> Version: 1.0.0

## Technical Requirements

### Database Schema Changes

#### New Tables

**custom_fields**
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `name` (VARCHAR(100) NOT NULL UNIQUE) - Field display name
- `description` (TEXT) - Optional field description
- `field_type` (VARCHAR(20) NOT NULL DEFAULT 'checkbox') - Field type (checkbox for phase 1)
- `is_active` (BOOLEAN NOT NULL DEFAULT 1) - Soft delete flag
- `display_order` (INTEGER NOT NULL DEFAULT 0) - Field ordering
- `created_at` (DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)
- `updated_at` (DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)

**position_custom_field_values**
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `position_id` (INTEGER NOT NULL) - Foreign key to positions table
- `custom_field_id` (INTEGER NOT NULL) - Foreign key to custom_fields table
- `value` (TEXT) - Field value (boolean as string for checkboxes)
- `created_at` (DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)
- `updated_at` (DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)
- `UNIQUE(position_id, custom_field_id)` - Constraint to prevent duplicates

#### Indexes
- `idx_custom_fields_active_order` ON `custom_fields(is_active, display_order)`
- `idx_position_custom_values_position` ON `position_custom_field_values(position_id)`
- `idx_position_custom_values_field` ON `position_custom_field_values(custom_field_id)`

#### Foreign Key Constraints
- `position_custom_field_values.position_id` REFERENCES `positions(id)` ON DELETE CASCADE
- `position_custom_field_values.custom_field_id` REFERENCES `custom_fields(id)` ON DELETE CASCADE

### Backend API Endpoints

#### Custom Field Management Endpoints

**GET /api/custom-fields**
- Returns all active custom fields ordered by display_order
- Response: `{fields: [CustomField]}`

**POST /api/custom-fields**
- Creates a new custom field
- Request: `{name: string, description?: string, field_type: string}`
- Response: `{field: CustomField}`
- Validation: name required, unique, max 100 chars

**PUT /api/custom-fields/{id}**
- Updates existing custom field
- Request: `{name?: string, description?: string, display_order?: number}`
- Response: `{field: CustomField}`

**DELETE /api/custom-fields/{id}**
- Soft deletes custom field (sets is_active=0)
- Response: `{success: boolean}`
- Cascades to position values (soft delete)

**POST /api/custom-fields/reorder**
- Updates display order for multiple fields
- Request: `{field_orders: [{id: number, display_order: number}]}`
- Response: `{success: boolean}`

#### Position Custom Field Value Endpoints

**GET /api/positions/{position_id}/custom-fields**
- Returns custom field values for a position
- Response: `{values: [{field: CustomField, value: any}]}`

**PUT /api/positions/{position_id}/custom-fields/{field_id}**
- Updates custom field value for a position
- Request: `{value: any}`
- Response: `{success: boolean, value: any}`

**PUT /api/positions/{position_id}/custom-fields**
- Bulk update custom field values for a position
- Request: `{values: [{field_id: number, value: any}]}`
- Response: `{success: boolean}`

#### Enhanced Notes Endpoints

**PUT /api/positions/{position_id}/notes**
- Updates position notes with enhanced formatting support
- Request: `{notes: string}`
- Response: `{success: boolean}`
- Validation: max length 10,000 characters

### Frontend UI Components

#### Custom Field Management Interface

**CustomFieldManager Component**
- Location: `static/js/components/CustomFieldManager.js`
- Features:
  - List all custom fields with edit/delete actions
  - Add new field form with validation
  - Drag-and-drop reordering
  - Field type selection (checkbox for phase 1)
  - Confirmation dialogs for destructive actions

**CustomFieldForm Component**
- Modal-based form for creating/editing fields
- Real-time validation feedback
- Field preview functionality
- Cancel/save actions with proper state management

#### Position Detail Page Enhancements

**CustomFieldSection Component**
- Location: `static/js/components/CustomFieldSection.js`
- Features:
  - Dynamic rendering of custom fields
  - Inline editing with immediate save
  - Checkbox state management
  - Loading states and error handling
  - Responsive grid layout

**EnhancedNotesSection Component**
- Location: `static/js/components/EnhancedNotesSection.js`
- Features:
  - Multi-line text area with auto-resize
  - Character count display
  - Auto-save functionality with debouncing
  - Formatting preservation
  - Edit/view mode toggle

#### Shared Components

**FieldValidator Utility**
- Location: `static/js/utils/fieldValidator.js`
- Functions:
  - `validateFieldName(name)` - Name validation rules
  - `validateFieldValue(value, fieldType)` - Value validation
  - `sanitizeInput(input)` - Input sanitization

**CustomFieldService**
- Location: `static/js/services/customFieldService.js`
- API communication layer for custom field operations
- Caching layer for field definitions
- Error handling and retry logic

### Integration with Existing Position Pages

#### Position Detail Page Modifications

**Template Updates (`templates/position_detail.html`)**
- Add custom fields section after standard position data
- Conditional rendering based on field existence
- Responsive layout adjustments
- Progressive enhancement approach

**JavaScript Integration**
- Modify existing position detail controller
- Add custom field state management
- Integrate with existing form handling
- Maintain backward compatibility

#### Navigation and Access

**Settings Page Integration**
- Add "Custom Fields" section to settings navigation
- User-friendly field management interface
- Bulk operations support
- Import/export preparation (for future phases)

### Performance Considerations

#### Database Optimization

**Query Optimization**
- Use JOIN queries to fetch position data with custom field values
- Implement query result caching for field definitions
- Optimize for N+1 query prevention
- Use database indexes effectively

**Example Optimized Query:**
```sql
SELECT p.*, cf.name as field_name, pcfv.value as field_value
FROM positions p
LEFT JOIN position_custom_field_values pcfv ON p.id = pcfv.position_id
LEFT JOIN custom_fields cf ON pcfv.custom_field_id = cf.id AND cf.is_active = 1
WHERE p.id = ?
ORDER BY cf.display_order
```

#### Frontend Performance

**Lazy Loading**
- Load custom field definitions once per session
- Lazy load custom field values when position detail is opened
- Implement virtual scrolling for large field lists
- Use debounced auto-save for field value updates

**Memory Management**
- Clean up event listeners on component unmount
- Use object pooling for frequently created components
- Implement proper garbage collection for form data
- Optimize DOM manipulation patterns

#### Caching Strategy

**Backend Caching**
- Cache custom field definitions in memory (5-minute TTL)
- Cache position custom field values per request
- Use ETags for conditional requests
- Implement cache invalidation on field updates

**Frontend Caching**
- Store field definitions in sessionStorage
- Cache position custom field values per position
- Implement cache busting on field definition changes
- Use service worker for offline field definition access

### Security Considerations

#### Input Validation
- Sanitize all user input for XSS prevention
- Validate field names against SQL injection
- Implement CSRF protection for all API endpoints
- Use parameterized queries for database operations

#### Access Control
- Verify user ownership of positions before allowing custom field access
- Implement rate limiting for custom field API endpoints
- Add audit logging for field definition changes
- Validate field value types against field definitions

#### Data Integrity
- Use database transactions for multi-table operations
- Implement referential integrity constraints
- Add data validation at multiple layers
- Use optimistic locking for concurrent updates

### Error Handling and Resilience

#### Backend Error Handling
- Comprehensive exception handling for database operations
- Graceful degradation when custom fields are unavailable
- Transaction rollback on partial failures
- Detailed error logging with correlation IDs

#### Frontend Error Handling
- User-friendly error messages for validation failures
- Retry mechanisms for network failures
- Fallback UI when custom fields can't be loaded
- Progress indicators for long-running operations

#### Data Migration and Rollback
- Database migration scripts with rollback capability
- Data backup before schema changes
- Gradual rollout strategy for feature deployment
- Monitoring and alerting for migration issues

### Testing Strategy

#### Unit Testing
- Test custom field CRUD operations
- Test position custom field value management
- Test UI component behavior in isolation
- Test validation and error handling logic

#### Integration Testing
- Test end-to-end custom field workflows
- Test database constraint enforcement
- Test API endpoint integration
- Test frontend-backend communication

#### Performance Testing
- Load testing for custom field queries
- Stress testing for concurrent field updates
- Memory usage testing for large field sets
- Response time testing for position detail pages

### Deployment Considerations

#### Database Migration
- Schema migration scripts with version control
- Data migration for existing positions
- Index creation with minimal downtime
- Rollback procedures for failed migrations

#### Feature Flags
- Progressive rollout using feature flags
- A/B testing capability for UI changes
- Gradual user base enablement
- Emergency disable capability

#### Monitoring and Observability
- Performance metrics for custom field operations
- Error rate monitoring for new endpoints
- User engagement tracking for feature adoption
- Database performance monitoring for new queries