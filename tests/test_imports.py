"""
Simple import tests that verify the basic structure is working
"""
import pytest
import sys
from pathlib import Path

def test_basic_imports():
    """Test that basic modules can be imported"""
    # Test config import
    try:
        import config
        assert hasattr(config, 'config')
    except ImportError as e:
        pytest.fail(f"Could not import config: {e}")
    
def test_database_import():
    """Test database module import"""
    try:
        from scripts.TradingLog_db import FuturesDB
        assert FuturesDB is not None
    except ImportError as e:
        pytest.fail(f"Could not import FuturesDB: {e}")

def test_utils_imports():
    """Test utility imports"""
    try:
        from utils.logging_config import setup_application_logging
        assert setup_application_logging is not None
    except ImportError as e:
        pytest.fail(f"Could not import logging utils: {e}")

def test_services_imports():
    """Test services imports"""
    try:
        from services.symbol_service import symbol_service
        assert symbol_service is not None
    except ImportError as e:
        pytest.fail(f"Could not import symbol_service: {e}")