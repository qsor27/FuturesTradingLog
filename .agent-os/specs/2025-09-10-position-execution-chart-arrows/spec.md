# Spec Requirements Document

> Spec: Position Execution Chart Arrows
> Created: 2025-09-10

## Overview

Enhance the positions page to display execution arrows on OHLC charts that visually indicate the exact time and price of each trade execution within a position. This feature will provide traders with precise visual context of their entry and exit points relative to market movement, improving trade analysis and decision-making capabilities.

## User Stories

### Position Analysis Enhancement

As a futures trader, I want to see visual arrows on my position charts showing exactly when and at what price my executions occurred, so that I can analyze my timing relative to market movement and improve my trading strategy.

When viewing a position detail page, the trader sees an OHLC chart with arrows pointing to the exact candle and price level where each execution occurred. Left-pointing arrows indicate entries (position opening), right-pointing arrows indicate exits (position closing), with colors indicating buy/sell direction. Hovering over arrows shows execution details including time, price, quantity, and P&L.

### Interactive Chart Analysis

As a trader analyzing my performance, I want to interact with execution markers on the chart to see detailed execution information and correlate it with the execution table, so that I can quickly identify and analyze specific trades.

Clicking on execution arrows highlights the corresponding row in the execution breakdown table below the chart. Hovering over arrows displays tooltips with complete execution details. The chart supports multiple timeframes (1m, 5m, 1h) with execution arrows adapting to the selected timeframe.

## Spec Scope

1. **Execution Arrow Display** - Add visual arrow markers to OHLC charts showing exact execution time and price points
2. **Interactive Tooltips** - Display comprehensive execution details on hover including time, price, quantity, side, and P&L
3. **Chart-Table Integration** - Link arrow clicks to corresponding execution table rows with highlighting
4. **Multi-Timeframe Support** - Support execution arrows on 1m, 5m, and 1h chart timeframes
5. **Visual Design System** - Implement consistent color coding and arrow direction logic (left=entry, right=exit, green=buy, red=sell)

## Out of Scope

- Real-time execution tracking for live positions
- Chart drawing tools or manual annotation features
- Historical execution data backfilling for positions created before this feature
- Mobile-specific chart interactions beyond responsive design
- Integration with external charting platforms

## Expected Deliverable

1. Position detail pages display OHLC charts with execution arrows at correct time/price coordinates
2. Interactive tooltips show complete execution details when hovering over arrows
3. Chart arrow clicks highlight corresponding rows in the execution breakdown table below