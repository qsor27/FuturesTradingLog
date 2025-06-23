#!/bin/bash
set -euo pipefail

# Security Hardening Script for Futures Trading Application
# Implements comprehensive security measures for production deployment

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/opt/logs/security-hardening.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

info() {
    local message="[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1"
    echo -e "${BLUE}${message}${NC}"
    echo "$message" >> "$LOG_FILE"
}

# Create log directory
create_log_directory() {
    log "Creating log directory..."
    mkdir -p "$(dirname "$LOG_FILE")"
    chmod 755 "$(dirname "$LOG_FILE")"
}

# System updates and prerequisites
update_system() {
    log "Updating system packages..."
    
    if command -v apt-get &> /dev/null; then
        apt-get update && apt-get upgrade -y
        apt-get install -y ufw fail2ban nginx certbot python3-certbot-nginx jq curl
    elif command -v yum &> /dev/null; then
        yum update -y
        yum install -y epel-release
        yum install -y firewalld fail2ban nginx certbot python3-certbot-nginx jq curl
    else
        error "Unsupported package manager. Manual installation required."
        exit 1
    fi
    
    log "System packages updated successfully"
}

# Configure UFW firewall
configure_firewall() {
    log "Configuring UFW firewall..."
    
    # Reset UFW to defaults
    ufw --force reset
    
    # Default policies
    ufw default deny incoming
    ufw default allow outgoing
    
    # Allow SSH (customize port as needed)
    ufw allow 22/tcp comment 'SSH access'
    
    # Allow HTTP and HTTPS
    ufw allow 80/tcp comment 'HTTP'
    ufw allow 443/tcp comment 'HTTPS'
    
    # Allow application port (behind nginx reverse proxy)
    ufw allow from 127.0.0.1 to any port 5000 comment 'Flask app (localhost only)'
    
    # Allow monitoring ports (restrict to local networks)
    ufw allow from 192.168.0.0/16 to any port 3000 comment 'Grafana (local network)'
    ufw allow from 10.0.0.0/8 to any port 3000 comment 'Grafana (private network)'
    ufw allow from 172.16.0.0/12 to any port 3000 comment 'Grafana (docker network)'
    
    ufw allow from 192.168.0.0/16 to any port 9090 comment 'Prometheus (local network)'
    ufw allow from 10.0.0.0/8 to any port 9090 comment 'Prometheus (private network)'
    ufw allow from 172.16.0.0/12 to any port 9090 comment 'Prometheus (docker network)'
    
    # Redis access (Docker containers only)
    ufw allow from 172.16.0.0/12 to any port 6379 comment 'Redis (docker network)'
    
    # Enable UFW
    ufw --force enable
    
    # Display status
    ufw status verbose
    
    log "UFW firewall configured successfully"
}

# Setup Docker security
configure_docker_security() {
    log "Configuring Docker security..."
    
    # Create Docker daemon configuration directory
    mkdir -p /etc/docker
    
    # Configure Docker daemon with security settings
    cat > /etc/docker/daemon.json << 'EOF'
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "100m",
        "max-file": "3"
    },
    "live-restore": true,
    "userland-proxy": false,
    "no-new-privileges": true,
    "icc": false,
    "userns-remap": "default",
    "default-ulimits": {
        "nofile": {
            "name": "nofile",
            "hard": 64000,
            "soft": 64000
        }
    },
    "storage-driver": "overlay2"
}
EOF
    
    # Restart Docker daemon
    systemctl restart docker
    
    # Verify Docker security configuration
    docker system info | grep -E "(Security Options|User|Logging Driver)" || true
    
    log "Docker security configured successfully"
}

