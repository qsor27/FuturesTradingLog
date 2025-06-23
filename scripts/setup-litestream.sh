#!/bin/bash

# FuturesTradingLog Litestream Setup Script
# Installs and configures Litestream for real-time SQLite replication

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="${DATA_DIR:-$PROJECT_ROOT/data}"
LITESTREAM_VERSION="0.3.13"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    shift
    local message="$*"
    
    case $level in
        ERROR)
            echo -e "${RED}[ERROR]${NC} $message" >&2
            ;;
        WARN)
            echo -e "${YELLOW}[WARN]${NC} $message"
            ;;
        SUCCESS)
            echo -e "${GREEN}[SUCCESS]${NC} $message"
            ;;
        INFO)
            echo -e "${BLUE}[INFO]${NC} $message"
            ;;
    esac
}

# Detect OS and architecture
detect_platform() {
    local os
    local arch
    
    case "$(uname -s)" in
        Linux*)     os="linux";;
        Darwin*)    os="darwin";;
        CYGWIN*|MINGW*|MSYS*) os="windows";;
        *)          
            log "ERROR" "Unsupported operating system: $(uname -s)"
            return 1
            ;;
    esac
    
    case "$(uname -m)" in
        x86_64|amd64)   arch="amd64";;
        arm64|aarch64)  arch="arm64";;
        armv7l)         arch="armv7";;
        *)              
            log "ERROR" "Unsupported architecture: $(uname -m)"
            return 1
            ;;
    esac
    
    echo "${os}-${arch}"
}

# Check if Litestream is already installed
check_existing_installation() {
    if command -v litestream &> /dev/null; then
        local current_version
        current_version=$(litestream version 2>/dev/null | grep -oP 'v\K[0-9.]+' || echo "unknown")
        
        log "INFO" "Litestream is already installed (version: $current_version)"
        
        if [[ "$current_version" == "$LITESTREAM_VERSION" ]]; then
            log "SUCCESS" "Litestream is up to date"
            return 0
        else
            log "WARN" "Litestream version mismatch. Current: $current_version, Required: $LITESTREAM_VERSION"
            read -p "Would you like to upgrade? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log "INFO" "Installation cancelled by user"
                return 0
            fi
        fi
    fi
    
    return 1
}

# Install Litestream
install_litestream() {
    log "INFO" "Installing Litestream v$LITESTREAM_VERSION"
    
    local platform
    platform=$(detect_platform)
    
    if [[ -z "$platform" ]]; then
        log "ERROR" "Failed to detect platform"
        return 1
    fi
    
    log "INFO" "Detected platform: $platform"
    
    # Determine download URL and filename
    local filename
    local url
    
    if [[ "$platform" == *"windows"* ]]; then
        filename="litestream-${platform}.zip"
    else
        filename="litestream-${platform}-static.tar.gz"
    fi
    
    url="https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/${filename}"
    
    log "INFO" "Downloading Litestream from: $url"
    
    # Create temporary directory
    local temp_dir
    temp_dir=$(mktemp -d)
    cd "$temp_dir"
    
    # Download Litestream
    if command -v curl &> /dev/null; then
        curl -L -o "$filename" "$url"
    elif command -v wget &> /dev/null; then
        wget -O "$filename" "$url"
    else
        log "ERROR" "Neither curl nor wget found. Please install one of them."
        return 1
    fi
    
    # Extract and install
    if [[ "$filename" == *.zip ]]; then
        unzip "$filename"
    else
        tar -xzf "$filename"
    fi
    
    # Find the binary and install it
    local binary_path
    if [[ -f "litestream" ]]; then
        binary_path="litestream"
    elif [[ -f "litestream.exe" ]]; then
        binary_path="litestream.exe"
    else
        log "ERROR" "Litestream binary not found in extracted files"
        return 1
    fi
    
    # Install to appropriate location
    local install_dir="/usr/local/bin"
    
    if [[ ! -w "$install_dir" ]]; then
        log "INFO" "Installing to /usr/local/bin requires sudo permissions"
        sudo mv "$binary_path" "$install_dir/"
        sudo chmod +x "$install_dir/$(basename "$binary_path")"
    else
        mv "$binary_path" "$install_dir/"
        chmod +x "$install_dir/$(basename "$binary_path")"
    fi
    
    # Clean up
    cd - > /dev/null
    rm -rf "$temp_dir"
    
    # Verify installation
    if litestream version &> /dev/null; then
        log "SUCCESS" "Litestream installed successfully"
        litestream version
    else
        log "ERROR" "Litestream installation verification failed"
        return 1
    fi
}

