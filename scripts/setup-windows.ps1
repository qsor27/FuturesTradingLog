<#
.SYNOPSIS
    Automated Windows setup script for FuturesTradingLog

.DESCRIPTION
    This script automates the installation of all dependencies required to run
    FuturesTradingLog on Windows without Docker. It will:
    - Install Python 3.11+ via winget
    - Install Git via winget
    - Download and install NSSM (service manager)
    - Create required directories
    - Set up Python virtual environment
    - Install Python dependencies
    - Provide instructions for Memurai (Redis)

.PARAMETER InstallPath
    Where to clone/install FuturesTradingLog
    Default: C:\Program Files\FuturesTradingLog

.PARAMETER DataPath
    Where to store application data
    Default: C:\ProgramData\FuturesTradingLog

.PARAMETER SkipPython
    Skip Python installation (if already installed)

.PARAMETER SkipGit
    Skip Git installation (if already installed)

.PARAMETER SkipNSSM
    Skip NSSM installation

.EXAMPLE
    .\setup-windows.ps1

.EXAMPLE
    .\setup-windows.ps1 -InstallPath "D:\Apps\FuturesTradingLog" -DataPath "D:\Data\FTL"

.NOTES
    Requires: Windows 10/11 with winget, Administrator privileges for NSSM
#>

[CmdletBinding()]
param(
    [string]$InstallPath = "C:\Program Files\FuturesTradingLog",
    [string]$DataPath = "C:\ProgramData\FuturesTradingLog",
    [switch]$SkipPython,
    [switch]$SkipGit,
    [switch]$SkipNSSM
)

$ErrorActionPreference = "Stop"

# Colors for output
function Write-Status {
    param([string]$Message, [string]$Type = "INFO")
    $Color = switch ($Type) {
        "SUCCESS" { "Green" }
        "ERROR" { "Red" }
        "WARN" { "Yellow" }
        "STEP" { "Cyan" }
        default { "White" }
    }
    $Prefix = switch ($Type) {
        "SUCCESS" { "[OK]" }
        "ERROR" { "[ERROR]" }
        "WARN" { "[WARN]" }
        "STEP" { "[STEP]" }
        default { "[INFO]" }
    }
    Write-Host "$Prefix $Message" -ForegroundColor $Color
}

