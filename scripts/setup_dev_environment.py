#!/usr/bin/env python3
"""
Development environment setup script
Automatically sets up a complete development environment for the Futures Trading Log
"""

import os
import sys
import subprocess
import shutil
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DevEnvironmentSetup:
    """Development environment setup manager"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.venv_path = self.project_root / 'venv'
        self.data_dir = self.project_root / 'data'
        self.config_dir = self.data_dir / 'config'
        
        # Required system packages
        self.system_packages = {
            'ubuntu': ['python3-venv', 'python3-pip', 'redis-server', 'sqlite3', 'git'],
            'macos': ['python3', 'redis', 'sqlite3', 'git'],
            'windows': ['python', 'redis', 'sqlite3', 'git']
        }
        
        # Required Python packages
        self.python_packages = [
            'flask>=2.0.0',
            'redis>=4.0.0',
            'pandas>=1.3.0',
            'numpy>=1.20.0',
            'yfinance>=0.1.70',
            'pytest>=6.0.0',
            'pytest-cov>=2.12.0',
            'pytest-xdist>=2.4.0',
            'pytest-json-report>=1.5.0',
            'flake8>=4.0.0',
            'black>=22.0.0',
            'isort>=5.10.0',
            'mypy>=0.910'
        ]
        
        # Development tools
        self.dev_tools = [
            'pre-commit>=2.15.0',
            'bandit>=1.7.0',
            'safety>=1.10.0',
            'jupyterlab>=3.2.0'
        ]
    
    def detect_system(self) -> str:
        """Detect the operating system"""
        system = sys.platform.lower()
        
        if system.startswith('linux'):
            return 'ubuntu'
        elif system.startswith('darwin'):
            return 'macos'
        elif system.startswith('win'):
            return 'windows'
        else:
            logger.warning(f"Unknown system: {system}, defaulting to ubuntu")
            return 'ubuntu'
    
    def check_prerequisites(self) -> List[str]:
        """Check for prerequisites and return list of missing items"""
        missing = []
        
        # Check Python version
        if sys.version_info < (3, 8):
            missing.append(f"Python 3.8+ required, found {sys.version_info.major}.{sys.version_info.minor}")
        
        # Check Git
        if not shutil.which('git'):
            missing.append("Git is not installed")
        
        # Check pip
        if not shutil.which('pip') and not shutil.which('pip3'):
            missing.append("pip is not installed")
        
        return missing
    
    def install_system_packages(self) -> bool:
        """Install required system packages"""
        system = self.detect_system()
        packages = self.system_packages.get(system, [])
        
        if not packages:
            logger.info("No system packages to install")
            return True
        
        logger.info(f"Installing system packages for {system}: {packages}")
        
        try:
            if system == 'ubuntu':
                subprocess.run(['sudo', 'apt-get', 'update'], check=True)
                subprocess.run(['sudo', 'apt-get', 'install', '-y'] + packages, check=True)
            elif system == 'macos':
                # Check if Homebrew is installed
                if not shutil.which('brew'):
                    logger.error("Homebrew is not installed. Please install it first: https://brew.sh/")
                    return False
                subprocess.run(['brew', 'install'] + packages, check=True)
            elif system == 'windows':
                logger.warning("Windows package installation not automated. Please install manually:")
                for package in packages:
                    logger.warning(f"  - {package}")
                return True
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install system packages: {e}")
            return False
    
    def create_virtual_environment(self) -> bool:
        """Create Python virtual environment"""
        logger.info(f"Creating virtual environment at {self.venv_path}")
        
        try:
            if self.venv_path.exists():
                logger.info("Virtual environment already exists, recreating...")
                shutil.rmtree(self.venv_path)
            
            subprocess.run([sys.executable, '-m', 'venv', str(self.venv_path)], check=True)
            
            # Get the correct Python executable path
            if sys.platform.startswith('win'):
                python_exe = self.venv_path / 'Scripts' / 'python.exe'
                pip_exe = self.venv_path / 'Scripts' / 'pip.exe'
            else:
                python_exe = self.venv_path / 'bin' / 'python'
                pip_exe = self.venv_path / 'bin' / 'pip'
            
            # Upgrade pip
            subprocess.run([str(pip_exe), 'install', '--upgrade', 'pip'], check=True)
            
            self.python_exe = python_exe
            self.pip_exe = pip_exe
            
            logger.info("Virtual environment created successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create virtual environment: {e}")
            return False
    
    def install_python_packages(self) -> bool:
        """Install Python packages"""
        logger.info("Installing Python packages...")
        
        try:
            # Install production packages
            all_packages = self.python_packages + self.dev_tools
            
            subprocess.run([
                str(self.pip_exe), 'install', '--upgrade'
            ] + all_packages, check=True)
            
            # Install from requirements.txt if it exists
            requirements_file = self.project_root / 'requirements.txt'
            if requirements_file.exists():
                logger.info("Installing from requirements.txt")
                subprocess.run([
                    str(self.pip_exe), 'install', '-r', str(requirements_file)
                ], check=True)
            
            logger.info("Python packages installed successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install Python packages: {e}")
            return False
    
    def setup_project_structure(self) -> bool:
        """Set up project directory structure"""
        logger.info("Setting up project structure...")
        
        try:
            # Create required directories
            directories = [
                self.data_dir,
                self.data_dir / 'db',
                self.data_dir / 'config',
                self.data_dir / 'logs',
                self.data_dir / 'charts',
                self.data_dir / 'archive',
                self.project_root / 'tests',
                self.project_root / 'config',
                self.project_root / 'scripts',
                self.project_root / 'docs'
            ]
            
            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created directory: {directory}")
            
            # Create configuration files
            self.create_configuration_files()
            
            # Create .gitignore
            self.create_gitignore()
            
            # Create development scripts
            self.create_development_scripts()
            
            logger.info("Project structure set up successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set up project structure: {e}")
            return False
    
    def create_configuration_files(self):
        """Create default configuration files"""
        logger.info("Creating configuration files...")
        
        # Create instrument multipliers
        multipliers = {
            'ES': 50.0,
            'NQ': 20.0,
            'YM': 5.0,
            'RTY': 50.0,
            'CL': 1000.0,
            'GC': 100.0,
            'SI': 5000.0
        }
        
        multipliers_file = self.config_dir / 'instrument_multipliers.json'
        with open(multipliers_file, 'w') as f:
            json.dump(multipliers, f, indent=2)
        
        # Create development environment file
        env_file = self.project_root / '.env.development'
        env_content = """
