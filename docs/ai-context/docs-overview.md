# Futures Trading Log - Documentation Architecture

This project uses a **comprehensive documentation system** that organizes knowledge by stability and scope, enabling efficient AI context loading and scalable development for the Futures Trading Log application.

## How the Documentation System Works

**Tier 1 (Foundation)**: Stable, system-wide documentation that rarely changes - architectural principles, technology decisions, cross-component patterns, and core development protocols for the Flask-based trading log system.

**Tier 2 (Component)**: Architectural guidance for major components - high-level design principles, integration patterns, and component-wide conventions for routes, services, and data processing.

**Tier 3 (Feature-Specific)**: Implementation-specific documentation co-located with code - specific patterns, technical details, and local architectural decisions that evolve with trading features.

This hierarchy allows AI agents to load targeted context efficiently while maintaining a stable foundation of core trading application knowledge.

## Documentation Principles
- **Co-location**: Documentation lives near relevant code
- **Smart Extension**: New documentation files created automatically when warranted
- **AI-First**: Optimized for efficient AI context loading and machine-readable patterns

## Tier 1: Foundational Documentation (System-Wide)

- **[Master Context](/CLAUDE.md)** - *Essential for every session.* **CRITICAL: Position building algorithm**, coding standards, security requirements, MCP server integration patterns, and development protocols
- **[Project Structure](/docs/ai-context/project-structure.md)** - *REQUIRED reading.* Complete Flask technology stack, file tree, and system architecture. Must be attached to Gemini consultations
- **[System Integration](/docs/ai-context/system-integration.md)** - *For cross-component work.* Flask blueprint patterns, data flow, testing strategies, and performance optimization
- **[Deployment Infrastructure](/docs/ai-context/deployment-infrastructure.md)** - *Infrastructure patterns.* Docker containerization, GitHub Actions CI/CD, monitoring, and scaling strategies
- **[Task Management](/docs/ai-context/handoff.md)** - *Session continuity.* Current tasks, documentation system progress, and next session goals

## Tier 2: Component-Level Documentation

### Core Application Components
- **[Flask Application](/app.py)** - *Main application.* Flask app initialization, blueprint registration, and background services integration
- **[Database Layer](/TradingLog_db.py)** - *Data persistence.* SQLAlchemy ORM models, aggressive indexing, and performance optimization
- **[Position Service](/position_service.py)** - *🚨 CRITICAL COMPONENT.* Position building algorithm, quantity flow analysis, and FIFO P&L calculation
- **[Configuration](/config.py)** - *Environment setup.* Cross-platform configuration, Docker support, and environment variables

### Data Processing Components
- **[Data Service](/data_service.py)** - *Market data.* yfinance integration, Redis caching, gap detection, and rate limiting
- **[Redis Cache Service](/redis_cache_service.py)** - *Performance layer.* 14-day TTL caching, intelligent cleanup, and background gap-filling
- **[Background Services](/background_services.py)** - *Automation.* Scheduled tasks, gap-filling, cache maintenance, and data updates
- **[Execution Processing](/ExecutionProcessing.py)** - *NinjaTrader integration.* CSV processing, multi-account support, and duplicate prevention

### Web Interface Components
- **[Route System](/routes/)** - *Flask blueprints.* Modular routing architecture with 13 specialized route files
- **[Template System](/templates/)** - *Jinja2 templates.* Component-based templates with dark theme and responsive design
- **[Static Assets](/static/)** - *Frontend resources.* CSS, JavaScript modules, and TradingView chart integration

### Infrastructure Components
- **[Docker Configuration](/Dockerfile)** - *Containerization.* Production-ready container deployment with security hardening
- **[GitHub Actions](/.github/workflows/)** - *CI/CD pipeline.* Automated testing, container building, and deployment
- **[Scripts](/scripts/)** - *Automation tools.* Deployment scripts, security setup, and maintenance utilities

## Tier 3: Feature-Specific Documentation

Granular implementation documentation co-located with code for minimal cascade effects:

