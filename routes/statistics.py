from flask import Blueprint, render_template, request, jsonify
from scripts.TradingLog_db import FuturesDB

statistics_bp = Blueprint('statistics', __name__, url_prefix='/statistics')

@statistics_bp.route('/')
def statistics():
    """Display trading statistics."""
    # Get filter parameters
    selected_accounts = request.args.getlist('accounts')
    
    with FuturesDB() as db:
        # Get list of all accounts for the filter dropdown
        accounts = db.get_unique_accounts()
        
        # Get statistics for different time periods
        stats = {
            'daily': db.get_statistics('daily', accounts=selected_accounts if selected_accounts else None),
            'weekly': db.get_statistics('weekly', accounts=selected_accounts if selected_accounts else None),
            'monthly': db.get_statistics('monthly', accounts=selected_accounts if selected_accounts else None)
        }
    
    return render_template('statistics.html',
        accounts=accounts,
        selected_accounts=selected_accounts,
        stats=stats
    )