# Create Litestream configuration
setup_configuration() {
    log "INFO" "Setting up Litestream configuration"
    
    local config_file="$PROJECT_ROOT/config/litestream.yml"
    
    if [[ -f "$config_file" ]]; then
        log "SUCCESS" "Litestream configuration already exists: $config_file"
    else
        log "ERROR" "Litestream configuration not found: $config_file"
        log "INFO" "Please run the backup system setup to create the configuration"
        return 1
    fi
    
    # Validate configuration
    if litestream -config "$config_file" validate; then
        log "SUCCESS" "Litestream configuration is valid"
    else
        log "ERROR" "Litestream configuration validation failed"
        return 1
    fi
}

# Setup systemd service (Linux only)
setup_systemd_service() {
    if [[ "$(uname -s)" != "Linux" ]]; then
        log "INFO" "Systemd service setup is only available on Linux"
        return 0
    fi
    
    log "INFO" "Setting up Litestream systemd service"
    
    local service_file="/etc/systemd/system/litestream.service"
    local config_file="$PROJECT_ROOT/config/litestream.yml"
    
    # Create systemd service file
    sudo tee "$service_file" > /dev/null << EOF
[Unit]
Description=Litestream SQLite Replication
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=1
User=root
ExecStart=/usr/local/bin/litestream replicate -config $config_file
Environment=DATA_DIR=$DATA_DIR

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd and enable service
    sudo systemctl daemon-reload
    sudo systemctl enable litestream
    
    log "SUCCESS" "Litestream systemd service created and enabled"
    log "INFO" "Start the service with: sudo systemctl start litestream"
    log "INFO" "Check status with: sudo systemctl status litestream"
}

# Test Litestream setup
test_litestream() {
    log "INFO" "Testing Litestream setup"
    
    local config_file="$PROJECT_ROOT/config/litestream.yml"
    local test_db="/tmp/litestream_test.db"
    local test_backup_dir="/tmp/litestream_test_backup"
    
    # Create test database
    sqlite3 "$test_db" "CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT); INSERT INTO test (data) VALUES ('test data');"
    
    # Create test configuration
    local test_config="/tmp/litestream_test.yml"
    cat > "$test_config" << EOF
dbs:
  - path: $test_db
    replicas:
      - type: file
        path: $test_backup_dir
        sync-interval: 1s
        snapshot-interval: 10s
EOF
    
    # Start Litestream in background
    log "INFO" "Starting test replication (10 seconds)"
    litestream replicate -config "$test_config" &
    local litestream_pid=$!
    
    # Wait for initial sync
    sleep 5
    
    # Add more test data
    sqlite3 "$test_db" "INSERT INTO test (data) VALUES ('additional test data');"
    
    # Wait for sync
    sleep 5
    
    # Stop Litestream
    kill $litestream_pid || true
    wait $litestream_pid 2>/dev/null || true
    
    # Test restore
    local restored_db="/tmp/litestream_test_restored.db"
    rm -f "$restored_db"
    
    if litestream restore -config "$test_config" "$restored_db"; then
        # Verify restored data
        local row_count
        row_count=$(sqlite3 "$restored_db" "SELECT COUNT(*) FROM test;")
        
        if [[ "$row_count" -eq 2 ]]; then
            log "SUCCESS" "Litestream test completed successfully"
        else
            log "ERROR" "Litestream test failed: Expected 2 rows, got $row_count"
            return 1
        fi
    else
        log "ERROR" "Litestream restore test failed"
        return 1
    fi
    
    # Clean up test files
    rm -f "$test_db" "$restored_db" "$test_config"
    rm -rf "$test_backup_dir"
}

