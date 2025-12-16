# Futures Trading Log

Flask-based futures trading analytics platform with position-based tracking, interactive TradingView charts, and high-performance database optimization.

## Key Features
- **Position-Based Architecture**: Quantity flow analysis (0 → +/- → 0 lifecycle)
- **TradingView Charts**: Interactive candlestick charts with trade execution overlays
- **High Performance**: 15-50ms chart loads for 10M+ records with aggressive indexing
- **NinjaTrader Integration**: Automated CSV export and processing
- **Redis Caching**: 14-day data retention for enhanced performance
- **Discord Notifications**: Real-time alerts for validation issues and trade activity
- **Docker Deployment**: Container-based production deployment

---

## Deployment Options

### Option 1: Docker (Recommended)

#### Quick Start
```bash
# 1. Create data directory
mkdir ~/TradingData

# 2. Run container with Redis
docker run -p 5000:5000 \
  -v ~/TradingData:/app/data \
  -e FLASK_SECRET_KEY=your-secure-random-key \
  -e AUTO_IMPORT_ENABLED=true \
  --name futures-trading-log \
  ghcr.io/qsor27/futurestradinglog:main

# 3. Access application
http://localhost:5000
```

#### Docker Compose (with Redis)
```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    image: ghcr.io/qsor27/futurestradinglog:latest
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
    environment:
      - FLASK_ENV=production
      - FLASK_SECRET_KEY=your-secure-random-key
      - REDIS_URL=redis://redis:6379/0
      - AUTO_IMPORT_ENABLED=true
      - DISCORD_WEBHOOK_URL=  # Optional: your Discord webhook
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

Run with: `docker-compose up -d`

### Option 2: Windows Native Install

#### Prerequisites
- Python 3.11+
- Redis for Windows (or WSL2 with Redis)

#### Installation
```powershell
# Clone repository
git clone https://github.com/qsor27/FuturesTradingLog.git
cd FuturesTradingLog

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
$env:FLASK_ENV = "production"
$env:FLASK_SECRET_KEY = "your-secure-random-key"
$env:DATA_DIR = "C:\ProgramData\FuturesTradingLog"
$env:REDIS_URL = "redis://localhost:6379/0"

# Run application
python app.py
```

---

## Configuration Reference

### Required Environment Variables

| Variable | Description | Docker Default | Windows Default |
|----------|-------------|----------------|-----------------|
| `FLASK_SECRET_KEY` | **REQUIRED** for production. Generate a secure random key. | - | - |
| `FLASK_ENV` | Environment mode: `development`, `production` | `production` | `development` |
| `DATA_DIR` | Where all data is stored (database, logs, config) | `/app/data` | `{home}/FuturesTradingLog/data` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` | `redis://localhost:6379/0` |

### Optional Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_WEBHOOK_URL` | Discord webhook for notifications | *(disabled)* |
| `AUTO_IMPORT_ENABLED` | Enable automatic NinjaTrader CSV import | `true` |
| `AUTO_IMPORT_INTERVAL` | Import check interval in seconds | `300` (5 min) |
| `CACHE_ENABLED` | Enable Redis caching | `true` |
| `CACHE_TTL_DAYS` | Cache retention in days | `14` |

### Data Directory Structure

The `DATA_DIR` path will contain:
```
DATA_DIR/
├── db/
│   └── futures_trades_clean.db    # SQLite database
├── config/
│   └── instrument_multipliers.json # Instrument settings
├── logs/
│   ├── app.log                    # Application logs
│   └── error.log                  # Error logs
└── archive/                       # Archived data
```

---

## Instrument Multipliers

Configure futures contract multipliers in **Settings** or edit `{DATA_DIR}/config/instrument_multipliers.json`:

```json
{
  "MNQ": 2,      // Micro NASDAQ-100: $2 per point
  "NQ": 20,      // E-mini NASDAQ-100: $20 per point
  "MES": 5,      // Micro S&P 500: $5 per point
  "ES": 50,      // E-mini S&P 500: $50 per point
  "RTY": 50,     // E-mini Russell 2000: $50 per point
  "M2K": 5,      // Micro Russell 2000: $5 per point
  "YM": 5,       // E-mini Dow: $5 per point
  "MYM": 0.5,    // Micro Dow: $0.50 per point
  "CL": 1000,    // Crude Oil: $1000 per point
  "GC": 100      // Gold: $100 per point
}
```

