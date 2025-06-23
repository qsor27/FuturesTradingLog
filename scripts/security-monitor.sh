#!/bin/bash
# Security Monitoring Script for Futures Trading Application
# Runs continuously to monitor security events and system health

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/opt/logs/security-monitor.log"
ALERT_LOG="/opt/logs/security-alerts.log"
METRICS_FILE="/opt/logs/security-metrics.json"

# Thresholds
MAX_FAILED_LOGINS=5
MAX_BANNED_IPS=10
MAX_CPU_USAGE=80
MAX_MEMORY_USAGE=80
MAX_DISK_USAGE=85

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create log directories
mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$(dirname "$ALERT_LOG")"
mkdir -p "$(dirname "$METRICS_FILE")"

# Logging functions
log() {
    local message="[$(date +'%Y-%m-%d %H:%M:%S')] $1"
    echo -e "${GREEN}${message}${NC}"
    echo "$message" >> "$LOG_FILE"
}

warn() {
    local message="[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1"
    echo -e "${YELLOW}${message}${NC}"
    echo "$message" >> "$LOG_FILE"
}

error() {
    local message="[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1"
    echo -e "${RED}${message}${NC}"
    echo "$message" >> "$LOG_FILE"
}

alert() {
    local message="[$(date +'%Y-%m-%d %H:%M:%S')] SECURITY ALERT: $1"
    echo -e "${RED}${message}${NC}"
    echo "$message" | tee -a "$LOG_FILE" >> "$ALERT_LOG"
    
    # Send email alert if configured
    if command -v mail &> /dev/null && [[ -n "${ALERT_EMAIL:-}" ]]; then
        echo "$message" | mail -s "Security Alert - Futures Trading App" "$ALERT_EMAIL"
    fi
}

info() {
    local message="[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1"
    echo -e "${BLUE}${message}${NC}"
    echo "$message" >> "$LOG_FILE"
}

# Check for failed login attempts
check_failed_logins() {
    local failed_logins=0
    
    if [[ -f /var/log/auth.log ]]; then
        # Count failed SSH logins in the last 10 minutes
        failed_logins=$(grep "Failed password" /var/log/auth.log | \
                       awk -v date="$(date -d '10 minutes ago' '+%b %d %H:%M')" '$0 > date' | \
                       wc -l)
    fi
    
    if [[ $failed_logins -gt $MAX_FAILED_LOGINS ]]; then
        alert "High number of failed SSH login attempts: $failed_logins in last 10 minutes"
        
        # Get attacking IPs
        local attacking_ips=$(grep "Failed password" /var/log/auth.log | \
                             awk -v date="$(date -d '10 minutes ago' '+%b %d %H:%M')" '$0 > date' | \
                             grep -oE 'from [0-9.]+' | awk '{print $2}' | sort | uniq -c | sort -nr | head -5)
        
        info "Top attacking IPs: $attacking_ips"
    fi
    
    return 0
}

# Check fail2ban status and banned IPs
check_fail2ban() {
    if ! systemctl is-active --quiet fail2ban; then
        alert "fail2ban service is not running"
        return 1
    fi
    
    # Get number of banned IPs across all jails
    local banned_ips=0
    if command -v fail2ban-client &> /dev/null; then
        banned_ips=$(fail2ban-client status | grep -o "Banned IP list.*" | wc -l)
        
        # Get detailed jail status
        local jails=$(fail2ban-client status | grep "Jail list:" | sed 's/.*Jail list:[[:space:]]*//' | tr ',' '\n')
        
        for jail in $jails; do
            jail=$(echo "$jail" | xargs)  # trim whitespace
            if [[ -n "$jail" ]]; then
                local jail_banned=$(fail2ban-client status "$jail" 2>/dev/null | grep "Currently banned:" | awk '{print $3}' || echo "0")
                if [[ $jail_banned -gt 0 ]]; then
                    info "Jail '$jail' has $jail_banned banned IPs"
                fi
            fi
        done
    fi
    
    if [[ $banned_ips -gt $MAX_BANNED_IPS ]]; then
        alert "High number of banned IPs across all jails: $banned_ips"
    fi
    
    return 0
}

