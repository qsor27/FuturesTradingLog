#!/bin/bash
set -euo pipefail

# SSL/TLS Certificate Setup Script for Futures Trading Application
# Configures nginx reverse proxy with SSL/TLS and security headers

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/opt/logs/ssl-setup.log"

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

# Install nginx and certbot if not present
install_prerequisites() {
    log "Installing SSL/TLS prerequisites..."
    
    if command -v apt-get &> /dev/null; then
        apt-get update
        apt-get install -y nginx certbot python3-certbot-nginx openssl
    elif command -v yum &> /dev/null; then
        yum update -y
        yum install -y epel-release
        yum install -y nginx certbot python3-certbot-nginx openssl
    else
        error "Unsupported package manager. Manual installation required."
        exit 1
    fi
    
    # Enable and start nginx
    systemctl enable nginx
    systemctl start nginx
    
    log "Prerequisites installed successfully"
}

# Get domain configuration
get_domain_config() {
    log "Configuring SSL domain settings..."
    
    if [[ -z "${DOMAIN_NAME:-}" ]]; then
        read -p "Enter your domain name (e.g., trading.yourdomain.com): " DOMAIN_NAME
    fi
    
    if [[ -z "$DOMAIN_NAME" ]]; then
        error "Domain name is required for SSL certificate setup"
        exit 1
    fi
    
    if [[ -z "${EMAIL:-}" ]]; then
        read -p "Enter your email for SSL certificate notifications: " EMAIL
    fi
    
    if [[ -z "$EMAIL" ]]; then
        EMAIL="admin@$DOMAIN_NAME"
        warn "Using default email: $EMAIL"
    fi
    
    log "Domain: $DOMAIN_NAME, Email: $EMAIL"
}

