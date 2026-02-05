# Spec Summary (Lite)

Fix candle chart display issues on position detail pages where charts fail to load due to missing specific contract data. Implement automatic fallback to continuous contract data, fix invalid initial timeframe selection ("0"), and resolve timeframe switching being blocked during loading states.

Additionally, implement a hybrid data freshness strategy: position-triggered fetching (auto-fetch OHLC when positions are imported) plus Celery background workers in Docker for scheduled gap-filling during market hours. This ensures charts always have up-to-date data for traded positions without excessive API calls.
