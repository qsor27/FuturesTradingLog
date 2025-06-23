#!/bin/bash
set -euo pipefail

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
# Comprehensive Health Check Script
# Validates all critical components of the Futures Trading Application
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
APP_NAME="futurestradinglog"
HEALTH_ENDPOINT="http://localhost:5000/health"
DETAILED_HEALTH_ENDPOINT="http://localhost:5000/health/detailed"
DATA_DIR="/mnt/c/Projects/FuturesTradingLog/data"
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
# Status tracking
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✅${NC} $1"
    ((CHECKS_PASSED++))
}
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️${NC} $1"
    ((CHECKS_WARNING++))
}
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ❌${NC} $1"
    ((CHECKS_FAILED++))
}
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
# Container health check
check_container() {
    log "Checking container status..."
    
    if docker ps | grep -q $APP_NAME; then
        local container_status=$(docker inspect --format='{{.State.Status}}' $APP_NAME 2>/dev/null || echo "unknown")
        if [[ "$container_status" == "running" ]]; then
            success "Container is running"
            
            # Check container health if healthcheck is configured
            local health_status=$(docker inspect --format='{{.State.Health.Status}}' $APP_NAME 2>/dev/null || echo "none")
            if [[ "$health_status" != "none" ]]; then
                if [[ "$health_status" == "healthy" ]]; then
                    success "Container health check: healthy"
                else
                    warn "Container health check: $health_status"
                fi
            fi
        else
            error "Container exists but status is: $container_status"
        fi
    else
        error "Container $APP_NAME is not running"
    fi
}
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
# Application health check
check_application() {
    log "Checking application health..."
    
    # Basic health endpoint
    local response_code=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_ENDPOINT 2>/dev/null || echo "000")
    if [[ "$response_code" == "200" ]]; then
        success "Basic health endpoint responding (HTTP $response_code)"
    else
        error "Basic health endpoint failed (HTTP $response_code)"
        return
    fi
    
    # Detailed health endpoint if available
    if curl -s $DETAILED_HEALTH_ENDPOINT > /tmp/health_detail.json 2>/dev/null; then
        local app_status=$(cat /tmp/health_detail.json | grep -o '"status":"[^"]*"' | cut -d'"' -f4 2>/dev/null || echo "unknown")
        case "$app_status" in
            "healthy")
                success "Detailed health status: healthy"
                ;;
            "warning")
                warn "Detailed health status: warning"
                ;;
            "unhealthy")
                error "Detailed health status: unhealthy"
                ;;
            *)
                warn "Detailed health status: $app_status"
                ;;
        esac
        rm -f /tmp/health_detail.json
    else
        warn "Detailed health endpoint not available"
    fi
}
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
# Database connectivity check
check_database() {
    log "Checking database connectivity..."
    
    # Check if database files exist
    local db_found=false
    for db_file in "$DATA_DIR/db/futures_trades.db" "$DATA_DIR/db/TradingLog.db" "$DATA_DIR/db/futures_log.db"; do
        if [[ -f "$db_file" ]]; then
            success "Database file found: $(basename "$db_file")"
            db_found=true
            
            # Check database integrity
            if docker exec $APP_NAME sqlite3 "$db_file" "PRAGMA integrity_check;" 2>/dev/null | grep -q "ok"; then
                success "Database integrity check passed for $(basename "$db_file")"
            else
                error "Database integrity check failed for $(basename "$db_file")"
            fi
            break
        fi
    done
    
    if [[ "$db_found" == false ]]; then
        error "No database files found in $DATA_DIR/db/"
    fi
    
    # Test database connection from application
    if docker exec $APP_NAME python3 -c "
import sqlite3
import os
db_path = '/app/data/db/futures_trades.db'
if not os.path.exists(db_path):
    db_path = '/app/data/db/TradingLog.db'
if not os.path.exists(db_path):
    db_path = '/app/data/db/futures_log.db'
try:
    conn = sqlite3.connect(db_path)
    conn.execute('SELECT 1')
    conn.close()
    print('SUCCESS')
except Exception as e:
    print(f'ERROR: {e}')
" 2>/dev/null | grep -q "SUCCESS"; then
        success "Database connection test passed"
    else
        error "Database connection test failed"
    fi
}
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
# Redis connectivity check (if available)
check_redis() {
    log "Checking Redis connectivity..."
    
    # Check if Redis is running
    if docker ps | grep -q redis; then
        success "Redis container is running"
        
        # Test Redis connection
        if docker exec $(docker ps --filter "name=redis" --format "{{.Names}}" | head -1) redis-cli ping 2>/dev/null | grep -q "PONG"; then
            success "Redis connection test passed"
        else
            error "Redis connection test failed"
        fi
    else
        warn "Redis container not found (may not be configured)"
    fi
}
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
# Disk space check
check_disk_space() {
    log "Checking disk space..."
    
    # Check root filesystem
    local root_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    if [[ $root_usage -lt 80 ]]; then
        success "Root filesystem usage: ${root_usage}%"
    elif [[ $root_usage -lt 90 ]]; then
        warn "Root filesystem usage: ${root_usage}% (getting high)"
    else
        error "Root filesystem usage: ${root_usage}% (critical)"
    fi
    
    # Check data directory size
    if [[ -d "$DATA_DIR" ]]; then
        local data_size=$(du -sh "$DATA_DIR" 2>/dev/null | awk '{print $1}' || echo "unknown")
        success "Data directory size: $data_size"
    else
        error "Data directory not found: $DATA_DIR"
    fi
    
    # Check available space
    local available_gb=$(df -BG / | tail -1 | awk '{print $4}' | sed 's/G//')
    if [[ $available_gb -gt 2 ]]; then
        success "Available disk space: ${available_gb}GB"
    else
        warn "Available disk space: ${available_gb}GB (low)"
    fi
}
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
# API endpoints check
check_api_endpoints() {
    log "Checking key API endpoints..."
    
    local endpoints=(
        "/positions/"
        "/api/chart-data/MNQ%20SEP25?timeframe=1h&days=1"
        "/statistics/"
    )
    
    for endpoint in "${endpoints[@]}"; do
        local url="http://localhost:5000${endpoint}"
        local response_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
        if [[ "$response_code" =~ ^[23] ]]; then
            success "API endpoint $endpoint responding (HTTP $response_code)"
        else
            error "API endpoint $endpoint failed (HTTP $response_code)"
        fi
    done
}
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
# Performance check
check_performance() {
    log "Checking performance metrics..."
    
    # Check response time for health endpoint
    local response_time=$(curl -s -o /dev/null -w "%{time_total}" $HEALTH_ENDPOINT 2>/dev/null || echo "999")
    local response_ms=$(echo "$response_time * 1000" | bc -l 2>/dev/null | cut -d. -f1 || echo "999")
    
    if [[ $response_ms -lt 1000 ]]; then
        success "Health endpoint response time: ${response_ms}ms"
    elif [[ $response_ms -lt 5000 ]]; then
        warn "Health endpoint response time: ${response_ms}ms (slow)"
    else
        error "Health endpoint response time: ${response_ms}ms (very slow)"
    fi
    
    # Check container resource usage
    if docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep -q $APP_NAME; then
        local stats=$(docker stats --no-stream --format "{{.CPUPerc}} {{.MemUsage}}" $APP_NAME 2>/dev/null || echo "N/A N/A")
        success "Container stats: CPU: $(echo $stats | awk '{print $1}'), Memory: $(echo $stats | awk '{print $2}')"
    else
        warn "Unable to retrieve container stats"
    fi
}
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
# Log file check
check_logs() {
    log "Checking log files..."
    
    # Check application logs
    if [[ -d "$DATA_DIR/logs" ]]; then
        success "Log directory exists"
        
        # Check for recent errors
        local error_count=$(find "$DATA_DIR/logs" -name "*.log" -mtime -1 -exec grep -c "ERROR" {} + 2>/dev/null | awk '{sum+=$1} END {print sum+0}')
        if [[ $error_count -eq 0 ]]; then
            success "No errors in recent logs"
        elif [[ $error_count -lt 10 ]]; then
            warn "Found $error_count errors in recent logs"
        else
            error "Found $error_count errors in recent logs (high)"
        fi
    else
        warn "Log directory not found: $DATA_DIR/logs"
    fi
    
    # Check Docker container logs for errors
    local docker_errors=$(docker logs $APP_NAME --since 1h 2>&1 | grep -ci error || echo "0")
    if [[ $docker_errors -eq 0 ]]; then
        success "No errors in recent container logs"
    elif [[ $docker_errors -lt 5 ]]; then
        warn "Found $docker_errors errors in recent container logs"
    else
        error "Found $docker_errors errors in recent container logs (high)"
    fi
}
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
# Summary report
print_summary() {
    echo ""
    echo "========================================"
    echo "         HEALTH CHECK SUMMARY"
    echo "========================================"
    echo -e "✅ Checks Passed: ${GREEN}$CHECKS_PASSED${NC}"
    echo -e "⚠️  Warnings: ${YELLOW}$CHECKS_WARNING${NC}"
    echo -e "❌ Checks Failed: ${RED}$CHECKS_FAILED${NC}"
    echo "========================================"
    
    if [[ $CHECKS_FAILED -eq 0 && $CHECKS_WARNING -eq 0 ]]; then
        echo -e "${GREEN}🎉 All systems healthy!${NC}"
        exit 0
    elif [[ $CHECKS_FAILED -eq 0 ]]; then
        echo -e "${YELLOW}⚠️  System operational with warnings${NC}"
        exit 1
    else
        echo -e "${RED}🚨 Critical issues detected!${NC}"
        exit 2
    fi
}
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
# Main execution
main() {
    echo "========================================"
    echo "    Futures Trading App Health Check"
    echo "========================================"
    
    check_container
    check_application
    check_database
    check_redis
    check_disk_space
    check_api_endpoints
    check_performance
    check_logs
    
    print_summary
}
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
# Install bc if not available (for floating point math)
if ! command -v bc &> /dev/null; then
    log "Installing bc for calculations..."
    sudo apt-get update && sudo apt-get install -y bc 2>/dev/null || true
