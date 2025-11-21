#!/usr/bin/env python3
"""Add deduplication method to enhanced_position_service_v2.py"""

file_path = r"c:\Projects\FuturesTradingLog\services\enhanced_position_service_v2.py"

dedup_method = '''    def _deduplicate_trades(self, trades: List[Dict]) -> List[Dict]:
        """
        Deduplicate trades that have the same entry_time, side_of_market, and entry_price.
        Sum quantities for duplicates and keep the first trade ID.
        """
        from collections import defaultdict
        from datetime import datetime

        # Group trades by (entry_time, side, entry_price)
        trade_groups = defaultdict(list)
        for trade in trades:
            key = (
                trade['entry_time'],
                trade['side_of_market'],
                trade.get('entry_price')
            )
            trade_groups[key].append(trade)

        # Deduplicate by summing quantities
        deduped_trades = []
        for key, group in trade_groups.items():
            if len(group) == 1:
                deduped_trades.append(group[0])
            else:
                # Multiple trades with same timestamp/price/side - sum quantities
                base_trade = group[0].copy()
                total_qty = sum(t['quantity'] for t in group)
                base_trade['quantity'] = total_qty

                logger.info(f"Deduped {len(group)} trades at {key[0]} into 1 trade with qty={total_qty}")
                deduped_trades.append(base_trade)

        return deduped_trades

'''

# Read the file
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find where to insert the method (before _process_trades_for_instrument)
insert_pos = content.find('    def _process_trades_for_instrument(')

if insert_pos == -1:
    print("ERROR: Could not find _process_trades_for_instrument method")
    exit(1)

# Insert the deduplication method
new_content = content[:insert_pos] + dedup_method + '\n' + content[insert_pos:]

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Successfully added _deduplicate_trades method")
