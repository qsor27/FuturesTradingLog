#!/bin/bash
set -euo pipefail

# Disable Watchtower Auto-Deployment Script
# This script safely removes Watchtower to prevent risky auto-deployments

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

log "Disabling Watchtower auto-deployment..."

# Stop and remove Watchtower container
if docker ps | grep -q watchtower; then
    log "Stopping Watchtower container..."
    docker stop watchtower
    docker rm watchtower
    log "Watchtower container removed"
else
    log "Watchtower container not found in running containers"
fi

# Check for stopped Watchtower containers
if docker ps -a | grep -q watchtower; then
    log "Found stopped Watchtower container, removing..."
    docker rm watchtower 2>/dev/null || true
fi

# Remove from docker-compose if present
if [[ -f docker-compose.yml ]]; then
    log "Checking docker-compose.yml for Watchtower configuration..."
    if grep -q "watchtower:" docker-compose.yml; then
        log "Found Watchtower in docker-compose.yml"
        warn "Manual removal from docker-compose.yml recommended"
        log "Please edit docker-compose.yml to remove the watchtower service section"
    else
        log "No Watchtower configuration found in docker-compose.yml"
    fi
fi

# Create backup of current docker-compose if it contains watchtower
if [[ -f docker-compose.yml ]] && grep -q "watchtower:" docker-compose.yml; then
    backup_file="docker-compose.yml.backup.$(date +%Y%m%d_%H%M%S)"
    cp docker-compose.yml "$backup_file"
    log "Created backup of docker-compose.yml: $backup_file"
fi

log "Watchtower disabled successfully"
log ""
log "IMPORTANT NEXT STEPS:"
log "1. Use ./scripts/deploy-production.sh for all future deployments"
log "2. Remove any watchtower service sections from docker-compose.yml"
log "3. Update any CI/CD workflows to use manual deployment triggers"
log ""
log "Manual deployment command:"
log "  ./scripts/deploy-production.sh <version>"
log ""
log "Example:"
log "  ./scripts/deploy-production.sh latest"
log "  ./scripts/deploy-production.sh a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"

# Check if the deployment script exists
if [[ -f "./scripts/deploy-production.sh" ]]; then
    log "Production deployment script is available"
    # Make it executable
    chmod +x ./scripts/deploy-production.sh
    log "Made deploy-production.sh executable"
else
    warn "Production deployment script not found at ./scripts/deploy-production.sh"
    warn "Please ensure the deployment script is created before removing Watchtower"
fi