### Route-Level Documentation
- **[Main Routes](/routes/main.py)** - *Homepage and listings.* Trade listing, filtering, pagination, and main dashboard functionality
- **[Trade Routes](/routes/trades.py)** - *Trade CRUD.* Individual trade operations, editing, deletion, and management
- **[Position Routes](/routes/positions.py)** - *🆕 Position features.* Position dashboard, detail pages, rebuild functionality, and debug interfaces
- **[Upload Routes](/routes/upload.py)** - *CSV import.* File upload workflow, NinjaTrader CSV processing, and error handling
- **[Chart Data Routes](/routes/chart_data.py)** - *Chart APIs.* OHLC data endpoints, trade markers, and high-performance data serving
- **[Statistics Routes](/routes/statistics.py)** - *Analytics.* Performance metrics, P&L analysis, and statistical calculations
- **[Trade Details Routes](/routes/trade_details.py)** - *Enhanced detail view.* Comprehensive execution breakdown, interactive charts, and position analysis
- **[Trade Links Routes](/routes/trade_links.py)** - *Trade linking.* Trade grouping, link management, and relationship tracking
- **[Settings Routes](/routes/settings.py)** - *Configuration.* Instrument multipliers, application settings, and user preferences
- **[Reports Routes](/routes/reports.py)** - *Reporting.* Report generation, performance analysis, and export functionality
- **[Data Monitoring Routes](/routes/data_monitoring.py)** - *Data quality.* Data validation, gap detection, and monitoring dashboards
- **[Execution Analysis Routes](/routes/execution_analysis.py)** - *Trade analysis.* Execution quality analysis and performance metrics

### Template-Level Documentation
- **[Position Templates](/templates/positions/)** - *Position UI.* Dashboard, detail views, and debug interfaces for position-based trading analysis
- **[Report Templates](/templates/reports/)** - *Reporting UI.* Performance reports, execution quality analysis, and dashboard views
- **[Monitoring Templates](/templates/monitoring/)** - *Data quality UI.* Data monitoring dashboards and validation interfaces
- **[Chart Components](/templates/components/)** - *Reusable UI.* TradingView chart integration, filter sections, and pagination components

### JavaScript Module Documentation
- **[Price Chart Module](/static/js/PriceChart.js)** - *🎯 Enhanced charts.* TradingView Lightweight Charts integration, execution overlays, and chart-table synchronization
- **[Trade Management](/static/js/trades.js)** - *Trade interactions.* Trade management UI, filtering, and table interactions
- **[Linked Trades](/static/js/linked_trades.js)** - *Trade linking.* Trade grouping UI, link management, and relationship visualization
- **[P&L Graphs](/static/js/PnLGraph.js)** - *Performance visualization.* P&L charting, performance metrics, and visual analytics
- **[Statistics Charts](/static/js/StatisticsChart.js)** - *Analytics visualization.* Statistical charting and performance metrics display
- **[Chart Settings API](/static/js/ChartSettingsAPI.js)** - *Chart configuration.* Chart settings management and user preferences

### Service-Level Documentation
- **[File Watcher Service](/services/file_watcher.py)** - *Auto-import.* File monitoring, automatic CSV processing, and background file handling
- **[Background Services](/background_services.py)** - *Automation.* Scheduled tasks, gap-filling automation, and system maintenance



## Adding New Documentation

### New Route Module
1. Create new route file in `/routes/new_feature.py`
2. Add blueprint registration in `/routes/__init__.py`
3. Add entry to this file under "Route-Level Documentation"
4. Create corresponding templates in `/templates/new_feature/`

### New Trading Feature
1. Add implementation to appropriate route file
2. Create templates in `/templates/` if needed
3. Add JavaScript module in `/static/js/` if interactive
4. Update this documentation with new feature details

### New Service Component
1. Create service file in root directory (e.g., `/new_service.py`)
2. Add integration to `/app.py` if needed
3. Add entry to this file under "Core Application Components"
4. Update configuration in `/config.py` if required

### Position-Related Features
1. **⚠️ CRITICAL**: Any changes to position building logic must be documented
2. Update `/position_service.py` with extreme care
3. Add new position features to `/routes/positions.py`
4. Create corresponding templates in `/templates/positions/`
5. Test thoroughly with `/positions/rebuild` functionality

### Deprecating Documentation
1. Remove obsolete route files and update blueprint registration
2. Remove corresponding templates and static assets
3. Update this mapping document
4. Check for broken references in other routes and templates

## Key Documentation Patterns

### Critical Component Documentation
- **Position Building Algorithm** - Most critical component requiring detailed documentation
- **Database Schema** - Changes require migration documentation
- **Chart Integration** - TradingView integration patterns and performance considerations
- **Performance Optimization** - Database indexing and caching strategies

### Development Workflow Documentation
- **Testing Strategy** - 120+ test suite maintenance and expansion
- **Deployment Process** - Docker containerization and GitHub Actions CI/CD
- **Security Patterns** - Container security and data protection
- **Performance Monitoring** - Database performance and Redis caching optimization

---

*This documentation architecture is specifically designed for the Futures Trading Log Flask application, emphasizing the critical position building algorithm and trading-specific features.*