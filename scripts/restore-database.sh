#!/bin/bash

# FuturesTradingLog Database Restore Script
# Provides database restoration from backups with safety checks

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="${DATA_DIR:-$PROJECT_ROOT/data}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
LOG_FILE="$DATA_DIR/logs/restore.log"

# Database paths
DB_PATH="$DATA_DIR/db/futures_trades.db"
OHLC_DB_PATH="$DATA_DIR/db/ohlc_cache.db"

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
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    mkdir -p "$(dirname "$LOG_FILE")"
    echo -e "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
    
    case $level in
        ERROR)
            echo -e "${RED}[$level]${NC} $message" >&2
            ;;
        WARN)
            echo -e "${YELLOW}[$level]${NC} $message"
            ;;
        SUCCESS)
            echo -e "${GREEN}[$level]${NC} $message"
            ;;
        INFO)
            echo -e "${BLUE}[$level]${NC} $message"
            ;;
    esac
}

# Validate backup file
validate_backup() {
    local backup_file=$1
    
    if [[ ! -f "$backup_file" ]]; then
        log "ERROR" "Backup file not found: $backup_file"
        return 1
    fi
    
    log "INFO" "Validating backup file: $(basename "$backup_file")"
    
    # Check if it's a gzipped file
    if [[ "$backup_file" == *.gz ]]; then
        if ! gunzip -t "$backup_file" 2>/dev/null; then
            log "ERROR" "Backup file is corrupted (gunzip test failed)"
            return 1
        fi
    fi
    
    # Create temporary file for validation
    local temp_file="/tmp/restore_test_$(date +%s).db"
    
    if [[ "$backup_file" == *.gz ]]; then
        gunzip -c "$backup_file" > "$temp_file"
    else
        cp "$backup_file" "$temp_file"
    fi
    
    # Validate SQLite integrity
    if sqlite3 "$temp_file" "PRAGMA integrity_check;" | grep -q "ok"; then
        log "SUCCESS" "Backup file validation passed"
        rm -f "$temp_file"
        return 0
    else
        log "ERROR" "Backup file validation failed (SQLite integrity check)"
        rm -f "$temp_file"
        return 1
    fi
}

# Create safety backup before restore
create_safety_backup() {
    local db_path=$1
    local db_name=$(basename "$db_path" .db)
    
    if [[ ! -f "$db_path" ]]; then
        log "INFO" "No existing database to backup: $db_name"
        return 0
    fi
    
    local safety_backup_dir="$BACKUP_DIR/safety"
    mkdir -p "$safety_backup_dir"
    
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local safety_backup="$safety_backup_dir/${db_name}_pre_restore_${timestamp}.db"
    
    log "INFO" "Creating safety backup: $(basename "$safety_backup")"
    
    # Validate current database before backup
    if sqlite3 "$db_path" "PRAGMA integrity_check;" | grep -q "ok"; then
        cp "$db_path" "$safety_backup"
        gzip "$safety_backup"
        log "SUCCESS" "Safety backup created: ${safety_backup}.gz"
        return 0
    else
        log "WARN" "Current database integrity check failed, creating backup anyway"
        cp "$db_path" "$safety_backup"
        gzip "$safety_backup"
        log "WARN" "Safety backup created but source database may be corrupted"
        return 0
    fi
}

# Stop application services
stop_services() {
    log "INFO" "Checking for running application services"
    
    # Check if Docker services are running
    if docker ps --format "table {{.Names}}" | grep -q "futurestradinglog"; then
        log "WARN" "FuturesTradingLog services are running. Please stop them before restore:"
        echo "  docker-compose -f docker/docker-compose.production.yml down"
        echo "  Or: docker stop futurestradinglog-app futurestradinglog-litestream"
        read -p "Continue with restore anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "INFO" "Restore cancelled by user"
            exit 0
        fi
    fi
    
    # Check for Python processes
    if pgrep -f "app.py" > /dev/null; then
        log "WARN" "Python application appears to be running"
        read -p "Continue with restore anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "INFO" "Restore cancelled by user"
            exit 0
        fi
    fi
}

