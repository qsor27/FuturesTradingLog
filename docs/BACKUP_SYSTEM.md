# FuturesTradingLog Backup System

## Overview

This document describes the comprehensive backup system implemented for FuturesTradingLog. The system provides multiple layers of protection for your trading data with automated real-time replication, scheduled backups, and easy recovery procedures.

## System Architecture

### Components

1. **Litestream** - Real-time SQLite replication
2. **Local File Backups** - Compressed database snapshots  
3. **Docker Compose Production Stack** - Integrated monitoring and services
4. **Backup Scripts** - Manual backup and restore operations
5. **Monitoring** - Prometheus and Grafana for backup health tracking

### Data Protection Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Protection Stack                    │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: Real-time Replication (Litestream)                │
│   • Continuous WAL streaming                               │
│   • Sub-second replication                                 │
│   • Local + S3 storage                                     │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Scheduled Backups                                 │
│   • Daily compressed snapshots                             │
│   • Automated validation                                   │
│   • Multiple retention policies                            │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: Safety Backups                                    │
│   • Pre-operation snapshots                                │
│   • Upgrade protection                                     │
│   • Manual backup on demand                                │
├─────────────────────────────────────────────────────────────┤
│ Layer 4: Monitoring & Alerts                               │
│   • Health checks                                          │
│   • Performance metrics                                    │
│   • Failure notifications                                  │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Basic Setup

```bash
# Install Litestream
./scripts/setup-litestream.sh install

# Create backup directories
mkdir -p backups/{manual,automated,safety,local}

# Copy environment template
cp .env.backup.template .env.backup
# Edit .env.backup with your settings
```

### 2. Production Deployment

```bash
# Start full production stack with backups
docker-compose -f docker/docker-compose.production.yml up -d

# Verify services are running
docker-compose -f docker/docker-compose.production.yml ps

# Check backup system status
./scripts/setup-litestream.sh status
```

### 3. First Backup

```bash
# Create manual backup
./scripts/backup-database.sh backup

# Verify backup
./scripts/backup-database.sh validate

# View backup statistics
./scripts/backup-database.sh stats
```

## Configuration

### Environment Variables

Copy `.env.backup.template` to `.env.backup` and configure:

```bash
# Basic settings
DATA_DIR=./data
BACKUP_DIR=./backups
LOCAL_RETENTION_DAYS=7

# AWS S3 (optional)
BACKUP_S3_BUCKET=your-bucket-name
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Monitoring
GRAFANA_PASSWORD=secure-password
```

### Litestream Configuration

The system includes a pre-configured `config/litestream.yml` with:

- **Real-time replication** with 1-second sync intervals
- **Local filesystem backups** with 72-hour retention
- **S3 backups** with 30-day retention (when configured)
- **Health monitoring** endpoints
- **Automatic validation** every hour

## Backup Operations

### Manual Backups

```bash
# Create backup
./scripts/backup-database.sh backup

# List all backups  
./scripts/backup-database.sh list

# Show detailed statistics
./scripts/backup-database.sh stats

# Validate all backups
./scripts/backup-database.sh validate

# Clean old backups
./scripts/backup-database.sh cleanup
```

### Restore Operations

```bash
# Interactive restore (recommended)
./scripts/restore-database.sh interactive

# Restore from specific backup
./scripts/restore-database.sh restore /path/to/backup.db.gz

# Restore from Litestream (latest)
./scripts/restore-database.sh litestream

# Restore from specific timestamp
./scripts/restore-database.sh litestream 2024-01-15T10:30:00

# List available backups
./scripts/restore-database.sh list
```

### Python API

```python
from backup_manager import BackupManager, BackupConfig
from pathlib import Path

# Setup configuration
config = BackupConfig(
    data_dir=Path('./data'),
    backup_dir=Path('./backups'),
    retention_days=7
)

manager = BackupManager(config)

# Create backup
result = manager.create_backup(
    db_path=Path('./data/db/futures_trades.db'),
    backup_type='manual',
    compress=True,
    validate=True
)

# List backups
backups = manager.list_backups()

# Get statistics
stats = manager.get_backup_statistics()
```

## Automated Backups

### Daily Scheduled Backups

The production Docker stack includes automated daily backups:

```yaml
# In docker-compose.production.yml
backup-validator:
  # Runs daily validation at 02:00
  command: python -c "schedule.every().day.at('02:00').do(run_validation)"
```

### Litestream Real-time Backups

Litestream provides continuous protection:

- **WAL streaming** - Changes replicated in real-time
- **Snapshots** - Periodic full database snapshots
- **Multiple destinations** - Local filesystem + S3
- **Automatic recovery** - Point-in-time restore capability

## Monitoring and Alerts

### Grafana Dashboard

Access Grafana at `http://localhost:3000` (admin/your-password):

- **Backup Health** - Success/failure rates
- **Storage Usage** - Backup space consumption
- **Replication Lag** - Litestream performance
- **Database Size** - Growth trends

### Prometheus Metrics

Available at `http://localhost:9090`:

- **litestream_replication_lag** - Replication delay
- **backup_success_total** - Successful backup count
- **backup_failure_total** - Failed backup count
- **backup_size_bytes** - Backup file sizes

### Health Checks

