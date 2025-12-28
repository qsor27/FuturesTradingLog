"""
Statistics Routes - Handle trading statistics views and API endpoints
"""
import logging
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, jsonify
from scripts.TradingLog_db import FuturesDB
from services.statistics_calculation_service import (
    DashboardStatisticsIntegration,
    StandardizedStatisticsCalculator
)

# Setup logging
logger = logging.getLogger('statistics')

statistics_bp = Blueprint('statistics', __name__, url_prefix='/statistics')

@statistics_bp.route('/')
def statistics():
    """Display trading statistics."""
    # Get filter parameters
    selected_accounts = request.args.getlist('accounts')
    
    with FuturesDB() as db:
        # Get list of all accounts for the filter dropdown
        accounts = db.get_unique_accounts()
        
        # Get statistics for different time periods using standardized calculations
        stats = {
            'daily': DashboardStatisticsIntegration.get_statistics_standardized('daily', accounts=selected_accounts if selected_accounts else None),
            'weekly': DashboardStatisticsIntegration.get_statistics_standardized('weekly', accounts=selected_accounts if selected_accounts else None),
            'monthly': DashboardStatisticsIntegration.get_statistics_standardized('monthly', accounts=selected_accounts if selected_accounts else None)
        }
    
    return render_template('statistics.html',
        accounts=accounts,
        selected_accounts=selected_accounts,
        stats=stats
    )


# =============================================================================
# API Endpoints for Enhanced Statistics
# =============================================================================

def _parse_date(date_str: str) -> date:
    """Parse date string in YYYY-MM-DD format."""
    return datetime.strptime(date_str, '%Y-%m-%d').date()


def _get_week_start(target_date: date) -> date:
    """Get Monday of the week containing target_date."""
    days_since_monday = target_date.weekday()
    return target_date - timedelta(days=days_since_monday)


@statistics_bp.route('/api/daily', methods=['GET'])
def api_daily_statistics():
    """
    GET /statistics/api/daily

    Returns enhanced daily statistics for position-based metrics.

    Query Parameters:
        date: Target date in YYYY-MM-DD format (default: today)
        accounts: Comma-separated list of account filters

    Returns:
        JSON response with daily statistics data
    """
    try:
        # Parse date parameter
        date_str = request.args.get('date')
        if date_str:
            try:
                target_date = _parse_date(date_str)
            except ValueError:
                return jsonify({
                    'error': 'Invalid date format',
                    'message': 'Date must be in YYYY-MM-DD format'
                }), 400
        else:
            target_date = date.today()

        # Parse account filter
        accounts_param = request.args.get('accounts')
        account_filter = accounts_param.split(',') if accounts_param else None

        # Get enhanced daily statistics
        # Convert date to string format expected by calculator
        target_date_str = target_date.strftime('%Y-%m-%d') if hasattr(target_date, 'strftime') else target_date
        logger.debug(f"Calculating daily statistics for {target_date_str}")
        stats = StandardizedStatisticsCalculator.get_daily_enhanced_statistics(
            target_date=target_date_str,
            account_filter=account_filter
        )

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error retrieving daily statistics: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'Unable to retrieve daily statistics'
        }), 500


@statistics_bp.route('/api/weekly', methods=['GET'])
def api_weekly_statistics():
    """
    GET /statistics/api/weekly

    Returns enhanced weekly statistics with day-of-week breakdown.

    Query Parameters:
        week_start: Monday of target week in YYYY-MM-DD format (default: current week)
        accounts: Comma-separated list of account filters

    Returns:
        JSON response with weekly statistics data
    """
    try:
        # Parse week_start parameter
        week_start_str = request.args.get('week_start')
        if week_start_str:
            try:
                week_start = _parse_date(week_start_str)
            except ValueError:
                return jsonify({
                    'error': 'Invalid date format',
                    'message': 'week_start must be in YYYY-MM-DD format'
                }), 400
        else:
            week_start = _get_week_start(date.today())

        # Parse account filter
        accounts_param = request.args.get('accounts')
        account_filter = accounts_param.split(',') if accounts_param else None

        # Get enhanced weekly statistics
        logger.debug(f"Calculating weekly statistics for week starting {week_start}")
        # Convert date to string format expected by calculator
        week_start_str = week_start.strftime('%Y-%m-%d') if hasattr(week_start, 'strftime') else week_start
        stats = StandardizedStatisticsCalculator.get_weekly_enhanced_statistics(
            week_start=week_start_str,
            account_filter=account_filter
        )

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error retrieving weekly statistics: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'Unable to retrieve weekly statistics'
        }), 500


