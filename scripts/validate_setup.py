#!/usr/bin/env python3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.validation import validate_and_print

if __name__ == '__main__':
    success = validate_and_print()
    sys.exit(0 if success else 1)
