# Futures Trading Log - Project Structure

This document provides the complete technology stack and file tree structure for the Futures Trading Log project. **AI agents MUST read this file to understand the project organization before making any changes.**

## Technology Stack

### Backend Technologies
- **Python 3.11+** with **pip** - Dependency management and packaging
- **Flask 3.0.0** - Web framework with Werkzeug 3.0.1 WSGI server
- **SQLAlchemy 2.0.23** - Database ORM and query builder
- **SQLite** - Local database for trade data and OHLC storage
- **python-dotenv** - Environment configuration management

### Integration Services & APIs
- **yfinance 0.2.28** - Financial data API for OHLC market data
- **requests 2.31.0** - HTTP client for external API calls
- **Redis 5.0.1** - Caching layer for performance optimization
- **schedule 1.2.0** - Background task scheduling
- **pandas 2.1.4** - Data processing and CSV manipulation
- **pymysql 1.1.0** - MySQL database connectivity (optional)

### Monitoring & System Health
- **prometheus-client 0.19.0** - Metrics collection and monitoring
- **psutil 5.9.6** - System resource monitoring
- **email-validator 2.1.0** - Input validation utilities
- **Comprehensive logging** - Multi-file rotating logs with health checks

### Development & Quality Tools
- **pytest 7.4.3** - Testing framework with coverage reporting
- **pytest-cov 4.1.0** - Test coverage analysis
- **pytest-mock 3.8.0+** - Mock testing utilities
- **Docker** - Containerized deployment with watchtower auto-updates
- **GitHub Actions** - CI/CD pipeline for automated testing and deployment

### Frontend Technologies
- **Jinja2** - Server-side templating engine
- **HTML5/CSS3** - Modern web standards with responsive design
- **JavaScript ES6+** - Client-side interactivity and chart integration
- **TradingView Lightweight Charts** - Advanced financial charting library
- **Bootstrap-inspired** - Custom CSS framework for professional UI

### External Integrations
- **NinjaTrader** - Trading platform integration via CSV export
- **GitHub Container Registry** - Docker image hosting and distribution
- **Watchtower** - Automated container updates in production

## Complete Project Structure

