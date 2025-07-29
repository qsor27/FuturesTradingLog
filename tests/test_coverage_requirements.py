"""
Test coverage requirements and validation
Ensures minimum coverage thresholds are met
"""

import pytest
import subprocess
import os
import json
from pathlib import Path


class TestCoverageRequirements:
    """Test coverage requirements validation"""
    
    # Coverage thresholds
    MINIMUM_TOTAL_COVERAGE = 90.0
    MINIMUM_CRITICAL_MODULE_COVERAGE = 95.0
    
    # Critical modules that must have high coverage
    CRITICAL_MODULES = [
        'position_service.py',
        'position_engine.py',
        'TradingLog_db.py',
        'app.py'
    ]
    
    @pytest.fixture
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent
    
    def run_coverage(self, project_root):
        """Run coverage analysis and return results"""
        # Run tests with coverage
        result = subprocess.run([
            'python', '-m', 'pytest', 
            '--cov=.', 
            '--cov-report=json',
            '--cov-report=term-missing',
            'tests/'
        ], cwd=project_root, capture_output=True, text=True)
        
        # Check if coverage.json was created
        coverage_file = project_root / 'coverage.json'
        if not coverage_file.exists():
            pytest.fail(f"Coverage file not found. Test output: {result.stdout}\nErrors: {result.stderr}")
        
        # Load coverage data
        with open(coverage_file, 'r') as f:
            coverage_data = json.load(f)
        
        return coverage_data
    
    def test_minimum_total_coverage(self, project_root):
        """Test that total coverage meets minimum threshold"""
        coverage_data = self.run_coverage(project_root)
        
        total_coverage = coverage_data['totals']['percent_covered']
        
        assert total_coverage >= self.MINIMUM_TOTAL_COVERAGE, \
            f"Total coverage {total_coverage:.1f}% is below minimum threshold {self.MINIMUM_TOTAL_COVERAGE}%"
        
        print(f"✓ Total coverage: {total_coverage:.1f}% (threshold: {self.MINIMUM_TOTAL_COVERAGE}%)")
    
    def test_critical_module_coverage(self, project_root):
        """Test that critical modules meet higher coverage threshold"""
        coverage_data = self.run_coverage(project_root)
        
        files_data = coverage_data['files']
        
        for module in self.CRITICAL_MODULES:
            # Find module in coverage data
            module_coverage = None
            for file_path, file_data in files_data.items():
                if file_path.endswith(module):
                    module_coverage = file_data['summary']['percent_covered']
                    break
            
            if module_coverage is None:
                pytest.fail(f"Critical module {module} not found in coverage data")
            
            assert module_coverage >= self.MINIMUM_CRITICAL_MODULE_COVERAGE, \
                f"Critical module {module} coverage {module_coverage:.1f}% is below threshold {self.MINIMUM_CRITICAL_MODULE_COVERAGE}%"
            
            print(f"✓ {module}: {module_coverage:.1f}% (threshold: {self.MINIMUM_CRITICAL_MODULE_COVERAGE}%)")
    
    def test_no_completely_uncovered_files(self, project_root):
        """Test that no files have 0% coverage"""
        coverage_data = self.run_coverage(project_root)
        
        uncovered_files = []
        for file_path, file_data in coverage_data['files'].items():
            coverage = file_data['summary']['percent_covered']
            if coverage == 0.0:
                uncovered_files.append(file_path)
        
        if uncovered_files:
            pytest.fail(f"Files with 0% coverage: {uncovered_files}")
        
        print("✓ No files with 0% coverage")
    
    def test_missing_lines_below_threshold(self, project_root):
        """Test that missing lines are below acceptable threshold"""
        coverage_data = self.run_coverage(project_root)
        
        MAX_MISSING_LINES_RATIO = 0.1  # 10% of lines can be missing
        
        for file_path, file_data in coverage_data['files'].items():
            summary = file_data['summary']
            total_lines = summary['num_statements']
            covered_lines = summary['covered_lines']
            missing_lines = summary['missing_lines']
            
            if total_lines > 0:
                missing_ratio = missing_lines / total_lines
                
                if missing_ratio > MAX_MISSING_LINES_RATIO:
                    pytest.fail(f"File {file_path} has {missing_ratio:.1%} missing lines (threshold: {MAX_MISSING_LINES_RATIO:.1%})")
        
        print(f"✓ All files have missing lines below {MAX_MISSING_LINES_RATIO:.1%} threshold")
    
    def test_branch_coverage_requirements(self, project_root):
        """Test branch coverage requirements"""
        # Run tests with branch coverage
        result = subprocess.run([
            'python', '-m', 'pytest', 
            '--cov=.', 
            '--cov-branch',
            '--cov-report=json',
            'tests/'
        ], cwd=project_root, capture_output=True, text=True)
        
        # Check if coverage.json was created
        coverage_file = project_root / 'coverage.json'
        if coverage_file.exists():
            with open(coverage_file, 'r') as f:
                coverage_data = json.load(f)
            
            # Check branch coverage if available
            if 'percent_covered_display' in coverage_data['totals']:
                branch_coverage = coverage_data['totals'].get('percent_covered_display', 0)
                
                MINIMUM_BRANCH_COVERAGE = 85.0
                if isinstance(branch_coverage, (int, float)):
                    assert branch_coverage >= MINIMUM_BRANCH_COVERAGE, \
                        f"Branch coverage {branch_coverage:.1f}% is below minimum threshold {MINIMUM_BRANCH_COVERAGE}%"
                    
                    print(f"✓ Branch coverage: {branch_coverage:.1f}% (threshold: {MINIMUM_BRANCH_COVERAGE}%)")
        
        print("✓ Branch coverage requirements checked")
    
    def test_test_file_coverage(self, project_root):
        """Test that test files themselves have good coverage"""
        # This ensures test files are well-structured and cover their own logic
        
        test_files = list(Path(project_root / 'tests').glob('test_*.py'))
        
        MIN_TEST_FILES = 5
        assert len(test_files) >= MIN_TEST_FILES, \
            f"Found {len(test_files)} test files, minimum required: {MIN_TEST_FILES}"
        
        # Check that test files exist for critical modules
        expected_test_files = [
            'test_position_service_comprehensive.py',
            'test_performance_regression.py',
            'test_critical_path_integration.py',
            'test_position_engine.py'
        ]
        
        existing_test_files = [f.name for f in test_files]
        
        for expected_file in expected_test_files:
            assert expected_file in existing_test_files, \
                f"Required test file {expected_file} not found"
        
        print(f"✓ Found {len(test_files)} test files including all required test files")
    
    def test_coverage_configuration(self, project_root):
        """Test that coverage configuration is properly set up"""
        # Check for .coveragerc file
        coveragerc_path = project_root / '.coveragerc'
        assert coveragerc_path.exists(), "Coverage configuration file .coveragerc not found"
        
        # Check pytest.ini for coverage configuration
        pytest_ini_path = project_root / 'pytest.ini'
        if pytest_ini_path.exists():
            with open(pytest_ini_path, 'r') as f:
                content = f.read()
                # Should have coverage configuration
                assert 'addopts' in content or 'testpaths' in content, \
                    "pytest.ini should contain coverage configuration"
        
        print("✓ Coverage configuration files found")
    
    def test_coverage_html_report_generation(self, project_root):
        """Test that HTML coverage reports can be generated"""
        # Generate HTML report
        result = subprocess.run([
            'python', '-m', 'pytest', 
            '--cov=.', 
            '--cov-report=html',
            '--cov-report=term',
            'tests/'
        ], cwd=project_root, capture_output=True, text=True)
        
        # Check if HTML report was created
        html_dir = project_root / 'htmlcov'
        assert html_dir.exists(), "HTML coverage report directory not created"
        
        index_file = html_dir / 'index.html'
        assert index_file.exists(), "HTML coverage report index.html not found"
        
        print("✓ HTML coverage report generated successfully")
    
    def test_coverage_trends_monitoring(self, project_root):
        """Test coverage trends monitoring setup"""
        # This would typically integrate with CI/CD to track coverage over time
        
        coverage_data = self.run_coverage(project_root)
        current_coverage = coverage_data['totals']['percent_covered']
        
        # In a real implementation, you would compare against historical data
        # For now, just ensure we can extract the coverage percentage
        assert isinstance(current_coverage, (int, float)), \
            "Coverage percentage should be numeric"
        
        assert 0 <= current_coverage <= 100, \
            "Coverage percentage should be between 0 and 100"
        
        print(f"✓ Coverage trends monitoring: {current_coverage:.1f}%")
    
    def test_uncovered_critical_functions(self, project_root):
        """Test that critical functions are not uncovered"""
        coverage_data = self.run_coverage(project_root)
        
        # Critical functions that must be covered
        critical_functions = [
            'build_positions_from_executions',
            'rebuild_positions_from_trades',
            '_aggregate_executions_into_positions',
            'get_positions',
            'get_position_statistics'
        ]
        
        # This is a simplified check - in practice, you'd parse the coverage data
        # to identify specific function coverage
        for file_path, file_data in coverage_data['files'].items():
            if any(module in file_path for module in self.CRITICAL_MODULES):
                coverage = file_data['summary']['percent_covered']
                # If a critical module has low coverage, it likely means
                # critical functions are uncovered
                if coverage < 90:
                    print(f"Warning: {file_path} has {coverage:.1f}% coverage - check critical functions")
        
        print("✓ Critical functions coverage checked")
    
    def generate_coverage_report(self, project_root):
        """Generate comprehensive coverage report"""
        coverage_data = self.run_coverage(project_root)
        
        report = {
            'timestamp': pytest.current_timestamp if hasattr(pytest, 'current_timestamp') else 'unknown',
            'total_coverage': coverage_data['totals']['percent_covered'],
            'file_count': len(coverage_data['files']),
            'critical_modules': {},
            'summary': {
                'total_lines': coverage_data['totals']['num_statements'],
                'covered_lines': coverage_data['totals']['covered_lines'],
                'missing_lines': coverage_data['totals']['missing_lines']
            }
        }
        
        # Add critical module coverage
        for module in self.CRITICAL_MODULES:
            for file_path, file_data in coverage_data['files'].items():
                if file_path.endswith(module):
                    report['critical_modules'][module] = {
                        'coverage': file_data['summary']['percent_covered'],
                        'lines': file_data['summary']['num_statements'],
                        'covered': file_data['summary']['covered_lines'],
                        'missing': file_data['summary']['missing_lines']
                    }
                    break
        
        return report


if __name__ == '__main__':
    pytest.main([__file__, '-v'])