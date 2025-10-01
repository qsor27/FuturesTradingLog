
# Data Collection Updates

This document outlines proposed updates to the data collection process, specifically regarding the downloading of OHLC data from Yahoo Finance.

## 1. Instrument Selection

The `update_all_active_instruments` method currently fetches data for all instruments with recent trade activity. This should be modified to fetch data for all instruments that the user has selected in their settings. This will likely involve adding a method to the `SettingsRepository` to get the user's selected instruments.

## 2. Chart Data Loading

The `OHLCDataService.get_chart_data` method should be updated to ensure that it correctly loads chart data for the specific instrument contract that the trade was made on. This might involve modifying the `get_ohlc_data` method in the `OHLCRepository` to handle instrument contracts correctly.

## 3. Error Handling

The `fetch_ohlc_data` method should be improved to handle cases where the Yahoo Finance API returns an error. For example, if the API returns a "404 Not Found" error, the method should not try to parse the response.

## 4. Data Consistency

The `_migrate_instrument_names` method in `OHLCDataService` is a good idea, but it's not implemented. This should be implemented to ensure that all instrument names are consistent in the database.

## 5. Configuration

The rate limit delay and retry delays are hardcoded in the `OHLCDataService`. These should be moved to the configuration file so that they can be easily changed.

## 6. Logging

The logging in the `OHLCDataService` is good, but it could be improved by adding more context to the log messages. For example, when a rate limit error occurs, the log message should include the instrument and timeframe that was being fetched.