```
FuturesTradingLog/
├── README.md                           # Project overview and setup
├── CLAUDE.md                           # Master AI context file
├── requirements.txt                    # Python dependencies
├── Dockerfile                          # Container configuration
├── docker-compose.yml                  # Local development setup
├── docker-compose.prod.yml             # Production deployment
├── pytest.ini                         # Testing configuration
├── .gitignore                          # Git ignore patterns
│
├── app.py                              # Flask application entry point
├── config.py                           # Application configuration
├── logging_config.py                   # Centralized logging setup
│
├── TradingLog_db.py                    # Database models and ORM
├── position_service.py                 # **CRITICAL** - Position building algorithm
├── data_service.py                     # OHLC data integration (yfinance)
├── redis_cache_service.py              # Redis caching layer
├── background_services.py              # Scheduled tasks and gap-filling
├── symbol_service.py                   # Instrument symbol mapping
├── backup_manager.py                   # Database backup automation
├── ExecutionProcessing.py              # NinjaTrader CSV processing
│
├── routes/                             # Flask route blueprints
│   ├── __init__.py                     # Blueprint registration
│   ├── main.py                         # Homepage and trade listing
│   ├── trades.py                       # Trade CRUD operations
│   ├── positions.py                    # **NEW** - Position dashboard & detail
│   ├── upload.py                       # CSV import workflow
│   ├── statistics.py                   # Performance analytics
│   ├── trade_details.py                # Enhanced trade detail pages
│   ├── trade_links.py                  # Trade linking functionality
│   ├── chart_data.py                   # OHLC data APIs
│   ├── settings.py                     # Application settings
│   ├── reports.py                      # Reporting functionality
│   ├── data_monitoring.py              # Data quality monitoring
│   └── execution_analysis.py           # Trade execution analysis
│
├── services/                           # Background services
│   ├── __init__.py                     # Service initialization
│   └── file_watcher.py                 # Auto-import file monitoring
│
├── templates/                          # Jinja2 HTML templates
│   ├── base.html                       # Base template with dark theme
│   ├── index.html                      # Homepage
│   ├── main.html                       # Trade listing page
│   ├── trade_detail.html               # Enhanced trade detail view
│   ├── chart.html                      # Standalone chart pages
│   ├── statistics.html                 # Performance analytics
│   ├── settings.html                   # Application settings
│   ├── upload.html                     # CSV import interface
│   ├── linked_trades.html              # Trade linking interface
│   ├── error.html                      # Error handling template
│   │
│   ├── positions/                      # **NEW** - Position templates
│   │   ├── dashboard.html              # Position dashboard
│   │   ├── detail.html                 # Position detail view
│   │   └── debug.html                  # Position building debug
│   │
│   ├── reports/                        # Reporting templates
│   │   ├── dashboard.html              # Reports dashboard
│   │   ├── performance.html            # Performance reports
│   │   └── execution_quality.html      # Execution analysis
│   │
│   ├── monitoring/                     # Monitoring templates
│   │   └── dashboard.html              # Data quality monitoring
│   │
│   ├── components/                     # Reusable template components
│   │   ├── filter_section.html         # Trade filtering
│   │   ├── import_section.html         # CSV import section
│   │   ├── pagination.html             # Pagination controls
│   │   └── price_chart.html            # TradingView chart component
│   │
│   └── partials/                       # Template partials
│       ├── filters.html                # Filter controls
│       ├── pagination.html             # Pagination partial
│       └── trade_table.html            # Trade table component
│
├── static/                             # Static web assets
│   ├── css/
│   │   └── styles.css                  # Professional dark theme CSS
│   │
│   └── js/                             # JavaScript modules
│       ├── main.js                     # Core application logic
│       ├── trades.js                   # Trade management interactions
│       ├── linked_trades.js            # Trade linking functionality
│       ├── PriceChart.js               # **ENHANCED** - TradingView integration
│       ├── PnLGraph.js                 # P&L visualization
│       ├── StatisticsChart.js          # Performance metrics charts
│       └── ChartSettingsAPI.js         # Chart configuration API
│
├── tests/                              # Comprehensive test suite (120+ tests)
│   ├── README.md                       # Testing documentation
│   ├── conftest.py                     # Test configuration
│   ├── test_app.py                     # Flask application tests
│   ├── test_chart_api.py               # Chart API tests
│   ├── test_data_service.py            # Data service tests
│   ├── test_integration.py             # Integration tests
│   ├── test_ohlc_database.py           # OHLC database tests
│   └── test_performance.py             # Performance validation
│
├── data/                               # **PERSISTENT** - Data storage directory
│   ├── db/                             # SQLite databases
│   │   └── futures_trades.db           # Main database (trades + OHLC)
│   ├── config/                         # Configuration files
│   │   └── instrument_multipliers.json # Instrument settings
│   ├── logs/                           # Application logs
│   │   ├── app.log                     # Main application log
│   │   ├── error.log                   # Error-only log
│   │   ├── database.log                # Database operations
│   │   ├── flask.log                   # Web server logs
│   │   └── file_watcher.log            # Auto-import monitoring
│   ├── charts/                         # Chart storage
│   └── archive/                        # Processed CSV files
│
├── docs/                               # Documentation
│   ├── README.md                       # Documentation overview
│   ├── CLAUDE.md                       # Project-specific AI context
│   │
│   ├── ai-context/                     # AI-specific documentation
│   │   ├── project-structure.md        # This file
│   │   ├── docs-overview.md            # Documentation architecture
│   │   ├── system-integration.md       # Integration patterns
│   │   ├── deployment-infrastructure.md # Infrastructure docs
│   │   └── handoff.md                  # Task management
│   │
│   ├── specs/                          # Technical specifications
│   │   ├── example-api-integration-spec.md
│   │   └── example-feature-specification.md
│   │
│   └── open-issues/                    # Issue tracking
│       └── example-api-performance-issue.md
│
├── scripts/                            # Automation and deployment scripts
│   ├── setup_data_dir.py               # Data directory initialization
│   ├── test_performance.py             # Performance testing
│   ├── backup-database.sh              # Database backup
│   ├── deploy-production.sh            # Production deployment
│   ├── health-check.sh                 # System health validation
│   ├── restore-database.sh             # Database restoration
│   ├── security-hardening.sh           # Security configuration
│   ├── security-monitor.sh             # Security monitoring
│   ├── setup-backup-system.sh          # Backup system setup
│   ├── setup-github-runner.sh          # GitHub Actions runner
│   ├── setup-litestream.sh             # Database streaming backup
│   ├── setup-ssl.sh                    # SSL certificate setup
│   └── validate-security.sh            # Security validation
│
├── config/                             # Infrastructure configuration
│   ├── nginx.conf                      # Nginx web server config
│   ├── nginx-trading-app.conf          # Application-specific config
│   ├── litestream.yml                  # Database streaming config
│   ├── prometheus.yml                  # Monitoring configuration
│   ├── fail2ban-jail.local             # Security configuration
│   ├── fail2ban-filters.conf           # Security filters
│   ├── docker-security.json            # Container security settings
│   │
│   └── grafana/                        # Monitoring dashboard
│       └── provisioning/
│           └── datasources/
│               └── prometheus.yml
│
├── docker/                             # Docker configurations
│   └── docker-compose.production.yml   # Production deployment
│
├── ninjascript/                        # NinjaTrader integration
│   └── ExecutionExporter.cs            # Real-time execution exporter
│
├── tools/                              # Utility tools
│   ├── manual_gap_fill.py              # Manual OHLC gap filling
│   ├── repair_ohlc_data.py             # Data repair utilities
│   └── simple_gap_fill.py              # Simple gap filling
│
└── [Various Documentation Files]       # Project documentation
    ├── AUTO_IMPORT_SETUP.md            # Auto-import configuration
    ├── BACKUP_SYSTEM.md                # Backup system documentation
    ├── DEPLOYMENT.md                   # Deployment guides
    ├── ENHANCED_POSITION_GUIDE.md      # Position feature guide
    ├── NINJASCRIPT_SETUP.md            # NinjaScript integration
    ├── REDIS_SETUP.md                  # Redis configuration
    ├── RESEARCH_RESULTS.md             # Research findings
    └── TODO.md                         # Development roadmap
```