# Create nginx configuration for trading application
create_nginx_config() {
    log "Creating nginx configuration for trading application..."
    
    # Create nginx configuration directory
    mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
    
    # Remove default nginx configuration
    rm -f /etc/nginx/sites-enabled/default
    
    # Create trading application nginx configuration
    cat > "/etc/nginx/sites-available/trading-app" << EOF
# Nginx configuration for Futures Trading Application
# Provides SSL/TLS termination and reverse proxy to Flask app

# Rate limiting zones
limit_req_zone \$binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone \$binary_remote_addr zone=login:10m rate=3r/m;

# Upstream definition for Flask application
upstream trading_app {
    server 127.0.0.1:5000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

# HTTP server - redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN_NAME;
    
    # Security headers for HTTP
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Let's Encrypt verification
    location /.well-known/acme-challenge/ {
        root /var/www/html;
        allow all;
    }
    
    # Redirect all other traffic to HTTPS
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

# HTTPS server - main configuration
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAIN_NAME;
    
    # SSL Configuration (certificates will be added by certbot)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_stapling on;
    ssl_stapling_verify on;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' unpkg.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self';" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
    
    # Logging
    access_log /var/log/nginx/trading-app-access.log;
    error_log /var/log/nginx/trading-app-error.log;
    
    # Main application
    location / {
        # Rate limiting
        limit_req zone=api burst=20 nodelay;
        
        # Proxy configuration
        proxy_pass http://trading_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$server_name;
        
        # Timeouts
        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffering
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        
        # Connection keep-alive
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
    
    # Static files optimization
    location /static/ {
        alias /opt/FuturesTradingLog/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header X-Content-Type-Options nosniff always;
        
        # Gzip compression for static files
        gzip on;
        gzip_vary on;
        gzip_types text/css application/javascript application/json text/javascript;
    }
    
    # API endpoints with stricter rate limiting
    location ~ ^/api/(chart-data|trade-markers)/ {
        limit_req zone=api burst=10 nodelay;
        
        proxy_pass http://trading_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # API-specific headers
        add_header X-Content-Type-Options nosniff always;
        add_header X-Frame-Options DENY always;
    }
    
    # Health check endpoint (no rate limiting)
    location /health {
        proxy_pass http://trading_app;
        proxy_set_header Host \$host;
        access_log off;
    }
    
    # Monitoring endpoints (restrict to local networks)
    location /metrics {
        allow 127.0.0.1;
        allow 192.168.0.0/16;
        allow 10.0.0.0/8;
        allow 172.16.0.0/12;
        deny all;
        
        proxy_pass http://trading_app;
        proxy_set_header Host \$host;
    }
    
    # Block access to sensitive paths
    location ~ /\.(git|env|htaccess) {
        deny all;
        return 404;
    }
    
    location ~ /(config|backup|log)/ {
        deny all;
        return 404;
    }
    
    # Favicon
    location = /favicon.ico {
        log_not_found off;
        access_log off;
    }
    
    # Robots.txt
    location = /robots.txt {
        log_not_found off;
        access_log off;
    }
}
EOF
    
    # Enable the site
    ln -sf /etc/nginx/sites-available/trading-app /etc/nginx/sites-enabled/
    
    # Test nginx configuration
    if ! nginx -t; then
        error "Nginx configuration test failed"
        exit 1
    fi
    
    log "Nginx configuration created successfully"
}

# Obtain SSL certificate
obtain_ssl_certificate() {
    log "Obtaining SSL certificate for $DOMAIN_NAME..."
    
    # Reload nginx to serve the new configuration
    systemctl reload nginx
    
    # Try to obtain Let's Encrypt certificate
    if certbot --nginx -d "$DOMAIN_NAME" --non-interactive --agree-tos --email "$EMAIL" --redirect; then
        log "Let's Encrypt certificate obtained successfully"
    else
        warn "Let's Encrypt certificate generation failed. Creating self-signed certificate..."
        create_self_signed_certificate
    fi
    
    # Setup automatic renewal
    setup_certificate_renewal
}

# Create self-signed certificate for testing/development
create_self_signed_certificate() {
    log "Creating self-signed certificate for $DOMAIN_NAME..."
    
    # Create directories
    mkdir -p /etc/ssl/private /etc/ssl/certs
    
    # Generate private key
    openssl genrsa -out "/etc/ssl/private/$DOMAIN_NAME.key" 2048
    
    # Generate certificate
    openssl req -new -x509 -key "/etc/ssl/private/$DOMAIN_NAME.key" \
        -out "/etc/ssl/certs/$DOMAIN_NAME.crt" \
        -days 365 \
        -subj "/C=US/ST=State/L=City/O=FuturesTrading/CN=$DOMAIN_NAME"
    
    # Set proper permissions
    chmod 600 "/etc/ssl/private/$DOMAIN_NAME.key"
    chmod 644 "/etc/ssl/certs/$DOMAIN_NAME.crt"
    
    # Update nginx configuration to use self-signed certificate
    sed -i "s|# ssl_certificate|ssl_certificate /etc/ssl/certs/$DOMAIN_NAME.crt;\n    ssl_certificate_key /etc/ssl/private/$DOMAIN_NAME.key;|g" \
        /etc/nginx/sites-available/trading-app
    
    log "Self-signed certificate created for $DOMAIN_NAME"
}

# Setup automatic certificate renewal
setup_certificate_renewal() {
    log "Setting up automatic certificate renewal..."
    
    # Create renewal script
    cat > /opt/scripts/renew-certificates.sh << 'EOF'
#!/bin/bash
# SSL Certificate Renewal Script

LOG_FILE="/opt/logs/ssl-renewal.log"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Renew certificates
log "Starting certificate renewal..."

if certbot renew --quiet --nginx; then
    log "Certificate renewal successful"
    
    # Reload nginx
    if systemctl reload nginx; then
        log "Nginx reloaded successfully"
    else
        log "ERROR: Failed to reload nginx"
    fi
else
    log "ERROR: Certificate renewal failed"
fi

log "Certificate renewal process completed"
EOF
    
    chmod +x /opt/scripts/renew-certificates.sh
    
    # Add to crontab (run twice daily)
    (crontab -l 2>/dev/null; echo "0 2,14 * * * /opt/scripts/renew-certificates.sh") | crontab -
    
    log "Automatic certificate renewal configured"
}

# Configure nginx security settings
configure_nginx_security() {
    log "Configuring nginx security settings..."
    
    # Update main nginx configuration
    cat > /etc/nginx/conf.d/security.conf << 'EOF'
# Nginx Security Configuration

# Hide nginx version
server_tokens off;

# Buffer overflow protection
client_body_buffer_size 1k;
client_header_buffer_size 1k;
client_max_body_size 10m;
large_client_header_buffers 2 1k;

# Timeout settings
client_body_timeout 10s;
client_header_timeout 10s;
keepalive_timeout 5s 5s;
send_timeout 10s;

# Gzip compression
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types
    text/plain
    text/css
    text/xml
    text/javascript
    application/javascript
    application/xml+rss
    application/json;

# SSL session cache
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
EOF
    
    # Create custom error pages
    mkdir -p /var/www/html/errors
    
    cat > /var/www/html/errors/403.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Access Forbidden</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f0f0f0; padding: 50px; text-align: center; }
        .error { background: white; padding: 30px; border-radius: 5px; max-width: 500px; margin: 0 auto; }
    </style>
</head>
<body>
    <div class="error">
        <h1>403 - Access Forbidden</h1>
        <p>You don't have permission to access this resource.</p>
    </div>
</body>
</html>
EOF
    
    cat > /var/www/html/errors/404.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Page Not Found</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f0f0f0; padding: 50px; text-align: center; }
        .error { background: white; padding: 30px; border-radius: 5px; max-width: 500px; margin: 0 auto; }
    </style>
