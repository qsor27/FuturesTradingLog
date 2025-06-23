# Security Hardening Setup Guide
## Futures Trading Application Production Security

This guide provides comprehensive security hardening for the Futures Trading Application, implementing enterprise-grade security measures suitable for financial applications.

## 🔐 Security Components Implemented

### 1. Firewall Configuration (UFW)
- **Default Policies**: Deny incoming, allow outgoing
- **Allowed Ports**: SSH (22), HTTP (80), HTTPS (443)
- **Application Access**: Flask app restricted to localhost only
- **Monitoring Access**: Grafana/Prometheus restricted to local networks
- **Container Communication**: Docker networks isolated

### 2. Intrusion Detection (fail2ban)
- **SSH Brute Force Protection**: 3 attempts, 2-hour ban
- **Nginx Attack Protection**: Multiple filters for common attacks
- **Application-Specific Protection**: Trading app error monitoring
- **API Abuse Prevention**: Rate limiting violation detection
- **Email Alerts**: Configurable email notifications for security events

### 3. SSL/TLS Configuration
- **Let's Encrypt Integration**: Automatic certificate management
- **Self-Signed Fallback**: Development/testing support
- **Security Headers**: HSTS, CSP, XSS protection, frame options
- **Modern Protocols**: TLS 1.2/1.3 only
- **Automatic Renewal**: Twice-daily certificate refresh checks

### 4. Nginx Reverse Proxy
- **SSL Termination**: Secure HTTPS handling
- **Rate Limiting**: API endpoint protection
- **Static File Optimization**: Efficient asset serving
- **Security Headers**: Comprehensive browser protection
- **Access Control**: Path-based restrictions

### 5. Docker Security
- **Non-Root Execution**: User namespace remapping
- **Resource Limits**: CPU, memory, file descriptor limits
- **Network Isolation**: Container communication restrictions
- **Security Profiles**: Seccomp and AppArmor integration
- **Logging Controls**: Structured log management

### 6. System Hardening
- **Kernel Parameters**: IP spoofing prevention, TCP hardening
- **Service Disabling**: Unused/insecure services removed
- **File Permissions**: Secure application directory access
- **Audit Logging**: Sensitive file monitoring
- **Log Rotation**: Automated log management

### 7. Security Monitoring
- **Real-time Monitoring**: 5-minute security checks
- **Alert System**: Email notifications for threats
- **Metrics Collection**: JSON-formatted security metrics
- **Log Analysis**: Failed login and attack pattern detection
- **Resource Monitoring**: CPU, memory, disk usage alerts

## 🚀 Quick Start

### Prerequisites
- Ubuntu/Debian-based system with root access
- Docker installed and running
- Trading application deployed

### 1. Run Complete Security Hardening
```bash
# Make scripts executable
chmod +x scripts/security-hardening.sh
chmod +x scripts/setup-ssl.sh
chmod +x scripts/security-monitor.sh
chmod +x scripts/validate-security.sh

# Run comprehensive security setup (requires root)
sudo ./scripts/security-hardening.sh
```

### 2. Configure SSL/TLS (Optional - if not done in step 1)
```bash
# Configure SSL with your domain
sudo ./scripts/setup-ssl.sh
```

### 3. Validate Security Configuration
```bash
# Run security validation
sudo ./scripts/validate-security.sh
```

### 4. Start Security Monitoring
```bash
# Start continuous monitoring (runs in background)
sudo ./scripts/security-monitor.sh continuous &

# Or setup as a service (recommended)
sudo systemctl enable security-monitor
sudo systemctl start security-monitor
```

## 📋 Manual Configuration Steps

### 1. Domain Configuration
Update nginx configuration with your domain:
```bash
# Copy template and customize
sudo cp config/nginx-trading-app.conf /etc/nginx/sites-available/trading-app

# Edit domain name
sudo sed -i 's/YOUR_DOMAIN_HERE/your-actual-domain.com/g' /etc/nginx/sites-available/trading-app

# Enable site
sudo ln -s /etc/nginx/sites-available/trading-app /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 2. Fail2ban Custom Configuration
```bash
# Copy jail configuration
sudo cp config/fail2ban-jail.local /etc/fail2ban/jail.local

# Copy filter configurations (extract individual sections)
sudo cp config/fail2ban-filters.conf /tmp/
# Extract individual filters to /etc/fail2ban/filter.d/

# Restart fail2ban
sudo systemctl restart fail2ban
```

### 3. Docker Security Configuration
```bash
# Apply Docker security settings
sudo cp config/docker-security.json /etc/docker/daemon.json
sudo systemctl restart docker
```

### 4. Email Alert Configuration
```bash
# Configure email for alerts (optional)
export ALERT_EMAIL="admin@yourdomain.com"

# Install mail utilities if needed
sudo apt-get install mailutils
```

## 🔍 Security Validation

### Run Security Checks
```bash
# Full validation
sudo ./scripts/validate-security.sh

# Quick check of essential services
sudo ./scripts/validate-security.sh quick

# Generate security report only
sudo ./scripts/validate-security.sh report-only
```

### Monitor Security Status
```bash
# View security monitoring logs
tail -f /opt/logs/security-monitor.log

# View security alerts
tail -f /opt/logs/security-alerts.log

# Check current security metrics
./scripts/security-monitor.sh metrics
```

### Check fail2ban Status
```bash
# Overall status
sudo fail2ban-client status

