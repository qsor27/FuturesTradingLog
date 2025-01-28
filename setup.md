# Detailed Setup Guide for Trading Log Application

## Comprehensive Installation Steps

### 1. System Requirements
- Operating System: Windows 10/11, macOS, or Linux
- Python Version: 3.8 or higher
- Minimum 2 GB RAM
- Minimum 500 MB free disk space

### 2. Python Installation
#### Windows
1. Download Python from official website: https://www.python.org/downloads/
2. Run installer
3. IMPORTANT: Check "Add Python to PATH" during installation
4. Verify installation:
   ```bash
   python --version
   pip --version
   ```

#### macOS
1. Install Homebrew (package manager):
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
2. Install Python:
   ```bash
   brew install python
   ```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

### 3. Git Installation
#### Windows
1. Download from: https://git-scm.com/download/win
2. Follow installation wizard
3. Choose "Use Git from the Windows Command Prompt"

#### macOS
```bash
brew install git
```

#### Linux
```bash
sudo apt install git
```

### 4. Clone Repository
```bash
# HTTPS Method
git clone https://github.com/yourusername/trading-log-app.git

# SSH Method (requires SSH key setup)
git clone git@github.com:yourusername/trading-log-app.git

cd trading-log-app
```

### 5. Virtual Environment Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 6. Install Dependencies
```bash
# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt
```

### 7. Database Initialization
```bash
# If using Flask-Migrate
flask db upgrade

# Or if you have a custom initialization script
python init_database.py
```

### 8. Run the Application
```bash
# Method 1
flask run

# Method 2
python app.py
```

### 9. Access the Application
- Open web browser
- Navigate to: http://localhost:5000

### 10. Troubleshooting Common Issues
- Ensure virtual environment is activated
- Check Python and pip versions
- Verify all dependencies are installed
- Check firewall settings
- Ensure no port conflicts

### 11. Updating the Application
```bash
# Pull latest changes
git pull origin main

# Update dependencies
pip install -r requirements.txt

# Run any migrations
flask db upgrade
```

## Additional Notes
- Always activate virtual environment before working
- Keep your dependencies updated
- Report any issues on GitHub repository
