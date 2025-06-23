#!/bin/bash
set -euo pipefail

# Emergency Rollback Script
# Rapid rollback to last known good version for production emergencies

APP_NAME="futurestradinglog"
BACKUP_DIR="/opt/backups"
DATA_DIR="/mnt/c/Projects/FuturesTradingLog/data"
HEALTH_ENDPOINT="http://localhost:5000/health"
MAX_HEALTH_RETRIES=20
HEALTH_RETRY_DELAY=3

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

emergency() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] 🚨 EMERGENCY:${NC} $1"
}

# Usage information
usage() {
    echo "Emergency Rollback Script"
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -v, --version VERSION    Rollback to specific image version"
    echo "  -d, --database           Restore database from backup"
    echo "  -f, --force              Force rollback without confirmation"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                       # Rollback to last known good container"
    echo "  $0 -v latest             # Rollback to latest stable version"
    echo "  $0 -d                    # Include database restore from backup"
    echo "  $0 -f -v a1b2c3d4        # Force rollback to specific version"
}

# Health check function
check_health() {
    local retries=0
    while [[ $retries -lt $MAX_HEALTH_RETRIES ]]; do
        if curl -f -s $HEALTH_ENDPOINT > /dev/null 2>&1; then
            return 0
        fi
        ((retries++))
        sleep $HEALTH_RETRY_DELAY
    done
    return 1
}

# Stop all application containers
stop_application() {
    emergency "Stopping application containers..."
    
    # Stop main container
    if docker ps | grep -q $APP_NAME; then
        docker stop $APP_NAME || true
    fi
    
    # Stop any backup containers that might be running
    for container in "${APP_NAME}_new" "${APP_NAME}_old" "${APP_NAME}_emergency"; do
        if docker ps | grep -q $container; then
            docker stop $container || true
        fi
    done
    
    log "All application containers stopped"
}

# Rollback container to specific version
rollback_container() {
    local version=${1:-latest}
    
    emergency "Rolling back container to version: $version"
    
    # Pull the rollback image
    log "Pulling rollback image..."
    if ! docker pull ghcr.io/qsor27/futurestradinglog:$version; then
        error "Failed to pull rollback image: $version"
        return 1
    fi
    
    # Remove current container
    docker rm $APP_NAME 2>/dev/null || true
    
    # Start rollback container
    log "Starting rollback container..."
    docker run -d \
        --name "${APP_NAME}" \
        --network host \
        -v "$DATA_DIR:/app/data" \
        -e FLASK_ENV=production \
        -e HOST_IP=0.0.0.0 \
        -e EXTERNAL_PORT=5000 \
        -e DATA_DIR=/app/data \
        ghcr.io/qsor27/futurestradinglog:$version
    
    # Wait for health check
    log "Waiting for application to be healthy..."
    if check_health; then
        log "✅ Rollback container is healthy"
        return 0
    else
        error "❌ Rollback container failed health check"
        return 1
    fi
}

# Restore database from backup
restore_database() {
    emergency "Restoring database from backup..."
    
    # Find latest backup
    if [[ ! -d "$BACKUP_DIR" ]]; then
        error "Backup directory not found: $BACKUP_DIR"
        return 1
    fi
    
    local latest_backup=$(ls -t "$BACKUP_DIR"/trades_backup_*.db 2>/dev/null | head -1)
    if [[ -z "$latest_backup" ]]; then
        error "No database backups found in $BACKUP_DIR"
        return 1
    fi
    
    log "Found latest backup: $(basename "$latest_backup")"
    
    # Confirm backup restore
    if [[ "$FORCE_ROLLBACK" != "true" ]]; then
        warn "⚠️  DATABASE RESTORE WILL LOSE ALL DATA SINCE BACKUP"
        warn "Backup date: $(basename "$latest_backup" | sed 's/trades_backup_//' | sed 's/_/ /' | sed 's/.db//')"
        read -p "Are you sure you want to restore from backup? (yes/no): " -r
        if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            log "Database restore cancelled"
            return 1
        fi
    fi
    
    # Stop application before database restore
    stop_application
    
    # Create backup of current database
    local current_db=""
    for db_file in "$DATA_DIR/db/futures_trades.db" "$DATA_DIR/db/TradingLog.db" "$DATA_DIR/db/futures_log.db"; do
        if [[ -f "$db_file" ]]; then
            current_db="$db_file"
            break
        fi
    done
    
    if [[ -n "$current_db" ]]; then
        local current_backup="${current_db}.emergency_backup.$(date +%Y%m%d_%H%M%S)"
        cp "$current_db" "$current_backup"
        log "Created emergency backup of current database: $(basename "$current_backup")"
    fi
    
    # Restore from backup
    if [[ -n "$current_db" ]]; then
        cp "$latest_backup" "$current_db"
        log "✅ Database restored from backup"
        
        # Verify restored database
        if sqlite3 "$current_db" "PRAGMA integrity_check;" | grep -q "ok"; then
            log "✅ Restored database integrity check passed"
        else
            error "❌ Restored database integrity check failed"
            if [[ -f "$current_backup" ]]; then
                cp "$current_backup" "$current_db"
                warn "Restored original database"
            fi
            return 1
        fi
    else
        error "No current database found to restore to"
        return 1
    fi
    
    return 0
}