# Setup fail2ban for intrusion detection
configure_fail2ban() {
    log "Configuring fail2ban for intrusion detection..."
    
    # Main fail2ban configuration
    cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
# Ban time in seconds (1 hour)
bantime = 3600

# Time window for counting failures (10 minutes)
findtime = 600

# Maximum failures before ban
maxretry = 5

# Email notifications
destemail = admin@localhost
sendername = Fail2Ban-FuturesTrading
mta = sendmail

# Actions
action = %(action_mwl)s

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 7200

[nginx-http-auth]
enabled = true
port = http,https
filter = nginx-http-auth
logpath = /var/log/nginx/error.log
maxretry = 3

[nginx-noscript]
enabled = true
port = http,https
filter = nginx-noscript
logpath = /var/log/nginx/access.log
maxretry = 6

[nginx-badbots]
enabled = true
port = http,https
filter = nginx-badbots
logpath = /var/log/nginx/access.log
maxretry = 2

[nginx-noproxy]
enabled = true
port = http,https
filter = nginx-noproxy
logpath = /var/log/nginx/access.log
maxretry = 2

[trading-app]
enabled = true
port = 5000
filter = trading-app
logpath = /opt/logs/flask.log
maxretry = 10
bantime = 1800
EOF
    
    # Create custom filter for trading application
    cat > /etc/fail2ban/filter.d/trading-app.conf << 'EOF'
[Definition]
# Detect failed login attempts and suspicious API calls
failregex = ^.*\[.*\] ".*" (40[14]|50[0-3]) .*$
            ^.*Failed authentication from <HOST>.*$
            ^.*Suspicious activity from <HOST>.*$
            ^.*Rate limit exceeded from <HOST>.*$

ignoreregex = ^.*\[.*\] "GET /health" 200 .*$
              ^.*\[.*\] "GET /static" .*$
EOF
    
    # Restart fail2ban
    systemctl restart fail2ban
    systemctl enable fail2ban
    
    # Display status
    fail2ban-client status
    
    log "fail2ban configured successfully"
}

# Setup SSL/TLS certificates
setup_ssl_certificates() {
    log "Setting up SSL/TLS certificates..."
    
    # Check if domain is configured
    read -p "Enter your domain name (e.g., trading.yourdomain.com): " DOMAIN_NAME
    
    if [[ -z "$DOMAIN_NAME" ]]; then
        warn "No domain provided. Skipping SSL certificate setup."
        warn "You can run this later with: ./scripts/setup-ssl.sh"
        return 0
    fi
    
    # Generate self-signed certificate for testing if Let's Encrypt fails
    if ! certbot --nginx -d "$DOMAIN_NAME" --non-interactive --agree-tos --email admin@"$DOMAIN_NAME"; then
        warn "Let's Encrypt certificate generation failed. Creating self-signed certificate..."
        
        mkdir -p /etc/ssl/private /etc/ssl/certs
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout "/etc/ssl/private/$DOMAIN_NAME.key" \
            -out "/etc/ssl/certs/$DOMAIN_NAME.crt" \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN_NAME"
        
        log "Self-signed certificate created for $DOMAIN_NAME"
    else
        log "Let's Encrypt certificate configured for $DOMAIN_NAME"
    fi
    
    # Setup automatic certificate renewal
    echo "0 3 * * * certbot renew --quiet --nginx" | crontab -
    
    log "SSL/TLS certificates configured successfully"
}

