import os
from pathlib import Path
import shutil
import json

def setup_data_directory(data_dir: str = None):
    """
    Set up the data directory structure and copy necessary files
    """
    if data_dir is None:
        # Use environment variable or cross-platform default
        data_dir = os.getenv('DATA_DIR', str(Path.home() / 'FuturesTradingLog' / 'data'))
    
    data_dir = Path(data_dir)
    
    # Create main directories
    directories = [
        data_dir / 'db',
        data_dir / 'config',
        data_dir / 'charts',
        data_dir / 'logs',
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")

    # Copy instrument_multipliers.json to config directory if it exists
    source_config = Path(__file__).parent.parent / 'instrument_multipliers.json'
    if source_config.exists():
        dest_config = data_dir / 'config' / 'instrument_multipliers.json'
        if not dest_config.exists():
            shutil.copy2(source_config, dest_config)
            print(f"Copied {source_config} to {dest_config}")

if __name__ == '__main__':
    setup_data_directory()