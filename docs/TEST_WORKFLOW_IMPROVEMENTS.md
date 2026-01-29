# Test Workflow Improvements

## Summary

This document describes the improvements made to fix the GitHub Actions workflow timeout issue and improve test organization.

## Problem

The release workflow (run #21404057371) failed after running for 6 hours due to:
1. No timeout configured on the test step
2. Tests hanging in `python -m testing.test_strategy ci`
3. Background service tests with long sleeps (10s) running in the standard test suite
4. Integration/slow tests not properly separated from unit tests

## Solutions Implemented

### 1. Test Markers Added ✅

Added `@pytest.mark.integration` and `@pytest.mark.slow` markers to the following test files:

**Integration Tests:**
- `test_ninjatrader_background_service.py` (also marked as slow)
- `test_ninjatrader_end_to_end.py` (some classes marked as slow)
- `test_integration.py`
- `test_daily_ohlc_integration.py`
- `test_position_builder_validation_integration.py`
- `test_position_chart_javascript_integration.py`
- `test_file_update_detection.py`

These markers allow pytest to selectively run or exclude these tests using the `-m` flag.

### 2. Release Workflow Updated ✅

**File:** `.github/workflows/release.yml`

**Changes:**
- Added `timeout-minutes: 30` to the test step
- Simplified test execution from `python -m testing.test_strategy ci` to direct pytest
- Added marker exclusions: `-m "not slow and not integration"`
- Added fail-fast options: `--maxfail=5 -x`

**New test command:**
```bash
pytest tests/ -v --tb=short -m "not slow and not integration" --maxfail=5 -x
```

**Benefits:**
- Runs only unit tests (fast, reliable)
- Fails fast on errors
- Hard timeout prevents 6-hour hangs
- Simple, predictable execution

### 3. Integration Test Workflow Created ✅

**File:** `.github/workflows/integration-tests.yml`

**Features:**
- Runs on pull requests, manually, or nightly at 2 AM UTC
- 60-minute overall timeout
- 45-minute timeout for integration tests
- Runs slow tests only on nightly schedule
- Automatically comments on PR if tests fail
- Uploads test results as artifacts

**Trigger options:**
```bash
# Automatically on PR
# Manually via GitHub UI: Actions > Integration Tests > Run workflow
# Nightly at 2 AM UTC
```

**Test commands:**
```bash
# Integration tests (45 min timeout, each test max 300s)
pytest tests/ -v --tb=short -m "integration" --timeout=300 --maxfail=3

# Slow tests (only on nightly schedule)
pytest tests/ -v --tb=short -m "slow and not integration" --timeout=600 --maxfail=3
```

### 4. Test Strategy Improvements ✅

**File:** `testing/test_strategy.py`

**Improvements:**
1. **Overall timeout support** - prevents entire test suite from hanging
2. **Dynamic timeout adjustment** - remaining time allocated to subsequent tests
3. **New `run_integration_tests()` method** - dedicated integration test runner
4. **Updated `run_ci_tests()`** - now runs only unit tests (integration tests separate)
5. **Increased unit test timeout** - 600s instead of 300s for better reliability

**Usage:**
```bash
# CI tests (unit tests only, 15 min timeout)
python -m testing.test_strategy ci

# Integration tests (45 min timeout)
python -m testing.test_strategy integration

# Development tests (unit + smoke)
python -m testing.test_strategy dev

# Release tests (unit + integration + performance + regression)
python -m testing.test_strategy release

# Nightly tests (all tests)
python -m testing.test_strategy nightly
```

## Test Organization

### Unit Tests
- **Markers:** None or `-m "not slow and not integration"`
- **Timeout:** 10 minutes per test type
- **Parallel:** Yes (pytest-xdist -n auto)
- **When:** Every push to release tags
- **Where:** `.github/workflows/release.yml`

### Integration Tests
- **Markers:** `@pytest.mark.integration`
- **Timeout:** 45 minutes total, 5 minutes per test
- **Parallel:** No
- **When:** Pull requests, manual trigger, nightly
- **Where:** `.github/workflows/integration-tests.yml`

### Slow Tests
- **Markers:** `@pytest.mark.slow`
- **Timeout:** 30 minutes total, 10 minutes per test
- **Parallel:** Varies by test type
- **When:** Nightly schedule only
- **Where:** `.github/workflows/integration-tests.yml`

## Running Tests Locally

### Run unit tests only (fast)
```bash
pytest tests/ -v -m "not slow and not integration"
```

### Run integration tests
```bash
pytest tests/ -v -m "integration"
```

### Run slow tests
```bash
pytest tests/ -v -m "slow"
```

### Run all tests
```bash
pytest tests/ -v
```

### Run specific test file
```bash
pytest tests/test_app.py -v
```

### Run with coverage
```bash
pytest tests/ -v --cov=. --cov-report=html
```

## Benefits

1. **Reliability:** Hard timeouts prevent infinite hangs
2. **Speed:** Unit tests run faster without integration tests
3. **Clarity:** Clear separation between test types
4. **Flexibility:** Can run test types independently
5. **Cost:** Reduced CI minutes by running integration tests separately
6. **Feedback:** Faster feedback on unit tests, detailed integration test results

## Troubleshooting

### Tests timing out?
- Check if tests are properly marked with `@pytest.mark.slow` or `@pytest.mark.integration`
- Review test logs to identify which test is hanging
- Consider mocking time-consuming operations in unit tests

### Integration tests failing in CI?
- Check the integration-tests workflow logs
- Ensure Redis service is healthy
- Verify file permissions in temporary directories
- Check for race conditions in background service tests

### Release workflow still timing out?
- Verify tests are excluded with `-m "not slow and not integration"`
- Check for unmarked slow/integration tests
- Review test execution time in logs

## Next Steps

Consider these additional improvements:

1. Add `@pytest.mark.performance` to performance tests
2. Create a smoke test suite for quick validation
3. Add test result reporting to Slack/Discord
4. Implement test quarantine for flaky tests
5. Add parallel execution for integration tests where safe
