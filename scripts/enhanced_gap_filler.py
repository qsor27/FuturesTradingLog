#!/usr/bin/env python3
"""
Enhanced Gap Filling Engine for Futures Trading Log
Comprehensive data gap detection and filling with intelligent strategies
"""

import sys
import os
sys.path.append('/mnt/c/Projects/FuturesTradingLog')

from datetime import datetime, timedelta
import logging
import time
from typing import List, Dict, Tuple, Optional
from services.data_service import ohlc_service
from scripts.TradingLog_db import FuturesDB
from services.background_services import gap_filling_service

class EnhancedGapFiller:
    """Enhanced gap filling engine with comprehensive coverage"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.db = None
        
    def get_instruments_needing_data(self, days_back: int = 30) -> List[str]:
        """Get instruments that have recent trade activity but missing OHLC data"""
        try:
            with FuturesDB() as db:
                # Get instruments with recent trades
                cutoff_date = datetime.now() - timedelta(days=days_back)
                
                # Query for instruments with recent trades
                recent_instruments = db.execute_query("""
                    SELECT DISTINCT instrument 
                    FROM trades 
                    WHERE entry_time >= ?
                """, (cutoff_date.strftime('%Y-%m-%d'),))
                
                instruments_needing_data = []
                
                for (instrument,) in recent_instruments:
                    # Check if OHLC data is current for this instrument
                    base_instrument = instrument.split(' ')[0] if ' ' in instrument else instrument
                    
                    # Check latest OHLC data timestamp
                    latest_data = db.execute_query("""
                        SELECT MAX(timestamp) 
                        FROM ohlc_data 
                        WHERE instrument IN (?, ?)
                    """, (instrument, base_instrument))
                    
                    if latest_data and latest_data[0] and latest_data[0][0]:
                        latest_timestamp = latest_data[0][0]
                        latest_date = datetime.fromtimestamp(latest_timestamp)
                        days_behind = (datetime.now() - latest_date).days
                        
                        if days_behind > 1:  # More than 1 day behind
                            self.logger.info(f"{base_instrument}: {days_behind} days behind (latest: {latest_date.strftime('%Y-%m-%d')})")
                            instruments_needing_data.append(base_instrument)
                    else:
                        self.logger.info(f"{base_instrument}: No OHLC data found")
                        instruments_needing_data.append(base_instrument)
                
                return list(set(instruments_needing_data))  # Remove duplicates
                
        except Exception as e:
            self.logger.error(f"Error getting instruments needing data: {e}")
            return []
    
    def fill_gaps_for_instruments(self, instruments: List[str], 
                                 timeframes: List[str] = None,
                                 days_back: int = 14) -> Dict[str, Dict[str, bool]]:
        """Fill gaps for specific instruments comprehensively"""
        if timeframes is None:
            timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        
        results = {}
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        self.logger.info(f"Enhanced gap filling for {len(instruments)} instruments:")
        self.logger.info(f"  Instruments: {', '.join(instruments)}")
        self.logger.info(f"  Timeframes: {', '.join(timeframes)}")
        self.logger.info(f"  Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        for i, instrument in enumerate(instruments):
            self.logger.info(f"\n[{i+1}/{len(instruments)}] Processing {instrument}")
            results[instrument] = {}
            
            for j, timeframe in enumerate(timeframes):
                self.logger.info(f"  [{j+1}/{len(timeframes)}] Filling {timeframe} gaps...")
                
                try:
                    success = ohlc_service.detect_and_fill_gaps(
                        instrument, timeframe, start_date, end_date
                    )
                    results[instrument][timeframe] = success
                    
                    if success:
                        self.logger.info(f"    ✅ Success")
                    else:
                        self.logger.warning(f"    ⚠️ Failed or no gaps found")
                        
                except Exception as e:
                    self.logger.error(f"    ❌ Error: {e}")
                    results[instrument][timeframe] = False
                
                # Small delay between requests
                time.sleep(0.5)
        
        return results
    
    def update_recent_data_comprehensive(self, instruments: List[str] = None,
                                       timeframes: List[str] = None) -> Dict[str, Dict[str, bool]]:
        """Comprehensive recent data update for instruments"""
        if instruments is None:
            instruments = self.get_instruments_needing_data()
        
        if timeframes is None:
            timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        
        if not instruments:
            self.logger.info("No instruments need data updates")
            return {}
        
        self.logger.info(f"Comprehensive data update for: {', '.join(instruments)}")
        
        results = {}
        
        for instrument in instruments:
            self.logger.info(f"\nUpdating {instrument}...")
            results[instrument] = {}
            
            for timeframe in timeframes:
                try:
                    success = ohlc_service.update_recent_data(instrument, [timeframe])
                    results[instrument][timeframe] = success
                    
                    if success:
                        self.logger.info(f"  {timeframe}: ✅ Updated")
                    else:
                        self.logger.warning(f"  {timeframe}: ⚠️ Failed")
                        
                except Exception as e:
                    self.logger.error(f"  {timeframe}: ❌ Error: {e}")
                    results[instrument][timeframe] = False
        
        return results
    
    def emergency_fill_for_trades(self, days_back: int = 7) -> Dict[str, Dict[str, bool]]:
        """Emergency gap filling for instruments with recent trades but missing data"""
        self.logger.info("🚨 EMERGENCY GAP FILLING FOR TRADE INSTRUMENTS")
        
        # Get instruments with recent trades
        instruments = self.get_instruments_needing_data(days_back)
        
        if not instruments:
            self.logger.info("No instruments need emergency gap filling")
            return {}
        
        self.logger.warning(f"Found {len(instruments)} instruments needing data: {', '.join(instruments)}")
        
        # Focus on essential timeframes for trading analysis
        critical_timeframes = ['5m', '15m', '1h', '1d']
        
        # Fill gaps with extended date range
        return self.fill_gaps_for_instruments(
            instruments, 
            critical_timeframes, 
            days_back=days_back * 2  # Double the range for safety
        )
    
    def get_gap_analysis(self) -> Dict[str, any]:
        """Analyze current gaps in the system"""
        try:
            with FuturesDB() as db:
                # Get all instruments with trades
                all_instruments = db.execute_query("""
                    SELECT DISTINCT instrument FROM trades 
                    ORDER BY instrument
                """)
                
                analysis = {
                    'total_instruments': len(all_instruments),
                    'instruments_with_data': 0,
                    'instruments_missing_data': 0,
                    'gap_summary': []
                }
                
                for (instrument,) in all_instruments:
                    base_instrument = instrument.split(' ')[0] if ' ' in instrument else instrument
                    
                    # Check OHLC data availability
                    ohlc_check = db.execute_query("""
                        SELECT timeframe, COUNT(*) as count,
                               datetime(MIN(timestamp), 'unixepoch') as min_date,
                               datetime(MAX(timestamp), 'unixepoch') as max_date
                        FROM ohlc_data 
                        WHERE instrument IN (?, ?)
                        GROUP BY timeframe
                        ORDER BY timeframe
                    """, (instrument, base_instrument))
                    
                    if ohlc_check:
                        analysis['instruments_with_data'] += 1
                        latest_date = max([row[3] for row in ohlc_check])
                        days_behind = (datetime.now() - datetime.strptime(latest_date, '%Y-%m-%d %H:%M:%S')).days
                        
                        analysis['gap_summary'].append({
                            'instrument': base_instrument,
                            'has_data': True,
                            'latest_date': latest_date,
                            'days_behind': days_behind,
                            'timeframes': len(ohlc_check)
                        })
                    else:
                        analysis['instruments_missing_data'] += 1
                        analysis['gap_summary'].append({
                            'instrument': base_instrument,
                            'has_data': False,
                            'latest_date': 'No data',
                            'days_behind': 999,
                            'timeframes': 0
                        })
                
                return analysis
                
        except Exception as e:
            self.logger.error(f"Error in gap analysis: {e}")
            return {'error': str(e)}

def main():
    """Main function for command-line usage"""
    import argparse
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description='Enhanced Gap Filling Engine')
    parser.add_argument('--mode', choices=['emergency', 'comprehensive', 'analysis'], 
                       default='emergency', help='Gap filling mode')
    parser.add_argument('--instruments', nargs='+', help='Specific instruments to process')
    parser.add_argument('--timeframes', nargs='+', 
                       default=['5m', '15m', '1h', '1d'],
                       help='Timeframes to process')
    parser.add_argument('--days', type=int, default=7, help='Days back to fill')
    
    args = parser.parse_args()
    
    filler = EnhancedGapFiller()
    
    if args.mode == 'analysis':
        print("\n🔍 GAP ANALYSIS")
        print("=" * 50)
        analysis = filler.get_gap_analysis()
        
        if 'error' in analysis:
            print(f"Error: {analysis['error']}")
            return
        
        print(f"Total instruments: {analysis['total_instruments']}")
        print(f"With data: {analysis['instruments_with_data']}")
        print(f"Missing data: {analysis['instruments_missing_data']}")
        
        print("\nInstrument Status:")
        for item in analysis['gap_summary']:
            status = "✅" if item['has_data'] else "❌"
            days_info = f"({item['days_behind']} days behind)" if item['has_data'] else ""
            print(f"  {status} {item['instrument']}: {item['latest_date']} {days_info}")
    
    elif args.mode == 'emergency':
        print("\n🚨 EMERGENCY GAP FILLING")
        print("=" * 50)
        results = filler.emergency_fill_for_trades(args.days)
        
        if not results:
            print("No emergency gap filling needed!")
        else:
            print(f"Processed {len(results)} instruments")
            for instrument, timeframe_results in results.items():
                success_count = sum(1 for success in timeframe_results.values() if success)
                total_count = len(timeframe_results)
                print(f"  {instrument}: {success_count}/{total_count} timeframes successful")
    
    elif args.mode == 'comprehensive':
        print("\n📊 COMPREHENSIVE GAP FILLING")
        print("=" * 50)
        
        instruments = args.instruments or filler.get_instruments_needing_data(args.days)
        
        if not instruments:
            print("No instruments need gap filling!")
            return
        
        results = filler.fill_gaps_for_instruments(
            instruments, args.timeframes, args.days
        )
        
        print(f"\nProcessed {len(results)} instruments")
        for instrument, timeframe_results in results.items():
            success_count = sum(1 for success in timeframe_results.values() if success)
            total_count = len(timeframe_results)
            print(f"  {instrument}: {success_count}/{total_count} timeframes successful")

if __name__ == '__main__':
    main()