# Deployment Runbook
## Futures Trading Application - Production Deployment Procedures

**Last Updated:** June 2025  
**Version:** 1.0  
**For:** Single-developer production environment

---

## Quick Reference

### Emergency Contacts
- **Primary Developer**: [Your Contact]
- **Infrastructure**: [Your Contact]  
- **Backup Contact**: [Secondary Contact]

### Critical URLs
- **Production App**: http://localhost:5000
- **Health Check**: http://localhost:5000/health
- **Backup Location**: `/opt/backups/futures-log/`

### Critical Commands
```bash
# Health check
./scripts/health_check.sh

# Manual backup
./scripts/backup_database.sh

# Deploy new version
./scripts/deploy.sh <git-sha>

# Emergency rollback
docker-compose -f docker-compose.prod.yml down
# Then restore from backup or restart old container
```

---

## Pre-Deployment Checklist

### Before Every Deployment

- [ ] **Fresh Backup Created**
  ```bash
  ./scripts/backup_database.sh
  ls -la /opt/backups/futures-log/ | tail -1  # Verify backup exists
  ```

- [ ] **Staging Environment Tested**
  ```bash
  # On staging server
  ./scripts/deploy.sh <new-git-sha>
  ./scripts/health_check.sh
  ```

- [ ] **Database Migration Tested** (if applicable)
  ```bash
  # On staging with production data copy
  yoyo apply --database sqlite:///staging_db.db
  ```

- [ ] **Git SHA Verified**
  ```bash
  # Confirm image exists in registry
  docker pull ghcr.io/qsor27/futurestradinglog:<git-sha>
  ```

- [ ] **Maintenance Window Scheduled** (for major changes)

---

## Standard Deployment Procedure

### 1. Pre-Deployment Preparation

```bash
# Navigate to application directory
cd /opt/futures-trading-app

# Ensure you have the latest deployment scripts
git pull origin main

# Verify current system health
./scripts/health_check.sh
```

### 2. Create Pre-Deployment Backup

```bash
# Create backup with timestamp
./scripts/backup_database.sh

# Verify backup was created and is valid
LATEST_BACKUP=$(ls -t /opt/backups/futures-log/backup_*.db | head -1)
echo "Latest backup: $LATEST_BACKUP"

# Test backup integrity
sqlite3 "$LATEST_BACKUP" "PRAGMA integrity_check;"
# Should output: ok
```

### 3. Deploy New Version

```bash
# Deploy using Git SHA from GitHub Actions
./scripts/deploy.sh <git-sha-from-github>

# Example:
# ./scripts/deploy.sh a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0
```

**Script will automatically:**
- Update `prod.env` with new image tag
- Pull new Docker image from registry
- Deploy using Docker Compose
- Wait for health check to pass
- Report success or failure

### 4. Post-Deployment Validation

```bash
# Run comprehensive health check
./scripts/health_check.sh

# Check application logs
docker logs futures-log-prod --tail 50

# Verify database connectivity
docker exec futures-log-prod sqlite3 /app/data/db/futures_trades.db "SELECT COUNT(*) FROM trades;"

# Test key application endpoints
curl -f http://localhost:5000/health
curl -f http://localhost:5000/positions/
```

### 5. Monitor for Issues

**Monitor for 30 minutes after deployment:**
```bash
# Watch logs in real-time
docker logs -f futures-log-prod

# Check for errors
docker logs futures-log-prod --since 30m | grep -i error

# Monitor system resources
docker stats futures-log-prod
```

---

## Database Migration Procedure

### For Schema Changes (Use Only When Required)

#### 1. Prepare Migration

```bash
# Create migration file in migrations/ directory
# Example: migrations/0003_add_new_column.sql

# Test migration on staging with production data copy
cp /opt/backups/futures-log/backup_latest.db staging_test.db
yoyo apply --database sqlite:///staging_test.db
```

#### 2. Execute Migration

