#!/usr/bin/env python3
"""
Data Quality Monitor
Simple monitoring tool for ongoing OHLC data quality
"""

from scripts.TradingLog_db import FuturesDB
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

class DataQualityMonitor:
    """Monitor OHLC data quality and detect issues automatically"""
    
    def __init__(self):
        self.quality_checks = [
            self._check_invalid_ohlc,
            self._check_extreme_outliers,
            self._check_volume_issues,
            self._check_data_freshness
        ]
    
    def monitor_instrument(self, instrument: str) -> Dict[str, Any]:
        """Run all quality checks for an instrument"""
        results = {
            'instrument': instrument,
            'checks_passed': 0,
            'checks_failed': 0,
            'issues': [],
            'summary': '',
            'quality_score': 'UNKNOWN'
        }
        
        with FuturesDB() as db:
            for check in self.quality_checks:
                try:
                    check_result = check(db, instrument)
                    if check_result['passed']:
                        results['checks_passed'] += 1
                    else:
                        results['checks_failed'] += 1
                        results['issues'].append(check_result)
                except Exception as e:
                    logger.error(f"Quality check failed: {e}")
                    results['checks_failed'] += 1
                    results['issues'].append({
                        'check': 'Error',
                        'passed': False,
                        'message': f"Check failed: {str(e)}"
                    })
        
        # Calculate quality score
        total_checks = results['checks_passed'] + results['checks_failed']
        if total_checks > 0:
            pass_rate = results['checks_passed'] / total_checks
            if pass_rate >= 0.9:
                results['quality_score'] = 'EXCELLENT'
            elif pass_rate >= 0.7:
                results['quality_score'] = 'GOOD'
            elif pass_rate >= 0.5:
                results['quality_score'] = 'FAIR'
            else:
                results['quality_score'] = 'POOR'
        
        # Generate summary
        if results['checks_failed'] == 0:
            results['summary'] = f"✅ All {results['checks_passed']} quality checks passed"
        else:
            results['summary'] = f"⚠️ {results['checks_failed']} of {total_checks} checks failed"
        
        return results
    
    def _check_invalid_ohlc(self, db: FuturesDB, instrument: str) -> Dict[str, Any]:
        """Check for invalid OHLC relationships"""
        query = """
        SELECT COUNT(*) FROM ohlc_data 
        WHERE instrument = ? AND (
            high_price < low_price OR
            high_price < CASE WHEN open_price > close_price THEN open_price ELSE close_price END OR
            low_price > CASE WHEN open_price < close_price THEN open_price ELSE close_price END OR
            open_price <= 0 OR high_price <= 0 OR low_price <= 0 OR close_price <= 0
        )
        """
        
        db.cursor.execute(query, (instrument,))
        invalid_count = db.cursor.fetchone()[0]
        
        return {
            'check': 'Invalid OHLC Relationships',
            'passed': invalid_count == 0,
            'count': invalid_count,
            'message': f"Found {invalid_count} invalid OHLC candles" if invalid_count > 0 else "No invalid OHLC relationships"
        }
    
    def _check_extreme_outliers(self, db: FuturesDB, instrument: str) -> Dict[str, Any]:
        """Check for extreme price outliers"""
        # Define reasonable ranges per instrument
        ranges = {
            'MNQ': {'min': 10000, 'max': 30000, 'max_range_pct': 8},
            'MES': {'min': 3000, 'max': 6000, 'max_range_pct': 8},
            'ES': {'min': 3000, 'max': 6000, 'max_range_pct': 8},
            'NQ': {'min': 10000, 'max': 30000, 'max_range_pct': 8}
        }
        
        range_config = ranges.get(instrument, {'min': 100, 'max': 100000, 'max_range_pct': 20})
        
        query = """
        SELECT COUNT(*) FROM ohlc_data 
        WHERE instrument = ? AND (
            high_price > ? OR 
            low_price < ? OR 
            (high_price - low_price) / low_price * 100 > ?
        )
        """
        
        db.cursor.execute(query, (
            instrument, 
            range_config['max'], 
            range_config['min'], 
            range_config['max_range_pct']
        ))
        outlier_count = db.cursor.fetchone()[0]
        
        return {
            'check': 'Extreme Price Outliers',
            'passed': outlier_count == 0,
            'count': outlier_count,
            'message': f"Found {outlier_count} extreme outliers" if outlier_count > 0 else "No extreme price outliers"
        }
    
    def _check_volume_issues(self, db: FuturesDB, instrument: str) -> Dict[str, Any]:
        """Check for volume data issues"""
        query = """
        SELECT COUNT(*) FROM ohlc_data 
        WHERE instrument = ? AND (
            volume < 0 OR
            (volume = 0 AND timeframe IN ('1m', '5m'))
        )
        """
        
        db.cursor.execute(query, (instrument,))
        volume_issues = db.cursor.fetchone()[0]
        
        return {
            'check': 'Volume Data Quality',
            'passed': volume_issues == 0,
            'count': volume_issues,
            'message': f"Found {volume_issues} volume issues" if volume_issues > 0 else "Volume data looks good"
        }
    
    def _check_data_freshness(self, db: FuturesDB, instrument: str) -> Dict[str, Any]:
        """Check if data is reasonably fresh"""
        import time
        
        query = """
        SELECT MAX(timestamp) FROM ohlc_data 
        WHERE instrument = ? AND timeframe = '1h'
        """
        
        db.cursor.execute(query, (instrument,))
        result = db.cursor.fetchone()
        
        if not result or not result[0]:
            return {
                'check': 'Data Freshness',
                'passed': False,
                'message': "No data found for freshness check"
            }
        
        latest_timestamp = result[0]
        current_time = int(time.time())
        hours_old = (current_time - latest_timestamp) / 3600
        
        # Data should be less than 48 hours old for active instruments
        is_fresh = hours_old < 48
        
        return {
            'check': 'Data Freshness',
            'passed': is_fresh,
            'hours_old': round(hours_old, 1),
            'message': f"Data is {hours_old:.1f} hours old" + (" (fresh)" if is_fresh else " (stale)")
        }