</head>
<body>
    <div class="error">
        <h1>404 - Page Not Found</h1>
        <p>The requested page could not be found.</p>
    </div>
</body>
</html>
EOF
    
    log "Nginx security settings configured"
}

# Test SSL configuration
test_ssl_config() {
    log "Testing SSL configuration..."
    
    # Test nginx configuration
    if ! nginx -t; then
        error "Nginx configuration test failed"
        exit 1
    fi
    
    # Reload nginx
    systemctl reload nginx
    
    # Test SSL certificate
    log "Testing SSL certificate..."
    
    if command -v openssl &> /dev/null; then
        echo | openssl s_client -connect "$DOMAIN_NAME:443" -servername "$DOMAIN_NAME" 2>/dev/null | \
            openssl x509 -noout -dates | head -2
    fi
    
    # Test HTTP to HTTPS redirect
    log "Testing HTTP to HTTPS redirect..."
    if command -v curl &> /dev/null; then
        local redirect_test=$(curl -s -I "http://$DOMAIN_NAME" | head -1 | grep -c "301\|302" || true)
        if [[ $redirect_test -gt 0 ]]; then
            log "✅ HTTP to HTTPS redirect working"
        else
            warn "❌ HTTP to HTTPS redirect may not be working"
        fi
    fi
    
    log "SSL configuration test completed"
}

# Validate security headers
validate_security_headers() {
    log "Validating security headers..."
    
    if command -v curl &> /dev/null; then
        local headers=$(curl -s -I "https://$DOMAIN_NAME" 2>/dev/null || true)
        
        local checks=(
            "strict-transport-security"
            "x-frame-options"
            "x-content-type-options"
            "x-xss-protection"
            "content-security-policy"
        )
        
        for header in "${checks[@]}"; do
            if echo "$headers" | grep -qi "$header"; then
                log "✅ Security header present: $header"
            else
                warn "❌ Security header missing: $header"
            fi
        done
    else
        warn "curl not available - skipping security header validation"
    fi
}

# Main execution function
main() {
    log "Starting SSL/TLS setup for Futures Trading Application..."
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
        exit 1
    fi
    
    create_log_directory
    install_prerequisites
    get_domain_config
    create_nginx_config
    configure_nginx_security
    obtain_ssl_certificate
    test_ssl_config
    validate_security_headers
    
    log "🎉 SSL/TLS setup completed successfully!"
    log "📋 Configuration summary:"
    log "  • Domain: $DOMAIN_NAME"
    log "  • Certificate: $(if [[ -d /etc/letsencrypt/live ]]; then echo "Let's Encrypt"; else echo "Self-signed"; fi)"
    log "  • Auto-renewal: Configured (runs twice daily)"
    log "  • Security headers: Enabled"
    log "  • Rate limiting: Configured"
    log ""
    log "🔗 Access your application at: https://$DOMAIN_NAME"
    log "📊 Nginx logs: /var/log/nginx/trading-app-*.log"
    log "🔐 SSL logs: /opt/logs/ssl-*.log"
}

# Trap for cleanup on script exit
trap 'error "SSL setup script interrupted"; exit 1' INT TERM

# Execute main function
main "$@"