```bash
# Stop application
docker-compose -f docker-compose.prod.yml down

# Create pre-migration backup
./scripts/backup_database.sh

# Run migration
yoyo apply --database sqlite:////app/data/db/futures_trades.db

# Restart application
docker-compose -f docker-compose.prod.yml up -d

# Verify migration success
docker exec futures-log-prod sqlite3 /app/data/db/futures_trades.db ".schema" | grep -A5 "new_changes"
```

#### 3. Validate Migration

```bash
# Check database integrity
docker exec futures-log-prod sqlite3 /app/data/db/futures_trades.db "PRAGMA integrity_check;"

# Run application health check
./scripts/health_check.sh

# Test position rebuilding if tables affected
curl -X POST http://localhost:5000/positions/rebuild
```

---

## Rollback Procedures

### Application Rollback (Quick)

```bash
# Rollback to previous working version
./scripts/deploy.sh <previous-working-git-sha>

# Or manually rollback
docker-compose -f docker-compose.prod.yml down
sed -i 's/^IMAGE_TAG=.*/IMAGE_TAG=<previous-sha>/' prod.env
docker-compose -f docker-compose.prod.yml up -d
```

### Database Rollback (Emergency Only)

⚠️ **WARNING**: Only use for catastrophic database corruption

```bash
# Stop application immediately
docker-compose -f docker-compose.prod.yml down

# Identify backup to restore
ls -la /opt/backups/futures-log/backup_*.db

# Restore backup (DESTRUCTIVE - loses all data since backup)
BACKUP_FILE="/opt/backups/futures-log/backup_YYYYMMDD_HHMMSS.db"
docker run --rm -v "futures-log-data:/data" -v "/opt/backups/futures-log:/backup" alpine cp "/backup/$(basename $BACKUP_FILE)" /data/db/futures_trades.db

# Restart application
docker-compose -f docker-compose.prod.yml up -d

# Verify restore
./scripts/health_check.sh
```

---

## Troubleshooting Guide

### Container Won't Start

```bash
# Check container logs
docker logs futures-log-prod

# Check if port is in use
netstat -tlnp | grep :5000

# Check if volume mount is correct
docker volume inspect futures-log-data

# Check environment variables
docker exec futures-log-prod env | grep DATA_DIR
```

### Database Issues

```bash
# Check database file exists and is readable
docker exec futures-log-prod ls -la /app/data/db/

# Check database integrity
docker exec futures-log-prod sqlite3 /app/data/db/futures_trades.db "PRAGMA integrity_check;"

# Check database connections
docker exec futures-log-prod sqlite3 /app/data/db/futures_trades.db ".databases"

# Check for locks
docker exec futures-log-prod fuser /app/data/db/futures_trades.db
```

### Application Errors

```bash
# Check recent application logs
docker logs futures-log-prod --since 1h | grep -i error

# Check health endpoint
curl -v http://localhost:5000/health

# Check position building
curl -X POST http://localhost:5000/positions/rebuild

# Check database connectivity from app
docker exec futures-log-prod python3 -c "
from config import config
import sqlite3
conn = sqlite3.connect(str(config.db_path))
print(f'Database accessible: {conn}')
conn.close()
"
```

### Performance Issues

```bash
# Check container resource usage
docker stats futures-log-prod

# Check database performance
docker exec futures-log-prod sqlite3 /app/data/db/futures_trades.db "PRAGMA compile_options;"

# Check disk space
df -h /var/lib/docker

# Check recent slow queries (if logging enabled)
docker logs futures-log-prod | grep -i "slow\|timeout"
```

---

## Maintenance Procedures

### Weekly Maintenance

```bash
# Check backup integrity
./scripts/backup_database.sh
LATEST_BACKUP=$(ls -t /opt/backups/futures-log/backup_*.db | head -1)
sqlite3 "$LATEST_BACKUP" "PRAGMA integrity_check;"

# Clean old Docker images
docker image prune -f

# Check log file sizes
du -h /var/log/
docker logs futures-log-prod --details | wc -l
```

