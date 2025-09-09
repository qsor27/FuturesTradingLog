# API Specification

This is the API specification for the spec detailed in @.agent-os/specs/2025-08-17-yahoo-data-reliability/spec.md

> Created: 2025-08-17
> Version: 1.0.0

## Endpoints

### Enhanced Data Service API

The following endpoints in `services/data_service.py` will be enhanced while maintaining backward compatibility:

#### 1. Chart Data Retrieval
```python
def get_chart_data(symbol, timeframe, start_date, end_date, use_cache=True)
```
**Enhancements:**
- Adaptive rate limiting integration
- Enhanced error handling with detailed error context
- Data quality validation before returning results
- Improved retry logic with circuit breaker

**Return Format (Unchanged):**
```python
{
    'data': pandas.DataFrame,  # OHLC data
    'metadata': {
        'symbol': str,
        'timeframe': str,
        'data_quality_score': float,  # NEW
        'cache_hit': bool,
        'download_time': float,
        'validation_status': str  # NEW
    }
}
```

#### 2. Symbol Validation
```python
def validate_symbol(symbol, contract_month=None)
```
**Enhancements:**
- Improved futures contract symbol mapping
- Better error messaging for invalid symbols
- Contract month validation for futures

#### 3. Health Check Endpoint (NEW)
```python
def get_data_service_health()
```
**Returns:**
```python
{
    'status': 'healthy|degraded|unhealthy',
    'last_successful_download': datetime,
    'circuit_breaker_status': str,
    'rate_limiting_status': {
        'current_delay': float,
        'success_rate': float,
        'last_reset': datetime
    },
    'error_statistics': {
        'last_hour_errors': int,
        'most_common_error': str,
        'consecutive_failures': int
    }
}
```

## Controllers

### Route Handler Enhancements

The following route handlers will be enhanced to leverage improved data service capabilities:

#### 1. Chart Data Route (`routes/chart_data.py`)
```python
@chart_data_bp.route('/api/chart/<symbol>/<timeframe>')
def get_chart_data(symbol, timeframe):
```
**Enhancements:**
- Enhanced error response handling
- Data quality indicators in response headers
- Performance metrics logging
- Circuit breaker status awareness

**Enhanced Response Headers:**
```
X-Data-Quality-Score: 0.95
X-Cache-Status: hit|miss
X-Download-Time: 0.025
X-Rate-Limit-Status: normal|throttled
X-Circuit-Breaker: closed|open|half-open
```

#### 2. Data Monitoring Route (`routes/data_monitoring.py`)
```python
@data_monitoring_bp.route('/api/data/health')
def data_health_check():
```
**New Endpoint for System Health:**
- Real-time data service health status
- Download success/failure rates
- Current rate limiting status
- Recent error summaries

#### 3. Symbol Management Routes
```python
@main_bp.route('/api/symbols/validate/<symbol>')
def validate_symbol_endpoint(symbol):
```
**Enhanced symbol validation with:**
- Futures contract month validation
- Symbol mapping suggestions for invalid symbols
- Contract expiration warnings

### Error Response Standardization

#### Enhanced Error Response Format
```python
{
    'error': {
        'code': 'RATE_LIMITED|NETWORK_ERROR|DATA_QUALITY|INVALID_SYMBOL|CIRCUIT_BREAKER',
        'message': str,  # User-friendly message
        'details': str,  # Technical details for debugging
        'retry_after': int,  # Seconds until retry recommended
        'suggested_action': str  # User guidance
    },
    'metadata': {
        'timestamp': datetime,
        'request_id': str,
        'circuit_breaker_status': str
    }
}
```

#### Error Code Definitions
- **RATE_LIMITED**: Yahoo Finance rate limiting detected
- **NETWORK_ERROR**: Connection timeout or network issues
- **DATA_QUALITY**: Downloaded data failed validation
- **INVALID_SYMBOL**: Symbol not found or invalid format
- **CIRCUIT_BREAKER**: Service temporarily unavailable due to persistent failures

### Performance Monitoring Integration

#### Request Metrics Collection
```python
# Enhanced request tracking
{
    'endpoint': str,
    'symbol': str,
    'timeframe': str,
    'cache_hit': bool,
    'download_time': float,
    'data_quality_score': float,
    'rate_limit_delay': float,
    'retry_count': int,
    'final_status': 'success|failed|cached'
}
```

#### Health Metrics Aggregation
```python
# Service health metrics
{
    'period': '1h|24h|7d',
    'total_requests': int,
    'success_rate': float,
    'average_response_time': float,
    'cache_hit_rate': float,
    'most_common_errors': list,
    'circuit_breaker_activations': int
}
```

### Configuration API (NEW)

#### Runtime Configuration Updates
```python
@admin_bp.route('/api/admin/data-service/config', methods=['GET', 'POST'])
def manage_data_service_config():
```
**Allows runtime adjustment of:**
- Rate limiting parameters
- Circuit breaker thresholds
- Retry strategies
- Data quality validation settings

**Configuration Update Format:**
```python
{
    'rate_limiting': {
        'base_delay': float,
        'max_delay': float,
        'adaptive_enabled': bool
    },
    'circuit_breaker': {
        'failure_threshold': int,
        'recovery_timeout': int
    },
    'data_quality': {
        'min_completeness_score': float,
        'validation_enabled': bool
    }
}
```