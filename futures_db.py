    def unlink_trades(self, trade_ids: List[int]) -> bool:
        """Remove trades from their link group."""
        try:
            db = self.get_db()
            placeholders = ','.join('?' * len(trade_ids))
            db.execute(f"""
                UPDATE trades 
                SET link_group_id = NULL 
                WHERE id IN ({placeholders})
            """, trade_ids)
            
            db.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error unlinking trades: {e}")
            return False