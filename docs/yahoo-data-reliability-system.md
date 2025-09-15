# Yahoo Data Reliability & Auto-Update System

## Overview

This document describes the enhanced Yahoo Finance data reliability system that ensures automatic, continuous updates of market data with intelligent freshness checking and error handling.

## Key Features

### 1. Automatic Data Freshness Checking
- **Real-time freshness validation** with configurable thresholds per timeframe
- **Smart prioritization** of critical timeframes for trading analysis
- **Comprehensive reporting** of data staleness across all instruments

### 2. Intelligent Background Updates
- **Scheduled smart updates** every 2 minutes for active instruments
- **Priority instrument updates** every 10 minutes (MNQ, ES, YM, RTY)
- **Comprehensive freshness checks** every hour with automatic remediation

### 3. Enhanced Data Validation
- **Multi-level validation** of Yahoo Finance data quality
- **OHLC relationship verification** (High >= Open/Close, Low <= Open/Close)
- **Anomaly detection** for extreme price movements and data gaps
- **Automatic filtering** of invalid records

### 4. Manual Refresh Endpoints
- **Instrument-specific updates** with customizable parameters
- **Priority instrument batch updates** for quick refresh
- **Emergency sync capabilities** for critical data gaps

## System Architecture

### Core Components

#### 1. Data Service (`services/data_service.py`)
- `check_data_freshness()` - Validates data currency across timeframes
- `auto_update_stale_data()` - Intelligently updates only stale data
- Enhanced validation with `_validate_ohlc_data()` and related methods

#### 2. Background Services (`services/background_services.py`)
- `DataUpdateService` - Intelligent scheduling and execution
- `BackgroundGapFillingService` - Gap detection and filling automation
- Real-time monitoring and statistics collection

#### 3. API Endpoints (`routes/data_monitoring.py`)
- `/api/data-refresh/freshness-check/<instrument>` - Check data freshness
- `/api/data-refresh/auto-update/<instrument>` - Trigger auto-update
- `/api/data-refresh/priority-update` - Update priority instruments
- `/api/data-refresh/emergency-sync` - Emergency data synchronization

## Configuration

### Freshness Thresholds
```python
freshness_thresholds = {
    '1m': timedelta(minutes=15),    # 1-min data: fresh within 15 minutes
    '5m': timedelta(minutes=30),    # 5-min data: fresh within 30 minutes  
    '15m': timedelta(hours=1),      # 15-min data: fresh within 1 hour
    '1h': timedelta(hours=2),       # 1-hour data: fresh within 2 hours
    '4h': timedelta(hours=6),       # 4-hour data: fresh within 6 hours
    '1d': timedelta(days=2)         # Daily data: fresh within 2 days
}
```

### Update Schedules
- **Smart updates**: Every 2 minutes (active instruments, limited scope)
- **Priority updates**: Every 10 minutes (MNQ, ES, YM, RTY)  
- **Comprehensive checks**: Every hour (all instruments, full validation)
- **Gap filling**: Every 15 minutes (recent gaps), Every 4 hours (extended gaps)

### Rate Limiting
- **Base delay**: 0.8 seconds between requests
- **Adaptive delays**: Automatically increase on failures
- **Circuit breaker**: Prevents API overload during failures
- **Batch processing**: Max 3 concurrent instruments

## Usage Examples

### 1. Check Data Freshness
```python
from services.data_service import ohlc_service

# Check specific timeframes
freshness_report = ohlc_service.check_data_freshness('MNQ', ['1h', '1d'])

# Check all timeframes
freshness_report = ohlc_service.check_data_freshness('MNQ')
```

### 2. Auto-Update Stale Data
```python
# Update up to 3 stale timeframes
results = ohlc_service.auto_update_stale_data('MNQ', max_updates=3)

# Priority-based update (1d, 1h, 4h first)
results = ohlc_service.auto_update_stale_data('ES')
```

