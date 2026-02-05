# Spec Requirements Document

> Spec: Position Detail Page Fixes
> Created: 2026-01-17

## Overview

Fix the position detail page to display individual execution P&L results (entry/exit pairs), resolve candle data loading issues, and add execution arrow markers on the price chart for clear trade visualization.

## User Stories

### Individual Execution Results Display

As a trader, I want to see the P&L for each entry/exit pair in my position, so that I can analyze which specific trades within a scaled position were profitable or not.

When I view a position with multiple executions (e.g., scaling in/out), I currently see only position-level totals. I need to see each matched entry+exit as a separate result row showing:
- Entry time and price
- Exit time and price
- Duration of that specific trade
- Points P&L for that pair
- Dollar P&L for that pair

### Candle Chart Data Display

As a trader, I want to see OHLC candlestick data on the position detail chart, so that I can analyze my trade entries/exits in the context of market price action.

Currently, candles are not appearing on the chart. The cache-only chart service requires pre-populated data, but the data pipeline appears to have issues loading data for the requested date ranges. I need the chart to show candles for the period covering my position's lifecycle.

### Execution Markers on Chart

As a trader, I want to see visual markers (arrows) on the price chart showing where I entered and exited the position, so that I can quickly visualize my trade timing relative to price action.

Entry markers should be green arrows, exit markers should be red arrows, positioned at the exact price and time of each execution.

## Spec Scope

1. **Execution Pair Display** - Modify the execution breakdown table to show individual entry/exit pairs with per-pair P&L calculations using FIFO matching
2. **Candle Data Pipeline Fix** - Diagnose and fix why OHLC candle data is not loading on the position detail chart
3. **Execution Arrow Markers** - Add green entry and red exit arrow markers on the price chart at execution timestamps
4. **Chart Date Range Handling** - Ensure chart requests the correct date range covering the position lifecycle with appropriate padding

## Out of Scope

- On-demand OHLC data fetching (keeping cache-only approach)
- Database schema changes (using existing execution data)
- Changes to the positions list/dashboard page
- Modifications to the NinjaTrader import pipeline
- Adding new timeframe options to the chart

## Expected Deliverable

1. Position detail page shows individual execution pair results with per-pair P&L in the execution breakdown table
2. OHLC candlestick data loads correctly on the position detail chart for the position's date range
3. Entry (green) and exit (red) arrow markers appear on the chart at correct timestamps and prices