fi
#!/bin/bash

# Enhanced Health Check Script for Futures Trading Application
# Monitors system health, database connectivity, and trading-specific metrics

set -e

# Configuration
APP_HOST="localhost"
APP_PORT="5000"
HEALTH_ENDPOINT="/health/detailed"
METRICS_ENDPOINT="/metrics"
ALERT_EMAIL="${ALERT_EMAIL:-}"
LOG_FILE="/tmp/health-check.log"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check HTTP endpoint
check_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="${3:-10}"
    
    log "Checking endpoint: $endpoint"
    
    response=$(curl -s -w "%{http_code}" --max-time "$timeout" \
        "http://${APP_HOST}:${APP_PORT}${endpoint}" || echo "000")
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint - Status: $http_code"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint - Status: $http_code"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources"
    
    # CPU Usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}✗${NC} High CPU usage: ${cpu_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        echo -e "${RED}✗${NC} High memory usage: ${memory_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage: ${memory_usage}%"
    fi
    
    # Disk Usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}✗${NC} High disk usage: ${disk_usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
    fi
    
    return 0
}

# Function to check Docker container (if running in Docker)
check_docker_container() {
    log "Checking Docker container status"
    
    if command -v docker &> /dev/null; then
        container_status=$(docker ps --filter "name=futurestradinglog" --format "{{.Status}}" 2>/dev/null || echo "not found")
        
        if [[ "$container_status" == *"Up"* ]]; then
            echo -e "${GREEN}✓${NC} Docker container is running"
            return 0
        else
            echo -e "${RED}✗${NC} Docker container status: $container_status"
            return 1
        fi
    else
        echo -e "${YELLOW}!${NC} Docker not available - skipping container check"
        return 0
    fi
}

