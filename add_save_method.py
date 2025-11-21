#!/usr/bin/env python3
"""Add _save_position_to_db method to enhanced_position_service_v2.py"""

file_path = "c:/Projects/FuturesTradingLog/services/enhanced_position_service_v2.py"

method_code = '''
    def _save_position_to_db(self, position) -> Optional[int]:
        """Save a Position domain object to the database"""
        try:
            # Insert position record
            self.cursor.execute("""
                INSERT INTO positions (
                    instrument, account, position_type, entry_time, exit_time,
                    total_quantity, average_entry_price, average_exit_price,
                    total_points_pnl, total_dollars_pnl, total_commission,
                    position_status, execution_count, max_quantity, risk_reward_ratio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position.instrument,
                position.account,
                position.position_type.value,  # Convert enum to string
                position.entry_time,
                position.exit_time,
                position.total_quantity,
                position.average_entry_price,
                position.average_exit_price,
                position.total_points_pnl,
                position.total_dollars_pnl,
                position.total_commission,
                position.position_status.value,  # Convert enum to string
                position.execution_count,
                position.max_quantity,
                position.risk_reward_ratio
            ))

            position_id = self.cursor.lastrowid
            logger.debug(f"Saved position {position_id} to database")

            return position_id

        except Exception as e:
            logger.error(f"Failed to save position to database: {e}")
            return None

'''

# Read the file
with open(file_path, 'r') as f:
    content = f.read()

# Find the location after _process_trades_for_instrument method
insert_marker = "            return {\n                'positions_created': 0,\n                'validation_errors': [error_msg]\n            }\n    \n    def _create_position_from_trade"

if insert_marker in content:
    # Insert the method
    content = content.replace(insert_marker, f"{insert_marker.replace('def _create_position_from_trade', method_code + 'def _create_position_from_trade')}")

    # Write back
    with open(file_path, 'w') as f:
        f.write(content)

    print("✓ Successfully added _save_position_to_db method")
else:
    print("✗ Could not find insertion point")
