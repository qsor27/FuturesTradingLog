#!/usr/bin/env python3
"""
OHLC Data Repair Tool
Comprehensive tool for cleaning and repairing problematic OHLC data
"""

import time
from datetime import datetime, timedelta
from TradingLog_db import FuturesDB
from typing import List, Dict, Any, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OHLCDataRepairer:
    def __init__(self, dry_run: bool = True):
        """
        Initialize data repairer
        
        Args:
            dry_run: If True, only analyze what would be repaired without making changes
        """
        self.dry_run = dry_run
        self.repair_log = []
        
    def repair_instrument_data(self, instrument: str = 'MNQ') -> Dict[str, Any]:
        """
        Comprehensive repair of OHLC data for an instrument
        
        Args:
            instrument: Instrument symbol to repair
            
        Returns:
            Dictionary with repair results and statistics
        """
        logger.info(f"Starting {'DRY RUN' if self.dry_run else 'LIVE'} repair for {instrument}")
        
        repair_results = {
            'instrument': instrument,
            'dry_run': self.dry_run,
            'repairs_applied': [],
            'statistics': {
                'invalid_ohlc_removed': 0,
                'extreme_outliers_removed': 0,
                'duplicate_timestamps_removed': 0,
                'volume_issues_fixed': 0,
                'price_gaps_smoothed': 0
            },
            'data_before': {},
            'data_after': {}
        }
        
        with FuturesDB() as db:
            # Get initial statistics
            repair_results['data_before'] = self._get_data_statistics(db, instrument)
            
            # 1. Remove invalid OHLC relationships
            invalid_count = self._remove_invalid_ohlc(db, instrument)
            repair_results['statistics']['invalid_ohlc_removed'] = invalid_count
            
            # 2. Remove extreme price outliers
            outlier_count = self._remove_extreme_outliers(db, instrument)
            repair_results['statistics']['extreme_outliers_removed'] = outlier_count
            
            # 3. Remove duplicate timestamps
            duplicate_count = self._remove_duplicate_timestamps(db, instrument)
            repair_results['statistics']['duplicate_timestamps_removed'] = duplicate_count
            
            # 4. Fix volume issues
            volume_fixes = self._fix_volume_issues(db, instrument)
            repair_results['statistics']['volume_issues_fixed'] = volume_fixes
            
            # 5. Smooth extreme price gaps (optional - be careful!)
            # gap_fixes = self._smooth_price_gaps(db, instrument, max_gap_percent=15)
            # repair_results['statistics']['price_gaps_smoothed'] = gap_fixes
            
            # Get final statistics
            repair_results['data_after'] = self._get_data_statistics(db, instrument)
            
            # Commit changes if not dry run
            if not self.dry_run:
                db.conn.commit()
                logger.info("✅ Repair changes committed to database")
            else:
                db.conn.rollback()
                logger.info("🔍 Dry run complete - no changes made")
        
        return repair_results
    
    def _get_data_statistics(self, db: FuturesDB, instrument: str) -> Dict[str, Any]:
        """Get current data statistics for an instrument"""
        stats = {}
        
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        for tf in timeframes:
            count = db.get_ohlc_count(instrument, tf)
            stats[tf] = count
        
        # Get total record count
        db.cursor.execute(
            "SELECT COUNT(*) FROM ohlc_data WHERE instrument = ?",
            (instrument,)
        )
        stats['total'] = db.cursor.fetchone()[0]
        
        # Get date range
        db.cursor.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM ohlc_data WHERE instrument = ?",
            (instrument,)
        )
        result = db.cursor.fetchone()
        if result and result[0] and result[1]:
            stats['date_range'] = {
                'start': datetime.fromtimestamp(result[0]).isoformat(),
                'end': datetime.fromtimestamp(result[1]).isoformat()
            }
        
        return stats
    
    def _remove_invalid_ohlc(self, db: FuturesDB, instrument: str) -> int:
        """Remove candles with invalid OHLC relationships"""
        logger.info("🔍 Checking for invalid OHLC relationships...")
        
        # First, find invalid candles
        invalid_queries = [
            # High < Low (impossible)
            "SELECT COUNT(*) FROM ohlc_data WHERE instrument = ? AND high_price < low_price",
            
            # High < max(Open, Close) (impossible)
            """SELECT COUNT(*) FROM ohlc_data 
               WHERE instrument = ? AND high_price < CASE 
                   WHEN open_price > close_price THEN open_price 
                   ELSE close_price 
               END""",
            
            # Low > min(Open, Close) (impossible)
            """SELECT COUNT(*) FROM ohlc_data 
               WHERE instrument = ? AND low_price > CASE 
                   WHEN open_price < close_price THEN open_price 
                   ELSE close_price 
               END""",
            
            # Prices <= 0 (invalid)
            """SELECT COUNT(*) FROM ohlc_data 
               WHERE instrument = ? AND (
                   open_price <= 0 OR high_price <= 0 OR 
                   low_price <= 0 OR close_price <= 0
               )"""
        ]
        
        total_invalid = 0
        for query in invalid_queries:
            db.cursor.execute(query, (instrument,))
            count = db.cursor.fetchone()[0]
            total_invalid += count
        
        if total_invalid > 0:
            logger.warning(f"Found {total_invalid} invalid OHLC candles")
            self.repair_log.append(f"Invalid OHLC candles: {total_invalid}")
            
            if not self.dry_run:
                # Remove all invalid OHLC relationships
                delete_query = """
                DELETE FROM ohlc_data 
                WHERE instrument = ? AND (
                    high_price < low_price OR
                    high_price < CASE WHEN open_price > close_price THEN open_price ELSE close_price END OR
                    low_price > CASE WHEN open_price < close_price THEN open_price ELSE close_price END OR
                    open_price <= 0 OR high_price <= 0 OR low_price <= 0 OR close_price <= 0
                )
                """
                db.cursor.execute(delete_query, (instrument,))
                removed = db.cursor.rowcount
                logger.info(f"✅ Removed {removed} invalid OHLC candles")
                return removed
        else:
            logger.info("✅ No invalid OHLC relationships found")
        
        return total_invalid
    
    def _remove_extreme_outliers(self, db: FuturesDB, instrument: str) -> int:
        """Remove candles with extreme price outliers"""
        logger.info("🔍 Checking for extreme price outliers...")
        
        # Define reasonable price ranges for common instruments
        price_ranges = {
            'MNQ': {'min': 10000, 'max': 30000, 'max_range_pct': 8},  # NASDAQ Mini
            'MES': {'min': 3000, 'max': 6000, 'max_range_pct': 8},    # S&P Mini
            'ES': {'min': 3000, 'max': 6000, 'max_range_pct': 8},     # S&P Standard
            'NQ': {'min': 10000, 'max': 30000, 'max_range_pct': 8}    # NASDAQ Standard
        }
        
        # Use default ranges if instrument not in list
        ranges = price_ranges.get(instrument, {'min': 100, 'max': 100000, 'max_range_pct': 20})
        
        # Find outliers
        outlier_query = """
        SELECT COUNT(*) FROM ohlc_data 
        WHERE instrument = ? AND (
            high_price > ? OR 
            low_price < ? OR 
            (high_price - low_price) / low_price * 100 > ?
        )
        """
        
        db.cursor.execute(outlier_query, (
            instrument, 
            ranges['max'], 
            ranges['min'], 
            ranges['max_range_pct']
        ))
        
        outlier_count = db.cursor.fetchone()[0]
        
        if outlier_count > 0:
            logger.warning(f"Found {outlier_count} extreme price outliers")
            self.repair_log.append(f"Extreme outliers: {outlier_count}")
            
            if not self.dry_run:
                delete_query = """
                DELETE FROM ohlc_data 
                WHERE instrument = ? AND (
                    high_price > ? OR 
                    low_price < ? OR 
                    (high_price - low_price) / low_price * 100 > ?
                )
                """
                db.cursor.execute(delete_query, (
                    instrument, 
                    ranges['max'], 
                    ranges['min'], 
                    ranges['max_range_pct']
                ))
                removed = db.cursor.rowcount
                logger.info(f"✅ Removed {removed} extreme outlier candles")
                return removed
        else:
            logger.info("✅ No extreme price outliers found")
        
        return outlier_count
    
    def _remove_duplicate_timestamps(self, db: FuturesDB, instrument: str) -> int:
        """Remove duplicate timestamp entries"""
        logger.info("🔍 Checking for duplicate timestamps...")
        
        # Find duplicates
        duplicate_query = """
        SELECT instrument, timeframe, timestamp, COUNT(*) as dup_count
        FROM ohlc_data 
        WHERE instrument = ?
        GROUP BY instrument, timeframe, timestamp
        HAVING COUNT(*) > 1
        """
        
        db.cursor.execute(duplicate_query, (instrument,))
        duplicates = db.cursor.fetchall()
        
        total_duplicates = sum(row[3] - 1 for row in duplicates)  # Keep 1, remove the rest
        
        if total_duplicates > 0:
            logger.warning(f"Found {total_duplicates} duplicate timestamp entries")
            self.repair_log.append(f"Duplicate timestamps: {total_duplicates}")
            
            if not self.dry_run:
                # Remove duplicates, keeping the one with the highest id (most recent)
                for dup in duplicates:
                    delete_query = """
                    DELETE FROM ohlc_data 
                    WHERE instrument = ? AND timeframe = ? AND timestamp = ?
                    AND id NOT IN (
                        SELECT MAX(id) FROM ohlc_data 
                        WHERE instrument = ? AND timeframe = ? AND timestamp = ?
                    )
                    """
                    db.cursor.execute(delete_query, (
                        dup[0], dup[1], dup[2], dup[0], dup[1], dup[2]
                    ))
                
                removed = db.cursor.rowcount
                logger.info(f"✅ Removed {removed} duplicate entries")
                return removed
        else:
            logger.info("✅ No duplicate timestamps found")
        
        return total_duplicates
    
    def _fix_volume_issues(self, db: FuturesDB, instrument: str) -> int:
        """Fix volume-related issues"""
        logger.info("🔍 Checking for volume issues...")
        
        # Find volume issues
        volume_query = """
        SELECT COUNT(*) FROM ohlc_data 
        WHERE instrument = ? AND (
            volume < 0 OR
            (volume = 0 AND timeframe IN ('1m', '5m'))
        )
        """
        
        db.cursor.execute(volume_query, (instrument,))
        volume_issues = db.cursor.fetchone()[0]
        
        if volume_issues > 0:
            logger.warning(f"Found {volume_issues} volume issues")
            self.repair_log.append(f"Volume issues: {volume_issues}")
            
            if not self.dry_run:
                # Fix negative volumes (set to 0)
                fix_negative_query = """
                UPDATE ohlc_data 
                SET volume = 0 
                WHERE instrument = ? AND volume < 0
                """
                db.cursor.execute(fix_negative_query, (instrument,))
                
                # For short timeframes with 0 volume, set to 1 (minimal volume)
                fix_zero_query = """
                UPDATE ohlc_data 
                SET volume = 1 
                WHERE instrument = ? AND volume = 0 AND timeframe IN ('1m', '5m')
                """
                db.cursor.execute(fix_zero_query, (instrument,))
                
                fixed = db.cursor.rowcount
                logger.info(f"✅ Fixed {fixed} volume issues")
                return fixed
        else:
            logger.info("✅ No volume issues found")
        
        return volume_issues
    
    def _smooth_price_gaps(self, db: FuturesDB, instrument: str, max_gap_percent: float = 10) -> int:
        """
        EXPERIMENTAL: Smooth extreme price gaps between consecutive candles
        WARNING: This modifies actual price data - use with extreme caution!
        """
        logger.warning("⚠️  EXPERIMENTAL: Price gap smoothing - modifies actual price data!")
        
        if self.dry_run:
            logger.info("🔍 Analyzing price gaps (dry run)")
            # TODO: Implement gap analysis
            return 0
        
        # For now, return 0 - this feature needs careful implementation
        logger.info("Price gap smoothing not implemented - too risky for automatic repair")
        return 0
    
    def generate_repair_report(self, results: Dict[str, Any]) -> str:
        """Generate a comprehensive repair report"""
        report = []
        report.append("=" * 80)
        report.append(f"OHLC DATA REPAIR REPORT - {results['instrument']}")
        report.append("=" * 80)
        report.append(f"Mode: {'DRY RUN' if results['dry_run'] else 'LIVE REPAIR'}")
        report.append(f"Timestamp: {datetime.now().isoformat()}")
        report.append("")
        
        # Statistics comparison
        report.append("📊 DATA STATISTICS")
        report.append("-" * 40)
        before = results['data_before']
        after = results['data_after']
        
        report.append(f"Total Records: {before.get('total', 0)} → {after.get('total', 0)}")
        
        for tf in ['1m', '5m', '15m', '1h', '4h', '1d']:
            b_count = before.get(tf, 0)
            a_count = after.get(tf, 0)
            if b_count != a_count:
                report.append(f"{tf:>3} timeframe: {b_count} → {a_count} ({a_count - b_count:+d})")
        
        report.append("")
        
        # Repairs applied
        report.append("🔧 REPAIRS APPLIED")
        report.append("-" * 40)
        stats = results['statistics']
        
        for repair_type, count in stats.items():
            if count > 0:
                report.append(f"• {repair_type.replace('_', ' ').title()}: {count}")
        
        if not any(stats.values()):
            report.append("• No repairs needed - data quality is good!")
        
        report.append("")
        
        # Recommendations
        report.append("💡 RECOMMENDATIONS")
        report.append("-" * 40)
        
        total_removed = stats['invalid_ohlc_removed'] + stats['extreme_outliers_removed']
        
        if total_removed > 100:
            report.append("⚠️  WARNING: Large number of records removed - review data source quality")
        elif total_removed > 0:
            report.append("ℹ️  INFO: Some problematic records removed - monitor data source")
        else:
            report.append("✅ EXCELLENT: No data quality issues found")
        
        if results['dry_run']:
            report.append("🔄 NEXT STEP: Run with dry_run=False to apply repairs")
        else:
            report.append("✅ COMPLETE: Repairs have been applied to the database")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)


def main():
    """Main repair function with user interaction"""
    print("🔧 OHLC Data Repair Tool")
    print("=" * 60)
    
    # Get instrument to repair
    instrument = input("Enter instrument to repair (default: MNQ): ").strip() or "MNQ"
    
    # Ask for repair mode
    print("\nRepair modes:")
    print("1. Dry Run (analyze only, no changes)")
    print("2. Live Repair (apply fixes to database)")
    
    mode = input("Select mode (1 or 2, default: 1): ").strip() or "1"
    dry_run = mode == "1"
    
    if not dry_run:
        confirm = input("\n⚠️  This will modify your database. Continue? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("❌ Repair cancelled")
            return
    
    # Run repair
    print(f"\n🚀 Starting {'dry run analysis' if dry_run else 'live repair'} for {instrument}...")
    
    repairer = OHLCDataRepairer(dry_run=dry_run)
    results = repairer.repair_instrument_data(instrument)
    
    # Generate and display report
    report = repairer.generate_repair_report(results)
    print("\n" + report)
    
    # Save report to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"repair_report_{instrument}_{timestamp}.txt"
    
    with open(filename, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Report saved to: {filename}")
    
    return results


if __name__ == "__main__":
    results = main()