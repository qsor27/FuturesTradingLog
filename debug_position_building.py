#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('/home/qadmin/FuturesTradingLog/data/db/futures_trades.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute('''
SELECT * FROM trades 
WHERE deleted = 0 OR deleted IS NULL
ORDER BY account, instrument, id
''')
trades = [dict(row) for row in cursor.fetchall()]
print(f'Retrieved {len(trades)} total trades')

account_instrument_groups = {}
for trade in trades:
    account = (trade.get('account') or '').strip()
    instrument = (trade.get('instrument') or '').strip()
    
    if not account or not instrument:
        continue
        
    key = (account, instrument)
    if key not in account_instrument_groups:
        account_instrument_groups[key] = []
    account_instrument_groups[key].append(trade)

print(f'Found {len(account_instrument_groups)} account/instrument groups:')
total_individual = 0
for (account, instrument), group_trades in account_instrument_groups.items():
    individual_executions = []
    summary_records = 0
    
    for trade in group_trades:
        entry_time = trade.get('entry_time', '')
        exit_time = trade.get('exit_time', '')
        
        if entry_time != exit_time:
            individual_executions.append(trade)
        else:
            summary_records += 1
    
    print(f'  {account} / {instrument}: {len(group_trades)} total, {len(individual_executions)} individual, {summary_records} summary')
    total_individual += len(individual_executions)

print(f'Total individual executions that should be processed: {total_individual}')

conn.close()