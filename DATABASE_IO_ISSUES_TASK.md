# Resolve Database I/O Issues

## Problem Summary

The application is experiencing persistent database I/O errors that prevent:
- Web application from starting properly (500 Internal Server Error)
- OHLC data from being stored successfully
- Multi-timeframe downloads from completing

### Error Messages Observed
```
Failed to connect to database: disk I/O error
Error during instrument name migration: disk I/O error
PermissionError: [Errno 13] Permission denied: '/app/data/logs/app.log'
```

## Root Cause Analysis

### Database File Issues
Current database state in container (`/app/data/db/`):
```
-rw-rw-r-- 1 appuser appuser 249856 Aug 20 03:46 futures_trades_clean.db
-rw-rw-r-- 1 appuser appuser  32768 Aug 20 03:46 futures_trades_clean.db-shm
-rw-rw-r-- 1 appuser appuser  74192 Aug 20 03:46 futures_trades_clean.db-wal
-rwxrwxrwx 1 root    root     32768 Aug 20 02:47 futures_trades.db-shm
-rwxrwxrwx 1 root    root         0 Aug 20 02:47 futures_trades.db-wal
```

**Issues Identified:**
1. **Mixed ownership**: Some files owned by `appuser`, others by `root`
2. **WAL mode conflicts**: Multiple WAL files with different permissions
3. **Database locking**: WAL (Write-Ahead Logging) files may be locked
4. **Permission mismatches**: Container user can't write to some database files

### Log Directory Issues
```
PermissionError: [Errno 13] Permission denied: '/app/data/logs/app.log'
```
Log files have restrictive permissions preventing container user from writing.

## Solution Strategy

### Phase 1: Database File Recovery

#### Task 6.1: Clean Database State
1. **Stop all containers** to release database locks
2. **Remove problematic WAL files** that have permission conflicts
3. **Backup current database** before making changes
4. **Reset database file permissions** to consistent ownership
5. **Restart with clean slate**

#### Task 6.2: Fix Database Configuration
1. **Disable WAL mode temporarily** to avoid locking issues
2. **Use DELETE mode** for simpler file handling
3. **Verify database integrity** after permission fixes
4. **Test basic CRUD operations**

### Phase 2: Container and Permission Fixes

#### Task 6.3: Fix Container User Permissions
1. **Ensure consistent user mapping** between host and container
2. **Fix data directory ownership** in Docker setup
3. **Update Dockerfile** if needed for proper permissions
4. **Test volume mounting** with correct permissions

#### Task 6.4: Logging Directory Fix
1. **Set proper ownership** for logs directory
2. **Update logging configuration** if needed
3. **Test log file creation** and rotation
4. **Verify application startup** completes without errors

### Phase 3: Testing and Verification

#### Task 6.5: Database Functionality Test
1. **Verify database connection** works without I/O errors
2. **Test OHLC data insertion** with sample data
3. **Confirm web application starts** without 500 errors
4. **Test multi-timeframe downloads** end-to-end

## Implementation Steps

### Step 1: Emergency Database Recovery
```bash
# Stop containers
docker-compose down

# Remove problematic WAL files
rm data/db/*.db-wal data/db/*.db-shm

# Backup current database
cp data/db/futures_trades_clean.db data/db/futures_trades_clean.db.backup

# Fix permissions (Windows)
icacls data /grant Everyone:F /T

# Or create fresh database if needed
```

### Step 2: Database Mode Configuration
```python
# In TradingLog_db.py or database connection setup
# Temporarily disable WAL mode
connection.execute("PRAGMA journal_mode = DELETE")
connection.execute("PRAGMA synchronous = NORMAL") 
```

### Step 3: Container Restart and Test
```bash
# Rebuild and start
docker-compose up -d --build

# Test database connection
docker exec container_name python -c "
from TradingLog_db import FuturesDB
with FuturesDB() as db:
    db.cursor.execute('SELECT COUNT(*) FROM trades')
    print('Database connection: OK')
"
```

### Step 4: Web Application Test
```bash
# Test web application
curl http://localhost:5000/
curl http://localhost:5000/charts
```

### Step 5: Multi-timeframe Download Test
```bash
# Test our enhanced multi-timeframe functionality
docker exec container_name python -c "
from data_service import OHLCDataService
service = OHLCDataService()
result = service.update_recent_data('TEST_SYMBOL', ['1h'])
print(f'Download test: {result}')
"
```

## Success Criteria

### Database Recovery
- [ ] No "disk I/O error" messages in logs
- [ ] Database connections succeed consistently
- [ ] OHLC data can be inserted and retrieved
- [ ] WAL file conflicts resolved

### Application Functionality
- [ ] Web application starts without 500 errors
- [ ] Charts page loads successfully
- [ ] "Update from API" button functions
- [ ] Logging system works without permission errors

### Multi-timeframe Downloads
- [ ] Enhanced update_recent_data method stores data successfully
- [ ] All supported timeframes can be downloaded
- [ ] Database shows multiple timeframes for test instruments
- [ ] Error handling works but doesn't prevent successful operations

## Risk Assessment

### High Risk
- **Data Loss**: Database corruption during permission fixes
- **Service Downtime**: Extended application unavailability
- **Container Issues**: Docker rebuild failures

### Mitigation
- **Database Backups**: Multiple backup copies before changes
- **Incremental Testing**: Test each step before proceeding
- **Rollback Plan**: Keep working backup available
- **Documentation**: Record all changes for reversal if needed

## Expected Timeline

- **Database Recovery**: 30-60 minutes
- **Container Fixes**: 30 minutes  
- **Testing & Verification**: 30 minutes
- **Total**: 1.5-2 hours

## Dependencies

### Prerequisites
- Docker containers stopped
- Database backup created
- Host system file permissions accessible

### External Dependencies
- Docker and docker-compose working
- Host filesystem permissions manageable
- No other processes locking database files

## Testing Plan

### Unit Tests
1. Database connection test
2. CRUD operations test
3. Logging system test

### Integration Tests
1. Web application startup
2. API endpoint functionality
3. Multi-timeframe download workflow

### System Tests
1. Full application workflow
2. Database persistence after container restart
3. Performance under load

This comprehensive approach ensures we resolve the database I/O issues systematically while preserving our working multi-timeframe download enhancements.