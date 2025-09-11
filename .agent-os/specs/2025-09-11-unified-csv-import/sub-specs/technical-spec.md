# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-09-11-unified-csv-import/spec.md

> Created: 2025-09-11
> Version: 1.0.0

## Technical Requirements

### File Monitoring System
- Enhanced file watcher service using `watchdog` library to monitor `/Data` directory
- Automatic detection of new `.csv` files matching NinjaTrader indicator naming pattern
- Debouncing mechanism to handle file write completion before processing
- Queue-based processing to handle multiple simultaneous file additions

### Unified CSV Import Service
- Single `UnifiedCSVImportService` class consolidating all import logic
- Standardized CSV validation and parsing using existing `parse_csv_line()` function
- Consistent error handling and logging across all import operations
- Atomic transaction processing to ensure data consistency

### Processing Pipeline
- File validation (format, structure, data integrity)
- Duplicate detection and handling based on timestamp and instrument
- Position generation using existing `rebuild_positions()` logic
- Cache invalidation for affected data ranges
- Real-time WebSocket notifications for UI updates

### Manual Re-processing Interface
- File selection interface showing available CSV files in `/Data` directory
- Date range filtering for targeted re-processing
- Progress tracking with real-time status updates
- Error reporting with specific line-level feedback

## Approach

### Phase 1: Service Consolidation
1. Create `UnifiedCSVImportService` combining logic from existing import methods
2. Implement unified validation and processing pipeline
3. Add comprehensive error handling and logging

### Phase 2: File Monitoring Enhancement
1. Enhance existing file watcher to use queue-based processing
2. Add debouncing to handle file write completion
3. Integrate with unified import service

### Phase 3: Legacy Cleanup
1. Remove deprecated import endpoints while maintaining error responses
2. Update frontend to use new manual re-processing interface
3. Remove unused import-related code and templates

### Phase 4: Testing and Validation
1. Comprehensive testing of automatic import functionality
2. Manual re-processing interface validation
3. Performance testing with large CSV files

## External Dependencies

### Python Libraries
- `watchdog` - File system monitoring (already in use)
- `pandas` - CSV processing (already in use)
- `flask-socketio` - Real-time UI updates (already in use)

### Existing Components
- Database models (`Execution`, `Position`, `Trade`)
- Position calculation logic (`rebuild_positions()`)
- Cache management system
- WebSocket notification system