function Test-Administrator {
    $CurrentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = New-Object Security.Principal.WindowsPrincipal($CurrentUser)
    return $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-CommandExists {
    param([string]$Command)
    $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

# Header
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   FuturesTradingLog - Windows Automated Setup" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Install Path: $InstallPath"
Write-Host "Data Path:    $DataPath"
Write-Host ""

# Check Administrator status upfront
$IsAdmin = Test-Administrator
if ($IsAdmin) {
    Write-Status "Running as Administrator" "SUCCESS"
} else {
    Write-Status "Running as standard user (some features limited)" "WARN"
    Write-Host ""
    Write-Host "  The following require Administrator privileges:" -ForegroundColor Yellow
    Write-Host "    - Installing NSSM to C:\nssm\"
    Write-Host "    - Creating directories in C:\ProgramData\"
    Write-Host "    - Installing as a Windows service"
    Write-Host ""
    Write-Host "  To run as Administrator:"
    Write-Host "    Right-click PowerShell -> 'Run as administrator'"
    Write-Host "    Or: Start-Process powershell -Verb RunAs"
    Write-Host ""

    $Continue = Read-Host "Continue with limited permissions? (y/n)"
    if ($Continue -ne 'y') {
        Write-Host ""
        Write-Host "Re-run this script as Administrator for full setup."
        exit 0
    }

    # Adjust data path for non-admin
    if ($DataPath -like "C:\ProgramData\*") {
        $DataPath = "$env:LOCALAPPDATA\FuturesTradingLog"
        Write-Status "Using user-local data path: $DataPath" "INFO"
    }
}
Write-Host ""

# Check for winget
if (-not (Test-CommandExists "winget")) {
    Write-Status "winget not found. Please install App Installer from Microsoft Store." "ERROR"
    Write-Host "  https://aka.ms/getwinget"
    exit 1
}
Write-Status "winget found" "SUCCESS"

# ============================================================
# Step 1: Install Python
# ============================================================
Write-Host ""
Write-Status "Checking Python installation..." "STEP"

$PythonInstalled = $false
$PythonPath = ""

if (Test-CommandExists "python") {
    $PythonVersion = python --version 2>&1
    # Accept Python 3.11, 3.12, or 3.13 only (3.14+ lacks pre-built wheels for pandas/numpy)
    if ($PythonVersion -match "Python 3\.1[1-3]\.") {
        Write-Status "Python already installed: $PythonVersion" "SUCCESS"
        $PythonInstalled = $true
        $PythonPath = (Get-Command python).Source
    } elseif ($PythonVersion -match "Python 3\.1[4-9]|Python 3\.[2-9]") {
        Write-Status "Python $PythonVersion is too new - pandas/numpy lack pre-built wheels" "ERROR"
        Write-Host "  Please install Python 3.11, 3.12, or 3.13 instead."
        Write-Host "  Run: winget install Python.Python.3.12"
        Write-Host "  Then restart this script."
        exit 1
    } else {
        Write-Status "Python found but version too old: $PythonVersion" "WARN"
    }
}

if (-not $PythonInstalled -and -not $SkipPython) {
    Write-Status "Installing Python 3.11..."
    winget install Python.Python.3.11 --accept-source-agreements --accept-package-agreements

    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

    if (Test-CommandExists "python") {
        Write-Status "Python installed successfully" "SUCCESS"
        $PythonInstalled = $true
    } else {
        Write-Status "Python installation may require terminal restart" "WARN"
    }
}

# ============================================================
# Step 2: Install Git
# ============================================================
Write-Host ""
Write-Status "Checking Git installation..." "STEP"

if (Test-CommandExists "git") {
    $GitVersion = git --version
    Write-Status "Git already installed: $GitVersion" "SUCCESS"
} elseif (-not $SkipGit) {
    Write-Status "Installing Git..."
    winget install Git.Git --accept-source-agreements --accept-package-agreements

    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

    if (Test-CommandExists "git") {
        Write-Status "Git installed successfully" "SUCCESS"
    } else {
        Write-Status "Git installation may require terminal restart" "WARN"
    }
}

# ============================================================
# Step 3: Install NSSM (Service Manager)
# ============================================================
Write-Host ""
Write-Status "Checking NSSM installation..." "STEP"

$NssmPath = "C:\nssm\nssm.exe"
if (Test-Path $NssmPath) {
    Write-Status "NSSM already installed at $NssmPath" "SUCCESS"
} elseif (-not $SkipNSSM) {
    if (-not (Test-Administrator)) {
        Write-Status "NSSM installation requires Administrator privileges" "WARN"
        Write-Host "  Run this script as Administrator, or manually download NSSM:"
        Write-Host "  https://nssm.cc/download"
        Write-Host "  Extract nssm.exe to C:\nssm\"
    } else {
        Write-Status "Downloading NSSM..."
        $NssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
        $NssmZip = "$env:TEMP\nssm.zip"
        $NssmExtract = "$env:TEMP\nssm-extract"

        try {
            Invoke-WebRequest -Uri $NssmUrl -OutFile $NssmZip
            Expand-Archive -Path $NssmZip -DestinationPath $NssmExtract -Force

            # Create destination and copy
            New-Item -ItemType Directory -Path "C:\nssm" -Force | Out-Null
            Copy-Item "$NssmExtract\nssm-2.24\win64\nssm.exe" "C:\nssm\nssm.exe"

            # Create marker file for uninstaller to know we installed NSSM
            "Installed by FuturesTradingLog setup on $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Set-Content "C:\nssm\.installed-by-ftl"

            # Cleanup
            Remove-Item $NssmZip -Force
            Remove-Item $NssmExtract -Recurse -Force

            Write-Status "NSSM installed to C:\nssm\nssm.exe" "SUCCESS"
        } catch {
            Write-Status "Failed to download NSSM: $_" "ERROR"
            Write-Host "  Please download manually from https://nssm.cc/download"
        }
    }
}

# ============================================================
# Step 4: Check for Redis (Optional)
# ============================================================
Write-Host ""
Write-Status "Checking for Redis (optional)..." "STEP"

$RedisAvailable = $false
$MemuraiService = Get-Service -Name "Memurai" -ErrorAction SilentlyContinue
$RedisService = Get-Service -Name "Redis" -ErrorAction SilentlyContinue

if ($MemuraiService) {
    Write-Status "Memurai (Redis) found - caching will be enabled" "SUCCESS"
    $RedisAvailable = $true
} elseif ($RedisService) {
    Write-Status "Redis found - caching will be enabled" "SUCCESS"
    $RedisAvailable = $true
} else {
    Write-Status "Redis not found - caching will be disabled (app works fine without it)" "INFO"
    Write-Host ""
    Write-Host "  Optional: To enable caching later, you can use:" -ForegroundColor Gray
    Write-Host "    - Docker: docker run -d -p 6379:6379 redis:alpine" -ForegroundColor Gray
    Write-Host "    - WSL2:   sudo apt install redis-server && sudo service redis-server start" -ForegroundColor Gray
    Write-Host "  Then set CACHE_ENABLED=true in .env" -ForegroundColor Gray
    Write-Host ""
}

# ============================================================
# Step 5: Clone or Update Repository
# ============================================================
Write-Host ""
Write-Status "Setting up repository..." "STEP"

if (Test-Path "$InstallPath\.git") {
    Write-Status "Repository exists at $InstallPath" "SUCCESS"

    $UpdateRepo = Read-Host "Update repository to latest? (y/n)"
    if ($UpdateRepo -eq 'y') {
        Push-Location $InstallPath
        git pull origin main
        Pop-Location
        Write-Status "Repository updated" "SUCCESS"
    }
} else {
    Write-Status "Cloning repository to $InstallPath..."
    $ParentPath = Split-Path $InstallPath -Parent
    if (-not (Test-Path $ParentPath)) {
        New-Item -ItemType Directory -Path $ParentPath -Force | Out-Null
    }

    git clone https://github.com/qsor27/FuturesTradingLog.git $InstallPath
    Write-Status "Repository cloned" "SUCCESS"
}

# ============================================================
# Step 6: Create Data Directories
# ============================================================
Write-Host ""
Write-Status "Creating data directories..." "STEP"

$Directories = @(
    $DataPath,
    "$DataPath\db",
    "$DataPath\logs",
    "$DataPath\config",
    "$DataPath\charts",
    "$DataPath\archive",
    "$DataPath\backups"
)

foreach ($Dir in $Directories) {
    if (-not (Test-Path $Dir)) {
        New-Item -ItemType Directory -Path $Dir -Force | Out-Null
        Write-Host "  Created: $Dir"
    }
}
Write-Status "Data directories ready" "SUCCESS"

# ============================================================
# Step 7: Setup Python Virtual Environment
# ============================================================
Write-Host ""
Write-Status "Setting up Python virtual environment..." "STEP"

Push-Location $InstallPath

$VenvPath = "$InstallPath\venv"
if (-not (Test-Path $VenvPath)) {
    Write-Status "Creating virtual environment..."
    python -m venv venv
}

# Activate and install dependencies
Write-Status "Installing Python dependencies (this may take a few minutes)..."
& "$VenvPath\Scripts\python.exe" -m pip install --upgrade pip

$PipInstall = & "$VenvPath\Scripts\pip.exe" install -r requirements.txt 2>&1
$PipExitCode = $LASTEXITCODE

if ($PipExitCode -ne 0) {
    Write-Status "Failed to install Python dependencies" "ERROR"
    Write-Host ""
    Write-Host "  Common causes:" -ForegroundColor Yellow
    Write-Host "    - Python version incompatible with pinned packages"
    Write-Host "    - Missing C compiler for packages that need compilation"
    Write-Host "    - Network issues downloading packages"
    Write-Host ""
    Write-Host "  Try installing Python 3.12 if using a newer version:"
    Write-Host "    winget install Python.Python.3.12"
    Write-Host ""
    Pop-Location
    exit 1
}

Write-Status "Python dependencies installed" "SUCCESS"

Pop-Location

# ============================================================
# Step 8: Generate Configuration
# ============================================================
Write-Host ""
Write-Status "Generating configuration..." "STEP"

$SecretKey = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 64 | ForEach-Object {[char]$_})

$CacheEnabled = if ($RedisAvailable) { "true" } else { "false" }

$EnvContent = @"
# FuturesTradingLog Environment Configuration
# Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

FLASK_ENV=production
FLASK_DEBUG=0
FLASK_SECRET_KEY=$SecretKey
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

DATA_DIR=$DataPath

# Redis caching (optional - app works without it)
REDIS_URL=redis://localhost:6379/0
CACHE_ENABLED=$CacheEnabled

AUTO_IMPORT_ENABLED=false
AUTO_IMPORT_INTERVAL=300

# Optional: Discord webhook for notifications
# DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your-webhook-url
"@

$EnvFile = "$InstallPath\.env"
if (-not (Test-Path $EnvFile)) {
    $EnvContent | Set-Content $EnvFile
    Write-Status "Created .env configuration file" "SUCCESS"
} else {
    Write-Status ".env file already exists (not overwritten)" "WARN"
}

# ============================================================
# Summary
# ============================================================
Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "   Setup Complete!" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Installation Summary:"
Write-Host "  Install Path: $InstallPath"
Write-Host "  Data Path:    $DataPath"
Write-Host "  Config:       $InstallPath\.env"
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Start the application manually:"
Write-Host "     cd $InstallPath"
Write-Host "     .\venv\Scripts\Activate"
Write-Host "     python app.py"
Write-Host ""
Write-Host "  2. Or install as a Windows service:"
Write-Host "     .\scripts\install-service.ps1"
Write-Host ""
Write-Host "  3. Access the web interface:"
Write-Host "     http://localhost:5000"
Write-Host ""

Write-Host "Documentation: $InstallPath\docs\WINDOWS_INSTALL.md"
Write-Host ""
