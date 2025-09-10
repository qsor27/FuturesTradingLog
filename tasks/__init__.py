"""
Celery tasks package

Contains all background task definitions organized by domain.
"""

try:
    from .position_building import *
except ImportError as e:
    print(f"Warning: Could not import position_building tasks: {e}")

try:
    from .file_processing import *
except ImportError as e:
    print(f"Warning: Could not import file_processing tasks: {e}")

try:
    from .gap_filling import *
except ImportError as e:
    print(f"Warning: Could not import gap_filling tasks: {e}")

try:
    from .cache_maintenance import *
except ImportError as e:
    print(f"Warning: Could not import cache_maintenance tasks: {e}")