# Check for suspicious network connections
check_network_connections() {
    # Check for unexpected listening ports
    local suspicious_ports=$(netstat -tuln 2>/dev/null | grep LISTEN | \
                           awk '{print $4}' | sed 's/.*://' | \
                           grep -v -E "^(22|53|80|443|5000|3000|6379|9090)$" | \
                           sort | uniq)
    
    if [[ -n "$suspicious_ports" ]]; then
        warn "Unexpected listening ports detected: $suspicious_ports"
    fi
    
    # Check for high number of connections
    local connection_count=$(netstat -an 2>/dev/null | grep ESTABLISHED | wc -l)
    if [[ $connection_count -gt 100 ]]; then
        warn "High number of established connections: $connection_count"
    fi
    
    return 0
}

# Check Docker container security
check_container_security() {
    if ! command -v docker &> /dev/null; then
        return 0
    fi
    
    # Check if containers are running as root
    local containers=$(docker ps --format "{{.Names}}" 2>/dev/null || true)
    local root_containers=0
    
    for container in $containers; do
        local user=$(docker exec "$container" whoami 2>/dev/null || echo "unknown")
        if [[ "$user" == "root" ]]; then
            ((root_containers++))
            warn "Container '$container' is running as root user"
        fi
    done
    
    if [[ $root_containers -gt 0 ]]; then
        alert "Found $root_containers containers running as root"
    fi
    
    # Check for containers with excessive privileges
    local privileged_containers=$(docker ps --filter "label=privileged=true" --format "{{.Names}}" 2>/dev/null | wc -l || echo "0")
    if [[ $privileged_containers -gt 0 ]]; then
        warn "Found $privileged_containers privileged containers"
    fi
    
    return 0
}

# Check system resource usage
check_system_resources() {
    # CPU usage
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//' || echo "0")
    cpu_usage=${cpu_usage%.*}  # Remove decimal part
    
    if [[ $cpu_usage -gt $MAX_CPU_USAGE ]]; then
        alert "High CPU usage detected: ${cpu_usage}%"
    fi
    
    # Memory usage
    local memory_usage=$(free | grep '^Mem' | awk '{printf "%.0f", $3/$2 * 100.0}')
    
    if [[ $memory_usage -gt $MAX_MEMORY_USAGE ]]; then
        alert "High memory usage detected: ${memory_usage}%"
    fi
    
    # Disk usage
    local disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    
    if [[ $disk_usage -gt $MAX_DISK_USAGE ]]; then
        alert "High disk usage detected: ${disk_usage}%"
    fi
    
    # Check for critical disk space (less than 1GB)
    local free_space_gb=$(df / | tail -1 | awk '{printf "%.1f", $4/1024/1024}')
    if (( $(echo "$free_space_gb < 1.0" | bc -l 2>/dev/null || echo "0") )); then
        alert "Critical disk space: only ${free_space_gb}GB free"
    fi
    
    return 0
}

# Check application-specific security
check_application_security() {
    # Check if trading application is running
    if ! pgrep -f "python.*app.py" > /dev/null; then
        alert "Trading application process not found"
    fi
    
    # Check application logs for security events
    local app_log="/opt/logs/flask.log"
    if [[ -f "$app_log" ]]; then
        # Check for 4xx/5xx errors in last 10 minutes
        local error_count=$(grep "$(date -d '10 minutes ago' '+%Y-%m-%d %H:%M')" "$app_log" 2>/dev/null | \
                          grep -E " (4[0-9]{2}|5[0-9]{2}) " | wc -l || echo "0")
        
        if [[ $error_count -gt 20 ]]; then
            warn "High number of HTTP errors in application log: $error_count in last 10 minutes"
        fi
        
        # Check for security-related log entries
        local security_events=$(grep -i "security\|attack\|intrusion\|malicious" "$app_log" 2>/dev/null | \
                              tail -10 | wc -l || echo "0")
        
        if [[ $security_events -gt 0 ]]; then
            warn "Security-related events found in application log: $security_events"
        fi
    fi
    
    return 0
}

