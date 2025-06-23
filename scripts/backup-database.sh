#!/bin/bash

# FuturesTradingLog Database Backup Script
# Provides manual backup, validation, and management functionality

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="${DATA_DIR:-$PROJECT_ROOT/data}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
LOG_FILE="$DATA_DIR/logs/backup.log"

# Database paths
DB_PATH="$DATA_DIR/db/futures_trades.db"
OHLC_DB_PATH="$DATA_DIR/db/ohlc_cache.db"

# Backup retention settings
LOCAL_RETENTION_DAYS=7
COMPRESSED_RETENTION_DAYS=30

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

# Create directories
setup_directories() {
    mkdir -p "$BACKUP_DIR"/{manual,automated,compressed}
    mkdir -p "$DATA_DIR/logs"
    
    log "INFO" "Backup directories created at $BACKUP_DIR"
}

# Validate database integrity
validate_database() {
    local db_path=$1
    local db_name=$(basename "$db_path" .db)
    
    if [[ ! -f "$db_path" ]]; then
        log "WARN" "Database $db_name not found at $db_path"
        return 1
    fi
    
    log "INFO" "Validating database integrity: $db_name"
    
    # Check SQLite integrity
    if sqlite3 "$db_path" "PRAGMA integrity_check;" | grep -q "ok"; then
        log "SUCCESS" "Database $db_name integrity check passed"
    else
        log "ERROR" "Database $db_name integrity check failed"
        return 1
    fi
    
    # Check WAL file if exists
    if [[ -f "$db_path-wal" ]]; then
        log "INFO" "WAL file detected for $db_name, running checkpoint"
        sqlite3 "$db_path" "PRAGMA wal_checkpoint(TRUNCATE);"
        log "SUCCESS" "WAL checkpoint completed for $db_name"
    fi
    
    return 0
}

# Create manual backup
create_backup() {
    local backup_type="${1:-manual}"
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_subdir="$BACKUP_DIR/$backup_type"
    
    log "INFO" "Starting $backup_type backup at $timestamp"
    
    setup_directories
    
    # Backup main database
    if [[ -f "$DB_PATH" ]]; then
        local backup_file="$backup_subdir/futures_trades_${timestamp}.db"
        log "INFO" "Creating backup: $(basename "$backup_file")"
        
        # Validate before backup
        if validate_database "$DB_PATH"; then
            cp "$DB_PATH" "$backup_file"
            
            # Verify backup integrity
            if validate_database "$backup_file"; then
                # Compress backup
                gzip "$backup_file"
                log "SUCCESS" "Main database backup created: ${backup_file}.gz"
            else
                rm -f "$backup_file"
                log "ERROR" "Backup validation failed, removing backup file"
                return 1
            fi
        else
            log "ERROR" "Source database validation failed, skipping backup"
            return 1
        fi
    else
        log "WARN" "Main database not found at $DB_PATH"
    fi
    
    # Backup OHLC cache database
    if [[ -f "$OHLC_DB_PATH" ]]; then
        local ohlc_backup_file="$backup_subdir/ohlc_cache_${timestamp}.db"
        log "INFO" "Creating OHLC cache backup: $(basename "$ohlc_backup_file")"
        
        if validate_database "$OHLC_DB_PATH"; then
            cp "$OHLC_DB_PATH" "$ohlc_backup_file"
            
            if validate_database "$ohlc_backup_file"; then
                gzip "$ohlc_backup_file"
                log "SUCCESS" "OHLC cache backup created: ${ohlc_backup_file}.gz"
            else
                rm -f "$ohlc_backup_file"
                log "ERROR" "OHLC backup validation failed, removing backup file"
            fi
        else
            log "WARN" "OHLC database validation failed, skipping backup"
        fi
    else
        log "INFO" "OHLC cache database not found (normal for new installations)"
    fi
    
    # Create backup manifest
    create_backup_manifest "$backup_subdir" "$timestamp"
    
    log "SUCCESS" "$backup_type backup completed successfully"
}

# Create backup manifest with metadata
create_backup_manifest() {
    local backup_dir=$1
    local timestamp=$2
    local manifest_file="$backup_dir/manifest_${timestamp}.json"
    
    cat > "$manifest_file" << EOF
{
    "timestamp": "$timestamp",
    "created_at": "$(date -Iseconds)",
    "backup_type": "$(basename "$backup_dir")",
    "files": [
$(find "$backup_dir" -name "*_${timestamp}.db.gz" -exec basename {} \; | sed 's/.*/"&"/' | paste -sd, -)
    ],
    "sizes": {
$(find "$backup_dir" -name "*_${timestamp}.db.gz" -exec sh -c 'echo "        \"$(basename "{}")\": $(stat -c%s "{}")"' \; | paste -sd, -)
    },
    "validation": {
        "integrity_check": "passed",
        "created_by": "backup-database.sh",
        "script_version": "1.0"
    }
}
EOF
    
    log "INFO" "Backup manifest created: $(basename "$manifest_file")"
}

