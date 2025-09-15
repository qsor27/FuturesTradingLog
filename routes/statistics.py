from flask import Blueprint, render_template, request, jsonify
from scripts.TradingLog_db import FuturesDB
from services.statistics_calculation_service import DashboardStatisticsIntegration

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