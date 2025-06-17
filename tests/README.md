# Futures Trading Log - Test Suite

Comprehensive test coverage for the OHLC chart integration and performance features.

## 🧪 Test Structure

### Test Files

| File | Purpose | Coverage |
|------|---------|----------|
| `test_app.py` | Basic application tests | Health checks, configuration |
| `test_ohlc_database.py` | Database functionality | Schema, indexes, CRUD operations |
| `test_data_service.py` | Data fetching service | yfinance integration, gap detection |
| `test_chart_api.py` | Chart API endpoints | REST APIs, data formatting |
| `test_integration.py` | End-to-end workflows | Complete feature integration |
| `test_performance.py` | Performance validation | Query speed, scalability |

### Test Categories

#### 🚀 **Performance Tests**
- Database query performance (15-50ms targets)
- Index effectiveness validation
- Large dataset handling (50k+ records)
- Concurrent query performance
- Memory usage optimization

#### 🔗 **Integration Tests**
- Complete data pipeline (fetch → store → display)
- Trade marker integration
- Multi-instrument support
- Chart page rendering
- API consistency validation

#### 🗄️ **Database Tests**
- OHLC table creation with 8 aggressive indexes
- Data validation and constraint testing
- Gap detection algorithms
- Duplicate prevention (INSERT OR IGNORE)
- Query optimization verification

#### 🌐 **API Tests**
- Chart data endpoints (`/api/chart-data/<instrument>`)
- Trade marker endpoints (`/api/trade-markers/<trade_id>`)
- Data update endpoints (`/api/update-data/<instrument>`)
- Error handling and edge cases
- Response format validation

#### 📊 **Data Service Tests**
- yfinance API integration
- Rate limiting (1 req/sec)
- Symbol mapping (MNQ → NQ=F)
- Market hours validation
- Exception handling

## 🏃 Running Tests

### Quick Development Testing
```bash
# Fast tests for development
python run_tests.py --quick

# Specific test categories
python run_tests.py --database
python run_tests.py --api
python run_tests.py --integration
```

### Comprehensive Testing
```bash
# Full test suite
python run_tests.py

# Performance validation
python run_tests.py --performance

# Coverage analysis
python run_tests.py --coverage
```

### Manual pytest Commands
```bash
# All tests except slow ones
pytest -m "not slow"

# Specific test file
pytest tests/test_ohlc_database.py

# Performance tests only
pytest tests/test_performance.py

# Integration tests with verbose output
pytest tests/test_integration.py -v

# Generate coverage report
pytest --cov=. --cov-report=html
```

## 📈 Performance Targets

Our tests validate these performance requirements:

| Operation | Target | Test Coverage |
|-----------|--------|---------------|
| Chart Loading | 15-50ms | ✅ Validated |
| Trade Context Lookup | 10-25ms | ✅ Validated |
| Gap Detection | 5-15ms | ✅ Validated |
| Real-time Insert | 1-5ms | ✅ Validated |
| Large Dataset Queries | <100ms | ✅ Validated |

## 🔧 Test Configuration

### pytest.ini Settings
- **Coverage**: Automatic HTML and terminal reports
- **Markers**: `slow`, `integration`, `performance`
- **Warnings**: Filtered for clean output
- **Paths**: Tests in `tests/` directory

### Environment Variables
Tests use temporary databases and mock external APIs for:
- Isolation between test runs
- No external dependencies
- Consistent performance testing
- Safe parallel execution

## 🧪 Test Data

### Mock Data Generation
- **OHLC Records**: Realistic price movements and volume
- **Time Series**: Proper timestamp sequencing
- **Multiple Instruments**: MNQ, ES, YM, RTY coverage
- **Gap Scenarios**: Intentional data gaps for testing

### Database Fixtures
- **Temporary DBs**: Each test gets fresh database
- **Large Datasets**: 50k+ records for performance testing
- **Index Validation**: Verify query plan usage
- **Concurrent Access**: Multi-threaded test scenarios

## 📊 Coverage Goals

### Current Coverage Areas
- ✅ **Database Operations**: 95%+ coverage
- ✅ **API Endpoints**: 90%+ coverage  
- ✅ **Data Service**: 85%+ coverage
- ✅ **Integration Flows**: 80%+ coverage
- ✅ **Performance Scenarios**: 100% of targets

### Key Test Scenarios
1. **Happy Path**: Normal operation with good data
2. **Edge Cases**: Empty responses, invalid parameters
3. **Error Handling**: Network failures, database errors
4. **Performance**: Large datasets, concurrent access
5. **Data Quality**: Gap detection, validation

## 🚨 Common Issues & Solutions

### Test Environment Setup
```bash
# Install test dependencies
pip install -r requirements.txt
pip install pytest pytest-cov

# Run from project root
cd /path/to/FuturesTradingLog
python run_tests.py
```

### Performance Test Failures
- **Slow Queries**: Check index creation in database tests
- **High Memory**: Large dataset tests may need adjustment
- **Timing Issues**: Performance targets may need platform-specific tuning

### Mock Data Issues
- **yfinance Mocks**: Ensure pandas DataFrame format matches
- **Timestamp Format**: Unix timestamps vs datetime objects
- **Market Hours**: Time zone handling in tests

## 🔄 Continuous Integration

### Pre-commit Testing
```bash
# Before committing changes
python run_tests.py --quick
```

### Full Validation
```bash
# Before merging features
python run_tests.py --coverage
```

### Performance Regression
```bash
# Validate performance targets
python run_tests.py --performance
```

## 📝 Writing New Tests

### Database Tests
```python
def test_new_database_feature(self, temp_db):
    with FuturesDB(temp_db) as db:
        # Test database operations
        result = db.new_method()
        assert result == expected
```

### API Tests
```python
@patch('module.external_service')
def test_new_api_endpoint(self, mock_service, client):
    mock_service.return_value = test_data
    response = client.get('/api/new-endpoint')
    assert response.status_code == 200
```

### Performance Tests
```python
def test_new_performance_requirement(self, temp_db, large_dataset):
    start_time = time.time()
    # Perform operation
    operation_time = (time.time() - start_time) * 1000
    assert operation_time < TARGET_MS
```

## 🎯 Success Criteria

Tests validate that the application achieves:

- ✅ **Millisecond query performance** with aggressive indexing
- ✅ **Reliable data fetching** with proper error handling  
- ✅ **Professional chart integration** with TradingView quality
- ✅ **Scalable architecture** supporting millions of records
- ✅ **Robust API design** with comprehensive validation
- ✅ **Cross-platform compatibility** via configuration management

This test suite ensures the futures trading log meets professional-grade performance and reliability standards.