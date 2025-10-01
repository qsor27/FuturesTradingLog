# Redis Setup Guide for Enhanced Caching

This guide explains how to set up and configure Redis for optimal performance with the enhanced position detail pages and background services.

## Overview

Redis provides:
- **2-Week Data Caching**: OHLC market data with automatic expiration
- **Intelligent Cache Management**: Automatic cleanup of unused instruments
- **Performance Optimization**: 15-50ms chart loading times
- **Background Service Support**: Cache warming and maintenance

## Installation Options

### Option 1: Docker (Recommended)
```bash
# Run Redis in Docker container
docker run -d \
  --name futures-redis \
  -p 6379:6379 \
  -v redis-data:/data \
  redis:7-alpine redis-server --appendonly yes

# Verify Redis is running
docker logs futures-redis
```

### Option 2: Native Installation

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

#### macOS (Homebrew)
```bash
brew install redis
brew services start redis
```

#### Windows
1. Download Redis from [Microsoft Archive](https://github.com/microsoftarchive/redis/releases)
2. Extract and run `redis-server.exe`
3. Verify with `redis-cli ping` (should return `PONG`)

### Option 3: Cloud Redis Services
- **AWS ElastiCache**: Managed Redis service
- **Azure Cache for Redis**: Microsoft's managed offering
- **Redis Cloud**: Official Redis hosting
- **Google Cloud Memorystore**: Google's Redis service

## Configuration

### Application Configuration
Set these environment variables for the Futures Trading Log:

```bash
# Redis connection (default: redis://localhost:6379/0)
REDIS_URL=redis://localhost:6379/0

# Enable caching (default: true)
CACHE_ENABLED=true

# Cache retention in days (default: 14)
CACHE_TTL_DAYS=14
```

### Redis Configuration
For production environments, configure `/etc/redis/redis.conf`:

```conf
# Basic Performance Settings
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence Settings
save 900 1
save 300 10
save 60 10000

# Network Settings
bind 0.0.0.0
port 6379
timeout 300

# Security (uncomment and set password)
# requirepass your_secure_password_here
```

### Docker Compose Integration
Add Redis to your `docker-compose.yml`:

```yaml
version: '3.8'
services:
  app:
    build: .
    environment:
      - REDIS_URL=redis://redis:6379/0
      - CACHE_ENABLED=true
    depends_on:
      - redis
  
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis-data:/data
    ports:
      - "6379:6379"

volumes:
  redis-data:
```

## Testing Redis Connection

### Command Line Test
```bash
# Test Redis connectivity
redis-cli ping
# Should return: PONG

# Test basic operations
redis-cli set test "Hello Redis"
redis-cli get test
# Should return: "Hello Redis"

# Clean up test
redis-cli del test
```

### Application Health Check
Visit `/health` endpoint to verify:
```json
{
  "status": "healthy",
  "background_services": {
    "cache_service": {
      "status": "healthy",
      "redis_connected": true,
      "operations": "working"
    }
  }
}
```

### Cache Statistics
Visit `/api/cache/stats` to see cache performance:
```json
{
  "redis_connected": true,
  "redis_memory_used": "1.2M",
  "total_instruments": 5,
  "ohlc_cache_entries": 150,
  "instruments": ["MNQ", "ES", "YM", "RTY", "NQ"]
}
```

## Performance Optimization

### Memory Configuration
```bash
# Set appropriate maxmemory (adjust based on available RAM)
redis-cli CONFIG SET maxmemory 2gb

# Use LRU eviction for cache behavior
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Enable lazy expiration for better performance
redis-cli CONFIG SET lazyfree-lazy-eviction yes
```

### Connection Optimization
```python
# Application automatically configures:
# - Connection pooling
# - Decode responses for JSON compatibility
# - Retry logic for connection failures
# - Graceful fallback when Redis unavailable
```

## Monitoring and Maintenance

### Redis Monitoring Commands
```bash
# Monitor Redis operations in real-time
redis-cli monitor

# Check memory usage
redis-cli info memory

# See all cache keys (development only)
redis-cli keys "*"

# Check specific instrument cache
redis-cli keys "ohlc:MNQ:*"
```

### Application Monitoring
Use these API endpoints for monitoring:

```bash
# Cache statistics
curl http://localhost:5000/api/cache/stats

# Background service status
curl http://localhost:5000/api/background-services/status

# Manual cache cleanup
curl -X POST http://localhost:5000/api/cache/clean
```

### Log Monitoring
Check application logs for cache-related activity:
```bash
# Application logs
tail -f data/logs/app.log | grep cache

# Background service logs
tail -f data/logs/app.log | grep background
```

## Cache Management

### Automatic Cleanup
The system automatically:
- **Removes expired data**: After 14 days (configurable)
- **Cleans unused instruments**: Daily at 02:00 UTC
- **Warms popular instruments**: Daily at 03:00 UTC
- **Monitors cache health**: Continuous health checks

### Manual Cache Operations

#### Clear All Cache
```bash
# WARNING: This removes all cached data
redis-cli FLUSHDB
```

#### Clear Specific Instrument
```bash
# Remove all data for MNQ
redis-cli --scan --pattern "ohlc:MNQ:*" | xargs redis-cli DEL
redis-cli DEL "instrument:MNQ:metadata"
```

#### Force Cache Refresh
```bash
# Trigger gap-filling for specific instrument
curl -X POST http://localhost:5000/api/gap-filling/force/MNQ \
  -H "Content-Type: application/json" \
  -d '{"timeframes": ["1m", "5m", "15m"], "days_back": 7}'
```

## Troubleshooting

### Common Issues

#### Redis Not Starting
```bash
# Check Redis status
systemctl status redis
# or
docker ps | grep redis

# Check Redis logs
journalctl -u redis
# or
docker logs futures-redis
```

#### Connection Refused
```bash
# Verify Redis is listening
netstat -tlnp | grep 6379
# or
ss -tlnp | grep 6379

# Test local connection
redis-cli -h localhost -p 6379 ping
```

#### Memory Issues
```bash
# Check Redis memory usage
redis-cli info memory

# Check maxmemory setting
redis-cli config get maxmemory

# Monitor evictions
redis-cli info stats | grep evicted
```

#### Application Cache Issues
```bash
# Check application logs for Redis errors
grep -i redis data/logs/app.log

# Verify cache service health
curl http://localhost:5000/api/cache/stats

# Test cache operations manually
curl -X POST http://localhost:5000/api/cache/clean
```

### Performance Issues

#### Slow Cache Operations
- Check Redis `info stats` for slow operations
- Monitor network latency between app and Redis
- Consider increasing Redis memory if evictions are frequent
- Review `maxmemory-policy` setting

#### High Memory Usage
- Check cache key expiration with `TTL` commands
- Review `CACHE_TTL_DAYS` setting (default: 14 days)
- Consider reducing cache retention for development
- Monitor background cleanup with `/api/cache/stats`

## Security Considerations

### Production Security
```conf
# Set Redis password
requirepass your_very_secure_password

# Bind to specific interfaces only
bind 127.0.0.1 192.168.1.100

# Disable dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command DEBUG ""
```

### Application Security
```bash
# Set Redis URL with password
export REDIS_URL="redis://:password@localhost:6379/0"

# Use TLS for production
export REDIS_URL="rediss://user:password@secure-redis:6380/0"
```

### Network Security
- Use firewall rules to restrict Redis port (6379) access
- Consider VPN or private networks for Redis communication
- Enable TLS encryption for production deployments
- Use Redis AUTH for authentication

## Performance Benchmarks

### Expected Performance (With Redis)
- **Chart Loading**: 15-50ms ✅
- **Cache Hit Rate**: >80% for frequently accessed instruments
- **Memory Usage**: ~1-2MB per instrument per timeframe
- **Background Processing**: <5ms for cache operations

### Fallback Performance (Without Redis)
- **Chart Loading**: 200-500ms (database only)
- **Gap Filling**: Always required, no caching benefits
- **Background Services**: Still functional, just slower

## Migration and Backup

### Cache Backup
```bash
# Redis provides automatic persistence
# Backup Redis dump file
cp /var/lib/redis/dump.rdb /backup/redis-backup-$(date +%Y%m%d).rdb

# For Docker
docker exec futures-redis redis-cli BGSAVE
docker cp futures-redis:/data/dump.rdb backup/
```

### Cache Migration
The cache is automatically rebuilt when:
- Application starts with empty Redis
- Background services run their first gap-filling cycle
- Users access charts for specific instruments

No manual migration is required - the system rebuilds cache as needed.

## Development vs Production

### Development Setup
```bash
# Simple local Redis
docker run -d --name dev-redis -p 6379:6379 redis:alpine

# Minimal configuration
export REDIS_URL="redis://localhost:6379/0"
export CACHE_TTL_DAYS="7"  # Shorter retention for development
```

### Production Setup
```bash
# Persistent Redis with authentication
docker run -d \
  --name prod-redis \
  --restart unless-stopped \
  -p 127.0.0.1:6379:6379 \
  -v redis-data:/data \
  redis:7-alpine redis-server \
  --appendonly yes \
  --requirepass your_secure_password

# Production configuration
export REDIS_URL="redis://:your_secure_password@localhost:6379/0"
export CACHE_TTL_DAYS="14"  # Full 2-week retention
```

This Redis setup provides optimal performance for the enhanced position detail pages while maintaining data integrity and system reliability.