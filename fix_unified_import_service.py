"""
Fix UnifiedCSVImportService to handle TradeValidation column

This script adds the missing trade_validation support to the import process.
"""

import os
import shutil
from datetime import datetime

# Backup the original file
source_file = 'services/unified_csv_import_service.py'
backup_file = f'services/unified_csv_import_service.py.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'

print(f"Creating backup: {backup_file}")
shutil.copy2(source_file, backup_file)

# Read the file
with open(source_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the _process_csv_file method and modify it to extract TradeValidation
old_process_trades_call = '''                processed_trades = process_trades(df, self.multipliers)
                processed_count = len(processed_trades)
                self.logger.info(
                    f"Processed {processed_count} trades from execution file {file_path.name} "
                    f"({csv_row_count} CSV rows → {processed_count} executions)"
                )'''

new_process_trades_call = '''                # Extract TradeValidation column if present
                validation_map = {}
                if 'TradeValidation' in df.columns:
                    self.logger.info(f"TradeValidation column detected in {file_path.name}")
                    for _, row in df.iterrows():
                        exec_id = row.get('ID')
                        val = str(row.get('TradeValidation', '')).strip()
                        if exec_id and val in ('Valid', 'Invalid'):
                            validation_map[exec_id] = val
                    self.logger.info(f"Extracted {len(validation_map)} validation entries from CSV")

                processed_trades = process_trades(df, self.multipliers)
                processed_count = len(processed_trades)

                # Add trade_validation to each execution
                if validation_map:
                    for trade in processed_trades:
                        exec_id = trade.get('execution_id')
                        if exec_id in validation_map:
                            trade['trade_validation'] = validation_map[exec_id]
                            self.logger.debug(f"Added validation '{validation_map[exec_id]}' to execution {exec_id}")

                self.logger.info(
                    f"Processed {processed_count} trades from execution file {file_path.name} "
                    f"({csv_row_count} CSV rows → {processed_count} executions)"
                )'''

if old_process_trades_call in content:
    content = content.replace(old_process_trades_call, new_process_trades_call)
    print("[OK] Modified _process_csv_file to extract TradeValidation")
else:
    print("[WARN] Could not find process_trades call to modify")

# Modify _import_trades_to_database to handle trade_validation
old_trade_data = '''                    if is_individual_execution:
                        # New format: Individual execution
                        trade_data = {
                            'instrument': trade.get('Instrument', ''),
                            'side_of_market': trade.get('action', ''),  # Buy/Sell
                            'quantity': trade.get('quantity', 0),
                            'entry_price': trade.get('entry_price', None),
                            'entry_time': trade.get('entry_time', None),
                            'exit_time': trade.get('exit_time', None),
                            'exit_price': trade.get('exit_price', None),
                            'points_gain_loss': None,  # Position builder calculates this
                            'dollars_gain_loss': None,  # Position builder calculates this
                            'entry_execution_id': trade.get('execution_id', ''),
                            'commission': trade.get('commission', 0.0),
                            'account': trade.get('Account', ''),
                            'import_batch_id': self.current_import_batch_id
                        }'''

new_trade_data = '''                    if is_individual_execution:
                        # New format: Individual execution
                        trade_data = {
                            'instrument': trade.get('Instrument', ''),
                            'side_of_market': trade.get('action', ''),  # Buy/Sell
                            'quantity': trade.get('quantity', 0),
                            'entry_price': trade.get('entry_price', None),
                            'entry_time': trade.get('entry_time', None),
                            'exit_time': trade.get('exit_time', None),
                            'exit_price': trade.get('exit_price', None),
                            'points_gain_loss': None,  # Position builder calculates this
                            'dollars_gain_loss': None,  # Position builder calculates this
                            'entry_execution_id': trade.get('execution_id', ''),
                            'commission': trade.get('commission', 0.0),
                            'account': trade.get('Account', ''),
                            'import_batch_id': self.current_import_batch_id,
                            'trade_validation': trade.get('trade_validation', None)  # Add validation!
                        }'''

if old_trade_data in content:
    content = content.replace(old_trade_data, new_trade_data)
    print("[OK] Modified _import_trades_to_database to include trade_validation")
else:
    print("[WARN] Could not find trade_data to modify")

# Write the modified content
with open(source_file, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n[SUCCESS] UnifiedCSVImportService has been enhanced to support TradeValidation!")
print(f"   Backup saved to: {backup_file}")
print("\nNext steps:")
print("1. Restart Docker: docker-compose restart")
print("2. Reimport CSV files to populate database")
print("3. Check validation data appears in web interface")
