import os
import pandas as pd
from datetime import datetime, timedelta
import logging
# Import both API implementations for flexibility
from ninja_trader_api import NinjaTraderAPI
from ninjatrader_dll_api import NinjaTraderDLL

logger = logging.getLogger(__name__)

class NinjaMarketData:
    def __init__(self, nt_data_path=None, use_dll=True):
        """
        Initialize NinjaTrader market data reader
        
        Args:
            nt_data_path: Path to NinjaTrader data directory
            use_dll: If True, use the DLL API; if False, use the socket API
        """
        logger.info("Initializing NinjaTrader market data reader")
        try:
            # Choose API implementation based on use_dll flag
            if use_dll:
                logger.info("Using NinjaTrader.Client.dll API")
                try:
                    # Use the correct DLL path
                    dll_path = r"C:\Program Files\NinjaTrader 8\bin\NinjaTrader.Client.dll"
                    self.api = NinjaTraderDLL(dll_path)
                    self.using_dll = True
                    
                    # Set a flag to indicate we're using the DLL API even if it's not connected yet
                    logger.info(f"Initialized NinjaTrader DLL API, connection status will be checked later")
                    
                    # We'll keep using the DLL API even if initial connection fails
                    # This allows the app to work even when NinjaTrader isn't running initially
                    # It will try to reconnect when needed
                except Exception as e:
                    logger.error(f"Error initializing DLL API: {e}")
                    # If there's a critical initialization error, we should fall back to socket API
                    logger.warning("Falling back to socket API due to DLL initialization error")
                    self.api = NinjaTraderAPI()
                    self.using_dll = False
                    
                    # Check if socket API connected
                    try:
                        status = self.api.get_status()
                        if status["connected"]:
                            logger.info("Successfully connected to NinjaTrader API using socket API")
                        else:
                            logger.warning("Not connected to NinjaTrader API using socket API")
                    except Exception as socket_error:
                        logger.error(f"Error checking socket API connection: {socket_error}")
            else:
                logger.info("Using NinjaTrader socket API")
                self.api = NinjaTraderAPI()
                self.using_dll = False
                
                # Check if we connected successfully
                status = self.api.get_status()
                if status["connected"]:
                    logger.info(f"Successfully connected to NinjaTrader API (DLL: {self.using_dll})")
                else:
                    logger.warning(f"Not connected to NinjaTrader API (DLL: {self.using_dll})")
            
        except Exception as e:
            logger.error(f"Failed to initialize NinjaTrader API: {e}")
            raise

    def get_instrument_data(self, symbol, date, timeframe='1 Minute'):
        """
        Read market data for a specific instrument and date using ATI
        Args:
            symbol (str): Instrument symbol (e.g., 'NQ 03-24')
            date (datetime): Date to retrieve
            timeframe (str): Bar timeframe
        """
        logger.info(f"Getting data for {symbol} on {date} ({timeframe})")
        
        try:
            # Get one full day of data
            start_date = datetime.combine(date.date(), datetime.min.time())
            end_date = start_date + timedelta(days=1)
            
            # Get data through ATI
            bars = self.api.get_bars(
                instrument=symbol,
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe
            )
            
            if not bars:
                logger.warning(f"No data found for {symbol} on {date}")
                return None
                
            # Convert to DataFrame
            df = pd.DataFrame(bars)
            df.rename(columns={
                'timestamp': 'DateTime',
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }, inplace=True)
            
            logger.info(f"Retrieved {len(df)} bars")
            return df
            
        except Exception as e:
            logger.error(f"Error getting data: {str(e)}")
            return None
            
    def get_data_around_time(self, symbol, timestamp, minutes_before=60, minutes_after=60):
        """
        Get market data surrounding a specific timestamp using ATI
        Args:
            symbol (str): Instrument symbol
            timestamp (datetime): Center timestamp
            minutes_before (int): Minutes of data before timestamp
            minutes_after (int): Minutes of data after timestamp
        """
        logger.info(f"Getting data for {symbol} around {timestamp} ({minutes_before} mins before, {minutes_after} mins after)")
        
        try:
            start_time = timestamp - timedelta(minutes=minutes_before)
            end_time = timestamp + timedelta(minutes=minutes_after)
            
            # Get data directly for the time range through ATI
            bars = self.api.get_bars(
                instrument=symbol,
                start_date=start_time,
                end_date=end_time,
                timeframe='1 Minute'  # Default to 1-minute bars for detailed view
            )
            
            if not bars:
                logger.warning("No data found for the specified time range")
                return None
                
            # Convert to DataFrame
            df = pd.DataFrame(bars)
            df.rename(columns={
                'timestamp': 'DateTime',
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }, inplace=True)
            
            logger.info(f"Retrieved {len(df)} bars")
            return df
            
        except Exception as e:
            logger.error(f"Error getting data: {str(e)}")
            return None
    
    def format_for_chart(self, df):
        """Convert DataFrame to Lightweight Charts format"""
        if df is None:
            logger.warning("No data to format for chart")
            return []
            
        chart_data = []
        for _, row in df.iterrows():
            try:
                # Check which columns are available (handle both column naming conventions)
                time_field = 'DateTime' if 'DateTime' in row else 'time'
                open_field = 'Open' if 'Open' in row else 'open'
                high_field = 'High' if 'High' in row else 'high'
                low_field = 'Low' if 'Low' in row else 'low'
                close_field = 'Close' if 'Close' in row else 'close'
                
                # Create chart data point
                data_point = {
                    'time': int(pd.Timestamp(row[time_field]).timestamp()),
                    'open': float(row[open_field]),
                    'high': float(row[high_field]),
                    'low': float(row[low_field]),
                    'close': float(row[close_field])
                }
                
                # Add volume if available
                if 'Volume' in row:
                    data_point['volume'] = int(row['Volume'])
                elif 'volume' in row:
                    data_point['volume'] = int(row['volume'])
                    
                chart_data.append(data_point)
            except Exception as e:
                logger.error(f"Error formatting row {row}: {str(e)}")
                continue
                
        logger.info(f"Formatted {len(chart_data)} points for chart")
        return chart_data