@statistics_bp.route('/api/monthly', methods=['GET'])
def api_monthly_statistics():
    """
    GET /statistics/api/monthly

    Returns enhanced monthly statistics with week-over-week breakdown.

    Query Parameters:
        year: Target year (default: current year)
        month: Target month 1-12 (default: current month)
        accounts: Comma-separated list of account filters

    Returns:
        JSON response with monthly statistics data
    """
    try:
        # Parse year and month parameters
        year_str = request.args.get('year')
        month_str = request.args.get('month')

        if year_str:
            try:
                year = int(year_str)
            except ValueError:
                return jsonify({
                    'error': 'Invalid year',
                    'message': 'Year must be a valid integer'
                }), 400
        else:
            year = date.today().year

        if month_str:
            try:
                month = int(month_str)
                if month < 1 or month > 12:
                    return jsonify({
                        'error': 'Invalid month',
                        'message': 'Month must be between 1 and 12'
                    }), 400
            except ValueError:
                return jsonify({
                    'error': 'Invalid month',
                    'message': 'Month must be a valid integer'
                }), 400
        else:
            month = date.today().month

        # Parse account filter
        accounts_param = request.args.get('accounts')
        account_filter = accounts_param.split(',') if accounts_param else None

        # Get enhanced monthly statistics
        logger.debug(f"Calculating monthly statistics for {year}-{month:02d}")
        stats = StandardizedStatisticsCalculator.get_monthly_enhanced_statistics(
            year=year,
            month=month,
            account_filter=account_filter
        )

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error retrieving monthly statistics: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'Unable to retrieve monthly statistics'
        }), 500


@statistics_bp.route('/api/chart/<metric>', methods=['GET'])
def api_chart_data(metric: str):
    """
    GET /statistics/api/chart/<metric>

    Returns chart-ready data for specific metrics.

    Path Parameters:
        metric: Chart metric type (day_breakdown, instrument_breakdown,
                long_short_distribution, win_rate_by_direction, week_performance)

    Query Parameters:
        date: Target date for daily charts (YYYY-MM-DD)
        week_start: Week start for weekly charts (YYYY-MM-DD)
        year: Target year for monthly charts
        month: Target month for monthly charts
        accounts: Comma-separated list of account filters

    Returns:
        JSON response with Chart.js compatible data structure
    """
    valid_metrics = [
        'day_breakdown', 'instrument_breakdown', 'long_short_distribution',
        'win_rate_by_direction', 'week_performance'
    ]

    if metric not in valid_metrics:
        return jsonify({
            'error': 'Invalid metric',
            'message': f'Metric must be one of: {", ".join(valid_metrics)}'
        }), 400

    try:
        # Parse account filter
        accounts_param = request.args.get('accounts')
        account_filter = accounts_param.split(',') if accounts_param else None

        # Determine which time period's data to use based on metric
        if metric in ['day_breakdown', 'instrument_breakdown']:
            # Weekly metrics
            week_start_str = request.args.get('week_start')
            if week_start_str:
                week_start = _parse_date(week_start_str)
            else:
                week_start = _get_week_start(date.today())

            stats = StandardizedStatisticsCalculator.get_weekly_enhanced_statistics(
                week_start=week_start,
                account_filter=account_filter
            )

            if metric == 'day_breakdown':
                chart_data = _format_day_breakdown_chart(stats.get('day_breakdown', {}))
            else:  # instrument_breakdown
                chart_data = _format_instrument_breakdown_chart(stats.get('instrument_breakdown', {}))

        elif metric in ['long_short_distribution', 'win_rate_by_direction']:
            # Daily metrics
            date_str = request.args.get('date')
            if date_str:
                target_date = _parse_date(date_str)
            else:
                target_date = date.today()

            stats = StandardizedStatisticsCalculator.get_daily_enhanced_statistics(
                target_date=target_date,
                account_filter=account_filter
            )

            if metric == 'long_short_distribution':
                chart_data = _format_long_short_distribution_chart(stats)
            else:  # win_rate_by_direction
                chart_data = _format_win_rate_by_direction_chart(stats)

        else:  # week_performance
            # Monthly metric
            year = int(request.args.get('year', date.today().year))
            month = int(request.args.get('month', date.today().month))

            stats = StandardizedStatisticsCalculator.get_monthly_enhanced_statistics(
                year=year,
                month=month,
                account_filter=account_filter
            )

            chart_data = _format_week_performance_chart(stats.get('week_breakdown', []))

        return jsonify(chart_data)

    except ValueError as e:
        return jsonify({
            'error': 'Invalid parameter',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error generating chart data for {metric}: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'Unable to generate chart data'
        }), 500


