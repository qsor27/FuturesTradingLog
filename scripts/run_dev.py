#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set environment
os.environ['FLASK_ENV'] = 'development'
os.environ['FLASK_DEBUG'] = 'true'

# Run the application
from app import create_app
from config.environments import get_config

config = get_config()
app = create_app(config)

if __name__ == '__main__':
    app.run(
        host=config.host,
        port=config.port,
        debug=config.debug
    )