# Development environment configuration
FLASK_ENV=development
FLASK_DEBUG=true
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_SECRET_KEY=dev-secret-key-change-in-production

# Data directory
DATA_DIR=./data

# Redis configuration
REDIS_URL=redis://localhost:6379/0
CACHE_ENABLED=true
CACHE_TTL_DAYS=1

# Auto import settings
AUTO_IMPORT_ENABLED=true
AUTO_IMPORT_INTERVAL=30

# Logging
LOG_LEVEL=DEBUG
"""
        
        with open(env_file, 'w') as f:
            f.write(env_content.strip())
        
        logger.info("Configuration files created")
    
    def create_gitignore(self):
        """Create .gitignore file"""
        gitignore_content = """
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Application
data/
logs/
*.log
*.db
*.sqlite
*.sqlite3

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
coverage.xml
test_results.json

# Environment
.env
.env.local
.env.development
.env.production

# Node.js (if using for frontend)
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Build artifacts
build/
dist/
*.egg-info/

# Temporary files
*.tmp
*.temp
temp_*

# Docker
.dockerignore
"""
        
        gitignore_file = self.project_root / '.gitignore'
        if not gitignore_file.exists():
            with open(gitignore_file, 'w') as f:
                f.write(gitignore_content.strip())
    
    def create_development_scripts(self):
        """Create useful development scripts"""
        logger.info("Creating development scripts...")
        
        # Create run_dev.py
        run_dev_content = """#!/usr/bin/env python3
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
"""
        
        run_dev_file = self.project_root / 'scripts' / 'run_dev.py'
        with open(run_dev_file, 'w') as f:
            f.write(run_dev_content)
        
        run_dev_file.chmod(0o755)
        
        # Create test runner script
        test_runner_content = """#!/usr/bin/env python3
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
"""
        
        test_runner_file = self.project_root / 'scripts' / 'run_tests.py'
        with open(test_runner_file, 'w') as f:
            f.write(test_runner_content)
        
        test_runner_file.chmod(0o755)
        
        # Create validation script
        validate_content = """#!/usr/bin/env python3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.validation import validate_and_print

if __name__ == '__main__':
    success = validate_and_print()
    sys.exit(0 if success else 1)
"""
        
        validate_file = self.project_root / 'scripts' / 'validate_setup.py'
        with open(validate_file, 'w') as f:
            f.write(validate_content)
        
        validate_file.chmod(0o755)
        
        logger.info("Development scripts created")
    
    def setup_pre_commit_hooks(self) -> bool:
        """Set up pre-commit hooks"""
        logger.info("Setting up pre-commit hooks...")
        
        try:
            # Create pre-commit configuration
            precommit_config = """
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-json
      - id: check-merge-conflict
      - id: debug-statements
      - id: requirements-txt-fixer
  
  - repo: https://github.com/psf/black
    rev: 22.10.0
    hooks:
      - id: black
        language_version: python3
  
  - repo: https://github.com/pycqa/isort
    rev: 5.10.1
    hooks:
      - id: isort
  
  - repo: https://github.com/pycqa/flake8
    rev: 5.0.4
    hooks:
      - id: flake8
        additional_dependencies: [flake8-docstrings]
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v0.991
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
        args: [--ignore-missing-imports]
  
  - repo: https://github.com/pycqa/bandit
    rev: 1.7.4
    hooks:
      - id: bandit
        args: [-r, ., -f, json, -o, bandit-report.json]
        exclude: ^tests/
