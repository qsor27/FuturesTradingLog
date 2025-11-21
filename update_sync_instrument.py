#!/usr/bin/env python3
"""
Script to update the _sync_instrument method with backfill logic
"""

# Read the file
with open('/app/services/data_service.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Define the new method
new_method = '''    def _sync_instrument(self, instrument: str, timeframes: List[str]) -> Dict[str, any]:
        """Sync all timeframes for a single instrument with automatic 365-day backfill

        Detects zero-record instruments and triggers automatic backfill for up to 365 days
        of historical data (respecting Yahoo Finance API limits per timeframe).

        Args:
            instrument: Yahoo Finance symbol (e.g., 'NQ=F')
            timeframes: List of timeframes to sync

        Returns:
            Dictionary with sync statistics including backfill metrics
        """
        stats = {
            'instrument': instrument,
            'timeframes_synced': 0,
            'timeframes_failed': 0,
            'candles_added': 0,
            'api_calls': 0,
            'errors': [],
            'backfilled_timeframes': []
        }

        self.logger.info(f"Syncing {instrument} for {len(timeframes)} timeframes...")
        base_instrument = self._get_base_instrument(instrument)

        for timeframe in timeframes:
            try:
                # Check if zero records exist for this instrument/timeframe (triggers backfill)
                with FuturesDB() as db:
                    record_count = db.get_ohlc_count(base_instrument, timeframe)

                is_backfill = record_count == 0

                if is_backfill:
                    # BACKFILL MODE: Zero records detected - fetch 365 days (respecting API limits)
                    days_limit = self.HISTORICAL_LIMITS.get(timeframe, 365)
                    actual_backfill_days = min(365, days_limit)
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=actual_backfill_days)

                    self.logger.info(
                        f"BACKFILL: Zero records detected for {base_instrument} {timeframe} - "
                        f"fetching {actual_backfill_days} days (API limit: {days_limit}d)"
                    )
                    self.logger.info(
                        f"BACKFILL: Date range {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
                    )

                    stats['backfilled_timeframes'].append(timeframe)
                else:
                    # NORMAL SYNC MODE: Records exist - use standard fetch window
                    start_date, end_date = self._get_fetch_window(timeframe)
                    self.logger.debug(f"  {timeframe}: Normal sync ({record_count} existing records)")

                # Fetch OHLC data (same flow for both backfill and normal sync)
                data = self.fetch_ohlc_data(instrument, timeframe, start_date, end_date)
                stats['api_calls'] += 1

                if data:
                    # Insert into database using batch optimization
                    inserted_count = 0
                    with FuturesDB() as db:
                        for record in data:
                            try:
                                db.insert_ohlc_data(
                                    record['instrument'], record['timeframe'], record['timestamp'],
                                    record['open_price'], record['high_price'], record['low_price'],
                                    record['close_price'], record['volume']
                                )
                                inserted_count += 1
                            except Exception as e:
                                # Skip duplicates silently
                                pass

                        # Update cache if cache service available
                        if self.cache_service and data:
                            start_ts = int(start_date.timestamp())
                            end_ts = int(end_date.timestamp())
                            self.cache_service.cache_ohlc_data(
                                base_instrument, timeframe, start_ts, end_ts,
                                data, ttl_days=config.cache_ttl_days
                            )

                    stats['candles_added'] += inserted_count
                    stats['timeframes_synced'] += 1

                    if is_backfill:
                        self.logger.info(
                            f"BACKFILL COMPLETE: {inserted_count} candles added for {base_instrument} {timeframe}"
                        )
                    else:
                        self.logger.debug(f"  {timeframe}: {inserted_count} candles added")
                else:
                    log_msg = f"  {timeframe}: No data returned"
                    if is_backfill:
                        log_msg = f"BACKFILL: No data available for {base_instrument} {timeframe}"
                    self.logger.warning(log_msg)
                    stats['timeframes_failed'] += 1

                # Rate limiting: 100ms delay between API calls (respects existing rate limiter)
                time.sleep(0.1)

            except Exception as e:
                error_msg = f"{timeframe}: {str(e)}"
                stats['errors'].append(error_msg)
                stats['timeframes_failed'] += 1
                self.logger.error(f"  Failed to sync {instrument} {timeframe}: {e}")

        return stats

'''

# Find and replace the method
start_line = None
end_line = None

for i, line in enumerate(lines):
    if '    def _sync_instrument(self, instrument: str, timeframes: List[str])' in line:
        start_line = i
    elif start_line is not None and line.strip().startswith('def ') and i > start_line + 1:
        end_line = i
        break

if start_line is None:
    print("ERROR: Could not find _sync_instrument method")
    exit(1)

if end_line is None:
    end_line = len(lines)

print(f"Found _sync_instrument at line {start_line + 1}")
print(f"Replacing lines {start_line + 1} to {end_line} ({end_line - start_line} lines)")

# Build new content
new_lines = lines[:start_line] + [new_method] + lines[end_line:]

# Write back
with open('/app/services/data_service.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Successfully updated data_service.py")
print(f"Old method: {end_line - start_line} lines")
print(f"New method: {len(new_method.split(chr(10)))} lines")
