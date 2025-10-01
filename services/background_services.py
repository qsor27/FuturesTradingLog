"""
Background Services for Futures Trading Log
Handles gap-filling, cache maintenance, and data updates
"""

import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import schedule
from services.data_service import ohlc_service
from services.redis_cache_service import get_cache_service
from config import config

# Get logger
bg_logger = logging.getLogger('background')

class BackgroundGapFillingService:
    """Background service for automatic gap detection and filling"""
    
    def __init__(self):
        self.is_running = False
        self.thread = None
        self.cache_service = get_cache_service() if config.cache_enabled else None
        self._last_health_check = None
        bg_logger.info("Background gap-filling service initialized")
    
    def start(self):
        """Start the background service"""
        if self.is_running:
            bg_logger.warning("Background service is already running")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        bg_logger.info("Background gap-filling service started")
    
    def stop(self):
        """Stop the background service"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        bg_logger.info("Background gap-filling service stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop"""
        # Schedule gap-filling tasks
        schedule.every(15).minutes.do(self._fill_recent_gaps)
        schedule.every(4).hours.do(self._fill_extended_gaps)
        schedule.every(2).hours.do(self._run_health_check)
        schedule.every().day.at("02:00").do(self._cache_maintenance)
        schedule.every().day.at("03:00").do(self._warm_popular_instruments)
        
        bg_logger.info("Background scheduler configured")
        
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                bg_logger.error(f"Error in background scheduler: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying
    
    def _fill_recent_gaps(self):
        """Fill gaps for recently accessed instruments (last 24 hours) with data health monitoring"""
        try:
            bg_logger.info("Starting recent gap filling with health monitoring")

            # Get recently accessed instruments from cache
            if self.cache_service:
                instruments = self._get_recent_instruments()
            else:
                # Fallback to common instruments
                instruments = ['MNQ', 'ES', 'YM', 'RTY']

            if not instruments:
                bg_logger.info("No instruments to process for recent gap filling")
                return

            # Check data health first to prioritize instruments needing attention
            timeframes = ['1m', '5m', '15m']  # Focus on intraday timeframes
            health_report = ohlc_service.check_data_health(instruments, timeframes)

            # Prioritize instruments with stale data
            priority_instruments = []
            for instrument, tf_data in health_report.items():
                has_stale_data = any(tf_info.get('is_stale', False) for tf_info in tf_data.values())
                if has_stale_data:
                    priority_instruments.append(instrument)
                    bg_logger.info(f"Priority instrument {instrument}: has stale data")

            # Process priority instruments first, then others
            all_instruments = priority_instruments + [i for i in instruments if i not in priority_instruments]

            # Fill gaps for last 2 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=2)

            successful_fills = 0
            failed_fills = 0

            for instrument in all_instruments:
                for timeframe in timeframes:
                    try:
                        # Check if this instrument/timeframe needs attention
                        tf_health = health_report.get(instrument, {}).get(timeframe, {})
                        if tf_health.get('status') == 'healthy':
                            bg_logger.debug(f"Skipping {instrument} {timeframe}: already healthy")
                            continue

                        success = ohlc_service.detect_and_fill_gaps(
                            instrument, timeframe, start_date, end_date
                        )
                        if success:
                            bg_logger.debug(f"Gap filling completed for {instrument} {timeframe}")
                            successful_fills += 1
                        else:
                            failed_fills += 1
                    except Exception as e:
                        bg_logger.error(f"Error filling gaps for {instrument} {timeframe}: {e}")
                        failed_fills += 1

            bg_logger.info(f"Recent gap filling completed: {successful_fills} successful, {failed_fills} failed")

        except Exception as e:
            bg_logger.error(f"Error in recent gap filling: {e}")
    
    def _fill_extended_gaps(self):
        """Fill gaps for all cached instruments (extended lookback)"""
        try:
            bg_logger.info("Starting extended gap filling")
            
            if self.cache_service:
                instruments = self.cache_service.get_cached_instruments()
            else:
                instruments = ['MNQ', 'ES', 'YM', 'RTY', 'NQ', 'CL', 'GC']
            
            # Fill gaps for last week
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            timeframes = ['1h', '4h', '1d']  # Focus on longer timeframes
            
            for instrument in instruments:
                for timeframe in timeframes:
                    try:
                        success = ohlc_service.detect_and_fill_gaps(
                            instrument, timeframe, start_date, end_date
                        )
                        if success:
                            bg_logger.debug(f"Extended gap filling completed for {instrument} {timeframe}")
                    except Exception as e:
                        bg_logger.error(f"Error in extended gap filling for {instrument} {timeframe}: {e}")
            
            bg_logger.info(f"Extended gap filling completed for {len(instruments)} instruments")
            
        except Exception as e:
            bg_logger.error(f"Error in extended gap filling: {e}")
    
    def _cache_maintenance(self):
        """Perform cache maintenance and cleanup"""
        try:
            bg_logger.info("Starting cache maintenance")
            
            if not self.cache_service:
                bg_logger.info("Cache service not available, skipping maintenance")
                return
            
            # Clean expired cache entries
            stats = self.cache_service.clean_expired_cache()
            bg_logger.info(f"Cache cleanup stats: {stats}")
            
            # Log cache statistics
            cache_stats = self.cache_service.get_cache_stats()
            bg_logger.info(f"Cache stats: {cache_stats.get('total_instruments', 0)} instruments, "
                          f"{cache_stats.get('ohlc_cache_entries', 0)} OHLC entries")
            
        except Exception as e:
            bg_logger.error(f"Error in cache maintenance: {e}")
    
    def _warm_popular_instruments(self):
        """Pre-warm cache for popular instruments"""
        try:
            bg_logger.info("Starting cache warming for popular instruments")
            
            if not self.cache_service:
                bg_logger.info("Cache service not available, skipping cache warming")
                return
            
            # Popular futures instruments
            popular_instruments = ['MNQ', 'ES', 'YM', 'RTY', 'NQ', 'CL', 'GC']
            timeframes = ['1m', '5m', '15m', '1h']
            
            for instrument in popular_instruments:
                try:
                    results = self.cache_service.warm_cache_for_instrument(
                        instrument, timeframes, days_back=3
                    )
                    success_count = sum(1 for success in results.values() if success)
                    bg_logger.debug(f"Cache warmed for {instrument}: {success_count}/{len(timeframes)} timeframes")
                except Exception as e:
                    bg_logger.error(f"Error warming cache for {instrument}: {e}")
            
            bg_logger.info(f"Cache warming completed for {len(popular_instruments)} instruments")

        except Exception as e:
            bg_logger.error(f"Error in cache warming: {e}")

    def _run_health_check(self):
        """Scheduled data health check"""
        try:
            bg_logger.info("Running scheduled data health check")
            health_results = self.run_data_health_check()

            # Log summary
            health_pct = health_results.get('health_percentage', 0)
            critical_count = len(health_results.get('critical_issues', []))

            if health_pct < 80:
                bg_logger.warning(f"Data health below threshold: {health_pct:.1f}% healthy")
            if critical_count > 0:
                bg_logger.warning(f"Found {critical_count} critical data issues")

            # Store health check results for status reporting
            self._last_health_check = {
                'timestamp': datetime.now().isoformat(),
                'health_percentage': health_pct,
                'critical_issues_count': critical_count,
                'recommendations_count': len(health_results.get('recommendations', []))
            }

        except Exception as e:
            bg_logger.error(f"Error in scheduled health check: {e}")

    def _get_recent_instruments(self) -> List[str]:
        """Get instruments accessed in the last 24 hours"""
        try:
            if not self.cache_service:
                return []
            
            all_instruments = self.cache_service.get_cached_instruments()
            recent_instruments = []
            
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            for instrument in all_instruments:
                metadata = self.cache_service.get_instrument_metadata(instrument)
                if metadata and metadata.get('last_access'):
                    last_access = datetime.fromisoformat(metadata['last_access'])
                    if last_access > cutoff_time:
                        recent_instruments.append(instrument)
            
            return recent_instruments
            
        except Exception as e:
            bg_logger.error(f"Error getting recent instruments: {e}")
            return []
    
    def force_gap_fill(self, instrument: str, timeframes: List[str] = None, 
                      days_back: int = 7) -> Dict[str, bool]:
        """Manually trigger gap filling for specific instrument"""
        if timeframes is None:
            timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        
        results = {}
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        bg_logger.info(f"Force gap filling for {instrument}: {timeframes}")
        
        for timeframe in timeframes:
            try:
                success = ohlc_service.detect_and_fill_gaps(
                    instrument, timeframe, start_date, end_date
                )
                results[timeframe] = success
                bg_logger.info(f"Force gap fill {instrument} {timeframe}: {'SUCCESS' if success else 'FAILED'}")
            except Exception as e:
                bg_logger.error(f"Error in force gap fill for {instrument} {timeframe}: {e}")
                results[timeframe] = False
        
        return results
    
    def emergency_gap_fill_for_trades(self, days_back: int = 7) -> Dict[str, Dict[str, bool]]:
        """Emergency gap filling for instruments with recent trades but missing OHLC data"""
        bg_logger.warning("🚨 EMERGENCY GAP FILLING TRIGGERED")
        
        try:
            from scripts.TradingLog_db import FuturesDB
            
            with FuturesDB() as db:
                # Get instruments with recent trades
                cutoff_date = datetime.now() - timedelta(days=days_back)
                recent_instruments_query = db.execute_query("""
                    SELECT DISTINCT instrument 
                    FROM trades 
                    WHERE entry_time >= ?
                """, (cutoff_date.strftime('%Y-%m-%d'),))
                
                instruments_needing_data = []
                
                for (instrument,) in recent_instruments_query:
                    # Extract base instrument (e.g., "MNQ SEP25" -> "MNQ")
                    base_instrument = instrument.split(' ')[0] if ' ' in instrument else instrument
                    
                    # Check if OHLC data is current
                    latest_data_query = db.execute_query("""
                        SELECT MAX(timestamp) 
                        FROM ohlc_data 
                        WHERE instrument IN (?, ?)
                    """, (instrument, base_instrument))
                    
                    if latest_data_query and latest_data_query[0] and latest_data_query[0][0]:
                        latest_timestamp = latest_data_query[0][0]
                        latest_date = datetime.fromtimestamp(latest_timestamp)
                        days_behind = (datetime.now() - latest_date).days
                        
                        if days_behind > 1:  # More than 1 day behind
                            bg_logger.warning(f"{base_instrument}: {days_behind} days behind OHLC data")
                            instruments_needing_data.append(base_instrument)
                    else:
                        bg_logger.warning(f"{base_instrument}: No OHLC data found")
                        instruments_needing_data.append(base_instrument)
                
                # Remove duplicates
                instruments_needing_data = list(set(instruments_needing_data))
                
                if not instruments_needing_data:
                    bg_logger.info("No instruments need emergency gap filling")
                    return {}
                
                bg_logger.warning(f"Emergency gap filling needed for: {', '.join(instruments_needing_data)}")
                
                # Focus on critical timeframes for trading analysis
                critical_timeframes = ['5m', '15m', '1h', '1d']
                
                results = {}
                for instrument in instruments_needing_data:
                    bg_logger.info(f"Emergency processing {instrument}...")
                    results[instrument] = self.force_gap_fill(
                        instrument, 
                        critical_timeframes, 
                        days_back * 2  # Extended range for safety
                    )
                
                return results

        except Exception as e:
            bg_logger.error(f"Error in emergency gap filling: {e}")
            return {}

    def run_data_health_check(self, instruments: List[str] = None) -> Dict[str, Any]:
        """Run comprehensive data health check and return detailed report"""
        try:
            bg_logger.info("Starting comprehensive data health check")

            if instruments is None:
                if self.cache_service:
                    instruments = self.cache_service.get_cached_instruments()
                else:
                    instruments = ['MNQ', 'ES', 'YM', 'RTY', 'NQ', 'CL', 'GC']

            timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']

            # Get health report
            health_report = ohlc_service.check_data_health(instruments, timeframes)

            # Analyze the health report
            analysis = {
                'total_instruments': len(instruments),
                'total_timeframes': len(timeframes),
                'healthy_count': 0,
                'stale_count': 0,
                'no_data_count': 0,
                'error_count': 0,
                'critical_issues': [],
                'recommendations': [],
                'detailed_report': health_report
            }

            for instrument, tf_data in health_report.items():
                for timeframe, health_info in tf_data.items():
                    status = health_info.get('status', 'unknown')

                    if status == 'healthy':
                        analysis['healthy_count'] += 1
                    elif status == 'stale':
                        analysis['stale_count'] += 1
                        staleness = health_info.get('staleness_minutes', 0)
                        if staleness > 1440:  # More than 24 hours
                            analysis['critical_issues'].append(
                                f"{instrument} {timeframe}: {staleness/60:.1f} hours stale"
                            )
                    elif status == 'no_data':
                        analysis['no_data_count'] += 1
                        analysis['critical_issues'].append(f"{instrument} {timeframe}: No data available")
                    elif status == 'error':
                        analysis['error_count'] += 1
                        error_msg = health_info.get('error', 'Unknown error')
                        analysis['critical_issues'].append(f"{instrument} {timeframe}: {error_msg}")

            # Generate recommendations
            if analysis['stale_count'] > 0:
                analysis['recommendations'].append(f"Run gap filling for {analysis['stale_count']} stale timeframes")

            if analysis['no_data_count'] > 0:
                analysis['recommendations'].append(f"Initialize data for {analysis['no_data_count']} missing timeframes")

            if analysis['error_count'] > 0:
                analysis['recommendations'].append(f"Investigate {analysis['error_count']} database/connection errors")

            # Calculate health percentage
            total_checks = analysis['healthy_count'] + analysis['stale_count'] + analysis['no_data_count'] + analysis['error_count']
            analysis['health_percentage'] = (analysis['healthy_count'] / total_checks * 100) if total_checks > 0 else 0

            bg_logger.info(f"Health check completed: {analysis['health_percentage']:.1f}% healthy "
                          f"({analysis['healthy_count']}/{total_checks} checks)")

            if analysis['critical_issues']:
                bg_logger.warning(f"Found {len(analysis['critical_issues'])} critical issues")
                for issue in analysis['critical_issues'][:5]:  # Log first 5 issues
                    bg_logger.warning(f"  - {issue}")

            return analysis

        except Exception as e:
            bg_logger.error(f"Error in data health check: {e}")
            return {
                'error': str(e),
                'health_percentage': 0,
                'critical_issues': [f"Health check failed: {str(e)}"]
            }

    def get_service_status(self) -> Dict[str, Any]:
        """Get status information about the background service"""
        status = {
            'is_running': self.is_running,
            'thread_alive': self.thread.is_alive() if self.thread else False,
            'cache_enabled': self.cache_service is not None,
            'next_runs': {
                'recent_gaps': 'Every 15 minutes',
                'extended_gaps': 'Every 4 hours',
                'health_check': 'Every 2 hours',
                'cache_maintenance': 'Daily at 02:00 UTC',
                'cache_warming': 'Daily at 03:00 UTC'
            },
            'last_check': datetime.now().isoformat()
        }

        # Add health check results if available
        if self._last_health_check:
            status['last_health_check'] = self._last_health_check
        else:
            status['last_health_check'] = {
                'timestamp': None,
                'health_percentage': None,
                'critical_issues_count': None,
                'recommendations_count': None
            }

        return status


class DataUpdateService:
    """Service for updating market data in real-time or near real-time"""
    
    def __init__(self):
        self.is_running = False
        self.thread = None
        bg_logger.info("Data update service initialized")
    
    def start(self):
        """Start the data update service"""
        if self.is_running:
            bg_logger.warning("Data update service is already running")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_updates, daemon=True)
        self.thread.start()
        bg_logger.info("Data update service started")
    
    def stop(self):
        """Stop the data update service"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        bg_logger.info("Data update service stopped")
    
    def _run_updates(self):
        """Main update loop"""
        # Schedule regular data updates
        schedule.every(5).minutes.do(self._update_active_instruments)
        schedule.every(30).minutes.do(self._update_all_timeframes)
        
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                bg_logger.error(f"Error in data update service: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying
    
    def _update_active_instruments(self):
        """Update data for actively traded instruments"""
        try:
            # Focus on most common instruments during market hours
            instruments = ['MNQ', 'ES', 'YM', 'RTY']
            timeframes = ['1m', '5m']
            
            for instrument in instruments:
                success = ohlc_service.update_recent_data(instrument, timeframes)
                if success:
                    bg_logger.debug(f"Updated recent data for {instrument}")
                
        except Exception as e:
            bg_logger.error(f"Error updating active instruments: {e}")
    
    def _update_all_timeframes(self):
        """Update all timeframes for tracked instruments"""
        try:
            cache_service = get_cache_service()
            if cache_service:
                instruments = cache_service.get_cached_instruments()
            else:
                instruments = ['MNQ', 'ES', 'YM', 'RTY', 'NQ', 'CL', 'GC']
            
            timeframes = ['15m', '1h', '4h', '1d']
            
            for instrument in instruments[:5]:  # Limit to first 5 to avoid overwhelming
                success = ohlc_service.update_recent_data(instrument, timeframes)
                if success:
                    bg_logger.debug(f"Updated all timeframes for {instrument}")
                
        except Exception as e:
            bg_logger.error(f"Error updating all timeframes: {e}")


# Global service instances
gap_filling_service = BackgroundGapFillingService()
data_update_service = DataUpdateService()

def start_background_services():
    """Start all background services"""
    bg_logger.info("Starting background services")
    gap_filling_service.start()
    data_update_service.start()
    bg_logger.info("All background services started")

def stop_background_services():
    """Stop all background services"""
    bg_logger.info("Stopping background services")
    gap_filling_service.stop()
    data_update_service.stop()
    bg_logger.info("All background services stopped")

def get_services_status() -> Dict[str, Any]:
    """Get status of all background services"""
    return {
        'gap_filling': gap_filling_service.get_service_status(),
        'data_update': {
            'is_running': data_update_service.is_running,
            'thread_alive': data_update_service.thread.is_alive() if data_update_service.thread else False
        },
        'cache_service': get_cache_service().health_check() if config.cache_enabled else {'status': 'disabled'}
    }