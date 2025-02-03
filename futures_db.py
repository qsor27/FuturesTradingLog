    def get_statistics(self, timeframe: str = 'daily', accounts: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Calculate detailed trading statistics with validation metrics"""
        try:
            db = self.get_db()
            
            # Define time grouping based on timeframe
            if timeframe == 'daily':
                time_group = "strftime('%Y-%m-%d', entry_time)"
                period_display = "strftime('%Y-%m-%d', entry_time)"
            elif timeframe == 'weekly':
                time_group = "strftime('%Y-%W', entry_time)"
                period_display = "strftime('%Y Week %W', entry_time)"
            elif timeframe == 'monthly':
                time_group = "strftime('%Y-%m', entry_time)"
                period_display = "strftime('%Y-%m', entry_time)"
            else:
                raise ValueError(f"Invalid timeframe: {timeframe}")

            # Build query with account filtering
            query = f"""
                WITH period_stats AS (
                    SELECT 
                        {time_group} as period,
                        {period_display} as period_display,
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN validated = 1 THEN 1 ELSE 0 END) as valid_trades,
                        CAST(SUM(CASE WHEN validated = 1 THEN 1 ELSE 0 END) AS FLOAT) / 
                            NULLIF(COUNT(*), 0) * 100 as valid_trade_percentage,
                        CAST(SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) AS FLOAT) / 
                            NULLIF(COUNT(CASE WHEN dollars_gain_loss != 0 THEN 1 END), 0) * 100 as win_rate,
                        SUM(CASE WHEN dollars_gain_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                        SUM(CASE WHEN dollars_gain_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                        SUM(points_gain_loss) as total_points,
                        SUM(dollars_gain_loss) as net_profit,
                        AVG(CASE WHEN dollars_gain_loss > 0 THEN dollars_gain_loss END) as avg_win,
                        AVG(CASE WHEN dollars_gain_loss < 0 THEN ABS(dollars_gain_loss) END) as avg_loss,
                        CASE 
                            WHEN AVG(CASE WHEN dollars_gain_loss < 0 THEN ABS(dollars_gain_loss) END) > 0
                            THEN ABS(AVG(CASE WHEN dollars_gain_loss > 0 THEN dollars_gain_loss END)) / 
                                AVG(CASE WHEN dollars_gain_loss < 0 THEN ABS(dollars_gain_loss) END)
                            ELSE NULL
                        END as reward_risk_ratio,
                        SUM(commission) as total_commission,
                        GROUP_CONCAT(DISTINCT instrument) as instruments_traded,
                        SUM(CASE WHEN dollars_gain_loss > 0 AND validated = 1 THEN 1 ELSE 0 END) as valid_winning_trades,
                        SUM(CASE WHEN dollars_gain_loss < 0 AND validated = 1 THEN 1 ELSE 0 END) as valid_losing_trades,
                        AVG(CASE WHEN dollars_gain_loss > 0 AND validated = 1 THEN dollars_gain_loss END) as avg_valid_win,
                        AVG(CASE WHEN dollars_gain_loss < 0 AND validated = 1 THEN ABS(dollars_gain_loss) END) as avg_valid_loss
                    FROM trades
                    WHERE entry_time IS NOT NULL
                    {f"AND account IN ({','.join('?' * len(accounts))})" if accounts else ""}
                    GROUP BY period
                    ORDER BY period DESC
                )
                SELECT *
                FROM period_stats
            """

            # Execute query with account parameters if provided
            params = accounts if accounts else []
            results = db.execute(query, params).fetchall()
            
            # Convert rows to dictionaries with null handling
            stats = []
            for row in results:
                stat_dict = dict(row)
                
                # Handle NULL values
                for key in stat_dict:
                    if stat_dict[key] is None:
                        if key in ['win_rate', 'valid_trade_percentage', 'reward_risk_ratio']:
                            stat_dict[key] = 0.0
                        elif key in ['total_points', 'net_profit', 'avg_win', 'avg_loss', 
                                   'avg_valid_win', 'avg_valid_loss']:
                            stat_dict[key] = 0.0
                
                # Calculate valid trade win rate
                if stat_dict['valid_trades'] > 0:
                    stat_dict['valid_win_rate'] = (stat_dict['valid_winning_trades'] / 
                                                 stat_dict['valid_trades']) * 100
                else:
                    stat_dict['valid_win_rate'] = 0.0
                
                stats.append(stat_dict)
            
            return stats

        except Exception as e:
            print(f"Error getting statistics: {e}")
            return []