# CLAUDE.md

## 🚨 **CRITICAL: POSITION BUILDING ALGORITHM**

**The `position_service.py` contains the MOST IMPORTANT component of this application. Modifying it affects ALL historical data.**

### **Core Algorithm - Never Modify Without Extreme Care**

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


## Deployment

### Production (Automatic)
1. Push to GitHub main → GitHub Actions builds container → Watchtower auto-updates
2. Changes live in 5-10 minutes

### Development (Fast)
```bash
./dev-update.sh          # Deploy immediately (30-60 seconds)
./dev-update.sh status   # Check status
./dev-update.sh logs     # View logs
```

### Local Development
```bash
# Docker Compose (recommended)
docker-compose up --build

# Direct Python (testing)
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && python app.py
```

### Common Commands
```bash
# Container management
docker ps                                    # Check containers
docker logs futurestradinglog                # View logs
docker restart futurestradinglog             # Restart container

# Testing
pytest tests/ -v                             # Run tests
curl http://localhost:5000/health            # Health check
```

## Architecture

### Core Components
- **`position_service.py`**: 🚨 CRITICAL - Position building algorithm (now uses enhanced validation)
- **`enhanced_position_service.py`**: Enhanced position service with comprehensive overlap prevention  
- **`position_overlap_prevention.py`**: Validation engine with automated error detection and recovery
- **`TradingLog_db.py`**: SQLite database with aggressive indexing and chart settings persistence
- **`data_service.py`**: yfinance integration with Redis caching and improved error handling
- **`app.py`**: Flask application with blueprint registration and validation endpoints
- **`routes/positions.py`**: Position dashboard with real-time validation status and detailed reporting
- **`routes/chart_data.py`**: High-performance OHLC data APIs with timeframe validation and adaptive resolution

### Database Schema
- **Trades**: Individual executions with P&L, linking via `link_group_id`
- **Positions**: Aggregated position data with lifecycle tracking
- **Position_Executions**: Maps positions to constituent trades
- **OHLC_Data**: Market data with 8 performance indexes (15-50ms queries)
- **Chart_Settings**: User preferences for timeframes, data ranges, and volume visibility
- **User_Profiles**: Named configuration profiles with settings snapshots and version history

### Frontend
- **Templates**: Jinja2 with position-based interface (`templates/positions/`) including validation status cards and modals
- **JavaScript**: Enhanced TradingView charts (`PriceChart.js`) with OHLC hover display, user settings API (`ChartSettingsAPI.js`), and validation monitoring
- **Static Assets**: Dark theme CSS, interactive components with real-time validation notifications

## Configuration

### Environment Variables
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

### Manual Process
1. Export execution report from NinjaTrader → Process with `ExecutionProcessing.py` → Import via web interface

### Automated Process (Recommended)
1. Install `ExecutionExporter.cs` NinjaScript indicator
2. Configure export path → Automatic real-time CSV export
3. See `NINJASCRIPT_SETUP.md` for setup details

## Performance

### Database Optimization
- **8 Aggressive Indexes**: 15-50ms chart loads for 10M+ records
- **SQLite WAL Mode**: Better concurrency with 1GB memory mapping
- **Cursor Pagination**: Scalable pagination for large datasets

### Testing
```bash
pytest tests/test_performance.py -v    # Performance validation
python run_tests.py --performance      # Quick performance check

# Validation system testing
curl http://localhost:5000/api/validation/health     # Validation system health
curl http://localhost:5000/api/validation/summary    # Position validation status
```


## Logging

### Log Files (`data/logs/`)
- **`error.log`**: Quick troubleshooting (errors only)
- **`app.log`**: Main application activity  
- **`database.log`**: Database operations and performance
- **`flask.log`**: Web server requests

### Quick Log Analysis
```bash
tail -f logs/error.log                    # Monitor errors
grep "performance\|slow" logs/database.log   # Performance issues
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
- **`docs/ai-context/project-structure.md`**: Complete project structure and technology stack
- **`NINJASCRIPT_SETUP.md`**: NinjaScript indicator installation and configuration
- **`ENHANCED_POSITION_GUIDE.md`**: Position features and chart synchronization guide
- **`requirements.txt`**: Python dependencies