## Key Architectural Components

### Core Database Files
- **`TradingLog_db.py`** - SQLAlchemy ORM models for trades, positions, and OHLC data
- **`position_service.py`** - **CRITICAL** - Position building algorithm (0→+/-→0 lifecycle)
- **`data_service.py`** - yfinance integration with Redis caching and gap detection
- **`redis_cache_service.py`** - 14-day TTL caching layer for performance optimization

### Flask Application Structure
- **`app.py`** - Main Flask application with blueprint registration
- **`config.py`** - Environment-based configuration with Docker support
- **`logging_config.py`** - Multi-file rotating logs with health checks
- **`routes/`** - Modular blueprint-based routing system

### Position-Based Architecture (NEW)
- **`routes/positions.py`** - Position dashboard, detail pages, and debug interfaces
- **`templates/positions/`** - Position-centric templates with execution breakdown
- **Position Building Algorithm** - Transforms individual executions into aggregated positions
- **FIFO P&L Calculation** - Proper entry/exit price averaging and profit calculation

### Enhanced Chart Integration
- **`static/js/PriceChart.js`** - TradingView Lightweight Charts with execution overlays
- **`templates/components/price_chart.html`** - Reusable chart component
- **`routes/chart_data.py`** - High-performance OHLC data APIs (15-50ms response times)
- **Multi-timeframe Support** - 1m, 5m, 15m, 1h, 4h, 1d with smart fallback

### Performance Optimizations
- **8 Aggressive Database Indexes** - Millisecond query performance for 10M+ records
- **Redis Caching** - 20-60x faster chart loading when available
- **Background Services** - Automated gap detection and data maintenance
- **Cursor-based Pagination** - Scalable pagination for large datasets

### Testing & Quality Assurance
- **120+ Test Suite** - Comprehensive testing with 100% success rate
- **Performance Validation** - Sub-50ms query performance targets
- **GitHub Actions CI/CD** - Automated testing and deployment
- **Docker Integration** - Containerized testing and deployment

### Deployment Architecture
- **Docker Containerization** - Production-ready container deployment
- **Watchtower Integration** - Automated container updates
- **GitHub Container Registry** - Image hosting and distribution
- **Health Check System** - Comprehensive system monitoring

## Critical Implementation Notes

### Position Building Algorithm
The `position_service.py` contains the **MOST CRITICAL** component of the entire application:
- **Quantity Flow Analysis** - Tracks running position quantity through all executions
- **Position Lifecycle** - Enforces 0→+/-→0 pattern (never Long→Short without flat)
- **FIFO Aggregation** - Proper entry/exit price calculation using quantity-weighted averages
- **⚠️ WARNING** - Any modifications to this algorithm affects ALL historical data interpretation

### Database Performance
- **SQLite WAL Mode** - Write-ahead logging for better concurrency
- **Memory Mapping** - 1GB mmap for large dataset performance
- **Optimized Indexes** - 8 carefully designed indexes for millisecond queries
- **Performance Monitoring** - Built-in query plan analysis and optimization

### Security & Production
- **Environment Configuration** - Secure secrets management
- **Health Check Endpoints** - System monitoring and alerting
- **Comprehensive Logging** - Multi-file logs with rotation and filtering
- **Container Security** - Hardened Docker deployment with security scanning

---

*This documentation provides AI agents with comprehensive understanding of the Futures Trading Log project structure, technology stack, and critical implementation details.*