**Note:** Contract names with expiration dates (e.g., `"MNQ SEP25"`, `"MES 12-25"`) are automatically matched to their base symbol multiplier.

---

## NinjaTrader Integration

### Manual Import
1. Export execution report from NinjaTrader as CSV
2. Upload via web interface at http://localhost:5000

### Automated Import (Recommended)
1. Install `ExecutionExporter.cs` NinjaScript indicator in NinjaTrader
2. Configure export path:
   - **Docker**: Export to your mounted data volume
   - **Windows**: Export to `{DATA_DIR}` folder
3. Automatic import runs every 5 minutes

See [`NINJATRADER_EXPORT_SETUP.md`](NINJATRADER_EXPORT_SETUP.md) for detailed setup.

---

## Discord Notifications

### Setup
1. Create a Discord webhook in your server (Server Settings → Integrations → Webhooks)
2. Set the environment variable:
   ```bash
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
   ```
3. Test with: `python scripts/test_discord_webhook.py`

### Notification Types
- **Validation Alerts**: Position integrity issues detected
- **Repair Summaries**: Automated repair operation results
- **Critical Alerts**: High-priority issues requiring attention

See [`docs/DISCORD_NOTIFICATIONS_SETUP.md`](docs/DISCORD_NOTIFICATIONS_SETUP.md) for full documentation.

---

## API Endpoints

```bash
# Chart data
curl "http://localhost:5000/api/chart-data/MNQ?timeframe=1h&days=7"

# Interactive charts
http://localhost:5000/chart/MNQ
http://localhost:5000/chart/ES

# Health check
curl http://localhost:5000/health

# Rebuild positions (after config changes)
curl -X POST http://localhost:5000/positions/rebuild
```

---

## Development Setup

```bash
# Clone and setup
git clone https://github.com/qsor27/FuturesTradingLog.git
cd FuturesTradingLog
python -m venv venv && source venv/bin/activate  # Linux/Mac
# or: .\venv\Scripts\Activate  # Windows
pip install -r requirements.txt

# Run application
python app.py

# Run tests
pytest tests/ -v
```

---

## Troubleshooting

### P&L Not Calculating Correctly
- Ensure your instrument has a multiplier configured in Settings
- After changing multipliers, rebuild positions: `POST /positions/rebuild`

### Redis Connection Failed
- Docker: Ensure redis service is running (`docker-compose ps`)
- Windows: Start Redis service or set `CACHE_ENABLED=false`

### NinjaTrader Import Not Working
- Check export path matches `DATA_DIR`
- Verify CSV file format matches expected columns
- Check logs at `{DATA_DIR}/logs/app.log`

---

## Architecture
- **Flask**: Web framework with blueprint-based routing
- **SQLite**: Primary database with WAL mode and aggressive indexing
- **Redis**: Caching layer for OHLC data and performance
- **Celery**: Background task processing (optional)
- **TradingView Lightweight Charts**: Professional chart visualization
- **Docker**: Production container deployment

---

## Documentation
- [`CLAUDE.md`](docs/CLAUDE.md): Development guide and critical algorithms
- [`docs/ai-context/project-structure.md`](docs/ai-context/project-structure.md): Complete project architecture
- [`NINJATRADER_EXPORT_SETUP.md`](NINJATRADER_EXPORT_SETUP.md): NinjaTrader indicator setup
- [`docs/DISCORD_NOTIFICATIONS_SETUP.md`](docs/DISCORD_NOTIFICATIONS_SETUP.md): Discord integration guide
- [`ENHANCED_POSITION_GUIDE.md`](ENHANCED_POSITION_GUIDE.md): Position features and chart integration

---

## Performance
- **Chart Loading**: 15-45ms (100x faster than traditional implementations)
- **Database Queries**: 8 aggressive indexes for millisecond performance
- **Scalability**: Handles 10M+ records efficiently
- **Cross-Platform**: Docker deployment on any OS

---

**Warning:** The position building algorithm in `position_service.py` is the most critical component. Any modifications require extreme care and testing.

## License
[Specify license]

## Contact
[Contact information]
