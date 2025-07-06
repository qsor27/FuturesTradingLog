#!/bin/bash

# Celery Management Script
# Provides easy commands for managing Celery workers and services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker Compose is available
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        log_error "docker-compose is not installed or not in PATH"
        exit 1
    fi
}

# Show usage
show_usage() {
    echo "Celery Management Script"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  start       Start all Celery services (workers, beat, flower)"
    echo "  stop        Stop all Celery services"
    echo "  restart     Restart all Celery services"
    echo "  status      Show status of all services"
    echo "  logs        Show logs for all services"
    echo "  logs-worker Show logs for workers only"
    echo "  logs-beat   Show logs for beat scheduler"
    echo "  scale       Scale workers (e.g., scale worker=3)"
    echo "  purge       Purge all queues (removes pending tasks)"
    echo "  monitor     Open Flower monitoring interface"
    echo "  shell       Start interactive shell with Celery app"
    echo ""
    echo "Worker-specific commands:"
    echo "  start-worker <queue>    Start worker for specific queue"
    echo "  stop-worker <queue>     Stop worker for specific queue"
    echo "  inspect                 Inspect active workers"
    echo ""
    echo "Queue management:"
    echo "  list-queues            List all available queues"
    echo "  queue-status           Show queue status and pending tasks"
    echo "  flush-queue <queue>    Flush specific queue"
    echo ""
    echo "Examples:"
    echo "  $0 start                Start all services"
    echo "  $0 logs-worker          Show worker logs"
    echo "  $0 scale worker=2       Scale general workers to 2 instances"
    echo "  $0 flush-queue gap_filling  Clear gap filling queue"
}

# Start all Celery services
start_services() {
    log_info "Starting Celery services..."
    check_docker_compose
    
    docker-compose -f docker-compose.celery.yml up -d
    
    log_success "Celery services started"
    log_info "Flower monitoring available at: http://localhost:5555"
}

# Stop all Celery services
stop_services() {
    log_info "Stopping Celery services..."
    check_docker_compose
    
    docker-compose -f docker-compose.celery.yml down
    
    log_success "Celery services stopped"
}

# Restart all Celery services
restart_services() {
    log_info "Restarting Celery services..."
    stop_services
    sleep 2
    start_services
}

# Show service status
show_status() {
    log_info "Celery service status:"
    check_docker_compose
    
    docker-compose -f docker-compose.celery.yml ps
    
    echo ""
    log_info "Worker inspection:"
    docker-compose -f docker-compose.celery.yml exec celery_worker celery -A celery_app inspect active || true
}

# Show logs
show_logs() {
    check_docker_compose
    docker-compose -f docker-compose.celery.yml logs -f
}

# Show worker logs only
show_worker_logs() {
    check_docker_compose
    docker-compose -f docker-compose.celery.yml logs -f celery_worker celery_worker_files celery_worker_gaps celery_worker_positions
}

# Show beat logs
show_beat_logs() {
    check_docker_compose
    docker-compose -f docker-compose.celery.yml logs -f celery_beat
}

# Scale workers
scale_workers() {
    if [ -z "$2" ]; then
        log_error "Please specify scaling configuration (e.g., worker=3)"
        exit 1
    fi
    
    log_info "Scaling workers: $2"
    check_docker_compose
    
    docker-compose -f docker-compose.celery.yml up -d --scale celery_worker="$2"
    
    log_success "Workers scaled"
}

# Purge all queues
purge_queues() {
    log_warning "This will remove ALL pending tasks from ALL queues!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Purging all queues..."
        check_docker_compose
        
        docker-compose -f docker-compose.celery.yml exec celery_worker celery -A celery_app purge -f
        
        log_success "All queues purged"
    else
        log_info "Operation cancelled"
    fi
}

# Open monitoring interface
open_monitor() {
    log_info "Opening Flower monitoring interface..."
    
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:5555
    elif command -v open &> /dev/null; then
        open http://localhost:5555
    else
        log_info "Please open http://localhost:5555 in your browser"
    fi
}

# Start interactive shell
start_shell() {
    log_info "Starting Celery shell..."
    check_docker_compose
    
    docker-compose -f docker-compose.celery.yml exec celery_worker python -c "
from celery_app import app
import tasks
print('Celery app and tasks loaded.')
print('Use app.send_task() to trigger tasks manually.')
print('Available tasks:', list(app.tasks.keys()))
"
}

# Start specific worker
start_worker() {
    if [ -z "$2" ]; then
        log_error "Please specify queue name"
        exit 1
    fi
    
    local queue=$2
    log_info "Starting worker for queue: $queue"
    check_docker_compose
    
    docker-compose -f docker-compose.celery.yml run --rm celery_worker celery -A celery_app worker --loglevel=info --queues="$queue"
}

# Stop specific worker
stop_worker() {
    if [ -z "$2" ]; then
        log_error "Please specify worker service name"
        exit 1
    fi
    
    local worker=$2
    log_info "Stopping worker: $worker"
    check_docker_compose
    
    docker-compose -f docker-compose.celery.yml stop "$worker"
}

# Inspect workers
inspect_workers() {
    log_info "Inspecting active workers..."
    check_docker_compose
    
    echo "Active tasks:"
    docker-compose -f docker-compose.celery.yml exec celery_worker celery -A celery_app inspect active
    
    echo ""
    echo "Registered tasks:"
    docker-compose -f docker-compose.celery.yml exec celery_worker celery -A celery_app inspect registered
    
    echo ""
    echo "Worker statistics:"
    docker-compose -f docker-compose.celery.yml exec celery_worker celery -A celery_app inspect stats
}

# List queues
list_queues() {
    log_info "Available queues:"
    echo "- default"
    echo "- file_processing"
    echo "- gap_filling"
    echo "- position_building"
    echo "- cache_maintenance"
}

# Show queue status
show_queue_status() {
    log_info "Queue status and pending tasks:"
    check_docker_compose
    
    docker-compose -f docker-compose.celery.yml exec celery_worker celery -A celery_app inspect active_queues
}

# Flush specific queue
flush_queue() {
    if [ -z "$2" ]; then
        log_error "Please specify queue name"
        exit 1
    fi
    
    local queue=$2
    log_warning "This will remove ALL pending tasks from queue: $queue"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Flushing queue: $queue"
        check_docker_compose
        
        # Note: Celery doesn't have direct queue flushing, but we can purge and restart
        docker-compose -f docker-compose.celery.yml exec redis redis-cli DEL "celery:$queue"
        
        log_success "Queue $queue flushed"
    else
        log_info "Operation cancelled"
    fi
}

# Main command processing
case "${1:-}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    logs-worker)
        show_worker_logs
        ;;
    logs-beat)
        show_beat_logs
        ;;
    scale)
        scale_workers "$@"
        ;;
    purge)
        purge_queues
        ;;
    monitor)
        open_monitor
        ;;
    shell)
        start_shell
        ;;
    start-worker)
        start_worker "$@"
        ;;
    stop-worker)
        stop_worker "$@"
        ;;
    inspect)
        inspect_workers
        ;;
    list-queues)
        list_queues
        ;;
    queue-status)
        show_queue_status
        ;;
    flush-queue)
        flush_queue "$@"
        ;;
    help|--help|-h)
        show_usage
        ;;
    "")
        log_error "No command specified"
        echo ""
        show_usage
        exit 1
        ;;
    *)
        log_error "Unknown command: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac