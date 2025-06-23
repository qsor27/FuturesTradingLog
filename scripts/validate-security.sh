#!/bin/bash
set -euo pipefail

# Security Configuration Validation Script
# Validates all security components and configurations

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/opt/logs/security-validation.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

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
    ((WARNINGS++))
}

error() {
    local message="[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1"
    echo -e "${RED}${message}${NC}"
    echo "$message" >> "$LOG_FILE"
    ((FAILED++))
}

pass() {
    local message="[$(date +'%Y-%m-%d %H:%M:%S')] PASS: $1"
    echo -e "${GREEN}✅ ${message}${NC}"
    echo "$message" >> "$LOG_FILE"
    ((PASSED++))
}

fail() {
    local message="[$(date +'%Y-%m-%d %H:%M:%S')] FAIL: $1"
    echo -e "${RED}❌ ${message}${NC}"
    echo "$message" >> "$LOG_FILE"
    ((FAILED++))
}

info() {
    local message="[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1"
    echo -e "${BLUE}${message}${NC}"
    echo "$message" >> "$LOG_FILE"
}

# Create log directory
create_log_directory() {
    mkdir -p "$(dirname "$LOG_FILE")"
    chmod 755 "$(dirname "$LOG_FILE")"
}

# Check UFW firewall configuration
check_ufw_firewall() {
    info "Checking UFW firewall configuration..."
    
    if ! command -v ufw &> /dev/null; then
        fail "UFW is not installed"
        return 1
    fi
    
    local ufw_status=$(ufw status | head -1)
    if [[ "$ufw_status" == *"Status: active"* ]]; then
        pass "UFW firewall is active"
    else
        fail "UFW firewall is not active"
        return 1
    fi
    
    # Check default policies
    local incoming_policy=$(ufw status verbose | grep "Default:" | grep "incoming" | awk '{print $2}')
    local outgoing_policy=$(ufw status verbose | grep "Default:" | grep "outgoing" | awk '{print $2}')
    
    if [[ "$incoming_policy" == "deny" ]]; then
        pass "Default incoming policy is deny"
    else
        fail "Default incoming policy is not deny (current: $incoming_policy)"
    fi
    
    if [[ "$outgoing_policy" == "allow" ]]; then
        pass "Default outgoing policy is allow"
    else
        warn "Default outgoing policy is not allow (current: $outgoing_policy)"
    fi
    
    # Check essential ports
    local essential_ports=("22/tcp" "80/tcp" "443/tcp")
    for port in "${essential_ports[@]}"; do
        if ufw status | grep -q "$port"; then
            pass "Port $port is configured in UFW"
        else
            warn "Port $port is not configured in UFW"
        fi
    done
    
    return 0
}

# Check fail2ban configuration
check_fail2ban() {
    info "Checking fail2ban configuration..."
    
    if ! command -v fail2ban-client &> /dev/null; then
        fail "fail2ban is not installed"
        return 1
    fi
    
    if systemctl is-active --quiet fail2ban; then
        pass "fail2ban service is running"
    else
        fail "fail2ban service is not running"
        return 1
    fi
    
    if systemctl is-enabled --quiet fail2ban; then
        pass "fail2ban service is enabled"
    else
        warn "fail2ban service is not enabled"
    fi
    
    # Check jail configuration
    if [[ -f /etc/fail2ban/jail.local ]]; then
        pass "fail2ban jail.local configuration exists"
    else
        fail "fail2ban jail.local configuration not found"
    fi
    
    # Check active jails
    local active_jails=$(fail2ban-client status | grep "Jail list:" | sed 's/.*Jail list:[[:space:]]*//' | wc -w)
    if [[ $active_jails -gt 0 ]]; then
        pass "fail2ban has $active_jails active jails"
        
        # List active jails
        local jails=$(fail2ban-client status | grep "Jail list:" | sed 's/.*Jail list:[[:space:]]*//' | tr ',' ' ')
        for jail in $jails; do
            jail=$(echo "$jail" | xargs)  # trim whitespace
            if [[ -n "$jail" ]]; then
                local jail_status=$(fail2ban-client status "$jail" 2>/dev/null | grep "Currently banned:" | awk '{print $3}' || echo "0")
                info "Jail '$jail' has $jail_status banned IPs"
            fi
        done
    else
        warn "fail2ban has no active jails"
    fi
    
    return 0
}

# Check nginx configuration
check_nginx() {
    info "Checking nginx configuration..."
    
    if ! command -v nginx &> /dev/null; then
        fail "nginx is not installed"
        return 1
    fi
    
    if systemctl is-active --quiet nginx; then
        pass "nginx service is running"
    else
        fail "nginx service is not running"
        return 1
    fi
    
    if systemctl is-enabled --quiet nginx; then
        pass "nginx service is enabled"
    else
        warn "nginx service is not enabled"
    fi
    
    # Test nginx configuration
    if nginx -t 2>/dev/null; then
        pass "nginx configuration test passed"
    else
        fail "nginx configuration test failed"
        return 1
    fi
    
    # Check for trading app configuration
    if [[ -f /etc/nginx/sites-available/trading-app ]]; then
        pass "nginx trading app configuration exists"
    else
        warn "nginx trading app configuration not found"
    fi
    
    if [[ -L /etc/nginx/sites-enabled/trading-app ]]; then
        pass "nginx trading app site is enabled"
    else
        warn "nginx trading app site is not enabled"
    fi
    
    # Check for security headers in configuration
    local config_file="/etc/nginx/sites-available/trading-app"
    if [[ -f "$config_file" ]]; then
        local security_headers=("Strict-Transport-Security" "X-Frame-Options" "X-Content-Type-Options" "X-XSS-Protection")
        for header in "${security_headers[@]}"; do
            if grep -q "$header" "$config_file"; then
                pass "Security header '$header' configured"
            else
                warn "Security header '$header' not found in configuration"
            fi
        done
    fi
    
    return 0
}

# Check SSL/TLS configuration
check_ssl() {
    info "Checking SSL/TLS configuration..."
    
    # Check for Let's Encrypt certificates
    if [[ -d /etc/letsencrypt/live ]]; then
        local cert_count=$(find /etc/letsencrypt/live -name "cert.pem" | wc -l)
        if [[ $cert_count -gt 0 ]]; then
            pass "Found $cert_count SSL certificate(s)"
            
            # Check certificate expiration
            for cert_dir in /etc/letsencrypt/live/*/; do
                if [[ -f "$cert_dir/cert.pem" ]]; then
                    local domain=$(basename "$cert_dir")
                    local expiry_date=$(openssl x509 -in "$cert_dir/cert.pem" -noout -enddate 2>/dev/null | cut -d= -f2)
                    local expiry_epoch=$(date -d "$expiry_date" +%s 2>/dev/null || echo "0")
                    local current_epoch=$(date +%s)
                    local days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))
                    
                    if [[ $days_until_expiry -gt 30 ]]; then
                        pass "SSL certificate for $domain is valid for $days_until_expiry days"
                    elif [[ $days_until_expiry -gt 7 ]]; then
                        warn "SSL certificate for $domain expires in $days_until_expiry days"
                    else
                        fail "SSL certificate for $domain expires in $days_until_expiry days"
                    fi
                fi
            done
        else
            warn "No Let's Encrypt certificates found"
        fi
    else
        warn "Let's Encrypt directory not found"
    fi
    
    # Check for self-signed certificates
    if [[ -d /etc/ssl/certs ]] && [[ -d /etc/ssl/private ]]; then
        local self_signed=$(find /etc/ssl/certs -name "*.crt" | wc -l)
        if [[ $self_signed -gt 0 ]]; then
            info "Found $self_signed self-signed certificate(s)"
        fi
    fi
    
    # Check SSL configuration in nginx
    if [[ -f /etc/nginx/sites-available/trading-app ]]; then
        if grep -q "ssl_protocols" /etc/nginx/sites-available/trading-app; then
            pass "SSL protocols configured in nginx"
        else
            warn "SSL protocols not configured in nginx"
        fi
        
        if grep -q "ssl_ciphers" /etc/nginx/sites-available/trading-app; then
            pass "SSL ciphers configured in nginx"
        else
            warn "SSL ciphers not configured in nginx"
        fi
    fi
    
    return 0
}

# Check Docker security
check_docker_security() {
    info "Checking Docker security configuration..."
    
    if ! command -v docker &> /dev/null; then
        warn "Docker is not installed"
        return 0
    fi
    
    # Check Docker daemon configuration
    if [[ -f /etc/docker/daemon.json ]]; then
        pass "Docker daemon configuration exists"
        
        # Check security settings
        local config_file="/etc/docker/daemon.json"
        local security_settings=("no-new-privileges" "userland-proxy" "live-restore")
        
        for setting in "${security_settings[@]}"; do
            if grep -q "$setting" "$config_file"; then
                pass "Docker security setting '$setting' configured"
            else
                warn "Docker security setting '$setting' not found"
            fi
        done
    else
        warn "Docker daemon configuration not found"
    fi
    
    # Check running containers
    local containers=$(docker ps --format "{{.Names}}" 2>/dev/null || true)
    if [[ -n "$containers" ]]; then
        info "Checking running containers..."
        
        for container in $containers; do
            # Check if running as root
            local user=$(docker exec "$container" whoami 2>/dev/null || echo "unknown")
            if [[ "$user" == "root" ]]; then
                warn "Container '$container' is running as root"
            else
                pass "Container '$container' is running as non-root user ($user)"
            fi
        done
    else
        info "No running containers found"
    fi
    
    return 0
}

# Check system security settings
check_system_security() {
    info "Checking system security settings..."
    
    # Check for important security packages
    local security_packages=("ufw" "fail2ban" "nginx" "openssl")
    for package in "${security_packages[@]}"; do
        if command -v "$package" &> /dev/null; then
            pass "Security package '$package' is installed"
        else
            fail "Security package '$package' is not installed"
        fi
    done
    
    # Check kernel parameters
    if [[ -f /etc/sysctl.conf ]]; then
        local security_params=("net.ipv4.conf.all.rp_filter" "net.ipv4.tcp_syncookies" "net.ipv4.icmp_echo_ignore_all")
        for param in "${security_params[@]}"; do
            if grep -q "$param" /etc/sysctl.conf; then
                pass "Security parameter '$param' is configured"
            else
                warn "Security parameter '$param' is not configured"
            fi
        done
    else
        warn "System control configuration (/etc/sysctl.conf) not found"
    fi
    
    # Check for unused services
    local unused_services=("telnet" "rsh" "rlogin" "finger")
    for service in "${unused_services[@]}"; do
        if systemctl is-enabled "$service" >/dev/null 2>&1; then
            fail "Insecure service '$service' is enabled"
        else
            pass "Insecure service '$service' is disabled or not installed"
        fi
    done
    
    return 0
}

# Check log security and rotation
check_log_security() {
    info "Checking log security and rotation..."
    
    # Check log directories
    local log_dirs=("/opt/logs" "/var/log/nginx" "/var/log/fail2ban")
    for log_dir in "${log_dirs[@]}"; do
        if [[ -d "$log_dir" ]]; then
            pass "Log directory '$log_dir' exists"
            
            # Check permissions
            local perms=$(stat -c "%a" "$log_dir")
            if [[ "$perms" =~ ^(755|750|700)$ ]]; then
                pass "Log directory '$log_dir' has secure permissions ($perms)"
            else
                warn "Log directory '$log_dir' has potentially insecure permissions ($perms)"
            fi
        else
            warn "Log directory '$log_dir' does not exist"
        fi
    done
    
    # Check logrotate configuration
    if [[ -f /etc/logrotate.d/trading-app ]]; then
        pass "Log rotation configuration exists for trading app"
    else
        warn "Log rotation configuration not found for trading app"
    fi
    
    # Check if logrotate service is running
    if systemctl is-active --quiet logrotate.timer 2>/dev/null || crontab -l | grep -q logrotate 2>/dev/null; then
        pass "Log rotation is scheduled"
    else
        warn "Log rotation may not be scheduled"
    fi
    
    return 0
}

# Check network security
check_network_security() {
    info "Checking network security..."
    
    # Check listening ports
    local listening_ports=$(netstat -tuln 2>/dev/null | grep LISTEN | awk '{print $4}' | sed 's/.*://' | sort -n | uniq)
    
    info "Listening ports: $(echo $listening_ports | tr '\n' ' ')"
    
    # Check for unexpected ports
    local expected_ports=("22" "53" "80" "443" "5000" "3000" "6379" "9090")
    local unexpected_ports=""
    
    for port in $listening_ports; do
        local is_expected=false
        for expected in "${expected_ports[@]}"; do
            if [[ "$port" == "$expected" ]]; then
                is_expected=true
                break
            fi
        done
        
        if [[ "$is_expected" == false ]]; then
            unexpected_ports="$unexpected_ports $port"
        fi
    done
    
    if [[ -n "$unexpected_ports" ]]; then
        warn "Unexpected listening ports found:$unexpected_ports"
    else
        pass "No unexpected listening ports found"
    fi
    
    # Check for high number of connections
    local connection_count=$(netstat -an 2>/dev/null | grep ESTABLISHED | wc -l)
    if [[ $connection_count -gt 100 ]]; then
        warn "High number of established connections: $connection_count"
    else
        pass "Normal number of established connections: $connection_count"
    fi
    
    return 0
}

# Check application security
check_application_security() {
    info "Checking application security..."
    
    # Check if trading application is running
    if pgrep -f "python.*app.py" > /dev/null; then
        pass "Trading application process is running"
    else
        fail "Trading application process not found"
    fi
    
    # Check application configuration
    local app_config="$PROJECT_ROOT/config.py"
    if [[ -f "$app_config" ]]; then
        pass "Application configuration file exists"
        
        # Check for debug mode
        if grep -q "DEBUG.*=.*False" "$app_config" || ! grep -q "DEBUG.*=.*True" "$app_config"; then
            pass "Debug mode appears to be disabled"
        else
            fail "Debug mode may be enabled in production"
        fi
    else
        warn "Application configuration file not found"
    fi
    
    # Check for environment variables
    local env_file="$PROJECT_ROOT/.env"
    if [[ -f "$env_file" ]]; then
        warn "Environment file exists - ensure it contains no secrets"
    fi
    
    # Check file permissions for sensitive files
    local sensitive_files=("$PROJECT_ROOT/TradingLog_db.py" "$PROJECT_ROOT/config.py")
    for file in "${sensitive_files[@]}"; do
        if [[ -f "$file" ]]; then
            local perms=$(stat -c "%a" "$file")
            if [[ "$perms" =~ ^(600|644|640)$ ]]; then
                pass "Sensitive file '$file' has secure permissions ($perms)"
            else
                warn "Sensitive file '$file' has potentially insecure permissions ($perms)"
            fi
        fi
    done
    
    return 0
}

# Generate security report
generate_security_report() {
    info "Generating security report..."
    
    local report_file="/opt/logs/security-report-$(date +%Y%m%d-%H%M%S).json"
    mkdir -p "$(dirname "$report_file")"
    
    cat > "$report_file" << EOF
{
    "timestamp": "$(date +'%Y-%m-%d %H:%M:%S')",
    "validation_summary": {
        "passed": $PASSED,
        "failed": $FAILED,
        "warnings": $WARNINGS,
        "total_checks": $((PASSED + FAILED + WARNINGS))
    },
    "system_info": {
        "hostname": "$(hostname)",
        "os": "$(lsb_release -d -s 2>/dev/null || echo 'Unknown')",
        "kernel": "$(uname -r)",
        "uptime": "$(uptime -p 2>/dev/null || echo 'Unknown')"
    },
    "security_services": {
        "ufw_active": $(ufw status | grep -q "Status: active" && echo "true" || echo "false"),
        "fail2ban_active": $(systemctl is-active --quiet fail2ban && echo "true" || echo "false"),
        "nginx_active": $(systemctl is-active --quiet nginx && echo "true" || echo "false")
    },
    "certificates": {
        "letsencrypt_count": $(find /etc/letsencrypt/live -name "cert.pem" 2>/dev/null | wc -l),
        "self_signed_count": $(find /etc/ssl/certs -name "*.crt" 2>/dev/null | wc -l)
    },
    "network": {
        "listening_ports": "$(netstat -tuln 2>/dev/null | grep LISTEN | awk '{print $4}' | sed 's/.*://' | sort -n | uniq | tr '\n' ' ')",
        "established_connections": $(netstat -an 2>/dev/null | grep ESTABLISHED | wc -l)
    }
}
EOF
    
    info "Security report generated: $report_file"
}

# Main validation function
main() {
    log "Starting comprehensive security validation..."
    
    create_log_directory
    
    # Run all security checks
    check_ufw_firewall
    check_fail2ban
    check_nginx
    check_ssl
    check_docker_security
    check_system_security
    check_log_security
    check_network_security
    check_application_security
    
    # Generate report
    generate_security_report
    
    # Summary
    echo ""
    log "🏁 Security Validation Summary:"
    log "✅ Passed: $PASSED"
    log "❌ Failed: $FAILED"
    log "⚠️  Warnings: $WARNINGS"
    log "📊 Total Checks: $((PASSED + FAILED + WARNINGS))"
    
    if [[ $FAILED -eq 0 ]]; then
        log "🎉 All critical security checks passed!"
        if [[ $WARNINGS -gt 0 ]]; then
            log "⚠️  Please review $WARNINGS warning(s) for security improvements"
        fi
        exit 0
    else
        error "❌ $FAILED security check(s) failed - immediate attention required!"
        exit 1
    fi
}

# Handle script arguments
case "${1:-validate}" in
    "validate")
        main
        ;;
    "report-only")
        create_log_directory
        generate_security_report
        ;;
    "quick")
        log "Running quick security validation..."
        create_log_directory
        check_ufw_firewall
        check_fail2ban
        check_nginx
        log "Quick validation completed. Passed: $PASSED, Failed: $FAILED, Warnings: $WARNINGS"
        ;;
    *)
        echo "Usage: $0 {validate|report-only|quick}"
        echo "  validate     - Run full security validation (default)"
        echo "  report-only  - Generate security report only"
        echo "  quick        - Run quick validation of essential services"
        exit 1
        ;;
esac