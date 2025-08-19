"""
Ultra-simple tests that should always pass in CI environment
"""
import pytest
import os
import sys
from pathlib import Path

def test_python_version():
    """Test that we're running Python 3.11+"""
    assert sys.version_info >= (3, 11)

def test_project_structure():
    """Test that basic project files exist"""
    project_root = Path(__file__).parent.parent
    
    # Check essential files exist
    assert (project_root / "app.py").exists()
    assert (project_root / "config.py").exists()
    assert (project_root / "requirements.txt").exists()
    
    # Check essential directories exist
    assert (project_root / "scripts").is_dir()
    assert (project_root / "services").is_dir()
    assert (project_root / "routes").is_dir()
    assert (project_root / "tests").is_dir()

def test_requirements_file():
    """Test that requirements.txt is readable"""
    project_root = Path(__file__).parent.parent
    req_file = project_root / "requirements.txt"
    
    with open(req_file, 'r') as f:
        content = f.read()
    
    # Should contain Flask
    assert "flask" in content.lower()
    assert len(content.strip()) > 0

def test_basic_math():
    """Simple test to verify pytest is working"""
    assert 1 + 1 == 2
    assert 2 * 2 == 4