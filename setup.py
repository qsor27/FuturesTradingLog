#!/usr/bin/env python3
"""
Simple setup script for Futures Trading Log
Fixes the sqlite3 package issue and runs the full setup
"""

import sys
from pathlib import Path

# Add current directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent))

from scripts.setup_dev_environment import DevEnvironmentSetup

def main():
    """Main setup function"""
    print("Setting up Futures Trading Log development environment...")
    print("Note: sqlite3 is a built-in Python module, not a pip package")
    
    setup = DevEnvironmentSetup()
    
    # Run the setup
    success = setup.run_setup()
    
    if success:
        print("\n✅ Setup completed successfully!")
        print("\nTo get started:")
        print("1. source venv/bin/activate")
        print("2. python scripts/run_dev.py")
    else:
        print("\n❌ Setup failed. Please check the errors above.")
        sys.exit(1)

if __name__ == '__main__':
    main()