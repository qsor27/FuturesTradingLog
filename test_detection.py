import sqlite3
conn = sqlite3.connect('data/db/futures_trades.db')
cursor = conn.cursor()

cursor.execute('SELECT entry_time, exit_time, entry_price, exit_price, dollars_gain_loss FROM trades WHERE DATE(entry_time) = "2025-07-07" LIMIT 5')
trades = cursor.fetchall()

print('Sample 07/07 trades:')
for trade in trades:
    entry_time, exit_time, entry_price, exit_price, dollars_gain_loss = trade
    print(f'Entry: {entry_time}, Exit: {exit_time}, P&L: {dollars_gain_loss}')
    
    # Test my logic
    if (entry_time and exit_time and entry_price and exit_price and entry_time != exit_time and dollars_gain_loss != 0):
        print('  -> DETECTED as completed trade')
    else:
        print('  -> NOT detected as completed trade')