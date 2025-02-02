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