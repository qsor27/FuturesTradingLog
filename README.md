# Futures Trading Log

Flask-based futures trading analytics platform with position-based tracking, interactive TradingView charts, and high-performance database optimization.

## Key Features
- **Position-Based Architecture**: Quantity flow analysis (0 → +/- → 0 lifecycle)
- **TradingView Charts**: Interactive candlestick charts with trade execution overlays
- **High Performance**: 15-50ms chart loads for 10M+ records with aggressive indexing
- **NinjaTrader Integration**: Automated CSV export and processing
- **Redis Caching**: 14-day data retention for enhanced performance
- **Docker Deployment**: Container-based production deployment

## Quick Start (Docker - Recommended)

```bash
# 1. Create data directory
mkdir ~/TradingData

# 2. Run container
docker run -p 5000:5000 \
  -v ~/TradingData:/app/data \
  -e AUTO_IMPORT_ENABLED=true \
  --name futures-trading-log \
  ghcr.io/qsor27/futurestradinglog:main

# 3. Access application
http://localhost:5000
```

## Development Setup

```bash
# Clone and setup
git clone https://github.com/qsor27/FuturesTradingLog.git
cd FuturesTradingLog
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run application
python app.py

# Run tests
pytest tests/ -v
```

## NinjaTrader Integration

### Manual Process
1. Export execution report from NinjaTrader as CSV
2. Upload via web interface at http://localhost:5000

### Automated Process (Recommended)
1. Install `ExecutionExporter.cs` NinjaScript indicator
2. Configure export path to match Docker volume
3. Automatic real-time import

See `NINJASCRIPT_SETUP.md` for detailed setup instructions.

## Performance
- **Chart Loading**: 15-45ms (100x faster than traditional implementations)
- **Database Queries**: 8 aggressive indexes for millisecond performance
- **Scalability**: Handles 10M+ records efficiently
- **Cross-Platform**: Docker deployment on any OS

## Documentation
- **`CLAUDE.md`**: Development guide and critical position building algorithm
- **`docs/ai-context/project-structure.md`**: Complete project structure and architecture
- **`NINJASCRIPT_SETUP.md`**: NinjaScript indicator setup
- **`ENHANCED_POSITION_GUIDE.md`**: Position features and chart integration

## API Endpoints
```bash
# Chart data
curl "http://localhost:5000/api/chart-data/MNQ?timeframe=1h&days=7"

# Interactive charts
http://localhost:5000/chart/MNQ
http://localhost:5000/chart/ES
```

## Architecture
- **Flask**: Web framework with blueprint-based routing
- **SQLite**: Primary database with WAL mode and aggressive indexing
- **Redis**: Optional caching layer for performance enhancement
- **TradingView Lightweight Charts**: Professional chart visualization
- **Docker**: Production container deployment

## Testing
```bash
# Run full test suite (120+ tests)
python run_tests.py

# Performance validation
python run_tests.py --performance
```

**⚠️ Critical Component**: The position building algorithm in `position_service.py` is the most important part of this application. Any modifications require extreme care and testing.

## License
[Specify license]

## Contact
[Contact information]