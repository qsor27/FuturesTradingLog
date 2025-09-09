# Technical Stack

> Last Updated: 2025-08-17
> Version: 1.0.0

## Application Framework

- **Framework:** Flask 3.0.0
- **Version:** 3.0.0
- **Architecture:** Blueprint-based routing with modular design
- **WSGI Server:** Gunicorn for production deployment

## Database

- **Primary Database:** SQLite with WAL mode
- **Performance:** 8 aggressive indexes for optimized queries
- **Cache Layer:** Redis 5.0.1 with 14-day retention
- **ORM:** SQLAlchemy with Pydantic models
- **Migration Strategy:** Schema versioning with automated updates

## JavaScript

- **Framework:** TradingView Lightweight Charts
- **Version:** Latest stable
- **Features:** Real-time chart rendering, trade execution overlays
- **Performance:** 15-50ms chart load times with Redis caching

## CSS Framework

- **Framework:** Bootstrap 5
- **Customization:** Custom trading-focused components
- **Responsive Design:** Mobile-first approach for dashboard access

## Data Processing

- **Core Library:** Pandas 2.1.4 for data manipulation
- **Market Data:** yfinance 0.2.28 for historical price data
- **File Processing:** Real-time CSV monitoring with automated import
- **Background Jobs:** Celery 5.3.4 with Redis broker

## Infrastructure & DevOps

- **Containerization:** Docker with multi-stage builds
- **Orchestration:** Docker Compose for development
- **Auto-Updates:** Watchtower for automatic container updates
- **CI/CD:** GitHub Actions with automated testing and deployment

## Monitoring & Observability

- **Metrics:** Prometheus with custom trading metrics
- **Health Checks:** Automated endpoint monitoring
- **Logging:** Structured logging with log rotation
- **Testing:** 120+ comprehensive tests with pytest

## External Integrations

- **Trading Platform:** NinjaTrader CSV import/export
- **Chart Provider:** TradingView Lightweight Charts
- **Market Data:** Yahoo Finance API via yfinance
- **File System:** Real-time file watching for automated sync

## Performance Optimizations

- **Database Indexing:** 8 strategic indexes for query optimization
- **Caching Strategy:** Redis with intelligent cache invalidation
- **Background Processing:** Asynchronous data processing with Celery
- **Memory Management:** Efficient pandas operations with chunked processing

## Security & Reliability

- **Data Integrity:** Position overlap detection and prevention
- **Error Handling:** Comprehensive exception handling and recovery
- **Backup Strategy:** Automated database backups with retention policies
- **Configuration Management:** Environment-based settings with validation