### Monthly Maintenance

```bash
# Database vacuum (during maintenance window)
docker-compose -f docker-compose.prod.yml down
docker run --rm -v "futures-log-data:/data" alpine sqlite3 /data/db/futures_trades.db "VACUUM;"
docker-compose -f docker-compose.prod.yml up -d

# Update system packages (if needed)
apt update && apt upgrade

# Rotate log files
logrotate /etc/logrotate.conf
```

### Quarterly Maintenance

```bash
# Full system backup
tar -czf "/opt/backups/system_backup_$(date +%Y%m%d).tar.gz" /opt/futures-trading-app/ /opt/backups/futures-log/

# Review and update documentation
# Review security settings
# Performance analysis and optimization
```

---

## Monitoring & Alerts

### Automated Health Checks

```bash
# Add to crontab:
# */5 * * * * /opt/futures-trading-app/scripts/health_check.sh >> /var/log/health_check.log 2>&1

# Manual check
crontab -l | grep health_check
```

### Log Monitoring

```bash
# Check for errors in last hour
docker logs futures-log-prod --since 1h | grep -i error

# Check application performance
docker logs futures-log-prod --since 1h | grep -E "(slow|timeout|performance)"

# Check health check logs
tail -f /var/log/health_check.log
```

### Disk Space Monitoring

```bash
# Check Docker volume usage
docker system df

# Check backup directory
du -sh /opt/backups/futures-log/

# Clean old backups (keep last 30 days)
find /opt/backups/futures-log/ -name "backup_*.db" -mtime +30 -delete
```

---

## Emergency Procedures

### Application Down

1. **Immediate Response**
   ```bash
   ./scripts/health_check.sh  # Confirm issue
   docker logs futures-log-prod --tail 100  # Check logs
   docker restart futures-log-prod  # Try restart
   ```

2. **If Restart Fails**
   ```bash
   ./scripts/deploy.sh <last-known-good-sha>  # Rollback
   ```

3. **If Rollback Fails**
   ```bash
   # Manual container start with last known good configuration
   docker-compose -f docker-compose.prod.yml down
   # Edit prod.env with working image tag
   docker-compose -f docker-compose.prod.yml up -d
   ```

### Database Corruption

1. **Immediate Assessment**
   ```bash
   docker exec futures-log-prod sqlite3 /app/data/db/futures_trades.db "PRAGMA integrity_check;"
   ```

2. **If Corruption Confirmed**
   ```bash
   # Stop application
   docker-compose -f docker-compose.prod.yml down
   
   # Restore from latest backup
   LATEST_BACKUP=$(ls -t /opt/backups/futures-log/backup_*.db | head -1)
   docker run --rm -v "futures-log-data:/data" -v "/opt/backups/futures-log:/backup" alpine cp "/backup/$(basename $LATEST_BACKUP)" /data/db/futures_trades.db
   
   # Restart
   docker-compose -f docker-compose.prod.yml up -d
   ```

### Disk Space Full

```bash
# Emergency cleanup
docker system prune -f
find /opt/backups/futures-log/ -name "backup_*.db" -mtime +7 -delete
docker logs futures-log-prod > /dev/null 2>&1  # Clear log buffer
```

---

## Contact Information

### Escalation Path

1. **Primary Developer**: [Your Contact Info]
2. **Backup Technical Contact**: [Secondary Contact]
3. **Business Contact**: [Business Owner Contact]

### External Resources

- **GitHub Repository**: https://github.com/qsor27/FuturesTradingLog
- **Docker Registry**: ghcr.io/qsor27/futurestradinglog
- **Documentation**: Project README.md and CLAUDE.md

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | June 2025 | Initial deployment runbook | Claude Code |

---

**Remember**: Always test in staging first, backup before changes, and monitor after deployment!