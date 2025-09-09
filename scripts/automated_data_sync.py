#!/usr/bin/env python3
"""
Automated Data Sync System for Futures Trading Log
Ensures OHLC data is always current for all instruments in the trading log
"""

import schedule
import time
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Set
import threading
import json
import os
from services.data_service import ohlc_service
from scripts.TradingLog_db import FuturesDB

class AutomatedDataSyncer:
    """Automated system to keep OHLC data current for all trading instruments"""
    
    def __init__(self):
        self.logger = logging.getLogger('data_sync')
        self.is_running = False
        self.thread = None
        self.last_sync_file = "data/last_sync.json"
        
        # Critical timeframes for trading analysis
        self.critical_timeframes = ['5m', '15m', '1h', '4h', '1d']
        
        # Sync intervals (more frequent for recent data)
        self.sync_intervals = {
            'startup_check': 'immediate',      # Run on startup
            'hourly_recent': 'every hour',     # Recent data (last 3 days)
            'daily_full': 'daily at 02:00',   # Full sync (last 30 days)
            'weekly_deep': 'weekly on sunday' # Deep historical sync
        }
        
        self.logger.info("Automated Data Syncer initialized")
    
    def get_all_trading_instruments(self) -> Set[str]:
        """Get all base instruments that have ever been traded"""
        try:
            with FuturesDB() as db:
                # Get all unique instruments from trades
                instruments_query = db.execute_query("""
                    SELECT DISTINCT instrument FROM trades 
                    ORDER BY instrument
                """)
                
                base_instruments = set()
                for (instrument,) in instruments_query:
                    # Extract base symbol (e.g., "MNQ SEP25" -> "MNQ")
                    base_symbol = instrument.split(' ')[0] if ' ' in instrument else instrument
                    base_instruments.add(base_symbol)
                
                self.logger.info(f"Found {len(base_instruments)} unique trading instruments: {', '.join(sorted(base_instruments))}")
                return base_instruments
                
        except Exception as e:
            self.logger.error(f"Error getting trading instruments: {e}")
            return set()
    
    def get_data_coverage_status(self, instrument: str) -> Dict[str, any]:
        """Get current data coverage status for an instrument"""
        try:
            with FuturesDB() as db:
                status = {
                    'instrument': instrument,
                    'has_trades': False,
                    'timeframe_coverage': {},
                    'critical_gaps': [],
                    'needs_sync': False
                }
                
                # Check if instrument has trades
                trades_check = db.execute_query("""
                    SELECT COUNT(*) FROM trades 
                    WHERE instrument LIKE ?
                """, (f"%{instrument}%",))
                
                if trades_check and trades_check[0][0] > 0:
                    status['has_trades'] = True
                
                # Check OHLC data coverage for each timeframe
                for timeframe in self.critical_timeframes:
                    coverage_check = db.execute_query("""
                        SELECT COUNT(*) as count,
                               MAX(timestamp) as latest_timestamp
                        FROM ohlc_data 
                        WHERE instrument = ? AND timeframe = ?
                    """, (instrument, timeframe))
                    
                    if coverage_check and coverage_check[0]:
                        count, latest_timestamp = coverage_check[0]
                        
                        if latest_timestamp:
                            latest_date = datetime.fromtimestamp(latest_timestamp)
                            days_behind = (datetime.now() - latest_date).days
                            hours_behind = (datetime.now() - latest_date).total_seconds() / 3600
                            
                            status['timeframe_coverage'][timeframe] = {
                                'record_count': count,
                                'latest_date': latest_date.isoformat(),
                                'days_behind': days_behind,
                                'hours_behind': round(hours_behind, 1),
                                'is_current': days_behind <= 1
                            }
                            
                            # Flag as critical gap if more than 1 day behind
                            if days_behind > 1:
                                status['critical_gaps'].append({
                                    'timeframe': timeframe,
                                    'days_behind': days_behind
                                })
                                status['needs_sync'] = True
                        else:
                            status['timeframe_coverage'][timeframe] = {
                                'record_count': 0,
                                'latest_date': None,
                                'days_behind': 999,
                                'hours_behind': 999,
                                'is_current': False
                            }
                            status['critical_gaps'].append({
                                'timeframe': timeframe,
                                'days_behind': 999
                            })
                            status['needs_sync'] = True
                
                return status
                
        except Exception as e:
            self.logger.error(f"Error getting coverage status for {instrument}: {e}")
            return {'instrument': instrument, 'error': str(e)}
    
    def sync_instrument_data(self, instrument: str, days_back: int = 7, 
                           timeframes: List[str] = None) -> Dict[str, bool]:
        """Sync OHLC data for a specific instrument"""
        if timeframes is None:
            timeframes = self.critical_timeframes
        
        self.logger.info(f"Syncing {instrument} data: {days_back} days, timeframes: {timeframes}")
        
        results = {}
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        for timeframe in timeframes:
            try:
                # First try gap filling
                success = ohlc_service.detect_and_fill_gaps(
                    instrument, timeframe, start_date, end_date
                )
                
                if not success:
                    # If gap filling didn't work, try recent data update
                    success = ohlc_service.update_recent_data(instrument, [timeframe])
                
                results[timeframe] = success
                
                if success:
                    self.logger.info(f"  ✅ {timeframe}: Successfully synced")
                else:
                    self.logger.warning(f"  ⚠️ {timeframe}: Sync failed")
                    
            except Exception as e:
                self.logger.error(f"  ❌ {timeframe}: Error during sync: {e}")
                results[timeframe] = False
        
        return results
    
    def startup_data_check(self) -> Dict[str, any]:
        """Comprehensive data check on startup - catch up on any missing data"""
        self.logger.info("🚀 STARTUP DATA VALIDATION AND CATCH-UP")
        
        instruments = self.get_all_trading_instruments()
        if not instruments:
            self.logger.warning("No trading instruments found")
            return {'success': False, 'error': 'No trading instruments found'}
        
        startup_summary = {
            'total_instruments': len(instruments),
            'instruments_needing_sync': [],
            'sync_results': {},
            'overall_success': True
        }
        
        # Check each instrument and sync if needed
        for instrument in instruments:
            self.logger.info(f"Checking {instrument}...")
            
            status = self.get_data_coverage_status(instrument)
            
            if status.get('needs_sync', False):
                self.logger.warning(f"  {instrument} needs sync: {len(status.get('critical_gaps', []))} gaps found")
                startup_summary['instruments_needing_sync'].append(instrument)
                
                # Perform extended sync (14 days to ensure we catch everything)
                sync_results = self.sync_instrument_data(instrument, days_back=14)
                startup_summary['sync_results'][instrument] = sync_results
                
                # Check if sync was successful
                success_rate = sum(1 for success in sync_results.values() if success) / len(sync_results)
                if success_rate < 0.5:  # Less than 50% success
                    startup_summary['overall_success'] = False
            else:
                self.logger.info(f"  ✅ {instrument}: Data is current")
        
        # Save sync timestamp
        self.save_last_sync_info({
            'type': 'startup_check',
            'timestamp': datetime.now().isoformat(),
            'results': startup_summary
        })
        
        return startup_summary
    
    def hourly_recent_sync(self) -> Dict[str, any]:
        """Hourly sync of recent data (last 3 days) for all instruments"""
        self.logger.info("⏰ HOURLY RECENT DATA SYNC")
        
        instruments = self.get_all_trading_instruments()
        results = {}
        
        for instrument in instruments:
            # Quick sync of just recent data
            sync_results = self.sync_instrument_data(
                instrument, 
                days_back=3, 
                timeframes=['5m', '15m', '1h']  # Focus on shorter timeframes
            )
            results[instrument] = sync_results
        
        self.save_last_sync_info({
            'type': 'hourly_recent',
            'timestamp': datetime.now().isoformat(),
            'results': results
        })
        
        return results
    
    def daily_full_sync(self) -> Dict[str, any]:
        """Daily comprehensive sync of all timeframes (last 30 days)"""
        self.logger.info("📅 DAILY FULL DATA SYNC")
        
        instruments = self.get_all_trading_instruments()
        results = {}
        
        for instrument in instruments:
            # Full sync of all critical timeframes
            sync_results = self.sync_instrument_data(
                instrument, 
                days_back=30, 
                timeframes=self.critical_timeframes
            )
            results[instrument] = sync_results
        
        self.save_last_sync_info({
            'type': 'daily_full',
            'timestamp': datetime.now().isoformat(),
            'results': results
        })
        
        return results
    
    def weekly_deep_sync(self) -> Dict[str, any]:
        """Weekly deep sync ensuring historical data completeness"""
        self.logger.info("🗓️ WEEKLY DEEP HISTORICAL SYNC")
        
        instruments = self.get_all_trading_instruments()
        results = {}
        
        for instrument in instruments:
            # Extended historical sync
            sync_results = self.sync_instrument_data(
                instrument, 
                days_back=90,  # 3 months of data
                timeframes=self.critical_timeframes + ['1m', '3m']  # Include all timeframes
            )
            results[instrument] = sync_results
        
        self.save_last_sync_info({
            'type': 'weekly_deep',
            'timestamp': datetime.now().isoformat(),
            'results': results
        })
        
        return results
    
    def save_last_sync_info(self, sync_info: Dict):
        """Save information about the last sync operation"""
        try:
            os.makedirs(os.path.dirname(self.last_sync_file), exist_ok=True)
            with open(self.last_sync_file, 'w') as f:
                json.dump(sync_info, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving sync info: {e}")
    
    def get_last_sync_info(self) -> Dict:
        """Get information about the last sync operation"""
        try:
            if os.path.exists(self.last_sync_file):
                with open(self.last_sync_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading sync info: {e}")
        return {}
    
    def start(self):
        """Start the automated data sync system"""
        if self.is_running:
            self.logger.warning("Data sync system is already running")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        
        # Run startup check immediately
        threading.Thread(target=self.startup_data_check, daemon=True).start()
        
        self.logger.info("🚀 Automated Data Sync System started")
    
    def stop(self):
        """Stop the automated data sync system"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("Automated Data Sync System stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop"""
        # Schedule sync operations
        schedule.every().hour.do(self.hourly_recent_sync)
        schedule.every().day.at("02:00").do(self.daily_full_sync)
        schedule.every().sunday.at("03:00").do(self.weekly_deep_sync)
        
        self.logger.info("Data sync scheduler configured:")
        self.logger.info("  - Hourly: Recent data sync (3 days)")
        self.logger.info("  - Daily 02:00: Full sync (30 days)")
        self.logger.info("  - Weekly Sunday 03:00: Deep sync (90 days)")
        
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                self.logger.error(f"Error in data sync scheduler: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying
    
    def get_status(self) -> Dict[str, any]:
        """Get current status of the data sync system"""
        instruments = self.get_all_trading_instruments()
        
        status = {
            'is_running': self.is_running,
            'thread_alive': self.thread.is_alive() if self.thread else False,
            'total_instruments': len(instruments),
            'last_sync': self.get_last_sync_info(),
            'instrument_status': {},
            'next_scheduled_runs': {
                'hourly_recent': 'Every hour',
                'daily_full': 'Daily at 02:00 UTC',
                'weekly_deep': 'Weekly Sunday at 03:00 UTC'
            }
        }
        
        # Get status for each instrument
        for instrument in instruments:
            status['instrument_status'][instrument] = self.get_data_coverage_status(instrument)
        
        return status

# Global instance
data_syncer = AutomatedDataSyncer()

def start_automated_data_sync():
    """Start the automated data sync system"""
    data_syncer.start()

def stop_automated_data_sync():
    """Stop the automated data sync system"""
    data_syncer.stop()

def get_data_sync_status():
    """Get data sync system status"""
    return data_syncer.get_status()

def force_data_sync(sync_type: str = 'startup'):
    """Force a data sync operation"""
    if sync_type == 'startup':
        return data_syncer.startup_data_check()
    elif sync_type == 'hourly':
        return data_syncer.hourly_recent_sync()
    elif sync_type == 'daily':
        return data_syncer.daily_full_sync()
    elif sync_type == 'weekly':
        return data_syncer.weekly_deep_sync()
    else:
        raise ValueError(f"Unknown sync type: {sync_type}")

if __name__ == "__main__":
    # Command line interface
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description='Automated Data Sync System')
    parser.add_argument('--action', choices=['start', 'status', 'sync'], 
                       default='status', help='Action to perform')
    parser.add_argument('--sync-type', choices=['startup', 'hourly', 'daily', 'weekly'], 
                       default='startup', help='Type of sync to perform')
    
    args = parser.parse_args()
    
    if args.action == 'start':
        print("Starting automated data sync system...")
        start_automated_data_sync()
        print("System started. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping...")
            stop_automated_data_sync()
    
    elif args.action == 'status':
        print("📊 DATA SYNC SYSTEM STATUS")
        print("=" * 50)
        status = get_data_sync_status()
        
        print(f"Running: {status['is_running']}")
        print(f"Thread alive: {status['thread_alive']}")
        print(f"Total instruments: {status['total_instruments']}")
        
        print(f"\nInstrument Status:")
        for instrument, inst_status in status['instrument_status'].items():
            gaps = len(inst_status.get('critical_gaps', []))
            needs_sync = inst_status.get('needs_sync', False)
            status_icon = "🔴" if needs_sync else "🟢"
            print(f"  {status_icon} {instrument}: {gaps} gaps, needs sync: {needs_sync}")
    
    elif args.action == 'sync':
        print(f"🔄 FORCING {args.sync_type.upper()} SYNC")
        print("=" * 50)
        
        result = force_data_sync(args.sync_type)
        
        if 'error' in result:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"✅ Sync completed successfully")
            if 'total_instruments' in result:
                print(f"   Processed {result['total_instruments']} instruments")
            if 'instruments_needing_sync' in result:
                print(f"   {len(result['instruments_needing_sync'])} instruments needed sync")