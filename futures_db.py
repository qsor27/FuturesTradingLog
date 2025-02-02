    def update_trade_details(self, trade_id: int, chart_url: Optional[str] = None, notes: Optional[str] = None, 
                           confirmed_valid: Optional[bool] = None, reviewed: Optional[bool] = None) -> bool:
        """Update trade details including validation status"""
        try:
            db = self.get_db()
            updates = []
            params = []
            
            if chart_url is not None:
                updates.append("chart_url = ?")
                params.append(chart_url)
            
            if notes is not None:
                updates.append("notes = ?")
                params.append(notes)
                
            if confirmed_valid is not None:
                updates.append("validated = ?")
                params.append(confirmed_valid)
                
            if reviewed is not None:
                updates.append("reviewed = ?")
                params.append(reviewed)
            
            if not updates:
                return True
                
            query = f"UPDATE trades SET {', '.join(updates)} WHERE id = ?"
            params.append(trade_id)
            
            db.execute(query, params)
            db.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Error updating trade details: {e}")
            return False