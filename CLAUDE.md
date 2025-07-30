# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 **CRITICAL: POSITION BUILDING ALGORITHM**

**The core position building algorithm is located in `domain/services/position_builder.py` and is the MOST IMPORTANT component of the application.**

### **Core Algorithm Location**

**LOCATION**: `domain/services/position_builder.py` - Contains the position building logic

Transforms NinjaTrader executions into position records using **Quantity Flow Analysis**:

#### **Fundamental Rules:**
1. **Position Lifecycle**: `0 → +/- → 0` (never Long→Short without reaching 0)
2. **Quantity Flow**: Track running quantity through all executions
3. **FIFO P&L**: Weighted averages for entry/exit prices

#### **Algorithm:**
```
For each execution:
  1. Calculate signed_qty_change (Long: +qty, Short: -qty)
  2. Update running_quantity += signed_qty_change
  3. Position lifecycle:
     - START (0→non-zero): Create position
     - MODIFY (non-zero→non-zero): Add to position  
     - CLOSE (non-zero→0): Complete position, save P&L
```

#### **⚠️ Critical Warning:**
- Algorithm is in `domain/services/position_builder.py` - **PRESERVE ALGORITHM INTEGRITY**
- Always test with `/positions/rebuild` after any changes
- Improper modifications break ALL historical P&L calculations

## Project Overview

Flask web application for futures traders - processes NinjaTrader executions into position-based trading analytics.

### Key Features
- **Position-Based Architecture**: Aggregates executions into meaningful positions with comprehensive overlap prevention
- **TradingView Charts**: Interactive charts with enhanced OHLC hover display and real-time validation status
- **High Performance**: 15-50ms chart loads with aggressive database indexing and adaptive resolution
- **Redis Caching**: 14-day data retention for faster performance with graceful fallback
- **Docker Deployment**: Container-based production deployment with health monitoring
- **Validation System**: Real-time position overlap detection with automated prevention and UI integration
- **User Preferences**: Persistent chart settings with localStorage caching and API synchronization

## Architecture

See **[docs/ai-context/project-structure.md](docs/ai-context/project-structure.md)** for complete project structure and technology stack.

### Core Components

#### **Modern Architecture (Repository Pattern)**
- **Domain Layer** (`domain/`):
  - `models/`: Core business entities (Position, Trade, Execution, PnL)
  - `services/`: Pure business logic (PositionBuilder, PnLCalculator, QuantityFlowAnalyzer)
  - `interfaces/`: Service and repository contracts
- **Application Services** (`services/`):
  - `position_engine/`: Position building orchestration
  - `trade_management/`: Trade operations and filtering
  - `chart_data/`: Chart data with performance optimization
  - `file_processing/`: CSV processing and validation
  - `position_management/`: Position dashboard and statistics
- **Repository Layer** (`repositories/`):
  - `trade_repository.py`: Trade data operations
  - `position_repository.py`: Position data operations
  - `ohlc_repository.py`: Market data operations
  - `settings_repository.py`: Configuration data operations
  - `profile_repository.py`: User profile operations
  - `statistics_repository.py`: Analytics and reporting operations

#### **Key Components**
- **`position_service.py`**: Position building algorithm (extracted to domain services)
- **`enhanced_position_service.py`**: Enhanced position service with comprehensive overlap prevention  
- **`database_manager.py`**: Repository pattern coordinator (replaces TradingLog_db.py)
- **`data_service.py`**: yfinance integration with repository pattern
- **`app.py`**: Flask application with repository pattern
- **`routes/`**: All route blueprints use repository pattern

### Database Schema
- **Trades**: Individual executions with P&L, linking via `link_group_id`
- **Positions**: Aggregated position data with lifecycle tracking
- **OHLC_Data**: Market data with 8 performance indexes (15-50ms queries)
- **Chart_Settings**: User preferences for timeframes and display options
- **User_Profiles**: Named configuration profiles with settings snapshots

## Development & Deployment

### Development (Docker-First)
```bash
# Standard development workflow
./dev.sh                                     # Start development environment

# Alternative
docker-compose -f docker-compose.dev.yml up --build

# Benefits:
# - Matches production environment exactly
# - Live code reloading (edit files normally) 
# - Debug mode enabled
# - No Python virtual environment needed
# - No dependency version conflicts
```

### Production Deployment
```bash
# Production (automatic via GitHub Actions)
git push origin main                          # Auto-deploy via GitHub Actions

# Production (manual)
docker-compose up --build                    # Production deployment

# Health checks
curl http://localhost:5000/health            # Basic health check
pytest tests/ -v                             # Run tests
```

