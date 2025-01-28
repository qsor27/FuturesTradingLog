from flask import Blueprint, render_template, request
from futures_db import FuturesDB

stats_bp = Blueprint('statistics', __name__)

@stats_bp.route('/statistics')
def statistics():
    # Get list of selected accounts from query parameters
    selected_accounts = request.args.getlist('account')
    
    with FuturesDB() as db:
        # Get all available accounts
        accounts = db.get_unique_accounts()
        
        # If no accounts are selected in the URL, use all accounts
        if not selected_accounts:
            selected_accounts = accounts
        
        # Get statistics for selected accounts
        print(f"Getting stats for accounts: {selected_accounts}")  # Debug print
        stats = {
            'daily': db.get_statistics('daily', accounts=selected_accounts if selected_accounts else None),
            'weekly': db.get_statistics('weekly', accounts=selected_accounts if selected_accounts else None),
            'monthly': db.get_statistics('monthly', accounts=selected_accounts if selected_accounts else None)
        }
        
        print(f"Daily stats: {stats['daily']}")  # Debug print
        
    return render_template('statistics.html', stats=stats, accounts=accounts, selected_accounts=selected_accounts)