# Restore database from backup
restore_database() {
    local backup_file=$1
    local target_db=$2
    local force=${3:-false}
    
    log "INFO" "Starting database restore"
    log "INFO" "Source: $(basename "$backup_file")"
    log "INFO" "Target: $target_db"
    
    # Validate backup file
    if ! validate_backup "$backup_file"; then
        log "ERROR" "Backup validation failed, restore aborted"
        return 1
    fi
    
    # Check if target database exists and is in use
    if [[ -f "$target_db" && "$force" != "true" ]]; then
        log "WARN" "Target database already exists: $target_db"
        read -p "Overwrite existing database? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "INFO" "Restore cancelled by user"
            return 0
        fi
    fi
    
    # Create safety backup
    create_safety_backup "$target_db"
    
    # Ensure target directory exists
    mkdir -p "$(dirname "$target_db")"
    
    # Perform restore
    log "INFO" "Restoring database from backup..."
    
    if [[ "$backup_file" == *.gz ]]; then
        if gunzip -c "$backup_file" > "$target_db"; then
            log "SUCCESS" "Database restored successfully"
        else
            log "ERROR" "Failed to restore database from compressed backup"
            return 1
        fi
    else
        if cp "$backup_file" "$target_db"; then
            log "SUCCESS" "Database restored successfully"
        else
            log "ERROR" "Failed to restore database"
            return 1
        fi
    fi
    
    # Validate restored database
    if sqlite3 "$target_db" "PRAGMA integrity_check;" | grep -q "ok"; then
        log "SUCCESS" "Restored database integrity check passed"
    else
        log "ERROR" "Restored database integrity check failed"
        return 1
    fi
    
    # Set appropriate permissions
    chmod 644 "$target_db"
    
    log "SUCCESS" "Database restore completed successfully"
}

# Restore from Litestream backup
restore_from_litestream() {
    local timestamp=${1:-}
    local target_db=${2:-$DB_PATH}
    
    log "INFO" "Restoring from Litestream backup"
    
    if [[ -z "$timestamp" ]]; then
        log "INFO" "No timestamp specified, restoring to latest point"
        timestamp="latest"
    fi
    
    # Check if Litestream is available
    if ! command -v litestream &> /dev/null; then
        log "ERROR" "Litestream not found. Install with: curl -sf https://github.com/benbjohnson/litestream/releases/latest/download/litestream-linux-amd64-static.tar.gz | tar -xzC /usr/local/bin"
        return 1
    fi
    
    # Create safety backup
    create_safety_backup "$target_db"
    
    # Restore using Litestream
    local litestream_config="$PROJECT_ROOT/config/litestream.yml"
    
    if [[ ! -f "$litestream_config" ]]; then
        log "ERROR" "Litestream configuration not found: $litestream_config"
        return 1
    fi
    
    log "INFO" "Running Litestream restore..."
    
    if litestream restore -config "$litestream_config" -timestamp "$timestamp" "$target_db"; then
        log "SUCCESS" "Litestream restore completed"
    else
        log "ERROR" "Litestream restore failed"
        return 1
    fi
    
    # Validate restored database
    if sqlite3 "$target_db" "PRAGMA integrity_check;" | grep -q "ok"; then
        log "SUCCESS" "Restored database integrity check passed"
    else
        log "ERROR" "Restored database integrity check failed"
        return 1
    fi
}