"""
            
            precommit_file = self.project_root / '.pre-commit-config.yaml'
            with open(precommit_file, 'w') as f:
                f.write(precommit_config.strip())
            
            # Install pre-commit hooks
            subprocess.run([str(self.pip_exe), 'install', 'pre-commit'], check=True)
            subprocess.run([
                str(self.venv_path / 'bin' / 'pre-commit'), 'install'
            ], check=True, cwd=self.project_root)
            
            logger.info("Pre-commit hooks set up successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set up pre-commit hooks: {e}")
            return False
    
    def start_services(self) -> bool:
        """Start required services"""
        logger.info("Starting services...")
        
        system = self.detect_system()
        
        try:
            if system == 'ubuntu':
                subprocess.run(['sudo', 'systemctl', 'start', 'redis-server'], check=True)
                subprocess.run(['sudo', 'systemctl', 'enable', 'redis-server'], check=True)
            elif system == 'macos':
                subprocess.run(['brew', 'services', 'start', 'redis'], check=True)
            elif system == 'windows':
                logger.warning("Please start Redis manually on Windows")
            
            logger.info("Services started successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start services: {e}")
            return False
    
    def validate_setup(self) -> bool:
        """Validate the development setup"""
        logger.info("Validating development setup...")
        
        try:
            # Get the correct Python executable path
            if hasattr(self, 'python_exe') and self.python_exe:
                python_exe = self.python_exe
            else:
                if sys.platform.startswith('win'):
                    python_exe = self.venv_path / 'Scripts' / 'python.exe'
                else:
                    python_exe = self.venv_path / 'bin' / 'python'
                
                # Fall back to system Python if venv doesn't exist
                if not python_exe.exists():
                    python_exe = sys.executable
            
            # Run configuration validation
            subprocess.run([
                str(python_exe), '-m', 'config.validation'
            ], check=True, cwd=self.project_root)
            
            # Run basic tests if they exist (but don't fail if tests have issues)
            tests_dir = self.project_root / 'tests'
            if tests_dir.exists():
                try:
                    subprocess.run([
                        str(python_exe), '-m', 'pytest', 'tests/', '-v', '--tb=short', '--maxfail=1'
                    ], check=True, cwd=self.project_root)
                    logger.info("Basic tests passed")
                except subprocess.CalledProcessError:
                    logger.warning("Some tests failed, but configuration validation passed")
            else:
                logger.info("No tests directory found, skipping test validation")
            
            logger.info("Setup validation passed")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Setup validation failed: {e}")
            return False
    
    def run_setup(self) -> bool:
        """Run the complete setup process"""
        logger.info("Starting development environment setup...")
        
        # Check prerequisites
        missing = self.check_prerequisites()
        if missing:
            logger.error("Prerequisites not met:")
            for item in missing:
                logger.error(f"  - {item}")
            return False
        
        # Install system packages
        if not self.install_system_packages():
            return False
        
        # Create virtual environment
        if not self.create_virtual_environment():
            return False
        
        # Install Python packages
        if not self.install_python_packages():
            return False
        
        # Set up project structure
        if not self.setup_project_structure():
            return False
        
        # Set up pre-commit hooks
        if not self.setup_pre_commit_hooks():
            return False
        
        # Start services
        if not self.start_services():
            return False
        
        # Validate setup
        if not self.validate_setup():
            return False
        
        logger.info("Development environment setup completed successfully!")
        self.print_next_steps()
        return True
    
    def print_next_steps(self):
        """Print next steps for the user"""
        print("\n" + "="*60)
        print("DEVELOPMENT ENVIRONMENT SETUP COMPLETE")
        print("="*60)
        print("\nNext steps:")
        print("1. Activate the virtual environment:")
        print(f"   source {self.venv_path}/bin/activate")
        print("\n2. Run the application:")
        print("   python scripts/run_dev.py")
        print("\n3. Run tests:")
        print("   python scripts/run_tests.py")
        print("\n4. Validate setup:")
        print("   python scripts/validate_setup.py")
        print("\n5. Access the application:")
        print("   http://localhost:5000")
        print("\nUseful commands:")
        print("  - Run development tests: python scripts/run_tests.py dev")
        print("  - Run all tests: python scripts/run_tests.py all")
        print("  - Format code: black .")
        print("  - Sort imports: isort .")
        print("  - Lint code: flake8 .")
        print("  - Type check: mypy .")
        print("="*60)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Set up development environment')
    parser.add_argument('--project-root', type=Path, help='Project root directory')
    parser.add_argument('--skip-system-packages', action='store_true', 
                       help='Skip system package installation')
    parser.add_argument('--skip-services', action='store_true', 
                       help='Skip service startup')
    parser.add_argument('--validate-only', action='store_true', 
                       help='Only run validation')
    
    args = parser.parse_args()
    
    setup = DevEnvironmentSetup(args.project_root)
    
    if args.validate_only:
        success = setup.validate_setup()
    else:
        success = setup.run_setup()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()