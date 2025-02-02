    def get_group_statistics(self, group_id: int) -> Dict[str, Any]:
        """Calculate detailed statistics for a group of linked trades"""
        trades = self.get_linked_trades(group_id)
        if not trades:
            return {
                'total_pnl': 0,
                'total_commission': 0,
                'trade_count': 0
            }
            
        try:
            db = self.get_db()
            stats = db.execute("""
                SELECT 
                    SUM(dollars_gain_loss) as total_pnl,
                    SUM(commission) as total_commission,
                    COUNT(*) as trade_count,
                    SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                    AVG(CASE WHEN dollars_gain_loss > 0 THEN dollars_gain_loss END) as avg_winner,
                    AVG(CASE WHEN dollars_gain_loss < 0 THEN dollars_gain_loss END) as avg_loser
                FROM trades 
                WHERE link_group_id = ?
            """, (group_id,)).fetchone()
            
            result = dict(stats)
            
            # Calculate win rate if there are trades
            if result['trade_count'] > 0:
                result['win_rate'] = (result['winning_trades'] / result['trade_count']) * 100
            else:
                result['win_rate'] = 0
                
            # Calculate reward/risk ratio if there are both winners and losers
            if result['avg_loser'] and result['avg_winner']:
                result['reward_risk_ratio'] = abs(result['avg_winner'] / result['avg_loser'])
            else:
                result['reward_risk_ratio'] = 0
                
            return result
            
        except sqlite3.Error as e:
            print(f"Error getting group statistics: {e}")
            return {
                'total_pnl': 0,
                'total_commission': 0,
                'trade_count': 0
            }

    def delete_trades(self, trade_ids: List[int]) -> bool:
        """Delete multiple trades by their IDs"""
        if not trade_ids:
            return False
            
        try:
            db = self.get_db()
            placeholders = ','.join('?' * len(trade_ids))
            db.execute(f"""
                DELETE FROM trades
                WHERE id IN ({placeholders})
            """, trade_ids)
            db.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Error deleting trades: {e}")
            return False

    def import_csv(self, csv_path: str) -> bool:
        """Import trades from a CSV file with duplicate checking"""
        try:
            print(f"\nImporting trades from {csv_path}...")
            
            # Read CSV file using pandas
            df = pd.read_csv(csv_path)
            print(f"Read {len(df)} rows from CSV")
            print(f"CSV columns: {list(df.columns)}")

            # Define column name mappings
            column_mappings = {
                'Instrument': 'instrument',
                'Side of Market': 'side_of_market',
                'Quantity': 'quantity',
                'Entry Price': 'entry_price',
                'Entry Time': 'entry_time',
                'Exit Time': 'exit_time',
                'Exit Price': 'exit_price',
                'Result Gain/Loss in Points': 'points_gain_loss',
                'Gain/Loss in Dollars': 'dollars_gain_loss',
                'Commission': 'commission',
                'Account': 'account',
                'ID': 'entry_execution_id'
            }
            
            # Rename columns based on mappings
            df = df.rename(columns=column_mappings)
            print(f"Columns after mapping: {list(df.columns)}")
            
            # Ensure required columns exist
            required_columns = {
                'instrument', 'side_of_market', 'quantity', 'entry_price',
                'entry_time', 'exit_time', 'exit_price', 'points_gain_loss',
                'dollars_gain_loss', 'commission', 'account', 'entry_execution_id'
            }
            
            missing_columns = required_columns - set(df.columns)
            if missing_columns:
                print(f"Missing required columns: {missing_columns}")
                return False

            # Convert datetime columns
            for col in ['entry_time', 'exit_time']:
                df[col] = pd.to_datetime(df[col]).dt.strftime('%Y-%m-%d %H:%M:%S')

            db = self.get_db()
            trades_added = 0
            trades_skipped = 0

            for _, row in df.iterrows():
                try:
                    # Check for duplicate based on account and execution ID
                    db.execute("""
                        SELECT COUNT(*) as count FROM trades
                        WHERE account = ? AND entry_execution_id = ?
                    """, (str(row['account']), str(row['entry_execution_id'])))
                    
                    count = db.execute("""
                        SELECT COUNT(*) as count FROM trades
                        WHERE account = ? AND entry_execution_id = ?
                    """, (str(row['account']), str(row['entry_execution_id']))).fetchone()['count']
                    
                    if count > 0:
                        trades_skipped += 1
                        print(f"Skipping duplicate trade: Entry={row['entry_time']}, ExecID={row['entry_execution_id']}, Account={row['account']}")
                        continue

                    # Insert if not a duplicate
                    db.execute("""
                        INSERT INTO trades (
                            instrument, side_of_market, quantity, entry_price,
                            entry_time, exit_time, exit_price, points_gain_loss,
                            dollars_gain_loss, commission, account, entry_execution_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(row['instrument']),
                        str(row['side_of_market']),
                        int(row['quantity']),
                        float(row['entry_price']),
                        str(row['entry_time']),
                        str(row['exit_time']),
                        float(row['exit_price']),
                        float(row['points_gain_loss']),
                        float(row['dollars_gain_loss']),
                        float(row['commission']),
                        str(row['account']),
                        str(row['entry_execution_id'])
                    ))
                    trades_added += 1
                    
                except (ValueError, KeyError) as e:
                    print(f"Error processing row: {e}")
                    continue
            
            db.commit()
            print(f"Import complete: {trades_added} trades added, {trades_skipped} duplicates skipped")
            return True
            
        except Exception as e:
            print(f"Error importing CSV: {e}")
            return False