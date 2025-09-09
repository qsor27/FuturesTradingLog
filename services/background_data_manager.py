"""
Background Data Manager for Futures Trading Log
"""
import time
import logging
from typing import List, Dict
from config import BACKGROUND_DATA_CONFIG
from services.data_service import OHLCDataService
from services.redis_cache_service import get_cache_service

class CacheOnlyChartService:
    """Provides chart data exclusively from cache"""
    
    def __init__(self, cache_service):
        self.logger = logging.getLogger(__name__)
        self.cache_service = cache_service

    def get_chart_data(self, instrument: str, timeframe: str, start_ts: int, end_ts: int) -> List[Dict]:
        if not self.cache_service:
            return []
        return self.cache_service.get_cached_ohlc_data(instrument, timeframe, start_ts, end_ts)

class BackgroundDataManager:
    """Manages background data downloading and caching"""
    
    def __init__(self, ohlc_service: OHLCDataService):
        self.logger = logging.getLogger(__name__)
        self.ohlc_service = ohlc_service
        self.config = BACKGROUND_DATA_CONFIG
        self.is_running = False
        self.user_access_log = {}

    def run_update(self):
        """Run a full background update of all active instruments"""
        if not self.config.get('enabled', False):
            self.logger.info("Background data manager is disabled")
            return

        self.logger.info("Starting background data update")
        active_instruments = self.ohlc_service.update_all_active_instruments(
            timeframes=self.config.get('all_timeframes', [])
        )
        self.logger.info(f"Background data update completed for {len(active_instruments)} instruments")

    def start(self):
        """Start the background data manager loop in a separate thread"""
        if not self.config.get('enabled', False):
            return

        import threading
        thread = threading.Thread(target=self._background_loop, daemon=True)
        thread.start()
        
    def _background_loop(self):
        """The actual background loop that runs in a thread"""
        self.is_running = True
        while True:
            self.run_update()
            time.sleep(self.config.get('full_update_interval', 300))
    
    def track_user_access(self, instrument: str, timeframe: str):
        """Track user access for prioritizing data updates"""
        key = f"{instrument}:{timeframe}"
        if key not in self.user_access_log:
            self.user_access_log[key] = {'count': 0, 'last_access': None}
        
        self.user_access_log[key]['count'] += 1
        self.user_access_log[key]['last_access'] = time.time()
        
        self.logger.debug(f"Tracked access for {key}, count: {self.user_access_log[key]['count']}")
    
    def get_performance_metrics(self) -> Dict:
        """Get background data manager performance metrics"""
        return {
            'background_processing_status': 'running' if self.is_running else 'stopped',
            'cache_hit_rate': 0.95,  # Placeholder
            'last_update_time': None,  # Placeholder  
            'active_instruments': len(self.user_access_log),
            'error_count': 0  # Placeholder
        }

# Create global instance
try:
    from services.data_service import ohlc_service
    background_data_manager = BackgroundDataManager(ohlc_service)
except ImportError:
    # Handle circular import by delaying initialization
    background_data_manager = None
