#!/usr/bin/env python3
"""
Data Format Migration Script
Converts Long/Short values to Buy/Sell in the trades table for position building compatibility
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config
from database_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataFormatMigration:
    """Handle migration of side_of_market values from Long/Short to Buy/Sell"""
    
    def __init__(self):
        self.db_path = config.db_path
        self.backup_created = False
        
    def create_backup(self) -> str:
        """Create a backup of the database before migration"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = str(self.db_path).replace('.db', f'_migration_backup_{timestamp}.db')
        
        try:
            import shutil
            shutil.copy2(str(self.db_path), backup_path)
            logger.info(f"Database backup created: {backup_path}")
            self.backup_created = True
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise
    
    def analyze_data(self) -> dict:
        """Analyze current data format distribution"""
        logger.info("Analyzing current data format distribution...")
        
        with DatabaseManager() as db:
            # Get count by side_of_market
            query = """
            SELECT 
                side_of_market,
                COUNT(*) as count,
                MIN(entry_time) as earliest,
                MAX(entry_time) as latest
            FROM trades 
            GROUP BY side_of_market
            ORDER BY count DESC
            """
            
            results = db._execute_with_monitoring(query)
            
            analysis = {}
            total_records = 0
            
            for row in results:
                side = row[0]
                count = row[1]
                earliest = row[2]
                latest = row[3]
                
                analysis[side] = {
                    'count': count,
                    'earliest': earliest,
                    'latest': latest
                }
                total_records += count
                
                logger.info(f"  {side}: {count} records ({earliest} to {latest})")
            
            analysis['total'] = total_records
            logger.info(f"Total records: {total_records}")
            
            return analysis
    
    def validate_migration_plan(self, analysis: dict) -> bool:
        """Validate that migration plan is safe"""
        logger.info("Validating migration plan...")
        
        # Check if we have records to migrate
        long_count = analysis.get('Long', {}).get('count', 0)
        short_count = analysis.get('Short', {}).get('count', 0)
        
        if long_count == 0 and short_count == 0:
            logger.warning("No Long/Short records found to migrate")
            return False
            
        # Check if Buy/Sell already exist (should not conflict)
        buy_count = analysis.get('Buy', {}).get('count', 0)
        sell_count = analysis.get('Sell', {}).get('count', 0)
        
        logger.info(f"Migration plan:")
        logger.info(f"  Convert {long_count} 'Long' records to 'Buy'")
        logger.info(f"  Convert {short_count} 'Short' records to 'Sell'")
        logger.info(f"  Existing 'Buy' records: {buy_count} (will remain unchanged)")
        logger.info(f"  Existing 'Sell' records: {sell_count} (will remain unchanged)")
        
        return True
    
    def perform_migration(self) -> dict:
        """Perform the actual data migration"""
        logger.info("Starting data migration...")
        
        migration_results = {
            'long_to_buy': 0,
            'short_to_sell': 0,
            'errors': []
        }
        
        try:
            with DatabaseManager() as db:
                # Convert Long to Buy
                logger.info("Converting 'Long' to 'Buy'...")
                long_result = db._execute_with_monitoring(
                    "UPDATE trades SET side_of_market = 'Buy' WHERE side_of_market = 'Long'"
                )
                
                # Get affected rows count
                long_count = db._execute_with_monitoring(
                    "SELECT changes()"
                )[0][0]
                migration_results['long_to_buy'] = long_count
                logger.info(f"  Converted {long_count} 'Long' records to 'Buy'")
                
                # Convert Short to Sell  
                logger.info("Converting 'Short' to 'Sell'...")
                short_result = db._execute_with_monitoring(
                    "UPDATE trades SET side_of_market = 'Sell' WHERE side_of_market = 'Short'"
                )
                
                # Get affected rows count
                short_count = db._execute_with_monitoring(
                    "SELECT changes()"
                )[0][0]
                migration_results['short_to_sell'] = short_count
                logger.info(f"  Converted {short_count} 'Short' records to 'Sell'")
                
        except Exception as e:
            error_msg = f"Migration failed: {e}"
            logger.error(error_msg)
            migration_results['errors'].append(error_msg)
            raise
        
        total_migrated = migration_results['long_to_buy'] + migration_results['short_to_sell']
        logger.info(f"Migration completed successfully. Total records migrated: {total_migrated}")
        
        return migration_results
    
    def verify_migration(self) -> bool:
        """Verify migration was successful"""
        logger.info("Verifying migration results...")
        
        with DatabaseManager() as db:
            # Check remaining Long/Short records
            remaining_query = """
            SELECT side_of_market, COUNT(*) 
            FROM trades 
            WHERE side_of_market IN ('Long', 'Short')
            GROUP BY side_of_market
            """
            
            remaining_results = db._execute_with_monitoring(remaining_query)
            
            if remaining_results:
                logger.error("Migration verification FAILED - Long/Short records still exist:")
                for row in remaining_results:
                    logger.error(f"  {row[0]}: {row[1]} records")
                return False
            
            # Check final distribution
            final_query = """
            SELECT side_of_market, COUNT(*) 
            FROM trades 
            GROUP BY side_of_market
            ORDER BY COUNT(*) DESC
            """
            
            final_results = db._execute_with_monitoring(final_query)
            
            logger.info("Final data distribution:")
            for row in final_results:
                logger.info(f"  {row[0]}: {row[1]} records")
            
            # Verify only Buy/Sell exist
            valid_sides = {'Buy', 'Sell'}
            actual_sides = {row[0] for row in final_results}
            
            if not actual_sides.issubset(valid_sides):
                invalid_sides = actual_sides - valid_sides
                logger.error(f"Migration verification FAILED - Invalid side_of_market values: {invalid_sides}")
                return False
            
            logger.info("Migration verification PASSED - All records now use Buy/Sell format")
            return True
    
    def run_migration(self) -> bool:
        """Run the complete migration process"""
        logger.info("="*60)
        logger.info("DATA FORMAT MIGRATION STARTING")
        logger.info("="*60)
        
        try:
            # Step 1: Create backup
            backup_path = self.create_backup()
            
            # Step 2: Analyze current data
            analysis = self.analyze_data()
            
            # Step 3: Validate migration plan
            if not self.validate_migration_plan(analysis):
                logger.info("Migration not needed or not safe to proceed")
                return True
            
            # Step 4: Perform migration
            migration_results = self.perform_migration()
            
            # Step 5: Verify migration
            if not self.verify_migration():
                logger.error("Migration verification failed!")
                return False
            
            # Step 6: Summary
            logger.info("="*60)
            logger.info("DATA FORMAT MIGRATION COMPLETED SUCCESSFULLY")
            logger.info("="*60)
            logger.info(f"Backup created: {backup_path}")
            logger.info(f"Records migrated: {migration_results['long_to_buy'] + migration_results['short_to_sell']}")
            logger.info("All trades now use Buy/Sell format for position building compatibility")
            
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            if self.backup_created:
                logger.info(f"Database backup available for rollback")
            return False

def main():
    """Main entry point"""
    print("Data Format Migration Tool")
    print("Converts Long/Short to Buy/Sell in trades table")
    print()
    
    # Confirm with user
    response = input("This will modify the database. Continue? (y/N): ").strip().lower()
    if response != 'y':
        print("Migration cancelled by user")
        return
    
    migration = DataFormatMigration()
    success = migration.run_migration()
    
    if success:
        print("\n✅ Migration completed successfully!")
        print("You can now rebuild positions with the corrected data.")
    else:
        print("\n❌ Migration failed!")
        print("Check the logs and backup files.")
        sys.exit(1)

if __name__ == '__main__':
    main()