# Function to check database
check_database() {
    log "Checking database connectivity via API"
    
    db_health=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', 'unknown'))" 2>/dev/null || echo "error")
    
    if [ "$db_health" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} Database status: $db_health"
        return 1
    fi
}

# Function to check background services
check_background_services() {
    log "Checking background services"
    
    services_status=$(curl -s --max-time 10 "http://${APP_HOST}:${APP_PORT}/health" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('background_services', {})
    running_count = sum(1 for status in services.values() if status)
    total_count = len(services)
    print(f'{running_count}/{total_count}')
except:
    print('error')
" 2>/dev/null || echo "error")
    
    if [[ "$services_status" == *"/"* ]] && [[ ! "$services_status" == "0/"* ]]; then
        echo -e "${GREEN}✓${NC} Background services: $services_status running"
        return 0
    else
        echo -e "${RED}✗${NC} Background services status: $services_status"
        return 1
    fi
}

# Function to send alert email
send_alert() {
    local message="$1"
    
    if [ -n "$ALERT_EMAIL" ]; then
        log "Sending alert email to $ALERT_EMAIL"
        echo "Subject: [CRITICAL] Trading App Health Check Failed
        
Trading Application Health Check Failed

$message

Timestamp: $(date)
Host: $(hostname)
        " | sendmail "$ALERT_EMAIL" 2>/dev/null || \
        log "Failed to send alert email"
    fi
}

# Main health check function
main() {
    log "Starting comprehensive health check"
    echo "Futures Trading Application - Health Check"
    echo "=========================================="
    
    failed_checks=0
    
    # Basic connectivity check
    if ! check_endpoint "/health" "200"; then
        ((failed_checks++))
    fi
    
    # Detailed health check
    if ! check_endpoint "$HEALTH_ENDPOINT" "200"; then
        ((failed_checks++))
    fi
    
    # System resources
    if ! check_system_resources; then
        ((failed_checks++))
    fi
    
    # Docker container
    if ! check_docker_container; then
        ((failed_checks++))
    fi
    
    # Database
    if ! check_database; then
        ((failed_checks++))
    fi
    
    # Background services
    if ! check_background_services; then
        ((failed_checks++))
    fi
    
    # Metrics endpoint (optional)
    if check_endpoint "$METRICS_ENDPOINT" "200"; then
        echo -e "${GREEN}✓${NC} Prometheus metrics available"
    else
        echo -e "${YELLOW}!${NC} Prometheus metrics not available"
    fi
    
    echo "=========================================="
    
    if [ $failed_checks -eq 0 ]; then
        echo -e "${GREEN}✓ All health checks passed${NC}"
        log "Health check completed successfully"
        exit 0
    else
        error_msg="Health check failed - $failed_checks check(s) failed"
        echo -e "${RED}✗ $error_msg${NC}"
        log "$error_msg"
        
        # Send alert for critical failures
        if [ $failed_checks -ge 2 ]; then
            send_alert "$error_msg"
        fi
        
        exit 1
    fi
}

# Run main function
main "$@"
# Run main function
main "$@"