# Check SSL certificate expiration
check_ssl_certificates() {
    if [[ -d /etc/letsencrypt/live ]]; then
        for cert_dir in /etc/letsencrypt/live/*/; do
            if [[ -f "$cert_dir/cert.pem" ]]; then
                local domain=$(basename "$cert_dir")
                local expiry_date=$(openssl x509 -in "$cert_dir/cert.pem" -noout -enddate 2>/dev/null | cut -d= -f2)
                local expiry_epoch=$(date -d "$expiry_date" +%s 2>/dev/null || echo "0")
                local current_epoch=$(date +%s)
                local days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))
                
                if [[ $days_until_expiry -lt 30 ]]; then
                    if [[ $days_until_expiry -lt 7 ]]; then
                        alert "SSL certificate for $domain expires in $days_until_expiry days"
                    else
                        warn "SSL certificate for $domain expires in $days_until_expiry days"
                    fi
                fi
            fi
        done
    fi
    
    return 0
}

# Generate security metrics JSON
generate_metrics() {
    local timestamp=$(date +%s)
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//' || echo "0")
    local memory_usage=$(free | grep '^Mem' | awk '{printf "%.0f", $3/$2 * 100.0}')
    local disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    local failed_logins=$(grep "Failed password" /var/log/auth.log 2>/dev/null | tail -100 | wc -l || echo "0")
    local banned_ips=$(fail2ban-client status 2>/dev/null | grep -o "Banned IP list.*" | wc -l || echo "0")
    
    cat > "$METRICS_FILE" << EOF
{
    "timestamp": $timestamp,
    "datetime": "$(date +'%Y-%m-%d %H:%M:%S')",
    "system": {
        "cpu_usage": ${cpu_usage%.*},
        "memory_usage": $memory_usage,
        "disk_usage": $disk_usage
    },
    "security": {
        "failed_logins": $failed_logins,
        "banned_ips": $banned_ips,
        "fail2ban_active": $(systemctl is-active --quiet fail2ban && echo "true" || echo "false"),
        "firewall_active": $(ufw status | grep -q "Status: active" && echo "true" || echo "false")
    },
    "application": {
        "process_running": $(pgrep -f "python.*app.py" > /dev/null && echo "true" || echo "false"),
        "docker_containers": $(docker ps --format "{{.Names}}" 2>/dev/null | wc -l || echo "0")
    }
}
EOF
}

# Main monitoring function
main() {
    log "Starting security monitoring cycle..."
    
    # Run all security checks
    check_failed_logins
    check_fail2ban
    check_network_connections
    check_container_security
    check_system_resources
    check_application_security
    check_ssl_certificates
    
    # Generate metrics
    generate_metrics
    
    log "Security monitoring cycle completed"
}

# Handle script arguments
case "${1:-monitor}" in
    "monitor")
        main
        ;;
    "continuous")
        log "Starting continuous security monitoring (5-minute intervals)..."
        while true; do
            main
            sleep 300  # 5 minutes
        done
        ;;
    "test")
        log "Running security monitoring test..."
        main
        log "Test completed. Check logs at: $LOG_FILE"
        ;;
    "metrics")
        generate_metrics
        cat "$METRICS_FILE"
        ;;
    *)
        echo "Usage: $0 {monitor|continuous|test|metrics}"
        echo "  monitor     - Run one monitoring cycle (default)"
        echo "  continuous  - Run continuous monitoring with 5-minute intervals"
        echo "  test        - Run test monitoring cycle"
        echo "  metrics     - Generate and display current metrics JSON"
        exit 1
        ;;
esac