#!/bin/bash
set -euo pipefail

# Production Deployment Script with Health Checks
# Usage: ./deploy-production.sh [version]

VERSION=${1:-latest}
APP_NAME="futurestradinglog"
BACKUP_DIR="$HOME/backups"
HEALTH_ENDPOINT="http://localhost:5000/health"
MAX_HEALTH_RETRIES=30
HEALTH_RETRY_DELAY=5
DATA_DIR="/mnt/c/Projects/FuturesTradingLog/data"

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

# Pre-deployment validation
validate_environment() {
    log "Validating deployment environment..."
    
    # Check if running during market hours (Monday-Friday 9:30AM-4:00PM EST / 14:30-21:00 UTC)
    current_hour=$(date +%H)
    current_day=$(date +%u)  # 1=Monday, 7=Sunday
    
    # Block deployments during weekday market hours (9:30AM-4:00PM EST = 14:30-21:00 UTC)
    if [[ $current_day -ge 1 && $current_day -le 5 ]]; then
        if [[ $current_hour -ge 14 && $current_hour -le 21 ]]; then
            warn "Deployment during market hours detected (Mon-Fri 9:30AM-4:00PM EST). Proceed with extra caution."
            read -p "Continue? (yes/no): " -r
            if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
                error "Deployment cancelled by user"
                exit 1
            fi
        fi
    fi
    
    # Check disk space (require at least 2GB free)
    available_space=$(df / | tail -1 | awk '{print $4}')
    if [[ $available_space -lt 2097152 ]]; then  # 2GB in KB
        error "Insufficient disk space. At least 2GB required."
        exit 1
    fi
    
    # Check if data directory exists
    if [[ ! -d "$DATA_DIR" ]]; then
        error "Data directory not found: $DATA_DIR"
        exit 1
    fi
    
    log "Environment validation passed"
}

# Create database backup
backup_database() {
    log "Creating database backup..."
    
    mkdir -p $BACKUP_DIR
    backup_file="$BACKUP_DIR/trades_backup_$(date +%Y%m%d_%H%M%S).db"
    
    # Backup SQLite database if it exists
    if [[ -f "$DATA_DIR/db/futures_trades.db" ]]; then
        cp "$DATA_DIR/db/futures_trades.db" "$backup_file"
        log "Database backup created: $backup_file"
    elif [[ -f "$DATA_DIR/db/TradingLog.db" ]]; then
        cp "$DATA_DIR/db/TradingLog.db" "$backup_file"
        log "Database backup created: $backup_file"
    else
        warn "No database file found to backup"
        return 0
    fi
    
    # Keep only last 7 backups
    ls -t $BACKUP_DIR/trades_backup_*.db | tail -n +8 | xargs -r rm
    
    if [[ -f $backup_file ]]; then
        log "Database backup verified: $backup_file"
    else
        error "Database backup failed"
        exit 1
    fi
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

# Blue-green deployment
deploy_new_version() {
    log "Starting blue-green deployment for version: $VERSION"
    
    # Pull new image
    log "Pulling new image..."
    if ! docker pull ghcr.io/qsor27/futurestradinglog:$VERSION; then
        error "Failed to pull new image"
        exit 1
    fi
    
    # Stop current container if running
    if docker ps | grep -q $APP_NAME; then
        log "Stopping current container..."
        docker stop $APP_NAME || true
        docker rename $APP_NAME "${APP_NAME}_old" || true
    fi
    
    # Create new container
    log "Creating new container..."
    docker run -d \
        --name "${APP_NAME}" \
        --network host \
        -v "$DATA_DIR:/app/data" \
        -e FLASK_ENV=production \
        -e HOST_IP=0.0.0.0 \
        -e EXTERNAL_PORT=5000 \
        -e DATA_DIR=/app/data \
        ghcr.io/qsor27/futurestradinglog:$VERSION
    
    # Wait for new container to be ready
    log "Waiting for new container to be healthy..."
    if ! check_health; then
        error "New container failed health check"
        rollback_deployment
        exit 1
    fi
    
    log "New container is healthy!"
    
    # Clean up old container
    if docker ps -a | grep -q "${APP_NAME}_old"; then
        log "Removing old container..."
        docker rm "${APP_NAME}_old" || true
    fi
    
    log "Deployment completed successfully!"
}

# Rollback function
rollback_deployment() {
    warn "Initiating rollback procedure..."
    
    # Stop new container
    docker stop "${APP_NAME}" 2>/dev/null || true
    docker rm "${APP_NAME}" 2>/dev/null || true
    
    # Restart old container if it exists
    if docker ps -a | grep -q "${APP_NAME}_old"; then
        docker rename "${APP_NAME}_old" $APP_NAME
        docker start $APP_NAME
        
        if check_health; then
            log "Rollback successful"
        else
            error "Rollback failed - manual intervention required"
        fi
    else
        error "No rollback target available - manual intervention required"
    fi
}

# Cleanup old images
cleanup_images() {
    log "Cleaning up old Docker images..."
    docker image prune -f
    docker system prune -f --volumes=false
}

# Main deployment flow
main() {
    log "Starting production deployment..."
    
    validate_environment
    backup_database
    deploy_new_version
    cleanup_images
    
    log "Production deployment completed successfully!"
    log "Application is running at: http://localhost:5000"
    log "Health check: $HEALTH_ENDPOINT"
}

# Trap for cleanup on script exit
trap 'error "Deployment script interrupted"; rollback_deployment; exit 1' INT TERM

# Execute main function
main "$@"