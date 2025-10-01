# Deployment Guide

Complete guide for deploying Futures Trading Log using GitHub Container Registry and Docker.

## 📋 **Prerequisites**

### **For Repository Owners**
If you're setting up the GitHub repository from scratch, follow the complete setup guide:
👉 **[GITHUB_SETUP.md](GITHUB_SETUP.md)** - Complete repository setup with automated Docker builds

### **For Users Deploying Existing Repository**
If the repository is already set up on GitHub, you can skip to deployment below.

## 🚀 **Quick Deployment**

### **One-Command Deployment**
```bash
# Download and run the deployment script
curl -fsSL https://raw.githubusercontent.com/qsor27/FuturesTradingLog/main/deploy.sh | bash
```

### **Manual GitHub Deployment**
```bash
# Pull the latest image from GitHub Container Registry
docker pull ghcr.io/qsor27/futurestradinglog:latest

# Run with default settings
docker run -d \
  --name futures-trading-log \
  -p 5000:5000 \
  -v ./data:/app/data \
  ghcr.io/qsor27/futurestradinglog:latest

# Access the application
open http://localhost:5000
```

## 🏗️ **GitHub Actions CI/CD Pipeline**

### **Automated Build Process**
When you push to GitHub, the following happens automatically:

1. **Testing Phase**:
   - Runs comprehensive test suite (120+ tests)
   - Validates performance benchmarks
   - Ensures code quality and reliability

2. **Build Phase**:
   - Multi-stage Docker build for optimized images
   - Builds for both AMD64 and ARM64 architectures
   - Pushes to GitHub Container Registry (ghcr.io)

3. **Security Phase**:
   - Trivy vulnerability scanning
   - Security report uploaded to GitHub Security tab
   - Automated dependency checks

### **Image Tagging Strategy**
```bash
# Latest stable release
ghcr.io/qsor27/futurestradinglog:latest

# Version tags
ghcr.io/qsor27/futurestradinglog:v2.0.0
ghcr.io/qsor27/futurestradinglog:v2.0

# Branch tags
ghcr.io/qsor27/futurestradinglog:main
ghcr.io/qsor27/futurestradinglog:develop
```

## 🔧 **Configuration Options**

### **Environment Variables**
```bash
# Required
DATA_DIR=/path/to/data              # Data storage directory
FLASK_SECRET_KEY=your-secret-key    # Session security key

# Optional
FLASK_ENV=production                # Environment mode
FLASK_HOST=0.0.0.0                 # Bind address
FLASK_PORT=5000                     # Application port
EXTERNAL_PORT=5000                  # External port mapping
```

### **Volume Mounting**
```bash
# Data persistence
-v /host/data:/app/data

# NinjaTrader integration
-v /path/to/ninja/exports:/app/ninja_exports

# Custom configuration
-v /path/to/config:/app/config
```

## 🐳 **Production Deployment**

### **Using Docker Compose (Recommended)**
```bash
# Clone the repository
git clone https://github.com/qsor27/FuturesTradingLog.git
cd FuturesTradingLog

# Create production environment file
cp .env.template .env.prod
# Edit .env.prod with your production settings

# Deploy with production compose
docker-compose -f docker-compose.prod.yml up -d
```

### **Production Environment File**
```bash
# .env.prod
FLASK_ENV=production
FLASK_DEBUG=0
DATA_DIR=/var/lib/futures-trading-log
EXTERNAL_PORT=5000
FLASK_SECRET_KEY=your-very-secure-secret-key-here
```

### **With Reverse Proxy (Optional)**
```bash
# Enable nginx reverse proxy
docker-compose -f docker-compose.prod.yml --profile nginx up -d
```

## 🌐 **Cloud Deployment**

### **AWS ECS**
```bash
# Create task definition using ghcr.io/qsor27/futurestradinglog:latest
# Configure EFS for persistent data storage
# Set environment variables in task definition

# Example ECS task definition snippet:
{
  "image": "ghcr.io/qsor27/futurestradinglog:latest",
  "environment": [
    {"name": "DATA_DIR", "value": "/app/data"},
    {"name": "FLASK_ENV", "value": "production"}
  ],
  "mountPoints": [
    {
      "sourceVolume": "futures-data",
      "containerPath": "/app/data"
    }
  ]
}
```

### **Google Cloud Run**
```bash
# Deploy to Cloud Run
gcloud run deploy futures-trading-log \
  --image ghcr.io/qsor27/futurestradinglog:latest \
  --platform managed \
  --port 5000 \
  --set-env-vars DATA_DIR=/app/data \
  --set-env-vars FLASK_ENV=production \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10
```

