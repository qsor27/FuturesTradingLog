"""
Unified testing strategy and test runner
Provides consistent testing approach across all test types
"""

import pytest
import os
import sys
import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TestType(Enum):
    """Types of tests"""
    UNIT = "unit"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    COVERAGE = "coverage"
    SMOKE = "smoke"
    REGRESSION = "regression"
    SECURITY = "security"
    API = "api"
    DATABASE = "database"
    ALL = "all"


@dataclass
class TestResult:
    """Result of a test run"""
    test_type: TestType
    passed: bool
    duration: float
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    coverage_percent: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    output: Optional[str] = None
    errors: List[str] = None


class TestRunner:
    """Unified test runner for all test types"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.results: Dict[TestType, TestResult] = {}
        
        # Test configurations
        self.test_configs = {
            TestType.UNIT: {
                'paths': ['tests/test_*.py'],
                'exclude': ['tests/test_performance_*.py', 'tests/test_*_integration.py', 'tests/test_critical_path_*.py'],
                'markers': '-m "not slow and not integration and not performance"',
                'timeout': 300,  # 5 minutes
                'parallel': True
            },
            TestType.INTEGRATION: {
                'paths': ['tests/test_*_integration.py', 'tests/test_critical_path_*.py'],
                'exclude': [],
                'markers': '-m "integration"',
                'timeout': 600,  # 10 minutes
                'parallel': False
            },
            TestType.PERFORMANCE: {
                'paths': ['tests/test_performance_*.py'],
                'exclude': [],
                'markers': '-m "performance"',
                'timeout': 900,  # 15 minutes
                'parallel': False
            },
            TestType.COVERAGE: {
                'paths': ['tests/'],
                'exclude': [],
                'markers': '',
                'timeout': 600,  # 10 minutes
                'parallel': True,
                'coverage': True
            },
            TestType.SMOKE: {
                'paths': ['tests/test_smoke_*.py'],
                'exclude': [],
                'markers': '-m "smoke"',
                'timeout': 120,  # 2 minutes
                'parallel': True
            },
            TestType.REGRESSION: {
                'paths': ['tests/test_*_regression.py'],
                'exclude': [],
                'markers': '-m "regression"',
                'timeout': 1800,  # 30 minutes
                'parallel': False
            },
            TestType.API: {
                'paths': ['tests/test_api_*.py'],
                'exclude': [],
                'markers': '-m "api"',
                'timeout': 300,  # 5 minutes
                'parallel': True
            },
            TestType.DATABASE: {
                'paths': ['tests/test_*_db.py', 'tests/test_database_*.py'],
                'exclude': [],
                'markers': '-m "database"',
                'timeout': 300,  # 5 minutes
                'parallel': False
            }
        }
    
    def run_tests(self, test_types: List[TestType], 
                  verbose: bool = False,
                  fail_fast: bool = False,
                  parallel: bool = None,
                  output_file: Optional[Path] = None) -> Dict[TestType, TestResult]:
        """Run specified test types"""
        if TestType.ALL in test_types:
            test_types = [t for t in TestType if t != TestType.ALL]
        
        self.results = {}
        
        for test_type in test_types:
            logger.info(f"Running {test_type.value} tests...")
            
            result = self._run_single_test_type(
                test_type,
                verbose=verbose,
                fail_fast=fail_fast,
                parallel=parallel
            )
            
            self.results[test_type] = result
            
            if fail_fast and not result.passed:
                logger.error(f"{test_type.value} tests failed, stopping due to fail_fast")
                break
        
        if output_file:
            self._save_results(output_file)
        
        return self.results
    
    def _run_single_test_type(self, test_type: TestType, 
                             verbose: bool = False,
                             fail_fast: bool = False,
                             parallel: bool = None) -> TestResult:
        """Run a single test type"""
        config = self.test_configs[test_type]
        
        # Build pytest command
        cmd = ['python', '-m', 'pytest']
        
        # Add paths
        for path in config['paths']:
            if (self.project_root / path).exists():
                cmd.append(path)
        
        # Add exclusions
        for exclude in config['exclude']:
            cmd.extend(['--ignore', exclude])
        
        # Add markers
        if config['markers']:
            cmd.append(config['markers'])
        
        # Add coverage if required
        if config.get('coverage', False):
            cmd.extend(['--cov=.', '--cov-report=json', '--cov-report=term-missing'])
        
        # Add verbosity
        if verbose:
            cmd.append('-v')
        
        # Add fail fast
        if fail_fast:
            cmd.append('-x')
        
        # Add parallel execution
        use_parallel = parallel if parallel is not None else config.get('parallel', False)
        if use_parallel:
            cmd.extend(['-n', 'auto'])
        
        # Add JSON output
        cmd.extend(['--json-report', '--json-report-file=test_results.json'])
        
        # Add timeout
        timeout = config.get('timeout', 300)
        
        # Run tests
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            duration = time.time() - start_time
            
            # Parse results
            return self._parse_test_result(test_type, result, duration, config)
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return TestResult(
                test_type=test_type,
                passed=False,
                duration=duration,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                errors=[f"Tests timed out after {timeout} seconds"]
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_type=test_type,
                passed=False,
                duration=duration,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                errors=[f"Test execution failed: {str(e)}"]
            )
    
    def _parse_test_result(self, test_type: TestType, 
                          result: subprocess.CompletedProcess,
                          duration: float,
                          config: Dict[str, Any]) -> TestResult:
        """Parse test result from subprocess output"""
        # Parse JSON report if available
        json_report_path = self.project_root / 'test_results.json'
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        coverage_percent = None
        details = {}
        
        if json_report_path.exists():
            try:
                with open(json_report_path, 'r') as f:
                    json_data = json.load(f)
                
                summary = json_data.get('summary', {})
                total_tests = summary.get('total', 0)
                passed_tests = summary.get('passed', 0)
                failed_tests = summary.get('failed', 0)
                skipped_tests = summary.get('skipped', 0)
                
                details = {
                    'duration': json_data.get('duration', duration),
                    'tests': json_data.get('tests', [])
                }
                
                # Clean up
                json_report_path.unlink()
                
            except (json.JSONDecodeError, IOError):
                pass
        
        # Parse coverage if available
        if config.get('coverage', False):
            coverage_file = self.project_root / 'coverage.json'
            if coverage_file.exists():
                try:
                    with open(coverage_file, 'r') as f:
                        coverage_data = json.load(f)
                    coverage_percent = coverage_data.get('totals', {}).get('percent_covered', 0)
                except (json.JSONDecodeError, IOError):
                    pass
        
        # Parse errors from output
        errors = []
        if result.returncode != 0:
            errors.append(f"Tests failed with return code {result.returncode}")
            if result.stderr:
                errors.append(result.stderr)
        
        return TestResult(
            test_type=test_type,
            passed=result.returncode == 0,
            duration=duration,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            coverage_percent=coverage_percent,
            details=details,
            output=result.stdout,
            errors=errors
        )
    
    def _save_results(self, output_file: Path):
        """Save test results to file"""
        results_data = {}
        
        for test_type, result in self.results.items():
            results_data[test_type.value] = {
                'passed': result.passed,
                'duration': result.duration,
                'total_tests': result.total_tests,
                'passed_tests': result.passed_tests,
                'failed_tests': result.failed_tests,
                'skipped_tests': result.skipped_tests,
                'coverage_percent': result.coverage_percent,
                'errors': result.errors,
                'details': result.details
            }
        
        with open(output_file, 'w') as f:
            json.dump(results_data, f, indent=2)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all test results"""
        if not self.results:
            return {}
        
        total_tests = sum(r.total_tests for r in self.results.values())
        total_passed = sum(r.passed_tests for r in self.results.values())
        total_failed = sum(r.failed_tests for r in self.results.values())
        total_skipped = sum(r.skipped_tests for r in self.results.values())
        total_duration = sum(r.duration for r in self.results.values())
        
        all_passed = all(r.passed for r in self.results.values())
        
        # Get coverage from coverage tests
        coverage_percent = None
        for test_type, result in self.results.items():
            if result.coverage_percent is not None:
                coverage_percent = result.coverage_percent
                break
        
        return {
            'overall_passed': all_passed,
            'total_tests': total_tests,
            'total_passed': total_passed,
            'total_failed': total_failed,
            'total_skipped': total_skipped,
            'total_duration': total_duration,
            'coverage_percent': coverage_percent,
            'test_types_run': len(self.results),
            'success_rate': (total_passed / total_tests * 100) if total_tests > 0 else 0,
            'results_by_type': {
                test_type.value: {
                    'passed': result.passed,
                    'tests': result.total_tests,
                    'duration': result.duration
                }
                for test_type, result in self.results.items()
            }
        }
    
    def print_summary(self):
        """Print test summary to console"""
        summary = self.get_summary()
        
        print("\n" + "="*60)
        print("TEST EXECUTION SUMMARY")
        print("="*60)
        
        if not summary:
            print("No tests were run.")
            return
        
        print(f"Overall Status: {'PASS' if summary['overall_passed'] else 'FAIL'}")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['total_passed']}")
        print(f"Failed: {summary['total_failed']}")
        print(f"Skipped: {summary['total_skipped']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        print(f"Total Duration: {summary['total_duration']:.2f} seconds")
        
        if summary['coverage_percent'] is not None:
            print(f"Coverage: {summary['coverage_percent']:.1f}%")
        
        print(f"Test Types Run: {summary['test_types_run']}")
        
        print("\nResults by Test Type:")
        print("-" * 60)
        
        for test_type, result in self.results.items():
            status = "PASS" if result.passed else "FAIL"
            print(f"{test_type.value:<15} {status:<6} {result.total_tests:>4} tests  {result.duration:>6.2f}s")
            
            if result.errors:
                for error in result.errors:
                    print(f"  Error: {error}")
        
        print("="*60)


class TestStrategy:
    """Test strategy configuration and execution"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.runner = TestRunner(project_root)
    
    def run_development_tests(self) -> bool:
        """Run tests for development workflow"""
        test_types = [TestType.UNIT, TestType.SMOKE]
        results = self.runner.run_tests(test_types, verbose=True, fail_fast=True)
        
        self.runner.print_summary()
        return all(r.passed for r in results.values())
    
    def run_ci_tests(self) -> bool:
        """Run tests for CI/CD pipeline"""
        test_types = [TestType.UNIT, TestType.INTEGRATION, TestType.COVERAGE]
        results = self.runner.run_tests(test_types, verbose=True, fail_fast=True)
        
        self.runner.print_summary()
        
        # Check coverage threshold
        coverage_result = results.get(TestType.COVERAGE)
        if coverage_result and coverage_result.coverage_percent is not None:
            if coverage_result.coverage_percent < 90:
                print(f"Coverage {coverage_result.coverage_percent:.1f}% is below threshold (90%)")
                return False
        
        return all(r.passed for r in results.values())
    
    def run_release_tests(self) -> bool:
        """Run tests for release validation"""
        test_types = [TestType.UNIT, TestType.INTEGRATION, TestType.PERFORMANCE, TestType.REGRESSION]
        results = self.runner.run_tests(test_types, verbose=True, fail_fast=False)
        
        self.runner.print_summary()
        return all(r.passed for r in results.values())
    
    def run_nightly_tests(self) -> bool:
        """Run comprehensive nightly tests"""
        test_types = [TestType.ALL]
        results = self.runner.run_tests(test_types, verbose=True, fail_fast=False)
        
        # Save results to file
        results_file = self.project_root / 'test_results_nightly.json'
        self.runner._save_results(results_file)
        
        self.runner.print_summary()
        return all(r.passed for r in results.values())
    
    def run_performance_baseline(self) -> bool:
        """Run performance tests to establish baseline"""
        test_types = [TestType.PERFORMANCE]
        results = self.runner.run_tests(test_types, verbose=True, fail_fast=False)
        
        # Save performance baseline
        baseline_file = self.project_root / 'performance_baseline.json'
        self.runner._save_results(baseline_file)
        
        self.runner.print_summary()
        return all(r.passed for r in results.values())
    
    def validate_test_environment(self) -> bool:
        """Validate test environment setup"""
        from config.validation import validate_configuration
        
        # Validate configuration
        config_valid, _ = validate_configuration()
        if not config_valid:
            print("Configuration validation failed")
            return False
        
        # Check test dependencies
        required_packages = ['pytest', 'pytest-cov', 'pytest-xdist', 'pytest-json-report']
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            print(f"Missing test dependencies: {missing_packages}")
            print("Install with: pip install " + " ".join(missing_packages))
            return False
        
        # Check test files exist
        test_files = list(self.project_root.glob('tests/test_*.py'))
        if len(test_files) < 5:
            print(f"Only {len(test_files)} test files found, expected at least 5")
            return False
        
        print("Test environment validation passed")
        return True
    
    def create_test_markers(self):
        """Create pytest markers configuration"""
        markers_content = """
[tool:pytest]
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    performance: marks tests as performance tests
    smoke: marks tests as smoke tests
    regression: marks tests as regression tests
    api: marks tests as API tests
    database: marks tests as database tests
    security: marks tests as security tests
"""
        
        setup_cfg = self.project_root / 'setup.cfg'
        if not setup_cfg.exists():
            with open(setup_cfg, 'w') as f:
                f.write(markers_content)
        
        # Also create pytest.ini
        pytest_ini_content = """[pytest]
addopts = 
    -ra
    --strict-markers
    --strict-config
    --cov-report=term-missing
    --cov-report=html
    --cov-report=xml
    --cov-fail-under=90
    --json-report
    --json-report-file=tests/results.json

markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    performance: marks tests as performance tests
    smoke: marks tests as smoke tests
    regression: marks tests as regression tests
    api: marks tests as API tests
    database: marks tests as database tests
    security: marks tests as security tests

testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
"""
        
        pytest_ini = self.project_root / 'pytest.ini'
        if not pytest_ini.exists():
            with open(pytest_ini, 'w') as f:
                f.write(pytest_ini_content)
        
        print("Test markers configuration created")


def main():
    """CLI interface for test strategy"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Unified test runner')
    parser.add_argument('strategy', choices=['dev', 'ci', 'release', 'nightly', 'performance', 'validate'],
                       help='Test strategy to run')
    parser.add_argument('--project-root', type=Path, help='Project root directory')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    strategy = TestStrategy(args.project_root)
    
    if args.strategy == 'dev':
        success = strategy.run_development_tests()
    elif args.strategy == 'ci':
        success = strategy.run_ci_tests()
    elif args.strategy == 'release':
        success = strategy.run_release_tests()
    elif args.strategy == 'nightly':
        success = strategy.run_nightly_tests()
    elif args.strategy == 'performance':
        success = strategy.run_performance_baseline()
    elif args.strategy == 'validate':
        success = strategy.validate_test_environment()
        strategy.create_test_markers()
    else:
        print(f"Unknown strategy: {args.strategy}")
        sys.exit(1)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()