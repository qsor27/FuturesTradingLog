#!/usr/bin/env python3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from testing.test_strategy import TestStrategy

if __name__ == '__main__':
    strategy = TestStrategy()
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1]
        if test_type == 'dev':
            success = strategy.run_development_tests()
        elif test_type == 'ci':
            success = strategy.run_ci_tests()
        elif test_type == 'all':
            success = strategy.run_nightly_tests()
        else:
            print(f"Unknown test type: {test_type}")
            sys.exit(1)
    else:
        success = strategy.run_development_tests()
    
    sys.exit(0 if success else 1)