### GitHub Actions Workflow
The deployment pipeline consists of 3 jobs:
1. **Test**: Code quality validation and basic functionality tests
2. **Build-and-Push**: Creates Docker image and pushes to GitHub Container Registry
3. **Security-Scan**: Vulnerability scanning with Trivy (optional but recommended)

## Configuration

See **[docs/CONFIGURATION_HIERARCHY.md](docs/CONFIGURATION_HIERARCHY.md)** for complete configuration management details.

### Key Environment Variables
- `DATA_DIR`: Data storage directory (default: `~/FuturesTradingLog/data`)
- `REDIS_URL`: Redis connection (default: `redis://localhost:6379/0`)
- `CACHE_TTL_DAYS`: Cache retention (default: `14`)

### Data Directory Structure
```
data/
├── db/              # SQLite database (persistent)
├── config/          # instrument_multipliers.json
├── logs/            # Application logs (rotating)
└── archive/         # Processed CSV files
```

### Storage Strategy
- **SQLite**: Primary storage - all data persists permanently
- **Redis**: Performance layer - 14-day TTL, 20-60x faster queries
- **Graceful fallback**: Redis unavailable → automatic SQLite fallback

## NinjaTrader Integration

See **[docs/NINJASCRIPT_SETUP.md](docs/NINJASCRIPT_SETUP.md)** for complete setup instructions.

### Quick Setup
1. **Manual**: Export execution report → Process with `ExecutionProcessing.py` → Import via web interface
2. **Automated**: Install `ExecutionExporter.cs` NinjaScript indicator for real-time CSV export

## Performance

### Database Optimization
- **8 Aggressive Indexes**: 15-50ms chart loads for 10M+ records
- **SQLite WAL Mode**: Better concurrency with 1GB memory mapping
- **Cursor Pagination**: Scalable pagination for large datasets

### Testing
```bash
pytest tests/test_performance.py -v                      # Performance validation
curl http://localhost:5000/api/validation/health         # Validation system health
curl http://localhost:5000/api/validation/summary        # Position validation status
```

## Logging

### Log Files (`data/logs/`)
- **`error.log`**: Quick troubleshooting (errors only)
- **`app.log`**: Main application activity  
- **`database.log`**: Database operations and performance
- **`flask.log`**: Web server requests

### Quick Log Analysis
```bash
tail -f logs/error.log                                   # Monitor errors
grep "performance\|slow" logs/database.log               # Performance issues
```

## Key Implementation Notes
- **Position-based architecture** with quantity flow analysis (0 → +/- → 0 lifecycle) and comprehensive overlap prevention
- **Enhanced validation system** with real-time monitoring, automated error detection, and UI integration
- **Professional chart interface** with OHLC hover display, volume data, price change indicators, and smooth animations
- **User preferences system** with persistent settings, localStorage caching, and API synchronization
- **Blueprint-based Flask routing** with context-managed database connections and validation endpoints
- **FIFO aggregation** with Entry/Exit marker processing and boundary validation
- **Performance-optimized database** with aggressive indexing and adaptive API resolution
- **Docker deployment** with cross-platform configuration and health monitoring

## Validation System Features

### Real-Time Monitoring
- **Position Overlap Detection**: Automatic detection of time-based and logic-based position overlaps
- **Boundary Validation**: Ensures positions follow proper 0 → +/- → 0 lifecycle without direction changes
- **Data Integrity Checks**: Validates execution timestamps, quantities, and consistency
- **UI Integration**: Live status indicators on position dashboard with color-coded alerts

### API Endpoints (`/api/validation/`)
- **`/health`**: Validation system health check
- **`/summary`**: Comprehensive validation summary with issue counts
- **`/current-positions`**: Detailed analysis of current position overlaps
- **`/boundary-validation`**: Position boundary and lifecycle validation
- **`/prevention-report`**: Full validation report with fix suggestions
- **`/overlap-analysis`**: Complete overlap analysis with detailed findings

### Automatic Prevention
- **Enhanced Position Service**: Drop-in replacement with validation enabled by default
- **Pre/Post Validation**: Checks before and after position building operations
- **Error Recovery**: Automatic fix suggestions and recovery mechanisms
- **Notification System**: Real-time alerts for validation status changes

## Documentation References

