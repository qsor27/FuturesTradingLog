"""
Test configuration and fixtures for Futures Trading Log
"""
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set environment for testing
os.environ['FLASK_ENV'] = 'testing'