"""
Test configuration and fixtures for Futures Trading Log
"""
import sys
import os
import tempfile
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set test environment with temp directory for data
temp_dir = tempfile.mkdtemp()
os.environ['DATA_DIR'] = temp_dir
os.environ['FLASK_ENV'] = 'test_local'  # Use a different value to avoid Docker path