#!/bin/bash

# Futures Trading Log - GitHub Docker Deployment Script
# This script pulls and runs the latest Docker image from GitHub Container Registry

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
GITHUB_REPO="qsor27/futurestradinglog"
IMAGE_NAME="ghcr.io/${GITHUB_REPO}"
CONTAINER_NAME="futures-trading-log"
DEFAULT_DATA_DIR="./data"
DEFAULT_PORT="5000"

# Functions
print_header() {
    echo -e "${BLUE}"
    echo "=================================================="
    echo "  Futures Trading Log - Docker Deployment"
    echo "=================================================="
    echo -e "${NC}"
}

print_step() {
    echo -e "${YELLOW}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    print_step "Checking requirements..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_success "Requirements check passed"
}

setup_environment() {
    print_step "Setting up environment..."
    
    # Create .env file if it doesn't exist
    if [ ! -f .env ]; then
        print_step "Creating .env file..."
        cat > .env << EOF
# Futures Trading Log Configuration
DATA_DIR=${DATA_DIR:-$DEFAULT_DATA_DIR}
EXTERNAL_PORT=${PORT:-$DEFAULT_PORT}
FLASK_SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || echo "change-this-secret-key")

# Optional: Uncomment for nginx reverse proxy
# HTTP_PORT=80
# HTTPS_PORT=443
EOF
        print_success "Created .env file with default configuration"
    else
        print_success "Using existing .env file"
    fi
    
    # Create data directory
    DATA_DIR_PATH=${DATA_DIR:-$DEFAULT_DATA_DIR}
    mkdir -p "$DATA_DIR_PATH"
    print_success "Data directory ready: $DATA_DIR_PATH"
}

pull_latest_image() {
    print_step "Pulling latest Docker image from GitHub Container Registry..."
    
    # Try to pull the latest image
    if docker pull "${IMAGE_NAME}:latest"; then
        print_success "Successfully pulled latest image"
    else
        print_error "Failed to pull image. Checking if image exists locally..."
        if docker image inspect "${IMAGE_NAME}:latest" &> /dev/null; then
            print_success "Using existing local image"
        else
            print_error "No image available. Please check repository and network connection."
            exit 1
        fi
    fi
}

stop_existing_container() {
    print_step "Checking for existing container..."
    
    if docker ps -a --format 'table {{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_step "Stopping and removing existing container..."
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        docker rm "$CONTAINER_NAME" 2>/dev/null || true
        print_success "Removed existing container"
    else
        print_success "No existing container found"
    fi
}

start_application() {
    print_step "Starting Futures Trading Log application..."
    
    # Use production docker-compose if available, otherwise development
    if [ -f docker-compose.prod.yml ]; then
        COMPOSE_FILE="docker-compose.prod.yml"
    else
        COMPOSE_FILE="docker-compose.yml"
    fi
    
    print_step "Using compose file: $COMPOSE_FILE"
    
    if docker-compose -f "$COMPOSE_FILE" up -d; then
        print_success "Application started successfully"
    else
        print_error "Failed to start application"
        exit 1
    fi
}

show_status() {
    print_step "Checking application status..."
    
    # Wait a moment for container to start
    sleep 5
    
    if docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -q "$CONTAINER_NAME"; then
        print_success "Container is running"
        
        # Show container info
        echo ""
        echo -e "${BLUE}Container Status:${NC}"
        docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep "$CONTAINER_NAME"
        
        # Test health endpoint
        PORT=${PORT:-$DEFAULT_PORT}
        print_step "Testing health endpoint..."
        sleep 10  # Give app time to start
        
        if curl -f "http://localhost:${PORT}/health" &> /dev/null; then
            print_success "Application is healthy and responding"
            echo ""
            echo -e "${GREEN}🚀 Deployment Successful!${NC}"
            echo -e "${BLUE}Application URL:${NC} http://localhost:${PORT}"
            echo -e "${BLUE}Chart Example:${NC} http://localhost:${PORT}/chart/MNQ"
            echo -e "${BLUE}API Health:${NC} http://localhost:${PORT}/health"
        else
            print_error "Application is not responding to health checks"
            echo "Check logs with: docker logs $CONTAINER_NAME"
        fi
    else
        print_error "Container failed to start"
        echo "Check logs with: docker logs $CONTAINER_NAME"
        exit 1
    fi
}

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -d, --data-dir DIR    Data directory path (default: ./data)"
    echo "  -p, --port PORT       External port (default: 5000)"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  DATA_DIR             Override data directory"
    echo "  PORT                 Override external port"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Use defaults"
    echo "  $0 -d /var/lib/futures -p 8080      # Custom data dir and port"
    echo "  DATA_DIR=/data PORT=3000 $0         # Using environment variables"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    print_header
    
    check_requirements
    setup_environment
    pull_latest_image
    stop_existing_container
    start_application
    show_status
    
    echo ""
    echo -e "${GREEN}Deployment completed successfully!${NC}"
    echo ""
    echo "Useful commands:"
    echo "  docker logs $CONTAINER_NAME          # View application logs"
    echo "  docker-compose down                  # Stop the application"
    echo "  docker-compose pull && docker-compose up -d  # Update to latest"
}

# Run main function
main "$@"