# List available backups for restore
list_backups_for_restore() {
    echo -e "\n${BLUE}Available Backups for Restore:${NC}"
    echo "================================="
    
    local backup_count=0
    
    echo -e "\n${YELLOW}Manual Backups:${NC}"
    if ls "$BACKUP_DIR/manual"/*.db.gz 2>/dev/null; then
        ((backup_count++))
    else
        echo "  No manual backups found"
    fi
    
    echo -e "\n${YELLOW}Automated Backups:${NC}"
    if ls "$BACKUP_DIR/automated"/*.db.gz 2>/dev/null; then
        ((backup_count++))
    else
        echo "  No automated backups found"
    fi
    
    echo -e "\n${YELLOW}Safety Backups:${NC}"
    if ls "$BACKUP_DIR/safety"/*.db.gz 2>/dev/null; then
        ((backup_count++))
    else
        echo "  No safety backups found"
    fi
    
    echo -e "\n${YELLOW}Litestream Backups:${NC}"
    if ls "$BACKUP_DIR/local"/* 2>/dev/null; then
        echo "  Use 'restore litestream' command for Litestream backups"
        ((backup_count++))
    else
        echo "  No Litestream backups found"
    fi
    
    if [[ $backup_count -eq 0 ]]; then
        echo -e "\n${RED}No backups available for restore${NC}"
    fi
}

# Interactive restore selection
interactive_restore() {
    list_backups_for_restore
    
    echo -e "\n${BLUE}Select restore option:${NC}"
    echo "1) Restore from manual backup"
    echo "2) Restore from automated backup" 
    echo "3) Restore from safety backup"
    echo "4) Restore from Litestream"
    echo "5) Cancel"
    
    read -p "Enter your choice (1-5): " choice
    
    case $choice in
        1)
            echo -e "\n${BLUE}Manual backups:${NC}"
            select backup_file in "$BACKUP_DIR/manual"/*.db.gz; do
                if [[ -n "$backup_file" ]]; then
                    restore_database "$backup_file" "$DB_PATH"
                    break
                fi
            done
            ;;
        2)
            echo -e "\n${BLUE}Automated backups:${NC}"
            select backup_file in "$BACKUP_DIR/automated"/*.db.gz; do
                if [[ -n "$backup_file" ]]; then
                    restore_database "$backup_file" "$DB_PATH"
                    break
                fi
            done
            ;;
        3)
            echo -e "\n${BLUE}Safety backups:${NC}"
            select backup_file in "$BACKUP_DIR/safety"/*.db.gz; do
                if [[ -n "$backup_file" ]]; then
                    restore_database "$backup_file" "$DB_PATH"
                    break
                fi
            done
            ;;
        4)
            read -p "Enter timestamp (YYYY-MM-DDTHH:MM:SS) or press Enter for latest: " timestamp
            restore_from_litestream "$timestamp"
            ;;
        5)
            log "INFO" "Restore cancelled by user"
            ;;
        *)
            log "ERROR" "Invalid choice"
            ;;
    esac
}

# Usage information
usage() {
    cat << EOF
FuturesTradingLog Database Restore Script

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    restore <backup_file> [target_db]  Restore from specific backup file
    litestream [timestamp]             Restore from Litestream backup
    interactive                        Interactive restore selection
    list                              List available backups
    help                              Show this help message

Options:
    --force                           Skip confirmation prompts

Examples:
    $0 restore /path/to/backup.db.gz          # Restore from specific backup
    $0 litestream                             # Restore from latest Litestream backup
    $0 litestream 2024-01-15T10:30:00         # Restore from specific timestamp
    $0 interactive                            # Interactive restore selection
    $0 list                                   # List available backups

Environment Variables:
    DATA_DIR       Data directory path (default: ../data)
    BACKUP_DIR     Backup directory path (default: ../backups)

EOF
}

# Main execution
main() {
    local command="${1:-interactive}"
    
    case "$command" in
        restore)
            if [[ $# -lt 2 ]]; then
                log "ERROR" "Backup file required for restore command"
                usage
                exit 1
            fi
            
            local backup_file="$2"
            local target_db="${3:-$DB_PATH}"
            local force="false"
            
            # Check for force flag
            if [[ "${4:-}" == "--force" ]]; then
                force="true"
            fi
            
            stop_services
            restore_database "$backup_file" "$target_db" "$force"
            ;;
        litestream)
            local timestamp="${2:-}"
            stop_services
            restore_from_litestream "$timestamp"
            ;;
        interactive)
            stop_services
            interactive_restore
            ;;
        list)
            list_backups_for_restore
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