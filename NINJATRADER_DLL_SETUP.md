# NinjaTrader DLL Integration Setup

This document explains how to set up the NinjaTrader DLL integration for live OHLC data retrieval.

## Overview

The application now supports two methods for connecting to NinjaTrader:

1. **Socket API** (original method): Uses NinjaTrader's ATI socket interface
2. **DLL API** (new method): Uses the NinjaTrader.Client.dll for direct integration

The DLL method provides better performance and reliability for real-time data.

## Requirements

- NinjaTrader 8 installed
- .NET Framework 4.8
- Python 3.7+ with the pythonnet (Python.NET) package

## Setup Instructions

1. **Verify NinjaTrader.Client.dll Location**

   The DLL should be located at:
   ```
   C:\Program Files\NinjaTrader 8\bin\NinjaTrader.Client.dll
   ```

   If your NinjaTrader installation is in a different location, update the path in `ninjatrader_dll_api.py`.

2. **Ensure Pythonnet is Installed**

   ```
   pip install pythonnet>=3.0.1
   ```

3. **Configure the Application**

   The application is configured to use the DLL API by default. You can switch between APIs:

   - In `app.py`: Change `use_dll=True` to `use_dll=False` to use the socket API
   - In `routes/ninja_trader.py`: Change `USE_DLL = True` to `USE_DLL = False` to use the socket API

4. **Running NinjaTrader**

   - Make sure NinjaTrader 8 is running before starting the application
   - Only one version of NinjaTrader can be open (close NinjaTrader 7 if it's running)
   - Ensure you're connected to a data feed in NinjaTrader

## Troubleshooting

If you experience issues with the DLL integration:

1. **Check NinjaTrader Connection**
   - Ensure NinjaTrader 8 is running
   - Verify you're connected to a data feed

2. **DLL Issues**
   - Ensure NinjaTrader.Client.dll is accessible
   - Try running the application with administrative privileges

3. **Fallback to Socket API**
   - If DLL integration fails, you can fall back to the socket API by changing `use_dll=True` to `use_dll=False` in app.py

4. **Logging**
   - Check the application logs for detailed error messages
   - The DLL API implementation includes detailed logging

## API Usage Notes

- The API does not include events - all methods must be called to send or receive data
- Historical data is not fully supported with the API - only real-time data is reliable
- Information about running NinjaScript Strategies is not supported with the API
- The API requires polling for data - there are no event callbacks
- When using the API only one version of NinjaTrader can be open and running
- An external project using the NinjaTrader.Client.dll should target .NET 4.8 for compatibility with NT8
- When NinjaTrader ATI is disabled, all API methods that do not relate to orders will continue to operate

## Important DLL Methods

- **MarketData(instrument, 0)**: Subscribe to market data for an instrument (0 = subscribe)
- **UnsubscribeMarketData(instrument)**: Unsubscribe from market data
- **Ask(instrument)**, **Bid(instrument)**, **Last(instrument)**: Get current prices
- **Open(instrument)**, **High(instrument)**, **Low(instrument)**: Get OHLC values for current bar
- **TearDown()**: Close the connection and clean up

## DLL API Documentation

The DLL API implementation in `ninjatrader_dll_api.py` provides these main functions:

- `get_status()`: Check connection status
- `get_bars()`: Get real-time OHLC bars
- `close()`: Close the connection and clean up resources

For more information on the NinjaTrader API, refer to the NinjaTrader documentation at:
https://support.ninjatrader.com/s/article/Developer-Guide-Using-the-API-DLL-with-an-external-application
