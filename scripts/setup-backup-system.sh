#!/bin/bash

# Comprehensive Monitoring Setup Script for Futures Trading Application
# Sets up Prometheus, Grafana, and alerting infrastructure

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/docker-compose.monitoring.yml"
CONFIG_DIR="$PROJECT_ROOT/config"

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
        exit 1
    fi
    
    log "Prerequisites check passed"
}

# Function to create monitoring configuration
create_monitoring_configs() {
    log "Creating monitoring configuration files..."
    
    # Create config directories
    mkdir -p "$CONFIG_DIR/prometheus"
    mkdir -p "$CONFIG_DIR/grafana/dashboards"
    mkdir -p "$CONFIG_DIR/grafana/provisioning/dashboards"
    mkdir -p "$CONFIG_DIR/grafana/provisioning/datasources"
    mkdir -p "$CONFIG_DIR/alertmanager"
    
    # Prometheus configuration
    cat > "$CONFIG_DIR/prometheus/prometheus.yml" << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'trading-app'
    static_configs:
      - targets: ['trading-app:5000']
    metrics_path: '/metrics'
    scrape_interval: 15s
    
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
EOF

    # Prometheus alert rules
    cat > "$CONFIG_DIR/prometheus/alert_rules.yml" << 'EOF'
groups:
  - name: trading_application_alerts
    rules:
      - alert: HighCPUUsage
        expr: system_cpu_usage_percent > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage detected"
          description: "CPU usage has been above 80% for more than 5 minutes"

      - alert: HighMemoryUsage
        expr: (system_memory_usage_bytes / (1024^3)) > 6
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage detected"
          description: "Memory usage above 6GB for more than 5 minutes"

      - alert: DatabaseDown
        expr: up{job="trading-app"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Trading application is down"
          description: "Cannot connect to trading application"

      - alert: SlowDatabaseQueries
        expr: histogram_quantile(0.95, trading_database_query_duration_seconds) > 0.5
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Slow database queries detected"
          description: "95th percentile of queries above 500ms"

      - alert: BackgroundServiceDown
        expr: trading_background_services_status == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Background service is down"
          description: "Background service has been down for more than 2 minutes"
EOF

    # Grafana datasource configuration
    cat > "$CONFIG_DIR/grafana/provisioning/datasources/prometheus.yml" << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
EOF

    # Grafana dashboard provisioning
    cat > "$CONFIG_DIR/grafana/provisioning/dashboards/dashboards.yml" << 'EOF'
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
EOF

    # Trading Application Dashboard
    cat > "$CONFIG_DIR/grafana/dashboards/trading-dashboard.json" << 'EOF'
{
  "dashboard": {
    "id": null,
    "title": "Futures Trading Application Dashboard",
    "tags": ["trading", "monitoring"],
    "style": "dark",
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "System Metrics",
        "type": "stat",
        "targets": [
          {
            "expr": "system_cpu_usage_percent",
            "legendFormat": "CPU %"
          },
          {
            "expr": "(system_memory_usage_bytes / (1024^3))",
            "legendFormat": "Memory (GB)"
          },
          {
            "expr": "(system_disk_usage_bytes / (1024^3))",
            "legendFormat": "Disk (GB)"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        "fieldConfig": {
          "defaults": {
            "color": {"mode": "palette-classic"},
            "custom": {"displayMode": "list", "orientation": "horizontal"},
            "thresholds": {
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 70},
                {"color": "red", "value": 90}
              ]
            }
          }
        }
      },
      {
        "id": 2,
        "title": "Trading Metrics",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(trading_trades_processed_total[5m])",
            "legendFormat": "Trades/min"
          },
          {
            "expr": "rate(trading_positions_created_total[5m])",
            "legendFormat": "Positions/min"
          },
          {
            "expr": "rate(trading_chart_requests_total[5m])",
            "legendFormat": "Chart Requests/min"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
      },
      {
        "id": 3,
        "title": "Request Latency",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.50, flask_request_duration_seconds)",
            "legendFormat": "50th percentile"
          },
          {
            "expr": "histogram_quantile(0.95, flask_request_duration_seconds)",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.99, flask_request_duration_seconds)",
            "legendFormat": "99th percentile"
          }
        ],
        "gridPos": {"h": 8, "w": 24, "x": 0, "y": 8},
        "yAxes": [
          {"label": "Seconds", "min": 0}
        ]
      },
      {
        "id": 4,
        "title": "Database Performance",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, trading_database_query_duration_seconds)",
            "legendFormat": "95th percentile query time"
          },
          {
            "expr": "rate(trading_database_queries_total[5m])",
            "legendFormat": "Queries per minute"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 16}
      },
      {
        "id": 5,
        "title": "Background Services Status",
        "type": "stat",
        "targets": [
          {
            "expr": "trading_background_services_status",
            "legendFormat": "{{service}}"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 16},
        "fieldConfig": {
          "defaults": {
            "mappings": [
              {"options": {"0": {"text": "Down", "color": "red"}}, "type": "value"},
              {"options": {"1": {"text": "Running", "color": "green"}}, "type": "value"}
            ]
          }
        }
      }
    ],
    "time": {"from": "now-1h", "to": "now"},
    "refresh": "30s"
  }
}
EOF

    # AlertManager configuration
    cat > "$CONFIG_DIR/alertmanager/alertmanager.yml" << 'EOF'
