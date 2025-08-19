def link_trades(self, trade_ids):
    """Link multiple trades together in a group."""
    try:
        # Get the next available group ID
        self.cursor.execute("SELECT MAX(link_group_id) FROM trades")
        result = self.cursor.fetchone()
        next_group_id = (result[0] or 0) + 1
        
        # Update all selected trades with the new group ID
        placeholders = ','.join('?' for _ in trade_ids)
        self.cursor.execute(f"""
            UPDATE trades 
            SET link_group_id = ? 
            WHERE id IN ({placeholders})
        """, [next_group_id] + trade_ids)
        
        self.conn.commit()
        return True, next_group_id
    except Exception as e:
        print(f"Error linking trades: {e}")
        self.conn.rollback()
        return False, None

def unlink_trades(self, trade_ids):
    """Remove trades from their link group."""
    try:
        placeholders = ','.join('?' for _ in trade_ids)
        self.cursor.execute(f"""
            UPDATE trades 
            SET link_group_id = NULL 
            WHERE id IN ({placeholders})
        """, trade_ids)
        
        self.conn.commit()
        return True
    except Exception as e:
        print(f"Error unlinking trades: {e}")
        self.conn.rollback()
        return False

def get_linked_trades(self, group_id):
    """Get all trades in a link group."""
    try:
        self.cursor.execute("""
            SELECT * FROM trades 
            WHERE link_group_id = ?
            ORDER BY entry_time
        """, (group_id,))
        
        return [dict(row) for row in self.cursor.fetchall()]
    except Exception as e:
        print(f"Error getting linked trades: {e}")
        return []

def get_group_statistics(self, group_id):
    """Get statistics for a linked trade group."""
    try:
        self.cursor.execute("""
            SELECT 
                SUM(dollars_gain_loss) as total_pnl,
                SUM(commission) as total_commission,
                COUNT(*) as trade_count
            FROM trades 
            WHERE link_group_id = ?
        """, (group_id,))
        
        return dict(self.cursor.fetchone())
    except Exception as e:
        print(f"Error getting group statistics: {e}")
        return {
            'total_pnl': 0,
            'total_commission': 0,
            'trade_count': 0
        }