### Core Documentation
- **[docs/ARCHITECTURAL_ANALYSIS.md](docs/ARCHITECTURAL_ANALYSIS.md)** - Architecture problems and coupling analysis
- **[docs/MODULAR_ARCHITECTURE_PLAN.md](docs/MODULAR_ARCHITECTURE_PLAN.md)** - Comprehensive refactoring plan
- **[docs/REFACTORING_ROADMAP.md](docs/REFACTORING_ROADMAP.md)** - Step-by-step implementation guide
- **[docs/ai-context/project-structure.md](docs/ai-context/project-structure.md)** - Complete project structure and technology stack

### Setup & Configuration
- **[docs/NINJASCRIPT_SETUP.md](docs/NINJASCRIPT_SETUP.md)** - NinjaScript indicator installation and configuration
- **[docs/CONFIGURATION_HIERARCHY.md](docs/CONFIGURATION_HIERARCHY.md)** - Configuration management details
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Deployment procedures and infrastructure
- **[docs/QUICK_START_GUIDE.md](docs/QUICK_START_GUIDE.md)** - Quick start guide for development

### Features & Guides
- **[docs/ENHANCED_POSITION_GUIDE.md](docs/ENHANCED_POSITION_GUIDE.md)** - Position features and chart synchronization guide
- **[docs/POSITION_OVERLAP_SOLUTION.md](docs/POSITION_OVERLAP_SOLUTION.md)** - Position overlap detection and prevention
- **[docs/USER_PROFILES_IMPLEMENTATION.md](docs/USER_PROFILES_IMPLEMENTATION.md)** - User profile system details
- **[docs/ENHANCED_SETTINGS_IMPLEMENTATION.md](docs/ENHANCED_SETTINGS_IMPLEMENTATION.md)** - Settings system implementation

### Infrastructure & Operations
- **[docs/REDIS_SETUP.md](docs/REDIS_SETUP.md)** - Redis caching configuration
- **[docs/BACKUP_SYSTEM.md](docs/BACKUP_SYSTEM.md)** - Backup system configuration
- **[docs/SECURITY_SETUP.md](docs/SECURITY_SETUP.md)** - Security configuration and hardening
- **[docs/GITHUB_AUTO_DEPLOY_SETUP.md](docs/GITHUB_AUTO_DEPLOY_SETUP.md)** - GitHub Actions deployment setup

## Important Implementation Notes
- Database uses context managers for connection handling
- All routes use blueprint registration pattern
- CSV processing includes duplicate detection and validation
- Trade linking allows grouping related positions
- Frontend uses hybrid server-side rendering with JavaScript enhancements
- Database automatically creates indexes and applies performance optimizations on startup
- Cursor-based pagination scales to millions of trades efficiently
- **Position-Based Architecture**: Complete trade aggregation system showing positions instead of individual executions
- **Quantity-Based Position Logic**: Positions tracked purely on contract quantity changes (0 → +/- → 0) without time-based grouping
- **Pure FIFO Position Flow**: Accurate position lifecycle from first non-zero quantity to return to zero quantity
- **Multi-Account Processing**: Proper separation and FIFO tracking for NinjaTrader trade copying
- **Execution Pairing**: Uses Entry/Exit markers (not Buy/Sell) for accurate position matching
- **Instrument Multipliers**: Web-based management with real-time updates to trade processing
- **Unique Trade IDs**: Traceable execution chains prevent duplicate database entries
- **Enhanced Error Handling**: Comprehensive logging and timestamp conversion for SQLite compatibility
- **Position Debug Interface**: Troubleshooting tools for examining trade grouping and position building logic
- **Gap Detection**: Enhanced algorithm prevents equal timestamp issues in OHLC data
- **Test Isolation**: Comprehensive mocking ensures tests don't depend on external APIs
- **Docker Ready**: Cross-platform deployment with optimized build configuration
- **CI/CD Pipeline**: GitHub Actions integration with robust error handling and security scanning
- **Redis Caching**: 2-week OHLC data retention with intelligent cleanup and cache warming
- **Background Services**: Automated gap-filling every 15 minutes with extended 4-hour cycles
- **Chart-Table Synchronization**: Bidirectional highlighting between execution tables and TradingView charts
- **Position Analysis**: Comprehensive FIFO tracking with execution flow visualization and lifecycle status
- **OHLC Chart Integration**: TradingView Lightweight Charts embedded in position detail pages for market context
- **Universal Dark Theme**: Professional dark color scheme enforced across all pages via base.html template
- **Compact UI Design**: Space-efficient filter controls and optimized dashboard layouts
- **CSV Re-import System**: Ability to scan data directory and re-import trades from archived CSV files