### 3. Manual API Triggers
```bash
# Check freshness via API
curl "http://localhost:5000/api/data-refresh/freshness-check/MNQ"

# Trigger priority instrument update
curl -X POST "http://localhost:5000/api/data-refresh/priority-update"

# Emergency sync for last 7 days
curl -X POST -H "Content-Type: application/json" \
  -d '{"days_back": 7}' \
  "http://localhost:5000/api/data-refresh/emergency-sync"
```

## Data Quality Validation

### Level 1: Yahoo Finance Response Validation
- Minimum data point requirements
- Required column presence (Open, High, Low, Close, Volume)
- NaN value percentage thresholds (>50% = error, >10% = warning)

### Level 2: OHLC Relationship Validation  
- High >= Open and High >= Close
- Low <= Open and Low <= Close
- Price positivity checks

### Level 3: Time Series Validation
- Chronological ordering verification
- Duplicate timestamp detection
- Time gap analysis based on expected intervals
- Extreme price movement detection (>50% changes)

### Level 4: Record Processing Validation
- Individual record sanity checks
- Type conversion error handling
- Final data integrity verification

## Monitoring & Alerting

### Status Monitoring
```python
from services.background_services import get_services_status
status = get_services_status()
```

### Key Metrics Tracked
- Update success/failure rates per instrument
- Data freshness statistics
- API request timing and throttling
- Background service health status
- Cache hit/miss ratios

### Alert Conditions
- Instruments with >3 stale timeframes
- Update failures exceeding threshold
- Background service interruptions
- Data quality validation failures

## Performance Optimizations

### 1. Intelligent Prioritization
- **Trading activity-based**: Focus on actively traded instruments
- **Timeframe importance**: Prioritize 1d > 1h > 4h > 15m > 5m > 1m
- **Update limiting**: Prevent API overload with configurable limits

### 2. Caching Strategy
- Redis-based caching with 14-day TTL
- Intelligent cache warming for popular instruments
- Cache-first data retrieval with fallback

### 3. Rate Limiting
- Adaptive rate limiting based on success/failure rates
- Circuit breaker pattern for API protection
- Batch processing optimization

## Error Handling

### Network Errors
- Automatic retry with exponential backoff
- Circuit breaker activation on repeated failures
- Graceful degradation to cached data

### Data Quality Errors
- Automatic filtering of invalid records
- Detailed logging of validation failures
- Partial success handling (some records valid)

### API Rate Limiting
- Intelligent delay adjustments
- Request prioritization during throttling
- Alternative data source fallbacks

## Troubleshooting

### Common Issues

#### 1. Stale Data Persisting
- **Check**: Background services running (`get_services_status()`)
- **Action**: Manual refresh via API endpoints
- **Prevention**: Verify schedule configuration

#### 2. Update Failures
- **Check**: Network connectivity and rate limiting
- **Action**: Review error logs for specific failure patterns
- **Prevention**: Adjust rate limiting parameters

#### 3. Data Quality Issues
- **Check**: Validation logs for specific instruments/timeframes
- **Action**: Manual data inspection and re-validation
- **Prevention**: Tighten validation thresholds

### Diagnostic Commands
```python
# Check individual instrument status
freshness = ohlc_service.check_data_freshness('MNQ')

# Force update specific instrument
results = ohlc_service.auto_update_stale_data('MNQ')

# Background service status
from services.background_services import get_services_status
status = get_services_status()
```

## Future Enhancements

### Planned Features
1. **Multiple data source integration** for redundancy
2. **Machine learning-based anomaly detection** for data quality
3. **Real-time WebSocket integration** for live updates
4. **Advanced caching strategies** with predictive pre-loading
5. **Custom alerting rules** per instrument/user

### Performance Improvements
1. **Parallel processing** for multiple instruments
2. **Database query optimization** with better indexing
3. **Streaming data processing** for real-time updates
4. **Intelligent prefetching** based on user patterns

This system ensures reliable, up-to-date market data with minimal manual intervention, supporting effective trading analysis and decision-making.