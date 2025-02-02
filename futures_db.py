    def get_statistics(self, period_type: str = None, accounts: Optional[List[str]] = None) -> Dict[str, Any]:
        """Calculate detailed trading statistics with validation metrics"""
        db = self.get_db()
        
        # Base query with validation metrics
        base_query = """
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(CASE WHEN validated = 1 THEN 1 ELSE 0 END) as valid_trades,
                CAST(SUM(CASE WHEN validated = 1 THEN 1 ELSE 0 END) AS FLOAT) / 
                    NULLIF(COUNT(*), 0) * 100 as valid_trade_percentage,
                ROUND(SUM(dollars_gain_loss), 2) as total_pnl,
                ROUND(SUM(CASE WHEN dollars_gain_loss > 0 THEN dollars_gain_loss ELSE 0 END), 2) as gross_profits,
                ROUND(SUM(CASE WHEN dollars_gain_loss < 0 THEN dollars_gain_loss ELSE 0 END), 2) as gross_losses,
                ROUND(AVG(CASE WHEN dollars_gain_loss > 0 THEN dollars_gain_loss END), 2) as avg_winner,
                ROUND(AVG(CASE WHEN dollars_gain_loss < 0 THEN dollars_gain_loss END), 2) as avg_loser,
                ROUND(AVG(CASE WHEN dollars_gain_loss > 0 AND validated = 1 THEN dollars_gain_loss END), 2) as avg_valid_winner,
                ROUND(AVG(CASE WHEN dollars_gain_loss < 0 AND validated = 1 THEN dollars_gain_loss END), 2) as avg_valid_loser
            FROM trades
            WHERE 1=1
        """
        
        params: List[Any] = []
        
        # Add time period filter
        if period_type:
            if period_type == 'daily':
                base_query += " AND date(entry_time) = date('now')"
            elif period_type == 'weekly':
                base_query += " AND entry_time >= date('now', '-7 days')"
            elif period_type == 'monthly':
                base_query += " AND entry_time >= date('now', '-30 days')"
        
        # Add account filter
        if accounts and len(accounts) > 0:
            placeholders = ','.join('?' * len(accounts))
            base_query += f" AND account IN ({placeholders})"
            params.extend(accounts)
            
        results = db.execute(base_query, params).fetchone()
        
        # Calculate derived statistics
        stats = dict(results)
        if stats['total_trades'] > 0:
            stats['win_rate'] = round((stats['winning_trades'] / stats['total_trades']) * 100, 2)
        else:
            stats['win_rate'] = 0.0
            
        if stats['avg_loser'] and stats['avg_winner']:
            stats['profit_factor'] = round(abs(stats['avg_winner'] / stats['avg_loser']), 2)
        else:
            stats['profit_factor'] = 0.0
            
        # Calculate valid trade metrics
        stats['valid_win_rate'] = 0.0
        if stats['valid_trades'] > 0:
            valid_winners = db.execute("""
                SELECT COUNT(*) as count
                FROM trades
                WHERE validated = 1 AND dollars_gain_loss > 0
                AND entry_time IS NOT NULL
                """ + 
                (f" AND account IN ({','.join('?' * len(accounts))})" if accounts else ""),
                params
            ).fetchone()['count']
            stats['valid_win_rate'] = round((valid_winners / stats['valid_trades']) * 100, 2)
            
        return stats