# Emergency fallback to basic container
emergency_fallback() {
    emergency "Executing emergency fallback..."
    
    # Try to start any available image
    local fallback_images=(
        "ghcr.io/qsor27/futurestradinglog:latest"
        "ghcr.io/qsor27/futurestradinglog:main"
    )
    
    for image in "${fallback_images[@]}"; do
        log "Attempting emergency start with image: $image"
        
        # Remove any existing containers
        docker rm $APP_NAME 2>/dev/null || true
        
        # Try to start with minimal configuration
        if docker run -d \
            --name "${APP_NAME}" \
            --network host \
            -v "$DATA_DIR:/app/data" \
            -e FLASK_ENV=production \
            -e HOST_IP=0.0.0.0 \
            -e EXTERNAL_PORT=5000 \
            "$image"; then
            
            log "Started container with image: $image"
            
            # Quick health check
            sleep 10
            if check_health; then
                log "✅ Emergency fallback successful with $image"
                return 0
            else
                warn "Emergency container started but health check failed"
                docker stop $APP_NAME || true
            fi
        else
            warn "Failed to start container with image: $image"
        fi
    done
    
    error "❌ All emergency fallback attempts failed"
    return 1
}

# Main rollback execution
main() {
    local version=""
    local restore_db=false
    local force=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -v|--version)
                version="$2"
                shift 2
                ;;
            -d|--database)
                restore_db=true
                shift
                ;;
            -f|--force)
                force=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
    
    # Set global force flag
    FORCE_ROLLBACK="$force"
    
    emergency "🚨 EMERGENCY ROLLBACK INITIATED"
    log "Timestamp: $(date)"
    log "Version: ${version:-latest}"
    log "Restore DB: $restore_db"
    log "Force: $force"
    
    # Confirmation unless forced
    if [[ "$force" != "true" ]]; then
        warn "⚠️  EMERGENCY ROLLBACK WILL STOP THE APPLICATION"
        read -p "Are you sure you want to proceed? (yes/no): " -r
        if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            log "Emergency rollback cancelled"
            exit 0
        fi
    fi
    
    # Execute rollback steps
    local rollback_success=false
    
    # Step 1: Stop application
    stop_application
    
    # Step 2: Restore database if requested
    if [[ "$restore_db" == "true" ]]; then
        if ! restore_database; then
            error "Database restore failed, continuing with container rollback..."
        fi
    fi
    
    # Step 3: Rollback container
    if [[ -n "$version" ]]; then
        if rollback_container "$version"; then
            rollback_success=true
        fi
    else
        # Try latest first, then fallback
        if rollback_container "latest"; then
            rollback_success=true
        elif rollback_container "main"; then
            rollback_success=true
        fi
    fi
    
    # Step 4: Emergency fallback if needed
    if [[ "$rollback_success" != "true" ]]; then
        warn "Standard rollback failed, attempting emergency fallback..."
        if emergency_fallback; then
            rollback_success=true
        fi
    fi
    
    # Final status
    if [[ "$rollback_success" == "true" ]]; then
        log "✅ EMERGENCY ROLLBACK COMPLETED SUCCESSFULLY"
        log "Application is running at: http://localhost:5000"
        log "Please verify functionality and investigate the original issue"
    else
        emergency "❌ EMERGENCY ROLLBACK FAILED"
        emergency "MANUAL INTERVENTION REQUIRED"
        emergency "Contact: [Your Emergency Contact]"
        exit 1
    fi
}

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR" 2>/dev/null || true

# Execute main function
main "$@"