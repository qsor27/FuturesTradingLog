#!/usr/bin/env python3
"""Fix position builder to correctly track running quantity and handle open positions"""

import re

file_path = r"c:\Projects\FuturesTradingLog\domain\services\position_builder.py"

# Read the file
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Update position_modify to track running quantity
old_modify = '''            elif event.event_type == 'position_modify':
                # Modifying existing position
                if current_position:
                    current_executions.append(event.trade)
                    current_position.max_quantity = max(current_position.max_quantity, abs(event.running_quantity))
                    current_position.execution_count = len(current_executions)

                    if abs(event.running_quantity) > abs(event.previous_quantity):
                        logger.info(f"Added to {current_position.position_type.value} position")
                    else:
                        logger.info(f"Reduced {current_position.position_type.value} position")'''

new_modify = '''            elif event.event_type == 'position_modify':
                # Modifying existing position
                if current_position:
                    current_executions.append(event.trade)
                    current_position.total_quantity = abs(event.running_quantity)  # Update running quantity
                    current_position.max_quantity = max(current_position.max_quantity, abs(event.running_quantity))
                    current_position.execution_count = len(current_executions)

                    if abs(event.running_quantity) > abs(event.previous_quantity):
                        logger.info(f"Added to {current_position.position_type.value} position (qty: {abs(event.running_quantity)})")
                    else:
                        logger.info(f"Reduced {current_position.position_type.value} position (qty: {abs(event.running_quantity)})")'''

content = content.replace(old_modify, new_modify)

# Fix 2: Update _calculate_position_totals_from_executions to handle open positions
old_calc = '''    def _calculate_position_totals_from_executions(self, position: Position, executions: List[Trade]):
        """Calculate position totals from aggregated executions using FIFO methodology"""
        if not executions:
            return

        # Set actual entry and exit times from first and last executions
        sorted_executions = sorted(executions, key=lambda x: x.entry_time or datetime.min)
        position.entry_time = sorted_executions[0].entry_time

        # For closed positions, set exit time to the last execution
        if position.position_status == PositionStatus.CLOSED:
            position.exit_time = sorted_executions[-1].entry_time

        # Calculate P&L using the PnL calculator
        pnl_result = self.pnl_calculator.calculate_position_pnl(position, executions)

        position.average_entry_price = pnl_result.average_entry_price
        position.average_exit_price = pnl_result.average_exit_price
        position.total_points_pnl = pnl_result.points_pnl
        position.total_dollars_pnl = pnl_result.dollars_pnl
        position.total_commission = sum(t.commission for t in executions)

        # Calculate risk/reward ratio
        if position.total_dollars_pnl != 0 and position.total_commission > 0:
            if position.total_dollars_pnl > 0:
                position.risk_reward_ratio = abs(position.total_dollars_pnl) / position.total_commission
            else:
                position.risk_reward_ratio = position.total_commission / abs(position.total_dollars_pnl)
        else:
            position.risk_reward_ratio = 0.0'''

new_calc = '''    def _calculate_position_totals_from_executions(self, position: Position, executions: List[Trade]):
        """Calculate position totals from aggregated executions using FIFO methodology"""
        if not executions:
            return

        # Set actual entry and exit times from first and last executions
        sorted_executions = sorted(executions, key=lambda x: x.entry_time or datetime.min)
        position.entry_time = sorted_executions[0].entry_time

        # For closed positions, set exit time to the last execution
        if position.position_status == PositionStatus.CLOSED:
            position.exit_time = sorted_executions[-1].entry_time

        # Calculate P&L using the PnL calculator (only for closed positions)
        if position.position_status == PositionStatus.CLOSED:
            pnl_result = self.pnl_calculator.calculate_position_pnl(position, executions)

            position.average_entry_price = pnl_result.average_entry_price
            position.average_exit_price = pnl_result.average_exit_price
            position.total_points_pnl = pnl_result.points_pnl
            position.total_dollars_pnl = pnl_result.dollars_pnl

            # Calculate risk/reward ratio
            if position.total_dollars_pnl != 0 and position.total_commission > 0:
                if position.total_dollars_pnl > 0:
                    position.risk_reward_ratio = abs(position.total_dollars_pnl) / position.total_commission
                else:
                    position.risk_reward_ratio = position.total_commission / abs(position.total_dollars_pnl)
            else:
                position.risk_reward_ratio = 0.0
        else:
            # Open position: calculate average entry price only
            entry_executions = [e for e in executions if self._is_entry_execution(position, e)]
            if entry_executions:
                total_entry_value = sum(e.entry_price * e.quantity for e in entry_executions)
                total_entry_quantity = sum(e.quantity for e in entry_executions)
                position.average_entry_price = total_entry_value / total_entry_quantity if total_entry_quantity > 0 else 0.0
            else:
                position.average_entry_price = 0.0

            # For open positions, exit price and P&L should be None/0
            position.average_exit_price = None
            position.total_points_pnl = 0.0
            position.total_dollars_pnl = 0.0
            position.risk_reward_ratio = 0.0

        position.total_commission = sum(t.commission for t in executions)

    def _is_entry_execution(self, position: Position, execution: Trade) -> bool:
        """Determine if an execution is an entry (increases position) or exit (decreases position)"""
        from ..models.trade import MarketSide
        from ..models.position import PositionType

        if position.position_type == PositionType.LONG:
            return execution.side_of_market in [MarketSide.BUY, MarketSide.BUY_TO_COVER, MarketSide.LONG]
        else:  # SHORT
            return execution.side_of_market in [MarketSide.SELL, MarketSide.SELL_SHORT, MarketSide.SHORT]'''

content = content.replace(old_calc, new_calc)

# Write the file back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully updated position_builder.py:")
print("✓ Fixed position_modify to track running quantity in total_quantity")
print("✓ Updated _calculate_position_totals_from_executions to handle open positions")
print("✓ Set average_exit_price to None for open positions")
print("✓ Added _is_entry_execution helper method")