### **Azure Container Instances**
```bash
# Deploy to Azure
az container create \
  --resource-group futures-rg \
  --name futures-trading-log \
  --image ghcr.io/qsor27/futurestradinglog:latest \
  --ports 5000 \
  --environment-variables DATA_DIR=/app/data FLASK_ENV=production \
  --memory 1 \
  --cpu 1
```

### **DigitalOcean App Platform**
```yaml
# app.yaml
name: futures-trading-log
services:
- name: web
  source_dir: /
  github:
    repo: qsor27/FuturesTradingLog
    branch: main
  image:
    registry: ghcr.io
    repository: qsor27/futurestradinglog
    tag: latest
  http_port: 5000
  instance_count: 1
  instance_size_slug: basic-xxs
  envs:
  - key: DATA_DIR
    value: /app/data
  - key: FLASK_ENV
    value: production
```

## 🔒 **Security Configuration**

### **Production Security Checklist**
- [ ] Change default `FLASK_SECRET_KEY`
- [ ] Use HTTPS with reverse proxy
- [ ] Enable container security scanning
- [ ] Configure firewall rules
- [ ] Set up log monitoring
- [ ] Enable automated backups

### **Secrets Management**
```bash
# Using Docker secrets
echo "your-secret-key" | docker secret create flask_secret_key -

# In docker-compose.yml
secrets:
  - flask_secret_key
environment:
  - FLASK_SECRET_KEY_FILE=/run/secrets/flask_secret_key
```

## 📊 **Monitoring & Logging**

### **Health Checks**
```bash
# Application health endpoint
curl http://localhost:5000/health

# Docker health check
docker inspect --format='{{.State.Health.Status}}' futures-trading-log

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' futures-trading-log
```

### **Application Logs**
```bash
# View application logs
docker logs futures-trading-log

# Follow logs in real-time
docker logs -f futures-trading-log

# With timestamps
docker logs -t futures-trading-log
```

### **Performance Monitoring**
```bash
# Container resource usage
docker stats futures-trading-log

# Database performance
docker exec futures-trading-log python -c "
from tests.test_performance import TestOHLCPerformance
print('Running performance validation...')
# Performance tests would run here
"
```

## 🔄 **Updates & Maintenance**

### **Updating to Latest Version**
```bash
# Pull latest image
docker pull ghcr.io/qsor27/futurestradinglog:latest

# Stop current container
docker stop futures-trading-log

# Start with new image
docker-compose up -d

# Or use the deployment script
./deploy.sh
```

### **Backup & Restore**
```bash
# Backup data directory
tar -czf futures-backup-$(date +%Y%m%d).tar.gz ./data/

# Backup database only
cp ./data/db/futures_trades.db ./backup/

# Restore from backup
tar -xzf futures-backup-20250117.tar.gz
```

### **Database Migration**
```bash
# The application automatically handles database schema updates
# No manual migration needed - just start the new version

# Verify database after update
docker exec futures-trading-log python -c "
from TradingLog_db import FuturesDB
with FuturesDB() as db:
    print('Database connection successful')
    print(f'Trade records: {db.get_trade_count()}')
    print(f'OHLC records: {db.get_ohlc_count()}')
"
```

## 🚨 **Troubleshooting**

### **Common Issues**

**Container Won't Start**
```bash
# Check logs for errors
docker logs futures-trading-log

# Verify environment variables
docker exec futures-trading-log env | grep FLASK

# Test data directory permissions
docker exec futures-trading-log ls -la /app/data
```

**Performance Issues**
```bash
# Run performance tests
docker exec futures-trading-log python run_tests.py --performance

# Check system resources
docker stats futures-trading-log

# Verify database indexes
docker exec futures-trading-log python -c "
from TradingLog_db import FuturesDB
with FuturesDB() as db:
    db.cursor.execute('PRAGMA index_list(ohlc_data)')
    print('OHLC Indexes:', db.cursor.fetchall())
"
```

**Data Issues**
```bash
# Verify data directory structure
docker exec futures-trading-log find /app/data -type d

# Check database integrity
docker exec futures-trading-log python -c "
from TradingLog_db import FuturesDB
with FuturesDB() as db:
    db.cursor.execute('PRAGMA integrity_check')
    print('Database integrity:', db.cursor.fetchone()[0])
"
```

## 📞 **Support**

- **GitHub Issues**: [Report problems or request features](https://github.com/qsor27/FuturesTradingLog/issues)
- **Documentation**: Complete guides available in repository
- **Performance**: All targets validated through automated testing

The GitHub-based deployment provides a robust, scalable solution for running the Futures Trading Log with minimal configuration and maximum reliability.