# Configure system security settings
configure_system_security() {
    log "Configuring system security settings..."
    
    # Disable unused services
    local unused_services=("telnet" "rsh" "rlogin" "finger")
    for service in "${unused_services[@]}"; do
        if systemctl is-enabled "$service" >/dev/null 2>&1; then
            systemctl disable "$service"
            systemctl stop "$service"
            log "Disabled service: $service"
        fi
    done
    
    # Configure kernel parameters for security
    cat >> /etc/sysctl.conf << 'EOF'

# Security hardening parameters
# Prevent IP spoofing
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# Ignore ICMP ping requests
net.ipv4.icmp_echo_ignore_all = 1

# Ignore ICMP redirects
net.ipv4.conf.all.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0

# Ignore IP source routing
net.ipv4.conf.all.accept_source_route = 0
net.ipv6.conf.all.accept_source_route = 0

# Log martian packets
net.ipv4.conf.all.log_martians = 1

# Disable IPv6 if not needed
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1

# TCP hardening
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.tcp_synack_retries = 2
net.ipv4.tcp_syn_retries = 5
EOF
    
    # Apply sysctl settings
    sysctl -p
    
    # Set secure file permissions for application directories
    chmod 750 /opt/FuturesTradingLog
    chmod 640 /opt/FuturesTradingLog/data/db/*.db 2>/dev/null || true
    
    log "System security settings configured successfully"
}

# Setup log monitoring and rotation
configure_log_monitoring() {
    log "Configuring log monitoring and rotation..."
    
    # Create logrotate configuration for application logs
    cat > /etc/logrotate.d/trading-app << 'EOF'
/opt/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    notifempty
    create 644 root root
    postrotate
        if [ -f /var/run/nginx.pid ]; then
            kill -USR1 `cat /var/run/nginx.pid`
        fi
    endscript
}
EOF
    
    # Setup audit logging for sensitive files
    if command -v auditctl &> /dev/null; then
        # Monitor database files
        auditctl -w /opt/FuturesTradingLog/data/db/ -p wa -k database_access
        
        # Monitor configuration files
        auditctl -w /etc/nginx/ -p wa -k nginx_config
        auditctl -w /etc/fail2ban/ -p wa -k fail2ban_config
        
        log "Audit logging configured for sensitive files"
    fi
    
    log "Log monitoring and rotation configured successfully"
}

# Create security monitoring script
create_security_monitor() {
    log "Creating security monitoring script..."
    
    mkdir -p /opt/scripts
    cat > /opt/scripts/security-monitor.sh << 'EOF'
#!/bin/bash
# Security monitoring script - runs every 5 minutes via cron
set -euo pipefail

LOG_FILE="/opt/logs/security-monitor.log"
ALERT_LOG="/opt/logs/security-alerts.log"

log_alert() {
    local message="[$(date +'%Y-%m-%d %H:%M:%S')] SECURITY ALERT: $1"
    echo "$message" | tee -a "$LOG_FILE" >> "$ALERT_LOG"
}

# Check for failed login attempts
check_failed_logins() {
    local failed_logins=$(grep "Failed password" /var/log/auth.log | tail -10 | wc -l)
    if [[ $failed_logins -gt 5 ]]; then
        log_alert "High number of failed login attempts: $failed_logins"
    fi
}

# Check fail2ban status
check_fail2ban() {
    if ! systemctl is-active --quiet fail2ban; then
        log_alert "fail2ban service is not running"
    fi
    
    local banned_ips=$(fail2ban-client status | grep "Banned IP list" | wc -l)
    if [[ $banned_ips -gt 10 ]]; then
        log_alert "High number of banned IPs: $banned_ips"
    fi
}

# Check for unusual network connections
check_network_connections() {
    local suspicious_connections=$(netstat -tuln | grep LISTEN | grep -v -E "(22|80|443|5000|3000|9090|6379)" | wc -l)
    if [[ $suspicious_connections -gt 0 ]]; then
        log_alert "Suspicious network connections detected"
    fi
}

# Check Docker container security
check_container_security() {
    # Check if containers are running as root
    local root_containers=$(docker ps --format "table {{.Names}}" | tail -n +2 | xargs -I {} docker exec {} whoami 2>/dev/null | grep -c "root" || true)
    if [[ $root_containers -gt 0 ]]; then
        log_alert "Containers running as root detected: $root_containers"
    fi
}

# Main monitoring function
main() {
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Starting security monitoring..." >> "$LOG_FILE"
    
    check_failed_logins
    check_fail2ban
    check_network_connections
    check_container_security
    
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Security monitoring completed" >> "$LOG_FILE"
}

main
EOF
    
    chmod +x /opt/scripts/security-monitor.sh
    
    # Add to crontab
    (crontab -l 2>/dev/null; echo "*/5 * * * * /opt/scripts/security-monitor.sh") | crontab -
    
    log "Security monitoring script created and scheduled"
}

# Validate security configuration
validate_security_config() {
    log "Validating security configuration..."
    
    local errors=0
    
    # Check UFW status
    if ! ufw status | grep -q "Status: active"; then
        error "UFW firewall is not active"
        ((errors++))
    fi
    
    # Check fail2ban status
    if ! systemctl is-active --quiet fail2ban; then
        error "fail2ban service is not running"
        ((errors++))
    fi
    
    # Check Docker security
    if ! docker system info | grep -q "User"; then
        warn "Docker user namespace remapping may not be configured"
    fi
    
    # Check SSL certificate
    if [[ -d /etc/letsencrypt/live ]]; then
        log "SSL certificates found"
    else
        warn "No SSL certificates found - consider running setup-ssl.sh"
    fi
    
    if [[ $errors -eq 0 ]]; then
        log "✅ Security configuration validation passed"
    else
        error "❌ Security configuration validation failed with $errors errors"
        return 1
    fi
}

# Main execution function
main() {
    log "Starting comprehensive security hardening for Futures Trading Application..."
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
        exit 1
    fi
    
    create_log_directory
    update_system
    configure_firewall
    configure_docker_security
    configure_fail2ban
    setup_ssl_certificates
    configure_system_security
    configure_log_monitoring
    create_security_monitor
    validate_security_config
    
    log "🎉 Security hardening completed successfully!"
    log "📋 Next steps:"
    log "  1. Configure your domain name and run ./scripts/setup-ssl.sh"
    log "  2. Review nginx configuration in /etc/nginx/sites-available/"
    log "  3. Monitor security logs in /opt/logs/security-*.log"
    log "  4. Test fail2ban with: fail2ban-client status"
    log "  5. Verify firewall rules with: ufw status verbose"
}

# Trap for cleanup on script exit
trap 'error "Security hardening script interrupted"; exit 1' INT TERM

# Execute main function
main "$@"