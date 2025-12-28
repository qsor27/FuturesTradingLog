"""
Statistics Calculation Service - Standardized calculations for dashboard accuracy
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Union
from collections import defaultdict
from scripts.TradingLog_db import FuturesDB

logger = logging.getLogger('statistics')

class StandardizedStatisticsCalculator:
    """
    Standardized statistics calculator that ensures consistent calculations
    across all dashboard components and resolves win rate inconsistencies.
    """
    
    @staticmethod
    def calculate_win_rate(trades_data: List[Dict[str, Any]], include_zero_pnl: bool = True) -> float:
        """
        Calculate win rate with consistent methodology
        
        Args:
            trades_data: List of trade dictionaries with 'dollars_gain_loss' field
            include_zero_pnl: Whether to include zero P&L trades in total count
            
        Returns:
            Win rate as percentage (0-100)
        """
        if not trades_data:
            return 0.0
            
        winning_trades = sum(1 for trade in trades_data if trade.get('dollars_gain_loss', 0) > 0)
        
        if include_zero_pnl:
            # Include all trades in denominator (recommended standard)
            total_trades = len(trades_data)
        else:
            # Exclude zero P&L trades from denominator (legacy behavior)
            total_trades = sum(1 for trade in trades_data if trade.get('dollars_gain_loss', 0) != 0)
        
        return (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    
    @staticmethod
    def calculate_basic_statistics(trades_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate basic trading statistics with standardized methodology
        
        Args:
            trades_data: List of trade dictionaries
            
        Returns:
            Dictionary with standardized statistics
        """
        if not trades_data:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'zero_pnl_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'gross_profit': 0.0,
                'gross_loss': 0.0,
                'profit_factor': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'reward_risk_ratio': 0.0,
                'total_commission': 0.0
            }
        
        # Count trade types
        winning_trades = []
        losing_trades = []
        zero_pnl_trades = []
        
        for trade in trades_data:
            pnl = trade.get('dollars_gain_loss', 0)
            if pnl > 0:
                winning_trades.append(trade)
            elif pnl < 0:
                losing_trades.append(trade)
            else:
                zero_pnl_trades.append(trade)
        
        # Calculate metrics
        total_trades = len(trades_data)
        winning_count = len(winning_trades)
        losing_count = len(losing_trades)
        zero_count = len(zero_pnl_trades)
        
        # P&L calculations
        total_pnl = sum(trade.get('dollars_gain_loss', 0) for trade in trades_data)
        gross_profit = sum(trade.get('dollars_gain_loss', 0) for trade in winning_trades)
        gross_loss = abs(sum(trade.get('dollars_gain_loss', 0) for trade in losing_trades))
        total_commission = sum(trade.get('commission', 0) for trade in trades_data)
        
        # Average calculations
        avg_win = gross_profit / winning_count if winning_count > 0 else 0.0
        avg_loss = gross_loss / losing_count if losing_count > 0 else 0.0
        
        # Ratios
        win_rate = StandardizedStatisticsCalculator.calculate_win_rate(trades_data, include_zero_pnl=True)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        reward_risk_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_count,
            'losing_trades': losing_count,
            'zero_pnl_trades': zero_count,
            'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2),
            'gross_profit': round(gross_profit, 2),
            'gross_loss': round(gross_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'reward_risk_ratio': round(reward_risk_ratio, 2),
            'total_commission': round(total_commission, 2)
        }

    # ============================================================================
    # POSITION-BASED STATISTICS (Enhanced Statistics Views)
    # ============================================================================

    @staticmethod
    def calculate_position_statistics(positions_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate comprehensive statistics from position data.

        Args:
            positions_data: List of position dictionaries with fields:
                - position_type: 'Long' or 'Short'
                - total_dollars_pnl: P&L in dollars
                - total_points_pnl: P&L in points
                - total_commission: Commission paid
                - instrument: Trading instrument
                - entry_time: Position entry timestamp

        Returns:
            Dictionary with position-based statistics
        """
        if not positions_data:
            return {
                'position_count': 0,
                'win_rate': 0.0,
                'long_count': 0,
                'short_count': 0,
                'long_percentage': 0.0,
                'short_percentage': 0.0,
                'long_win_rate': 0.0,
                'short_win_rate': 0.0,
                'best_position_pnl': 0.0,
                'worst_position_pnl': 0.0,
                'avg_points_per_position': 0.0,
                'profit_factor': 0.0,
                'total_pnl': 0.0,
                'gross_profit': 0.0,
                'gross_loss': 0.0,
                'total_commission': 0.0
            }

        # Separate positions by type and outcome
        long_positions = [p for p in positions_data if p.get('position_type', '').lower() == 'long']
        short_positions = [p for p in positions_data if p.get('position_type', '').lower() == 'short']

        winning_positions = [p for p in positions_data if p.get('total_dollars_pnl', 0) > 0]
        losing_positions = [p for p in positions_data if p.get('total_dollars_pnl', 0) < 0]

        winning_longs = [p for p in long_positions if p.get('total_dollars_pnl', 0) > 0]
        winning_shorts = [p for p in short_positions if p.get('total_dollars_pnl', 0) > 0]

        # Counts
        position_count = len(positions_data)
        long_count = len(long_positions)
        short_count = len(short_positions)

        # Percentages
        long_percentage = (long_count / position_count * 100) if position_count > 0 else 0.0
        short_percentage = (short_count / position_count * 100) if position_count > 0 else 0.0

        # Win rates
        win_rate = (len(winning_positions) / position_count * 100) if position_count > 0 else 0.0
        long_win_rate = (len(winning_longs) / long_count * 100) if long_count > 0 else 0.0
        short_win_rate = (len(winning_shorts) / short_count * 100) if short_count > 0 else 0.0

        # P&L metrics
        pnl_values = [p.get('total_dollars_pnl', 0) for p in positions_data]
        points_values = [p.get('total_points_pnl', 0) for p in positions_data]

        total_pnl = sum(pnl_values)
        gross_profit = sum(p.get('total_dollars_pnl', 0) for p in winning_positions)
        gross_loss = abs(sum(p.get('total_dollars_pnl', 0) for p in losing_positions))

        best_position_pnl = max(pnl_values) if pnl_values else 0.0
        worst_position_pnl = min(pnl_values) if pnl_values else 0.0
        avg_points_per_position = sum(points_values) / position_count if position_count > 0 else 0.0

        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0

        total_commission = sum(p.get('total_commission', 0) for p in positions_data)

        return {
            'position_count': position_count,
            'win_rate': round(win_rate, 2),
            'long_count': long_count,
            'short_count': short_count,
            'long_percentage': round(long_percentage, 2),
            'short_percentage': round(short_percentage, 2),
            'long_win_rate': round(long_win_rate, 2),
            'short_win_rate': round(short_win_rate, 2),
            'best_position_pnl': round(best_position_pnl, 2),
            'worst_position_pnl': round(worst_position_pnl, 2),
            'avg_points_per_position': round(avg_points_per_position, 2),
            'profit_factor': round(profit_factor, 2),
            'total_pnl': round(total_pnl, 2),
            'gross_profit': round(gross_profit, 2),
            'gross_loss': round(gross_loss, 2),
            'total_commission': round(total_commission, 2)
        }

    @staticmethod
    def calculate_weekly_statistics(positions_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate weekly statistics with day-of-week breakdown.

        Args:
            positions_data: List of position dictionaries

        Returns:
            Dictionary with weekly statistics including day breakdown
        """
        if not positions_data:
            return {
                'position_count': 0,
                'total_pnl': 0.0,
                'win_rate': 0.0,
                'day_breakdown': {},
                'best_day': {'day': None, 'win_rate': 0.0},
                'worst_day': {'day': None, 'win_rate': 0.0},
                'instrument_breakdown': {},
                'long_count': 0,
                'short_count': 0,
                'long_percentage': 0.0,
                'short_percentage': 0.0,
                'long_win_rate': 0.0,
                'short_win_rate': 0.0,
                'profit_factor': 0.0
            }

        # Get basic position stats
        basic_stats = StandardizedStatisticsCalculator.calculate_position_statistics(positions_data)

        # Group positions by day of week
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        positions_by_day = defaultdict(list)
        positions_by_instrument = defaultdict(list)

        for pos in positions_data:
            entry_time_str = pos.get('entry_time', '')
            if entry_time_str:
                try:
                    if isinstance(entry_time_str, str):
                        entry_time = datetime.strptime(entry_time_str[:19], '%Y-%m-%d %H:%M:%S')
                    else:
                        entry_time = entry_time_str
                    day_name = day_names[entry_time.weekday()]
                    positions_by_day[day_name].append(pos)
                except (ValueError, TypeError):
                    pass

            instrument = pos.get('instrument', 'Unknown')
            positions_by_instrument[instrument].append(pos)

        # Calculate day breakdown
        day_breakdown = {}
        for day_name in day_names:
            day_positions = positions_by_day.get(day_name, [])
            if day_positions:
                winning = sum(1 for p in day_positions if p.get('total_dollars_pnl', 0) > 0)
                total = len(day_positions)
                pnl = sum(p.get('total_dollars_pnl', 0) for p in day_positions)
                day_breakdown[day_name] = {
                    'position_count': total,
                    'win_rate': round((winning / total * 100) if total > 0 else 0.0, 2),
                    'pnl': round(pnl, 2)
                }

        # Find best and worst days
        best_day = {'day': None, 'win_rate': 0.0}
        worst_day = {'day': None, 'win_rate': 100.0}

        for day_name, stats in day_breakdown.items():
            if stats['win_rate'] > best_day['win_rate']:
                best_day = {'day': day_name, 'win_rate': stats['win_rate']}
            if stats['win_rate'] < worst_day['win_rate']:
                worst_day = {'day': day_name, 'win_rate': stats['win_rate']}

        if worst_day['day'] is None:
            worst_day = {'day': None, 'win_rate': 0.0}

        # Calculate instrument breakdown
        instrument_breakdown = {}
        for instrument, inst_positions in positions_by_instrument.items():
            winning = sum(1 for p in inst_positions if p.get('total_dollars_pnl', 0) > 0)
            total = len(inst_positions)
            pnl = sum(p.get('total_dollars_pnl', 0) for p in inst_positions)
            instrument_breakdown[instrument] = {
                'position_count': total,
                'win_rate': round((winning / total * 100) if total > 0 else 0.0, 2),
                'pnl': round(pnl, 2)
            }

        return {
            'position_count': basic_stats['position_count'],
            'total_pnl': basic_stats['total_pnl'],
            'win_rate': basic_stats['win_rate'],
            'day_breakdown': day_breakdown,
            'best_day': best_day,
            'worst_day': worst_day,
            'instrument_breakdown': instrument_breakdown,
            'long_count': basic_stats['long_count'],
            'short_count': basic_stats['short_count'],
            'long_percentage': basic_stats['long_percentage'],
            'short_percentage': basic_stats['short_percentage'],
            'long_win_rate': basic_stats['long_win_rate'],
            'short_win_rate': basic_stats['short_win_rate'],
            'profit_factor': basic_stats['profit_factor'],
            'gross_profit': basic_stats['gross_profit'],
            'gross_loss': basic_stats['gross_loss']
        }

    @staticmethod
    def calculate_monthly_statistics(
        positions_data: List[Dict[str, Any]],
        year: int = None,
        month: int = None,
        previous_month_pnl: float = None,
        previous_month_win_rate: float = None
    ) -> Dict[str, Any]:
        """
        Calculate monthly statistics with week-over-week breakdown.

        Args:
            positions_data: List of position dictionaries
            year: Year for the month
            month: Month number (1-12)
            previous_month_pnl: P&L from previous month for comparison
            previous_month_win_rate: Win rate from previous month for comparison

        Returns:
            Dictionary with monthly statistics including week breakdown
        """
        if not positions_data:
            return {
                'position_count': 0,
                'total_pnl': 0.0,
                'win_rate': 0.0,
                'avg_positions_per_day': 0.0,
                'week_breakdown': [],
                'best_week': {'week_number': None, 'pnl': 0.0},
                'worst_week': {'week_number': None, 'pnl': 0.0},
                'vs_previous_month': {
                    'pnl_difference': 0.0,
                    'pnl_percentage_change': 0.0,
                    'win_rate_difference': 0.0
                },
                'long_count': 0,
                'short_count': 0,
                'long_percentage': 0.0,
                'short_percentage': 0.0,
                'long_win_rate': 0.0,
                'short_win_rate': 0.0,
                'profit_factor': 0.0
            }

        # Get basic position stats
        basic_stats = StandardizedStatisticsCalculator.calculate_position_statistics(positions_data)

        # Group positions by week
        positions_by_week = defaultdict(list)
        trading_days = set()

        for pos in positions_data:
            entry_time_str = pos.get('entry_time', '')
            if entry_time_str:
                try:
                    if isinstance(entry_time_str, str):
                        entry_time = datetime.strptime(entry_time_str[:19], '%Y-%m-%d %H:%M:%S')
                    else:
                        entry_time = entry_time_str

                    # Get week number within the month
                    day_of_month = entry_time.day
                    week_number = (day_of_month - 1) // 7 + 1
                    week_start = entry_time - timedelta(days=entry_time.weekday())

                    positions_by_week[week_number].append({
                        'position': pos,
                        'week_start': week_start.strftime('%Y-%m-%d')
                    })

                    trading_days.add(entry_time.strftime('%Y-%m-%d'))
                except (ValueError, TypeError):
                    pass

        # Calculate week breakdown
        week_breakdown = []
        for week_num in sorted(positions_by_week.keys()):
            week_data = positions_by_week[week_num]
            week_positions = [d['position'] for d in week_data]
            week_start = week_data[0]['week_start'] if week_data else ''

            winning = sum(1 for p in week_positions if p.get('total_dollars_pnl', 0) > 0)
            total = len(week_positions)
            pnl = sum(p.get('total_dollars_pnl', 0) for p in week_positions)

            week_breakdown.append({
                'week_number': week_num,
                'week_start': week_start,
                'position_count': total,
                'win_rate': round((winning / total * 100) if total > 0 else 0.0, 2),
                'pnl': round(pnl, 2)
            })

        # Find best and worst weeks
        best_week = {'week_number': None, 'pnl': float('-inf')}
        worst_week = {'week_number': None, 'pnl': float('inf')}

        for week in week_breakdown:
            if week['pnl'] > best_week['pnl']:
                best_week = {'week_number': week['week_number'], 'pnl': week['pnl']}
            if week['pnl'] < worst_week['pnl']:
                worst_week = {'week_number': week['week_number'], 'pnl': week['pnl']}

        if best_week['week_number'] is None:
            best_week = {'week_number': None, 'pnl': 0.0}
        if worst_week['week_number'] is None:
            worst_week = {'week_number': None, 'pnl': 0.0}

        # Calculate comparison to previous month
        vs_previous_month = {
            'pnl_difference': 0.0,
            'pnl_percentage_change': 0.0,
            'win_rate_difference': 0.0
        }

        if previous_month_pnl is not None:
            vs_previous_month['pnl_difference'] = round(basic_stats['total_pnl'] - previous_month_pnl, 2)
            if previous_month_pnl != 0:
                vs_previous_month['pnl_percentage_change'] = round(
                    ((basic_stats['total_pnl'] - previous_month_pnl) / abs(previous_month_pnl)) * 100, 2
                )

        if previous_month_win_rate is not None:
            vs_previous_month['win_rate_difference'] = round(
                basic_stats['win_rate'] - previous_month_win_rate, 2
            )

        # Calculate average positions per trading day
        trading_day_count = len(trading_days)
        avg_positions_per_day = (
            basic_stats['position_count'] / trading_day_count
            if trading_day_count > 0 else 0.0
        )

        return {
            'position_count': basic_stats['position_count'],
            'total_pnl': basic_stats['total_pnl'],
            'win_rate': basic_stats['win_rate'],
            'avg_positions_per_day': round(avg_positions_per_day, 2),
            'week_breakdown': week_breakdown,
            'best_week': best_week,
            'worst_week': worst_week,
            'vs_previous_month': vs_previous_month,
            'long_count': basic_stats['long_count'],
            'short_count': basic_stats['short_count'],
            'long_percentage': basic_stats['long_percentage'],
            'short_percentage': basic_stats['short_percentage'],
            'long_win_rate': basic_stats['long_win_rate'],
            'short_win_rate': basic_stats['short_win_rate'],
            'profit_factor': basic_stats['profit_factor'],
            'gross_profit': basic_stats['gross_profit'],
            'gross_loss': basic_stats['gross_loss']
        }

    @staticmethod
    def get_daily_enhanced_statistics(
        target_date: str = None,
        account_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get enhanced daily statistics from the database.

        Args:
            target_date: Date in YYYY-MM-DD format. Defaults to today.
            account_filter: Optional list of accounts to filter by.

        Returns:
            Enhanced daily statistics dictionary
        """
        try:
            with FuturesDB() as db:
                if target_date is None:
                    target_date = date.today().strftime('%Y-%m-%d')

                # Build query for positions
                where_conditions = [
                    "position_status = 'closed'",
                    "strftime('%Y-%m-%d', entry_time) = ?"
                ]
                params = [target_date]

                if account_filter:
                    placeholders = ','.join('?' * len(account_filter))
                    where_conditions.append(f"account IN ({placeholders})")
                    params.extend(account_filter)

                where_clause = " AND ".join(where_conditions)

                query = f"""
                    SELECT
                        position_type,
                        total_dollars_pnl,
                        total_points_pnl,
                        total_commission,
                        instrument,
                        account,
                        entry_time
                    FROM positions
                    WHERE {where_clause}
                    ORDER BY entry_time ASC
                """

                result = db._execute_with_monitoring(
                    query,
                    params,
                    operation="select",
                    table="positions"
                )

                positions_data = [dict(row) for row in result.fetchall()]

                stats = StandardizedStatisticsCalculator.calculate_position_statistics(positions_data)
                stats['date'] = target_date

                return stats

        except Exception as e:
            logger.error(f"Error getting daily enhanced statistics: {e}")
            return StandardizedStatisticsCalculator.calculate_position_statistics([])

    @staticmethod
    def get_weekly_enhanced_statistics(
        week_start: str = None,
        account_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get enhanced weekly statistics from the database.

        Args:
            week_start: Start date (Monday) of the week in YYYY-MM-DD format.
            account_filter: Optional list of accounts to filter by.

        Returns:
            Enhanced weekly statistics dictionary
        """
        try:
            with FuturesDB() as db:
                if week_start is None:
                    today = date.today()
                    week_start_date = today - timedelta(days=today.weekday())
                    week_start = week_start_date.strftime('%Y-%m-%d')
                else:
                    week_start_date = datetime.strptime(week_start, '%Y-%m-%d').date()

                week_end_date = week_start_date + timedelta(days=6)
                week_end = week_end_date.strftime('%Y-%m-%d')

                # Build query for positions
                where_conditions = [
                    "position_status = 'closed'",
                    "strftime('%Y-%m-%d', entry_time) >= ?",
                    "strftime('%Y-%m-%d', entry_time) <= ?"
                ]
                params = [week_start, week_end]

                if account_filter:
                    placeholders = ','.join('?' * len(account_filter))
                    where_conditions.append(f"account IN ({placeholders})")
                    params.extend(account_filter)

                where_clause = " AND ".join(where_conditions)

                query = f"""
                    SELECT
                        position_type,
                        total_dollars_pnl,
                        total_points_pnl,
                        total_commission,
                        instrument,
                        account,
                        entry_time
                    FROM positions
                    WHERE {where_clause}
                    ORDER BY entry_time ASC
                """

                result = db._execute_with_monitoring(
                    query,
                    params,
                    operation="select",
                    table="positions"
                )

                positions_data = [dict(row) for row in result.fetchall()]

                stats = StandardizedStatisticsCalculator.calculate_weekly_statistics(positions_data)
                stats['week_start'] = week_start
                stats['week_end'] = week_end

                return stats

        except Exception as e:
            logger.error(f"Error getting weekly enhanced statistics: {e}")
            return StandardizedStatisticsCalculator.calculate_weekly_statistics([])

    @staticmethod
    def get_monthly_enhanced_statistics(
        year: int = None,
        month: int = None,
        account_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get enhanced monthly statistics from the database.

        Args:
            year: Year (defaults to current year)
            month: Month number 1-12 (defaults to current month)
            account_filter: Optional list of accounts to filter by.

        Returns:
            Enhanced monthly statistics dictionary
        """
        try:
            with FuturesDB() as db:
                today = date.today()
                if year is None:
                    year = today.year
                if month is None:
                    month = today.month

                # Calculate month date range
                month_start = date(year, month, 1)
                if month == 12:
                    month_end = date(year + 1, 1, 1) - timedelta(days=1)
                else:
                    month_end = date(year, month + 1, 1) - timedelta(days=1)

                # Build query for current month positions
                where_conditions = [
                    "position_status = 'closed'",
                    "strftime('%Y-%m-%d', entry_time) >= ?",
                    "strftime('%Y-%m-%d', entry_time) <= ?"
                ]
                params = [month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')]

                if account_filter:
                    placeholders = ','.join('?' * len(account_filter))
                    where_conditions.append(f"account IN ({placeholders})")
                    params.extend(account_filter)

                where_clause = " AND ".join(where_conditions)

                query = f"""
                    SELECT
                        position_type,
                        total_dollars_pnl,
                        total_points_pnl,
                        total_commission,
                        instrument,
                        account,
                        entry_time
                    FROM positions
                    WHERE {where_clause}
                    ORDER BY entry_time ASC
                """

                result = db._execute_with_monitoring(
                    query,
                    params,
                    operation="select",
                    table="positions"
                )

                positions_data = [dict(row) for row in result.fetchall()]

                # Get previous month data for comparison
                if month == 1:
                    prev_year, prev_month = year - 1, 12
                else:
                    prev_year, prev_month = year, month - 1

                prev_month_start = date(prev_year, prev_month, 1)
                if prev_month == 12:
                    prev_month_end = date(prev_year + 1, 1, 1) - timedelta(days=1)
                else:
                    prev_month_end = date(prev_year, prev_month + 1, 1) - timedelta(days=1)

                prev_where_conditions = [
                    "position_status = 'closed'",
                    "strftime('%Y-%m-%d', entry_time) >= ?",
                    "strftime('%Y-%m-%d', entry_time) <= ?"
                ]
                prev_params = [prev_month_start.strftime('%Y-%m-%d'), prev_month_end.strftime('%Y-%m-%d')]

                if account_filter:
                    placeholders = ','.join('?' * len(account_filter))
                    prev_where_conditions.append(f"account IN ({placeholders})")
                    prev_params.extend(account_filter)

                prev_where_clause = " AND ".join(prev_where_conditions)

                prev_query = f"""
                    SELECT
                        total_dollars_pnl
                    FROM positions
                    WHERE {prev_where_clause}
                """

                prev_result = db._execute_with_monitoring(
                    prev_query,
                    prev_params,
                    operation="select",
                    table="positions"
                )

                prev_positions = [dict(row) for row in prev_result.fetchall()]
                prev_month_pnl = sum(p.get('total_dollars_pnl', 0) for p in prev_positions)
                prev_winning = sum(1 for p in prev_positions if p.get('total_dollars_pnl', 0) > 0)
                prev_month_win_rate = (prev_winning / len(prev_positions) * 100) if prev_positions else None

                stats = StandardizedStatisticsCalculator.calculate_monthly_statistics(
                    positions_data,
                    year=year,
                    month=month,
                    previous_month_pnl=prev_month_pnl if prev_positions else None,
                    previous_month_win_rate=prev_month_win_rate
                )

                stats['year'] = year
                stats['month'] = month
                stats['month_name'] = month_start.strftime('%B')

                return stats

        except Exception as e:
            logger.error(f"Error getting monthly enhanced statistics: {e}")
            return StandardizedStatisticsCalculator.calculate_monthly_statistics([])

    @staticmethod
    def get_standardized_overview_statistics(account_filter: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get overview statistics using standardized calculation methods

        Args:
            account_filter: Optional list of accounts to filter by

        Returns:
            Standardized overview statistics
        """
        try:
            with FuturesDB() as db:
                # Build query with optional account filtering
                where_conditions = ["entry_time IS NOT NULL"]
                params = []

                if account_filter:
                    placeholders = ','.join('?' * len(account_filter))
                    where_conditions.append(f"account IN ({placeholders})")
                    params.extend(account_filter)

                where_clause = " AND ".join(where_conditions)

                query = f"""
                    SELECT
                        dollars_gain_loss,
                        commission,
                        entry_time,
                        instrument,
                        account
                    FROM trades
                    WHERE {where_clause}
                """
                
                result = db._execute_with_monitoring(
                    query, 
                    params,
                    operation="select",
                    table="trades"
                )
                
                trades_data = [dict(row) for row in result.fetchall()]
                
                # Calculate standardized statistics
                stats = StandardizedStatisticsCalculator.calculate_basic_statistics(trades_data)
                
                # Add additional metadata
                stats.update({
                    'instruments_traded': len(set(trade.get('instrument') for trade in trades_data if trade.get('instrument'))),
                    'accounts_traded': len(set(trade.get('account') for trade in trades_data if trade.get('account'))),
                    'first_trade_date': min((trade.get('entry_time') for trade in trades_data if trade.get('entry_time')), default=None),
                    'last_trade_date': max((trade.get('entry_time') for trade in trades_data if trade.get('entry_time')), default=None),
                    'avg_trade_pnl': round(stats['total_pnl'] / stats['total_trades'], 2) if stats['total_trades'] > 0 else 0.0
                })
                
                return stats
                
        except Exception as e:
            logger.error(f"Error calculating standardized overview statistics: {e}")
            return {}
    
    @staticmethod
    def get_standardized_timeframe_statistics(
        timeframe: str = 'daily', 
        account_filter: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get timeframe-based statistics using standardized calculation methods
        
        Args:
            timeframe: 'daily', 'weekly', or 'monthly'
            account_filter: Optional list of accounts to filter by
            
        Returns:
            List of standardized statistics grouped by timeframe
        """
        try:
            with FuturesDB() as db:
                # Define time grouping
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
                
                # Build query with optional account filtering
                where_conditions = ["entry_time IS NOT NULL"]
                params = []
                
                if account_filter:
                    placeholders = ','.join('?' * len(account_filter))
                    where_conditions.append(f"account IN ({placeholders})")
                    params.extend(account_filter)
                
                where_clause = " AND ".join(where_conditions)
                
                query = f"""
                    SELECT 
                        {time_group} as period,
                        {period_display} as period_display,
                        dollars_gain_loss,
                        commission,
                        instrument
                    FROM trades
                    WHERE {where_clause}
                    ORDER BY period DESC
                """
                
                result = db._execute_with_monitoring(
                    query,
                    params,
                    operation="select",
                    table="trades"
                )
                
                trades_by_period = {}
                for row in result.fetchall():
                    row_dict = dict(row)
                    period = row_dict['period']
                    if period not in trades_by_period:
                        trades_by_period[period] = {
                            'period': period,
                            'period_display': row_dict['period_display'],
                            'trades': []
                        }
                    trades_by_period[period]['trades'].append(row_dict)
                
                # Calculate statistics for each period
                period_stats = []
                for period_data in trades_by_period.values():
                    trades = period_data['trades']
                    stats = StandardizedStatisticsCalculator.calculate_basic_statistics(trades)
                    
                    # Add period information and template compatibility fields
                    stats.update({
                        'period': period_data['period'],
                        'period_display': period_data['period_display'],
                        'instruments_traded': list(set(trade.get('instrument') for trade in trades if trade.get('instrument'))),
                        # Template compatibility fields
                        'valid_trades': stats['total_trades'] - stats['zero_pnl_trades'],  # Non-zero trades
                        'valid_trade_percentage': (stats['total_trades'] - stats['zero_pnl_trades']) / stats['total_trades'] * 100 if stats['total_trades'] > 0 else 0.0,
                        'total_points_all_trades': 0.0,  # Would need instrument point values to calculate this
                        'net_profit': stats['total_pnl']
                    })
                    
                    period_stats.append(stats)
                
                return period_stats
                
        except Exception as e:
            logger.error(f"Error calculating standardized timeframe statistics: {e}")
            return []

def get_standardized_overview_statistics(account_filter: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Convenience function to get standardized overview statistics
    
    This function replaces the inconsistent calculations in get_overview_statistics()
    """
    return StandardizedStatisticsCalculator.get_standardized_overview_statistics(account_filter)

def get_standardized_timeframe_statistics(
    timeframe: str = 'daily', 
    account_filter: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function to get standardized timeframe statistics
    
    This function replaces the inconsistent calculations in get_statistics()
    """
    return StandardizedStatisticsCalculator.get_standardized_timeframe_statistics(timeframe, account_filter)

class DashboardStatisticsIntegration:
    """
    Integration service to replace inconsistent database methods with standardized calculations
    """
    
    @staticmethod
    def get_overview_statistics_standardized(account_filter: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Drop-in replacement for FuturesDB.get_overview_statistics() with standardized calculations
        """
        return StandardizedStatisticsCalculator.get_standardized_overview_statistics(account_filter)
    
    @staticmethod
    def get_statistics_standardized(
        timeframe: str = 'daily', 
        accounts: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Drop-in replacement for FuturesDB.get_statistics() with standardized calculations
        """
        return StandardizedStatisticsCalculator.get_standardized_timeframe_statistics(timeframe, accounts)
    
    @staticmethod
    def get_summary_statistics_standardized(
        account: Optional[str] = None,
        instrument: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Drop-in replacement for FuturesDB.get_summary_statistics() with standardized calculations
        """
        try:
            with FuturesDB() as db:
                # Build WHERE clause based on filters
                where_conditions = ["entry_time IS NOT NULL"]
                params = []
                
                if account:
                    where_conditions.append("account = ?")
                    params.append(account)
                
                if instrument:
                    where_conditions.append("instrument = ?")
                    params.append(instrument)
                
                if start_date:
                    where_conditions.append("entry_time >= ?")
                    params.append(start_date)
                
                if end_date:
                    where_conditions.append("entry_time <= ?")
                    params.append(end_date)
                
                where_clause = " AND ".join(where_conditions)
                
                query = f"""
                    SELECT 
                        dollars_gain_loss,
                        commission,
                        entry_time,
                        instrument,
                        account
                    FROM trades
                    WHERE {where_clause}
                """
                
                result = db._execute_with_monitoring(
                    query, 
                    params,
                    operation="select",
                    table="trades"
                )
                
                trades_data = [dict(row) for row in result.fetchall()]
                
                # Use standardized calculations
                return StandardizedStatisticsCalculator.calculate_basic_statistics(trades_data)
                
        except Exception as e:
            logger.error(f"Error in get_summary_statistics_standardized: {e}")
            return {}