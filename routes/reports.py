from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, timedelta
from scripts.TradingLog_db import FuturesDB
from services.statistics_calculation_service import DashboardStatisticsIntegration
from utils.logging_config import get_logger

logger = get_logger(__name__)
reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/reports')
def reports_dashboard():
    """Main reports dashboard with overview cards and filters"""
    try:
        with FuturesDB() as db:
            # Get basic overview stats using standardized calculations
            overview_stats = DashboardStatisticsIntegration.get_overview_statistics_standardized()
            
            # Get available accounts for filtering
            accounts = db.get_unique_accounts()
            
            # Get available instruments for filtering
            instruments = db.get_unique_instruments()
            
            # Get date range for filtering
            date_range = db.get_date_range()
            
        return render_template('reports/dashboard.html',
                             overview_stats=overview_stats,
                             accounts=accounts,
                             instruments=instruments,
                             date_range=date_range)
    except Exception as e:
        logger.error(f"Error loading reports dashboard: {e}")
        return render_template('error.html', error="Failed to load reports dashboard"), 500

@reports_bp.route('/reports/performance')
def performance_report():
    """Historical performance analysis report"""
    try:
        # Get filter parameters
        account = request.args.get('account')
        instrument = request.args.get('instrument')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        period = request.args.get('period', 'daily')  # daily, weekly, monthly
        
        with FuturesDB() as db:
            # Get performance data
            performance_data = db.get_performance_analysis(
                account=account,
                instrument=instrument,
                start_date=start_date,
                end_date=end_date,
                period=period
            )
            
            # Get accounts and instruments for filters
            accounts = db.get_unique_accounts()
            instruments = db.get_unique_instruments()
            
        return render_template('reports/performance.html',
                             performance_data=performance_data,
                             accounts=accounts,
                             instruments=instruments,
                             filters={
                                 'account': account,
                                 'instrument': instrument,
                                 'start_date': start_date,
                                 'end_date': end_date,
                                 'period': period
                             })
    except Exception as e:
        logger.error(f"Error loading performance report: {e}")
        return render_template('error.html', error="Failed to load performance report"), 500

@reports_bp.route('/reports/monthly-summary')
def monthly_summary():
    """Monthly performance summary report"""
    try:
        # Get filter parameters
        account = request.args.get('account')
        year = request.args.get('year', str(datetime.now().year))
        
        with FuturesDB() as db:
            # Get monthly data
            monthly_data = db.get_monthly_performance(account=account, year=int(year))
            
            # Get available years and accounts
            years = db.get_available_years()
            accounts = db.get_unique_accounts()
            
        return render_template('reports/monthly_summary.html',
                             monthly_data=monthly_data,
                             years=years,
                             accounts=accounts,
                             filters={
                                 'account': account,
                                 'year': year
                             })
    except Exception as e:
        logger.error(f"Error loading monthly summary: {e}")
        return render_template('error.html', error="Failed to load monthly summary"), 500

@reports_bp.route('/reports/instrument-analysis')
def instrument_analysis():
    """Instrument-specific performance analysis"""
    try:
        # Get filter parameters
        account = request.args.get('account')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        with FuturesDB() as db:
            # Get instrument performance data
            instrument_data = db.get_instrument_performance(
                account=account,
                start_date=start_date,
                end_date=end_date
            )
            
            # Get accounts for filters
            accounts = db.get_unique_accounts()
            
        return render_template('reports/instrument_analysis.html',
                             instrument_data=instrument_data,
                             accounts=accounts,
                             filters={
                                 'account': account,
                                 'start_date': start_date,
                                 'end_date': end_date
                             })
    except Exception as e:
        logger.error(f"Error loading instrument analysis: {e}")
        return render_template('error.html', error="Failed to load instrument analysis"), 500

@reports_bp.route('/reports/trade-distribution')
def trade_distribution():
    """Trade size and time distribution analysis"""
    try:
        # Get filter parameters
        account = request.args.get('account')
        instrument = request.args.get('instrument')
        
        with FuturesDB() as db:
            # Get distribution data
            distribution_data = db.get_trade_distribution_analysis(
                account=account,
                instrument=instrument
            )
            
            # Get accounts and instruments for filters
            accounts = db.get_unique_accounts()
            instruments = db.get_unique_instruments()
            
        return render_template('reports/trade_distribution.html',
                             distribution_data=distribution_data,
                             accounts=accounts,
                             instruments=instruments,
                             filters={
                                 'account': account,
                                 'instrument': instrument
                             })
    except Exception as e:
        logger.error(f"Error loading trade distribution: {e}")
        return render_template('error.html', error="Failed to load trade distribution"), 500

@reports_bp.route('/api/reports/performance-data')
def api_performance_data():
    """API endpoint for performance chart data"""
    try:
        # Get parameters
        account = request.args.get('account')
        instrument = request.args.get('instrument')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        period = request.args.get('period', 'daily')
        
        with FuturesDB() as db:
            data = db.get_performance_chart_data(
                account=account,
                instrument=instrument,
                start_date=start_date,
                end_date=end_date,
                period=period
            )
            
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting performance chart data: {e}")
        return jsonify({'error': str(e)}), 500

@reports_bp.route('/api/reports/summary-stats')
def api_summary_stats():
    """API endpoint for summary statistics"""
    try:
        # Get parameters
        account = request.args.get('account')
        instrument = request.args.get('instrument')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        with FuturesDB() as db:
            stats = DashboardStatisticsIntegration.get_summary_statistics_standardized(
                account=account,
                instrument=instrument,
                start_date=start_date,
                end_date=end_date
            )
            
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting summary statistics: {e}")
        return jsonify({'error': str(e)}), 500