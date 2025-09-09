# Fix Multiple Timeframe Download Issue

## Problem Analysis

The system is currently only downloading one timeframe (1h) for instruments instead of the full range of supported timeframes. This severely limits chart functionality and data analysis capabilities.

### Current Situation
- **Database contains**: Only MNQ with 1h timeframe (168 records)
- **Expected**: MNQ should have data for 1m, 5m, 15m, 1h, 4h, 1d timeframes
- **Impact**: Users can only view charts in 1h timeframe, severely limiting analysis options

### Root Cause Investigation

Based on code analysis, there are several potential causes:

1. **API Rate Limiting**: The data service has rate limiting that might be causing early termination
2. **Error Handling**: Errors in one timeframe might stop processing of remaining timeframes
3. **yfinance Limitations**: Some timeframes might be failing due to API restrictions
4. **Database Transaction Issues**: Bulk inserts might be failing for certain timeframes
5. **Background Service Configuration**: The automated download might not be configured for multiple timeframes

## Technical Investigation Required

### 1. Check Error Logs
- Examine container logs for any errors during data fetching
- Look for yfinance API errors or rate limiting messages
- Check for database insert failures

### 2. Test Manual Download
- Test the manual "Update from API" button on charts page
- Monitor logs during manual update to see if all timeframes are attempted
- Verify if rate limiting is causing issues

### 3. Verify Configuration
- Check `SUPPORTED_TIMEFRAMES` and `YFINANCE_TIMEFRAME_MAP` in config
- Verify background service is configured correctly
- Check if any filters are limiting timeframe processing

### 4. Database Transaction Analysis
- Check if database bulk inserts are working properly
- Verify no constraints are preventing multiple timeframe inserts
- Test database connection stability during bulk operations

## Implementation Plan

### Phase 1: Diagnosis and Immediate Fix

#### Task 1: Enhanced Logging and Monitoring
- Add detailed logging to track each timeframe download attempt
- Log success/failure status for each timeframe individually
- Add timing information to identify bottlenecks
- Include yfinance API response details in logs

#### Task 2: Improve Error Handling
- Ensure errors in one timeframe don't stop processing of others
- Add retry logic for failed timeframe downloads
- Implement graceful degradation if some timeframes fail
- Log detailed error information for debugging

#### Task 3: Test Multiple Timeframe Download
- Create a test endpoint to trigger manual multi-timeframe download
- Test with various instruments to ensure consistency
- Monitor database inserts in real-time
- Verify all timeframes are processed sequentially

### Phase 2: System Improvements

#### Task 4: Optimize Data Fetching Strategy
- Review yfinance rate limits and adjust delays if necessary
- Implement smarter retry logic for transient failures
- Add exponential backoff for rate-limited requests
- Consider parallel downloads where appropriate (with rate limiting)

#### Task 5: Enhanced Database Operations
- Implement transaction-based bulk inserts for better reliability
- Add duplicate detection to prevent data conflicts
- Optimize database schema for multi-timeframe operations
- Add data validation before insertion

#### Task 6: User Interface Improvements
- Add progress indicators for multi-timeframe downloads
- Show which timeframes are being processed
- Display success/failure status for each timeframe
- Provide detailed feedback on data availability

### Phase 3: Long-term Reliability

#### Task 7: Background Service Enhancement
- Ensure background services download all timeframes
- Add scheduling for different timeframes (e.g., 1m more frequently than 1d)
- Implement smart gap detection and filling
- Add health monitoring for background downloads

#### Task 8: Data Quality Assurance
- Add data validation rules for each timeframe
- Implement data consistency checks across timeframes
- Add alerts for missing timeframe data
- Create data quality reports

## Immediate Action Plan

### Step 1: Enable Debug Logging
```python
# Add to services/data_service.py in update_recent_data method
self.logger.setLevel(logging.DEBUG)
for i, timeframe in enumerate(timeframes):
    self.logger.info(f"Processing timeframe {i+1}/{len(timeframes)}: {timeframe}")
    try:
        recent_data = self.fetch_ohlc_data(instrument, timeframe, start_date, end_date)
        self.logger.info(f"Fetched {len(recent_data)} records for {timeframe}")
        # ... existing code ...
        self.logger.info(f"Successfully stored {len(recent_data)} records for {timeframe}")
    except Exception as e:
        self.logger.error(f"Failed to process {timeframe}: {e}")
        continue  # Don't stop processing other timeframes
```

### Step 2: Test Manual Download
1. Go to charts page
2. Click "Update from API" button for MNQ
3. Monitor container logs for detailed progress
4. Check database after completion

### Step 3: Fix Immediate Issues
Based on log analysis, implement targeted fixes:
- Rate limiting adjustments
- Error handling improvements
- Database transaction fixes
- API parameter corrections

## Expected Outcomes

### Immediate (Phase 1)
- All supported timeframes download successfully for existing instruments
- Clear visibility into any failures or limitations
- Robust error handling that doesn't stop processing

### Short-term (Phase 2)
- Reliable multi-timeframe downloads for all instruments
- User-friendly feedback during download process
- Optimized performance with minimal API calls

### Long-term (Phase 3)
- Automated background downloads maintain all timeframes
- High data quality across all timeframes
- Proactive monitoring and alerting

## Success Criteria

1. **Database Verification**: After fix, MNQ should have data for all supported timeframes (1m, 5m, 15m, 1h, 4h, 1d)
2. **Consistent Downloads**: New instruments should automatically get all timeframes
3. **Error Recovery**: System should handle individual timeframe failures gracefully
4. **User Feedback**: Clear indication of download progress and results
5. **Background Reliability**: Automated systems maintain complete timeframe coverage

## Risk Assessment

### High Risk
- **API Rate Limits**: Aggressive downloading might trigger yfinance restrictions
- **Database Locks**: Concurrent timeframe inserts might cause conflicts
- **Memory Usage**: Large timeframe downloads might consume excessive resources

### Medium Risk
- **Data Consistency**: Different timeframes might have slight timestamp mismatches
- **Performance Impact**: Multiple timeframe processing might slow down UI
- **Storage Growth**: Complete timeframe coverage will increase database size significantly

### Mitigation Strategies
- Implement conservative rate limiting (2-3 seconds between requests)
- Use database transactions with proper error handling
- Add memory monitoring and cleanup
- Implement data validation and consistency checks
- Monitor storage usage and implement retention policies

## Testing Strategy

### Unit Tests
- Test each timeframe download individually
- Verify error handling for each potential failure point
- Test database operations with various data scenarios

### Integration Tests
- Test complete multi-timeframe download flow
- Verify UI updates correctly after downloads
- Test background service integration

### Performance Tests
- Measure download times for full timeframe sets
- Test system behavior under various network conditions
- Verify memory and CPU usage during bulk operations

This comprehensive approach ensures we not only fix the immediate issue but also create a robust, reliable system for ongoing multi-timeframe data management.