#!/usr/bin/env python3
"""Update _deduplicate_trades method to use entry_execution_id"""

file_path = r"c:\Projects\FuturesTradingLog\services\enhanced_position_service_v2.py"

new_method = '''    def _deduplicate_trades(self, trades: List[Dict]) -> List[Dict]:
        """
        Deduplicate trades by entry_execution_id (unique NinjaTrader execution identifier).

        NinjaTrader CSV imports often create multiple database records for the same execution,
        with quantities like [1,1,2,2] that need to be summed. The entry_execution_id uniquely
        identifies each real execution, so we group by this field and sum quantities.

        For trades without entry_execution_id, falls back to grouping by
        (entry_time, side_of_market, entry_price).

        Args:
            trades: List of trade dictionaries from database

        Returns:
            List of deduplicated trades with summed quantities
        """
        from collections import defaultdict

        # Group trades by entry_execution_id (or fallback key)
        trade_groups = defaultdict(list)

        for trade in trades:
            exec_id = trade.get('entry_execution_id')

            if exec_id:
                # Use execution ID as primary grouping key
                key = f"EXEC_{exec_id}"
            else:
                # Fallback to timestamp/price/side for trades without execution ID
                key = f"FALLBACK_{trade['entry_time']}_{trade['side_of_market']}_{trade.get('entry_price')}"

            trade_groups[key].append(trade)

        # Deduplicate by summing quantities within each group
        deduped_trades = []
        duplicates_found = 0

        for key, group in trade_groups.items():
            if len(group) == 1:
                # No duplicates for this execution
                deduped_trades.append(group[0])
            else:
                # Multiple trades with same execution ID - sum quantities
                base_trade = group[0].copy()
                total_qty = sum(t['quantity'] for t in group)
                base_trade['quantity'] = total_qty

                exec_id = group[0].get('entry_execution_id', 'N/A')
                logger.info(f"Deduped {len(group)} trades with execution_id={exec_id} into 1 trade with qty={total_qty}")

                duplicates_found += len(group) - 1
                deduped_trades.append(base_trade)

        if duplicates_found > 0:
            logger.info(f"Deduplication summary: removed {duplicates_found} duplicate trade records")

        return deduped_trades

'''

# Read the file
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the old method
import re
pattern = r'    def _deduplicate_trades\(self, trades: List\[Dict\]\) -> List\[Dict\]:.*?return deduped_trades\n'

match = re.search(pattern, content, re.DOTALL)
if not match:
    print("ERROR: Could not find _deduplicate_trades method")
    exit(1)

# Replace with new method
new_content = content.replace(match.group(0), new_method)

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Successfully updated _deduplicate_trades method to use entry_execution_id")