# =============================================================================
# Chart Data Formatters (Chart.js compatible)
# =============================================================================

def _format_day_breakdown_chart(day_breakdown: dict) -> dict:
    """Format day breakdown data for Chart.js bar chart."""
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    labels = []
    pnl_data = []
    win_rate_data = []

    for day in days_order:
        if day in day_breakdown:
            labels.append(day[:3])  # Mon, Tue, etc.
            pnl_data.append(day_breakdown[day].get('pnl', 0))
            win_rate_data.append(day_breakdown[day].get('win_rate', 0))
        else:
            labels.append(day[:3])
            pnl_data.append(0)
            win_rate_data.append(0)

    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'P&L ($)',
                'data': pnl_data,
                'backgroundColor': ['#4ade80' if p >= 0 else '#f87171' for p in pnl_data],
                'yAxisID': 'y'
            },
            {
                'label': 'Win Rate (%)',
                'data': win_rate_data,
                'type': 'line',
                'borderColor': '#60a5fa',
                'backgroundColor': 'transparent',
                'yAxisID': 'y1'
            }
        ]
    }


def _format_instrument_breakdown_chart(instrument_breakdown: dict) -> dict:
    """Format instrument breakdown data for Chart.js bar chart."""
    labels = list(instrument_breakdown.keys())
    pnl_data = [instrument_breakdown[inst].get('pnl', 0) for inst in labels]
    position_count_data = [instrument_breakdown[inst].get('position_count', 0) for inst in labels]

    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'P&L ($)',
                'data': pnl_data,
                'backgroundColor': ['#4ade80' if p >= 0 else '#f87171' for p in pnl_data]
            },
            {
                'label': 'Position Count',
                'data': position_count_data,
                'backgroundColor': '#60a5fa'
            }
        ]
    }


def _format_long_short_distribution_chart(stats: dict) -> dict:
    """Format long/short distribution data for Chart.js pie chart."""
    return {
        'labels': ['Long', 'Short'],
        'datasets': [{
            'data': [
                stats.get('long_count', 0),
                stats.get('short_count', 0)
            ],
            'backgroundColor': ['#4ade80', '#f87171']
        }]
    }


def _format_win_rate_by_direction_chart(stats: dict) -> dict:
    """Format win rate by direction data for Chart.js bar chart."""
    return {
        'labels': ['Long', 'Short', 'Overall'],
        'datasets': [{
            'label': 'Win Rate (%)',
            'data': [
                stats.get('long_win_rate', 0),
                stats.get('short_win_rate', 0),
                stats.get('win_rate', 0)
            ],
            'backgroundColor': ['#4ade80', '#f87171', '#60a5fa']
        }]
    }


def _format_week_performance_chart(week_breakdown: list) -> dict:
    """Format week performance data for Chart.js line chart."""
    labels = [f"Week {w.get('week', i+1)}" for i, w in enumerate(week_breakdown)]
    pnl_data = [w.get('pnl', 0) for w in week_breakdown]
    win_rate_data = [w.get('win_rate', 0) for w in week_breakdown]

    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'P&L ($)',
                'data': pnl_data,
                'borderColor': '#4ade80',
                'backgroundColor': 'rgba(74, 222, 128, 0.1)',
                'fill': True,
                'yAxisID': 'y'
            },
            {
                'label': 'Win Rate (%)',
                'data': win_rate_data,
                'borderColor': '#60a5fa',
                'backgroundColor': 'transparent',
                'yAxisID': 'y1'
            }
        ]
    }