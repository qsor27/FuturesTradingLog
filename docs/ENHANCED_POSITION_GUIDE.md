# Enhanced Position Guide

## Position Features
- **Quantity-Based Tracking**: Position lifecycle follows 0 → +/- → 0 pattern
- **TradingView Charts**: Interactive charts with execution overlays
- **Chart-Table Sync**: Click rows to highlight chart markers
- **FIFO Analysis**: Detailed entry/exit execution breakdown
- **Real-time Status**: Open/Closed position tracking

## Access Position Details
- **Dashboard**: `/positions/` → Click "View Details"
- **Direct URL**: `/positions/<position_id>`
- **Legacy**: Trade list → Click Trade ID (redirects to position)

## Position Logic
- **Start**: Quantity changes from 0 to non-zero
- **Tracking**: Long (+), Short (-), Running quantity maintained
- **End**: Quantity returns to 0

## Chart Features
- **Multi-Timeframe**: 1m, 5m, 15m, 1h, 4h, 1d with smart fallback
- **Trade Markers**: Entry/exit points overlaid on price action
- **Market Context**: See price movement during position lifecycle
- **Interactive Controls**: Zoom, pan, timeframe switching

## Execution Table
- **FIFO Pairing**: Entry/exit executions paired chronologically
- **Running P&L**: Cumulative profit/loss tracking
- **Commission Tracking**: Total commissions per execution
- **Price Analysis**: Average entry/exit prices with quantity weighting

## Troubleshooting
- **Missing Charts**: Charts auto-populate with market data
- **Position Rebuild**: Use `/positions/rebuild` to recalculate positions
- **Debug Interface**: `/positions/debug` for position building analysis

## Performance
- **Chart Loading**: 15-50ms for interactive charts
- **Data Caching**: Redis caching for enhanced performance
- **Background Updates**: Automatic gap-filling for missing market data

**Note**: Position building algorithm in `position_service.py` is critical - any modifications require extensive testing.