# Setup backup directories
setup_directories() {
    log "INFO" "Setting up backup directories"
    
    local backup_dir="$PROJECT_ROOT/backups"
    
    mkdir -p "$backup_dir"/{local,manual,automated,safety,compressed}
    mkdir -p "$DATA_DIR/logs"
    
    log "SUCCESS" "Backup directories created"
}

# Show setup status
show_status() {
    echo -e "\n${BLUE}Litestream Setup Status:${NC}"
    echo "========================="
    
    # Check Litestream installation
    if command -v litestream &> /dev/null; then
        echo -e "${GREEN}✓${NC} Litestream installed: $(litestream version 2>/dev/null | head -1)"
    else
        echo -e "${RED}✗${NC} Litestream not installed"
    fi
    
    # Check configuration
    local config_file="$PROJECT_ROOT/config/litestream.yml"
    if [[ -f "$config_file" ]]; then
        echo -e "${GREEN}✓${NC} Configuration file exists: $config_file"
        if litestream -config "$config_file" validate 2>/dev/null; then
            echo -e "${GREEN}✓${NC} Configuration is valid"
        else
            echo -e "${RED}✗${NC} Configuration validation failed"
        fi
    else
        echo -e "${RED}✗${NC} Configuration file missing: $config_file"
    fi
    
    # Check backup directories
    local backup_dir="$PROJECT_ROOT/backups"
    if [[ -d "$backup_dir" ]]; then
        echo -e "${GREEN}✓${NC} Backup directories exist: $backup_dir"
    else
        echo -e "${RED}✗${NC} Backup directories missing: $backup_dir"
    fi
    
    # Check systemd service (Linux only)
    if [[ "$(uname -s)" == "Linux" ]]; then
        if systemctl is-enabled litestream &>/dev/null; then
            echo -e "${GREEN}✓${NC} Systemd service enabled"
            if systemctl is-active litestream &>/dev/null; then
                echo -e "${GREEN}✓${NC} Systemd service running"
            else
                echo -e "${YELLOW}!${NC} Systemd service not running"
            fi
        else
            echo -e "${RED}✗${NC} Systemd service not enabled"
        fi
    fi
    
    # Check database files
    local db_path="$DATA_DIR/db/futures_trades.db"
    if [[ -f "$db_path" ]]; then
        echo -e "${GREEN}✓${NC} Main database exists: $db_path"
    else
        echo -e "${YELLOW}!${NC} Main database not found: $db_path"
    fi
}

# Usage information
usage() {
    cat << EOF
FuturesTradingLog Litestream Setup Script

Usage: $0 [COMMAND]

Commands:
    install     Install Litestream binary
    configure   Setup configuration (requires existing config file)
    systemd     Setup systemd service (Linux only)
    test        Test Litestream functionality
    status      Show setup status
    full        Complete setup (install + configure + systemd)
    help        Show this help message

Examples:
    $0 install     # Install Litestream binary
    $0 full        # Complete setup
    $0 status      # Check setup status
    $0 test        # Test functionality

Environment Variables:
    DATA_DIR       Data directory path (default: ../data)

EOF
}

# Main execution
main() {
    local command="${1:-status}"
    
    case "$command" in
        install)
            if ! check_existing_installation; then
                install_litestream
            fi
            ;;
        configure)
            setup_configuration
            setup_directories
            ;;
        systemd)
            setup_systemd_service
            ;;
        test)
            test_litestream
            ;;
        status)
            show_status
            ;;
        full)
            setup_directories
            if ! check_existing_installation; then
                install_litestream
            fi
            setup_configuration
            setup_systemd_service
            test_litestream
            show_status
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            log "ERROR" "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"