```bash
# Check all backup services
curl http://localhost:5000/health
curl http://localhost:8080/health  # Litestream
curl http://localhost:9090/health  # Prometheus

# View service logs
docker logs futurestradinglog-litestream
docker logs futurestradinglog-backup-validator
```

## Recovery Procedures

### Scenario 1: Database Corruption

```bash
# 1. Stop application
docker stop futurestradinglog-app

# 2. Restore from latest backup
./scripts/restore-database.sh litestream

# 3. Verify database integrity
sqlite3 data/db/futures_trades.db "PRAGMA integrity_check;"

# 4. Restart application
docker start futurestradinglog-app
```

### Scenario 2: Accidental Data Loss

```bash
# 1. Stop application to prevent further changes
docker stop futurestradinglog-app

# 2. List available backups
./scripts/restore-database.sh list

# 3. Choose appropriate backup (before data loss)
./scripts/restore-database.sh restore backups/manual/futures_trades_20240115_143000.db.gz

# 4. Restart application
docker start futurestradinglog-app
```

### Scenario 3: Complete System Recovery

```bash
# 1. Restore from S3 (if configured)
aws s3 sync s3://your-bucket/db/ ./restored-data/

# 2. Extract and restore databases
gunzip restored-data/*.db.gz
./scripts/restore-database.sh restore restored-data/futures_trades.db

# 3. Rebuild containers
docker-compose -f docker/docker-compose.production.yml up -d

# 4. Verify system health
./scripts/setup-litestream.sh status
```

## Best Practices

### 1. Regular Testing

```bash
# Monthly backup restoration test
./scripts/restore-database.sh restore latest-backup.db.gz /tmp/test-restore.db
sqlite3 /tmp/test-restore.db "SELECT COUNT(*) FROM trades;"

# Automated validation
./scripts/backup-database.sh validate
```

### 2. Monitoring

- **Set up alerts** for backup failures
- **Monitor storage usage** to prevent disk space issues
- **Check replication lag** regularly
- **Verify S3 backups** are working (if configured)

### 3. Security

```bash
# Encrypt sensitive backups
gpg --encrypt --recipient your-key backup.db.gz

# Secure S3 bucket permissions
aws s3api put-bucket-encryption --bucket your-bucket --server-side-encryption-configuration ...

# Rotate access keys regularly
```

### 4. Documentation

- **Document recovery procedures** specific to your environment
- **Keep contact information** for emergency access
- **Maintain backup schedules** documentation
- **Test disaster recovery plans** regularly

## Troubleshooting

### Common Issues

#### Litestream Not Replicating

```bash
# Check Litestream status
docker logs futurestradinglog-litestream

# Verify configuration
litestream -config config/litestream.yml validate

# Test connection to S3
aws s3 ls s3://your-bucket/
```

#### Backup Validation Failures

```bash
# Check specific backup
./scripts/backup-database.sh validate

# Test database integrity
sqlite3 backup.db "PRAGMA integrity_check;"

# Verify file permissions
ls -la backups/manual/
```

#### Disk Space Issues

```bash
# Check backup storage usage
du -sh backups/

# Clean old backups
./scripts/backup-database.sh cleanup

# Adjust retention policies in .env.backup
```

#### Restore Failures

```bash
# Verify backup file integrity
gunzip -t backup.db.gz

# Check target directory permissions
ls -la data/db/

# Try manual restore
cp backup.db data/db/futures_trades.db
```

### Getting Help

1. **Check logs** in `data/logs/` directory
2. **Review service status** with Docker commands
3. **Validate configuration** with provided scripts
4. **Test with smaller datasets** first
5. **Contact system administrator** for complex issues

## Advanced Configuration

### Custom Retention Policies

```yaml
# In config/litestream.yml
dbs:
  - path: /data/db/futures_trades.db
    replicas:
      - type: file
        retention: 168h  # 7 days
      - type: s3
        retention: 720h  # 30 days
```

### Performance Tuning

```yaml
# Optimize for high-frequency trading
sync-interval: 100ms
snapshot-interval: 5m
validation-interval: 30m
```

### Multiple Database Support

```bash
# Backup all databases
for db in data/db/*.db; do
    ./scripts/backup-database.sh backup --db-path "$db"
done
```

## Security Considerations

- **Encrypt backups** containing sensitive trading data
- **Secure S3 bucket** with proper IAM policies
- **Rotate access keys** regularly
- **Monitor access logs** for unauthorized activity
- **Use VPC endpoints** for S3 access in production

## Performance Impact

The backup system is designed for minimal performance impact:

- **Litestream** uses SQLite WAL mode (< 1% overhead)
- **Scheduled backups** run during low-usage periods
- **Compression** reduces storage requirements by ~60%
- **Background validation** doesn't affect application performance

## Cost Optimization

### S3 Storage Classes

```bash
# Use Intelligent Tiering for cost optimization
aws s3api put-bucket-intelligent-tiering-configuration \
    --bucket your-bucket \
    --id trading-backups \
    --intelligent-tiering-configuration Status=Enabled
```

### Local Storage Management

```bash
# Monitor backup growth
./scripts/backup-database.sh stats

# Adjust retention based on usage
# Edit LOCAL_RETENTION_DAYS in .env.backup
```