def monitor_all_instruments() -> Dict[str, Any]:
    """Monitor data quality for all instruments in the database"""
    results = {}
    monitor = DataQualityMonitor()
    
    with FuturesDB() as db:
        # Get all unique instruments
        db.cursor.execute("SELECT DISTINCT instrument FROM ohlc_data")
        instruments = [row[0] for row in db.cursor.fetchall()]
    
    for instrument in instruments:
        logger.info(f"Monitoring {instrument}...")
        results[instrument] = monitor.monitor_instrument(instrument)
    
    return results


def main():
    """Main monitoring function"""
    print("📊 Data Quality Monitor")
    print("=" * 60)
    
    # Monitor all instruments
    results = monitor_all_instruments()
    
    # Display results
    for instrument, result in results.items():
        print(f"\n🔍 {instrument}")
        print("-" * 40)
        print(f"Quality Score: {result['quality_score']}")
        print(f"Summary: {result['summary']}")
        
        if result['issues']:
            print("Issues found:")
            for issue in result['issues']:
                status = "❌" if not issue['passed'] else "✅"
                print(f"  {status} {issue['check']}: {issue['message']}")
    
    # Overall summary
    total_instruments = len(results)
    excellent_count = sum(1 for r in results.values() if r['quality_score'] == 'EXCELLENT')
    
    print(f"\n📋 OVERALL SUMMARY")
    print("=" * 60)
    print(f"Instruments monitored: {total_instruments}")
    print(f"Excellent quality: {excellent_count}/{total_instruments}")
    
    if excellent_count == total_instruments:
        print("🎉 All instruments have excellent data quality!")
    elif excellent_count > total_instruments * 0.8:
        print("✅ Most instruments have good data quality")
    else:
        print("⚠️ Some instruments need data quality attention")


if __name__ == "__main__":
    main()