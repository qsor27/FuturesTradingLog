# Spec Requirements Document

> Spec: Unified CSV Import System
> Created: 2025-09-11

## Overview

Consolidate the fragmented CSV import system into a single automated process that monitors NinjaTrader indicator CSV files in /Data and automatically imports them, while providing one manual re-processing option and removing all other import methods.

## User Stories

### Automated CSV Import Processing

As a trader, I want the system to automatically detect and import new CSV files from my NinjaTrader indicator, so that my trading data is always up-to-date without manual intervention.

The system continuously monitors the /Data directory for new CSV files from the NinjaTrader indicator, automatically processes them through the unified import pipeline, generates positions, and updates all caches and charts in real-time.

### Manual Re-processing Interface

As a trader, I want a single interface to manually re-process CSV files when needed, so that I can fix data issues or re-import historical data without dealing with multiple import methods.

A streamlined interface allows selection of specific CSV files or date ranges for re-processing, with clear feedback on processing status and any errors encountered.

### Clean Import Architecture

As a developer, I want all legacy import endpoints removed and replaced with a unified system, so that maintenance is simplified and data processing is consistent.

All fragmented import methods are consolidated into one service with consistent validation, error handling, and processing logic.

## Spec Scope

1. **Unified CSV Import Service** - Single service handling all NinjaTrader CSV file processing with automatic detection and import
2. **Automatic File Monitoring** - Enhanced file watcher that monitors /Data directory for new CSV files and triggers immediate processing
3. **Manual Re-processing Interface** - Single endpoint/UI for manual file re-processing with file selection capabilities
4. **Legacy Import Cleanup** - Remove all existing import endpoints (/upload, /batch-import-csv, /reimport-csv, /process-nt-executions, /csv-manager)
5. **Unified Processing Pipeline** - Consistent data validation, position generation, and cache invalidation across all import operations

## Out of Scope

- Changes to the underlying database schema or position calculation logic
- Modifications to the TradingView chart integration
- Changes to the NinjaTrader indicator output format
- Real-time data streaming (focus on file-based import only)

## Expected Deliverable

1. Single automatic CSV import system that processes NinjaTrader files from /Data without user intervention
2. One manual re-processing interface replacing all current import methods
3. Complete removal of legacy import endpoints with proper error handling for deprecated routes