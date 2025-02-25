import socket
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import random
import time

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class NinjaTraderAPI:
    def __init__(self, host: str = "localhost", port: int = 36973):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.timeout = 5.0  # Increased timeout
        self.ati_enabled = False
        self._initialize_connection()
        
    def _initialize_connection(self) -> bool:
        try:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                    
            logger.debug(f"Attempting to connect to {self.host}:{self.port}")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            try:
                self.socket.connect((self.host, self.port))
            except ConnectionRefusedError:
                logger.error("Connection refused - is NinjaTrader running?")
                return False
            except Exception as e:
                logger.error(f"Connection error: {str(e)}")
                return False
            
            # Test commands to verify connection
            commands = [
                "REQUEST;CONNECTION",
                "REQUEST;ATI",
            ]
            
            for cmd in commands:
                response = self._send_command(cmd)
                logger.debug(f"Command '{cmd}' response: {response}")
                if response:
                    # Check if ATI is enabled
                    cleaned_response = response.replace('\x00', ' ').replace('|', ' ')
                    if any(x in cleaned_response for x in ["ATI True", "ATITrue", "True"]):
                        self.connected = True
                        self.ati_enabled = True
                        logger.info("Successfully connected to NinjaTrader ATI")
                        return True
            
            self.connected = False
            logger.error("ATI not enabled or connection failed")
            return False
            
        except Exception as e:
            self.connected = False
            logger.error(f"Failed to connect to NinjaTrader ATI: {str(e)}")
            return False
            
    def _send_command(self, command: str, extended_timeout: bool = False) -> Optional[str]:
        if not self.connected and not command.startswith(("REQUEST;CONNECTION", "REQUEST;ATI")):
            logger.warning("Not connected to NinjaTrader")
            return None
            
        try:
            # Ensure proper command termination
            if not command.endswith('\r\n'):
                command += '\r\n'
                
            logger.debug(f"Sending command: {command.strip()}")
            bytes_sent = self.socket.send(command.encode('utf-8'))
            logger.debug(f"Sent {bytes_sent} bytes")
            
            # Read response with buffer
            buffer = bytearray()
            start_time = time.time()
            max_time = 10.0 if extended_timeout else self.timeout  # Longer timeout for BARS
            
            while True:
                try:
                    chunk = self.socket.recv(4096)
                    if chunk:
                        buffer.extend(chunk)
                        # For BARS request, wait for more data
                        if extended_timeout:
                            time.sleep(0.2)  # Longer wait between chunks
                        # Check for response terminators
                        if (not extended_timeout and (b'\r\n' in chunk or b'|' in chunk or b'\x00' in chunk)):
                            break
                    elif buffer:  # No more data but we have something
                        break
                    elif time.time() - start_time > max_time:
                        break
                except socket.timeout:
                    if buffer:  # If we have data, consider it complete
                        break
                    if time.time() - start_time > max_time:
                        break
                    continue
                    
            if buffer:
                response = buffer.decode('utf-8', errors='ignore')
                logger.debug(f"Response received ({len(buffer)} bytes)")
                return response.strip()
            else:
                logger.warning("No response received")
                return None
                
        except Exception as e:
            logger.error(f"Error sending command to NinjaTrader: {str(e)}")
            self.connected = False
            return None
            
    def get_status(self) -> Dict[str, bool]:
        """Get NinjaTrader connection and ATI status."""
        status = {
            "connected": self.connected,
            "ati_enabled": self.ati_enabled
        }
        
        if self.connected:
            response = self._send_command("REQUEST;ATI")
            if response:
                cleaned_response = response.replace('\x00', ' ').replace('|', ' ')
                status["ati_enabled"] = any(x in cleaned_response for x in ["ATI True", "ATITrue", "True"])
            else:
                status["connected"] = False
                status["ati_enabled"] = False
                
        return status
        
    def get_bars(
        self,
        instrument: str,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        timeframe: str = "1 Minute"
    ) -> List[Dict]:
        if not self.connected:
            logger.warning("Not connected to NinjaTrader, attempting to reconnect...")
            self._initialize_connection()
            
        if not self.connected:
            logger.warning("Still not connected to NinjaTrader, using sample data")
            return self._generate_sample_data(start_date, end_date or datetime.now())
            
        try:
            # Format dates - ensure we're using NT8's expected format
            start_str = start_date.strftime("%Y%m%d%H%M%S")
            end_str = (end_date or datetime.now()).strftime("%Y%m%d%H%M%S")
            
            # Always use 1 for 1-minute bars
            command = f"REQUEST;GetBars;{instrument};1;LAST;300"
            logger.info(f"Requesting 1-minute bars: {command}")
            
            # Use extended timeout for BARS request
            response = self._send_command(command, extended_timeout=True)
            
            if response:
                logger.debug(f"Got bars response: {response[:200]}...")
                bars = []
                
                # Split response into lines and process each bar
                for line in response.split('\r\n'):
                    if not line.strip() or line.startswith('ERROR'):
                        continue
                        
                    try:
                        parts = line.split(';')
                        if len(parts) >= 5:  # Need at least OHLC
                            timestamp_str = parts[0]
                            timestamp = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                            
                            bar = {
                                'time': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                                'open': float(parts[1]),
                                'high': float(parts[2]),
                                'low': float(parts[3]),
                                'close': float(parts[4])
                            }
                            bars.append(bar)
                    except ValueError as ve:
                        logger.error(f"Date parsing error: {str(ve)} for line: {line}")
                        continue
                    except Exception as e:
                        logger.error(f"Error parsing bar: {str(e)} for line: {line}")
                        continue
                
                if bars:
                    logger.info(f"Retrieved {len(bars)} 1-minute bars from NinjaTrader")
                    logger.info(f"First bar: {bars[0]}")
                    logger.info(f"Last bar: {bars[-1]}")
                    return bars
                else:
                    logger.info("No valid bars in response, falling back to sample data")
            else:
                logger.info("No real-time data available, falling back to sample data")
            
            return self._generate_sample_data(start_date, end_date or datetime.now())
                
        except Exception as e:
            logger.error(f"Error getting market data: {str(e)}")
            return self._generate_sample_data(start_date, end_date or datetime.now())
            
    def _generate_sample_data(
        self,
        start_date: datetime,
        end_date: datetime,
        num_bars: int = 100
    ) -> List[Dict]:
        bars = []
        interval = (end_date - start_date) / (num_bars - 1)
        
        last_close = 21800.0  # Starting price for NQ
        for i in range(num_bars):
            timestamp = start_date + interval * i
            
            price_change = random.uniform(-20.0, 20.0)
            close = last_close + price_change
            high = close + random.uniform(0, 10.0)
            low = close - random.uniform(0, 10.0)
            open_price = last_close + random.uniform(-10.0, 10.0)
            
            bars.append({
                'time': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close, 2)
            })
            
            last_close = close
            
        return bars
        
    def close(self):
        if self.socket:
            try:
                self._send_command("DISCONNECT")
                self.socket.close()
            except Exception as e:
                logger.error(f"Error closing socket: {str(e)}")
        self.connected = False
        self.ati_enabled = False