# Clean old backups
cleanup_old_backups() {
    log "INFO" "Cleaning up old backups"
    
    # Clean manual backups older than LOCAL_RETENTION_DAYS
    find "$BACKUP_DIR/manual" -name "*.db.gz" -mtime +$LOCAL_RETENTION_DAYS -delete 2>/dev/null || true
    find "$BACKUP_DIR/manual" -name "manifest_*.json" -mtime +$LOCAL_RETENTION_DAYS -delete 2>/dev/null || true
    
    # Clean automated backups older than LOCAL_RETENTION_DAYS
    find "$BACKUP_DIR/automated" -name "*.db.gz" -mtime +$LOCAL_RETENTION_DAYS -delete 2>/dev/null || true
    find "$BACKUP_DIR/automated" -name "manifest_*.json" -mtime +$LOCAL_RETENTION_DAYS -delete 2>/dev/null || true
    
    # Clean compressed backups older than COMPRESSED_RETENTION_DAYS
    find "$BACKUP_DIR/compressed" -name "*.db.gz" -mtime +$COMPRESSED_RETENTION_DAYS -delete 2>/dev/null || true
    
    log "SUCCESS" "Backup cleanup completed"
}

# List available backups
list_backups() {
    log "INFO" "Available backups:"
    
    echo -e "\n${BLUE}Manual Backups:${NC}"
    if ls "$BACKUP_DIR/manual"/*.db.gz 2>/dev/null | head -10; then
        echo ""
    else
        echo "  No manual backups found"
    fi
    
    echo -e "\n${BLUE}Automated Backups:${NC}"
    if ls "$BACKUP_DIR/automated"/*.db.gz 2>/dev/null | head -10; then
        echo ""
    else
        echo "  No automated backups found"
    fi
    
    echo -e "\n${BLUE}Litestream Backups:${NC}"
    if ls "$BACKUP_DIR/local"/* 2>/dev/null | head -5; then
        echo ""
    else
        echo "  No Litestream backups found"
    fi
}

# Validate all backups
validate_all_backups() {
    log "INFO" "Validating all backup files"
    local validation_failed=0
    
    for backup_file in "$BACKUP_DIR"/*/*.db.gz; do
        if [[ -f "$backup_file" ]]; then
            log "INFO" "Validating backup: $(basename "$backup_file")"
            
            # Create temporary file
            local temp_file="/tmp/$(basename "$backup_file" .gz)"
            
            # Decompress and validate
            if gunzip -c "$backup_file" > "$temp_file" 2>/dev/null; then
                if validate_database "$temp_file"; then
                    log "SUCCESS" "Backup $(basename "$backup_file") is valid"
                else
                    log "ERROR" "Backup $(basename "$backup_file") validation failed"
                    ((validation_failed++))
                fi
                rm -f "$temp_file"
            else
                log "ERROR" "Failed to decompress backup $(basename "$backup_file")"
                ((validation_failed++))
            fi
        fi
    done
    
    if [[ $validation_failed -eq 0 ]]; then
        log "SUCCESS" "All backups validated successfully"
        return 0
    else
        log "ERROR" "$validation_failed backup(s) failed validation"
        return 1
    fi
}

# Show backup statistics
show_stats() {
    echo -e "\n${BLUE}Backup Statistics:${NC}"
    echo "===================="
    
    # Count backups
    local manual_count=$(find "$BACKUP_DIR/manual" -name "*.db.gz" 2>/dev/null | wc -l)
    local auto_count=$(find "$BACKUP_DIR/automated" -name "*.db.gz" 2>/dev/null | wc -l)
    
    echo "Manual backups: $manual_count"
    echo "Automated backups: $auto_count"
    
    # Calculate total size
    local total_size=$(find "$BACKUP_DIR" -name "*.db.gz" -exec stat -c%s {} \; 2>/dev/null | awk '{sum+=$1} END {print sum}')
    if [[ -n "$total_size" && "$total_size" -gt 0 ]]; then
        echo "Total backup size: $(numfmt --to=iec "$total_size")"
    fi
    
    # Show disk usage
    echo "Backup directory usage:"
    du -sh "$BACKUP_DIR" 2>/dev/null || echo "  Cannot calculate usage"
    
    # Latest backup
    local latest_backup=$(find "$BACKUP_DIR" -name "*.db.gz" -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)
    if [[ -n "$latest_backup" ]]; then
        echo "Latest backup: $(basename "$latest_backup")"
        echo "Created: $(stat -c %y "$latest_backup" 2>/dev/null | cut -d'.' -f1)"
    fi
}

# Usage information
usage() {
    cat << EOF
FuturesTradingLog Database Backup Script

Usage: $0 [COMMAND]

Commands:
    backup          Create manual backup (default)
    validate        Validate all existing backups
    list           List all available backups
    cleanup        Remove old backups according to retention policy
    stats          Show backup statistics
    help           Show this help message

Environment Variables:
    DATA_DIR       Data directory path (default: ../data)
    BACKUP_DIR     Backup directory path (default: ../backups)

Examples:
    $0 backup       # Create manual backup
    $0 validate     # Validate all backups
    $0 cleanup      # Clean old backups
    $0 stats        # Show backup statistics

EOF
}

# Main execution
main() {
    local command="${1:-backup}"
    
    case "$command" in
        backup)
            create_backup "manual"
            ;;
        validate)
            validate_all_backups
            ;;
        list)
            list_backups
            ;;
        cleanup)
            cleanup_old_backups
            ;;
        stats)
            show_stats
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