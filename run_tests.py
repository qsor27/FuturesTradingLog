#!/usr/bin/env python3
"""
Test runner script for Futures Trading Log
Provides convenient ways to run different test suites
"""
import sys
import os
import subprocess
import argparse
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle the output"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, shell=True, capture_output=False)
    return result.returncode == 0

def main():
    # Ensure we're running from the project root
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Set PYTHONPATH to include current directory for imports
    current_path = os.environ.get('PYTHONPATH', '')
    if current_path:
        os.environ['PYTHONPATH'] = f"{script_dir}:{current_path}"
    else:
        os.environ['PYTHONPATH'] = str(script_dir)
    
    parser = argparse.ArgumentParser(description='Run tests for Futures Trading Log')
    parser.add_argument('--quick', action='store_true', 
                       help='Run quick tests only (skip slow and integration tests)')
    parser.add_argument('--performance', action='store_true',
                       help='Run performance tests only')
    parser.add_argument('--integration', action='store_true',
                       help='Run integration tests only')
    parser.add_argument('--database', action='store_true',
                       help='Run database tests only')
    parser.add_argument('--api', action='store_true',
                       help='Run API tests only')
    parser.add_argument('--coverage', action='store_true',
                       help='Generate detailed coverage report')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Base pytest command
    pytest_cmd = "pytest"
    
    if args.verbose:
        pytest_cmd += " -v"
    
    success = True
    
    if args.quick:
        # Run quick tests only
        cmd = f'{pytest_cmd} -m "not slow" tests/test_app.py tests/test_ohlc_database.py'
        success &= run_command(cmd, "Quick Tests")
        
    elif args.performance:
        # Run performance tests only
        cmd = f'{pytest_cmd} tests/test_performance.py'
        success &= run_command(cmd, "Performance Tests")
        
    elif args.integration:
        # Run integration tests only
        cmd = f'{pytest_cmd} tests/test_integration.py'
        success &= run_command(cmd, "Integration Tests")
        
    elif args.database:
        # Run database tests only
        cmd = f'{pytest_cmd} tests/test_ohlc_database.py'
        success &= run_command(cmd, "Database Tests")
        
    elif args.api:
        # Run API tests only
        cmd = f'{pytest_cmd} tests/test_chart_api.py tests/test_data_service.py'
        success &= run_command(cmd, "API Tests")
        
    elif args.coverage:
        # Run full test suite with detailed coverage
        cmd = f'{pytest_cmd} --cov=. --cov-report=html --cov-report=term-missing -m "not slow"'
        success &= run_command(cmd, "Full Test Suite with Coverage")
        print("\nCoverage report generated in htmlcov/index.html")
        
    else:
        # Run default test suite
        print("Running comprehensive test suite...")
        print("Use --quick for faster testing during development")
        
        # 1. Basic functionality tests
        cmd = f'{pytest_cmd} tests/test_app.py'
        success &= run_command(cmd, "Basic App Tests")
        
        # 2. Database tests
        cmd = f'{pytest_cmd} tests/test_ohlc_database.py -m "not slow"'
        success &= run_command(cmd, "OHLC Database Tests")
        
        # 3. Data service tests
        cmd = f'{pytest_cmd} tests/test_data_service.py'
        success &= run_command(cmd, "Data Service Tests")
        
        # 4. API tests
        cmd = f'{pytest_cmd} tests/test_chart_api.py'
        success &= run_command(cmd, "Chart API Tests")
        
        # 5. Integration tests
        cmd = f'{pytest_cmd} tests/test_integration.py'
        success &= run_command(cmd, "Integration Tests")
        
        # 6. Performance tests (subset)
        cmd = f'{pytest_cmd} tests/test_performance.py::TestOHLCPerformance::test_performance_meets_targets'
        success &= run_command(cmd, "Performance Validation")
    
    # Summary
    print(f"\n{'='*60}")
    if success:
        print("✅ All tests completed successfully!")
    else:
        print("❌ Some tests failed. Check output above for details.")
    print(f"{'='*60}")
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())