global:
  smtp_smarthost: '${SMTP_SERVER}:${SMTP_PORT}'
  smtp_from: '${SMTP_USERNAME}'
  smtp_auth_username: '${SMTP_USERNAME}'
  smtp_auth_password: '${SMTP_PASSWORD}'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'trading-alerts'

receivers:
  - name: 'trading-alerts'
    email_configs:
      - to: '${ALERT_RECIPIENTS}'
        subject: '[{{ .Status | toUpper }}] Trading App Alert: {{ .GroupLabels.alertname }}'
        body: |
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          Severity: {{ .Labels.severity }}
          Component: {{ .Labels.component }}
          {{ end }}
EOF

    log "Monitoring configuration files created"
}

# Function to create Docker Compose for monitoring stack
create_docker_compose() {
    log "Creating Docker Compose configuration for monitoring stack..."
    
    cat > "$DOCKER_COMPOSE_FILE" << 'EOF'
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'
    restart: unless-stopped
    networks:
      - monitoring

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana_data:/var/lib/grafana
      - ./config/grafana/provisioning:/etc/grafana/provisioning
      - ./config/grafana/dashboards:/var/lib/grafana/dashboards
    restart: unless-stopped
    networks:
      - monitoring

  alertmanager:
    image: prom/alertmanager:latest
    container_name: alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./config/alertmanager:/etc/alertmanager
      - alertmanager_data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
      - '--web.external-url=http://localhost:9093'
    restart: unless-stopped
    networks:
      - monitoring

  trading-app:
    image: ghcr.io/qsor27/futurestradinglog:main
    container_name: trading-app
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
      - DATA_DIR=/app/data
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    networks:
      - monitoring
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    container_name: redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - monitoring

volumes:
  prometheus_data:
  grafana_data:
  alertmanager_data:
  redis_data:

networks:
  monitoring:
    driver: bridge
EOF

    log "Docker Compose file created at $DOCKER_COMPOSE_FILE"
}

# Function to start monitoring stack
start_monitoring_stack() {
    log "Starting monitoring stack..."
    
    cd "$PROJECT_ROOT"
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d
    
    log "Monitoring stack started successfully!"
    log "Services available at:"
    log "  - Trading App: http://localhost:5000"
    log "  - Prometheus: http://localhost:9090"
    log "  - Grafana: http://localhost:3000 (admin/admin123)"
    log "  - AlertManager: http://localhost:9093"
}

# Function to setup monitoring scripts
setup_monitoring_scripts() {
    log "Setting up monitoring scripts..."
    
    # Make health check script executable
    chmod +x "$SCRIPT_DIR/health-check.sh"
    
    # Create monitoring cron job
    cat > "$SCRIPT_DIR/monitor.sh" << 'EOF'
#!/bin/bash

# Continuous monitoring script for Trading Application
# Runs health checks and sends alerts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEALTH_CHECK_SCRIPT="$SCRIPT_DIR/health-check.sh"

# Run health check
if ! "$HEALTH_CHECK_SCRIPT"; then
    echo "Health check failed - check logs for details"
    exit 1
fi

echo "Health check passed"
EOF

    chmod +x "$SCRIPT_DIR/monitor.sh"
    
    log "Monitoring scripts setup complete"
}

# Main function
main() {
    log "Starting comprehensive monitoring setup for Futures Trading Application"
    
    check_prerequisites
    create_monitoring_configs
    create_docker_compose
    setup_monitoring_scripts
    
    echo
    log "Monitoring setup completed successfully!"
    echo
    echo "To start the monitoring stack:"
    echo "  cd $PROJECT_ROOT"
    echo "  docker-compose -f docker-compose.monitoring.yml up -d"
    echo
    echo "To run health checks:"
    echo "  $SCRIPT_DIR/health-check.sh"
    echo
    echo "To run continuous monitoring:"
    echo "  $SCRIPT_DIR/monitor.sh"
    echo
    echo "Environment variables to configure email alerts:"
    echo "  export SMTP_SERVER=smtp.gmail.com"
    echo "  export SMTP_PORT=587"
    echo "  export SMTP_USERNAME=your-email@gmail.com"
    echo "  export SMTP_PASSWORD=your-app-password"
    echo "  export ALERT_RECIPIENTS=alerts@your-domain.com"
}

# Run main function
main "$@"