# Specific jail status
sudo fail2ban-client status sshd
sudo fail2ban-client status trading-app

# Unban IP if needed
sudo fail2ban-client set sshd unbanip 192.168.1.100
```

### Firewall Management
```bash
# Check firewall status
sudo ufw status verbose

# Allow new port temporarily
sudo ufw allow 8080

# Remove rule
sudo ufw delete allow 8080

# Reset firewall (careful!)
sudo ufw --force reset
```

## 📊 Security Monitoring Dashboard

### Key Metrics Monitored
- Failed login attempts (threshold: 5 per 10 minutes)
- Banned IP addresses (threshold: 10 total)
- System resource usage (CPU: 80%, Memory: 80%, Disk: 85%)
- Container security status
- SSL certificate expiration
- Service availability (fail2ban, nginx, UFW)

### Log Locations
```bash
/opt/logs/security-monitor.log     # Main monitoring log
/opt/logs/security-alerts.log      # Security alerts only
/opt/logs/security-metrics.json    # Current metrics (JSON)
/opt/logs/security-validation.log  # Validation results
/opt/logs/ssl-setup.log           # SSL configuration log
/var/log/nginx/trading-app-*.log  # Nginx access/error logs
/var/log/fail2ban.log            # fail2ban activity
```

### Alert Triggers
- **Critical**: Application down, certificate expired, high failed logins
- **Warning**: High resource usage, certificate expiring soon, service issues
- **Info**: Regular status updates, successful validations

## 🔧 Troubleshooting

### Common Issues

#### 1. UFW Blocks Application Access
```bash
# Check if application port is allowed
sudo ufw status | grep 5000

# Allow application port from localhost only
sudo ufw allow from 127.0.0.1 to any port 5000
```

#### 2. fail2ban Not Starting
```bash
# Check configuration syntax
sudo fail2ban-client -t

# Check logs for errors
sudo journalctl -u fail2ban -f

# Restart with verbose logging
sudo fail2ban-client -v start
```

#### 3. SSL Certificate Issues
```bash
# Check certificate status
sudo certbot certificates

# Test certificate renewal
sudo certbot renew --dry-run

# Force certificate renewal
sudo certbot renew --force-renewal
```

#### 4. Nginx Configuration Errors
```bash
# Test configuration
sudo nginx -t

# Check error logs
sudo tail -f /var/log/nginx/error.log

# Reload configuration
sudo systemctl reload nginx
```

#### 5. Docker Security Issues
```bash
# Check Docker security info
docker system info | grep -E "(Security|User)"

# Verify container users
docker exec <container> whoami

# Check container privileges
docker inspect <container> | grep -i privilege
```

### Emergency Procedures

#### Disable Security Temporarily
```bash
# Disable UFW (emergency access)
sudo ufw disable

# Stop fail2ban (if blocking legitimate access)
sudo systemctl stop fail2ban

# Disable security monitoring
sudo pkill -f security-monitor.sh
```

#### Reset Security Configuration
```bash
# Reset UFW to defaults
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Reset fail2ban
sudo systemctl stop fail2ban
sudo rm /etc/fail2ban/jail.local
sudo systemctl start fail2ban

# Restore from backup
sudo cp /etc/nginx/sites-available/default.backup /etc/nginx/sites-available/trading-app
```

## 📚 Security Best Practices

### 1. Regular Maintenance
- Update system packages monthly
- Review security logs weekly
- Test backup/restore procedures quarterly
- Validate security configuration after changes

### 2. Access Control
- Use SSH keys instead of passwords
- Implement 2FA for administrative access
- Regular audit of user accounts and permissions
- Monitor for unauthorized access attempts

### 3. Application Security
- Keep application dependencies updated
- Regular security code reviews
- Implement input validation and sanitization
- Use HTTPS for all communications

### 4. Monitoring & Alerting
- Set up email alerts for critical events
- Monitor application and system metrics
- Regular security assessment and penetration testing
- Incident response plan and procedures

### 5. Data Protection
- Encrypt sensitive data at rest
- Secure database access and credentials
- Regular backup testing and validation
- Implement data retention policies

## 📞 Support & Resources

### Security Tools Documentation
- [UFW Documentation](https://help.ubuntu.com/community/UFW)
- [fail2ban Manual](https://www.fail2ban.org/wiki/index.php/MANUAL_0_8)
- [Nginx Security](https://nginx.org/en/docs/http/securing_http.html)
- [Docker Security](https://docs.docker.com/engine/security/)

### Emergency Contacts
- Primary Security Admin: [Configure your contact]
- Secondary Contact: [Configure backup contact]
- Infrastructure Team: [Configure team email]

### Security Incident Response
1. **Immediate**: Isolate affected systems
2. **Assessment**: Determine scope and impact
3. **Containment**: Stop ongoing attacks
4. **Recovery**: Restore services safely
5. **Analysis**: Post-incident review and improvements

---

## ⚠️ Important Security Notes

- **Never disable all security measures simultaneously**
- **Test changes in staging environment first**
- **Keep security configurations backed up**
- **Document all security-related changes**
- **Regular security training for all administrators**

This security hardening implementation provides enterprise-grade protection suitable for financial applications while maintaining usability and performance. Regular monitoring and maintenance ensure continued security effectiveness.