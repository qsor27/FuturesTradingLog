from flask import Blueprint, render_template, request, jsonify
from futures_db import FuturesDB

trades_bp = Blueprint('trades', __name__)

@trades_bp.route('/detail/<int:trade_id>')
def trade_detail(trade_id):
    with FuturesDB() as db:
        trade = db.get_trade_by_id(trade_id)
    return render_template('trade_detail.html', trade=trade)

@trades_bp.route('/update-notes/<int:trade_id>', methods=['POST'])
def update_notes(trade_id):
    data = request.get_json()
    notes = data.get('notes', '')
    chart_url = data.get('chart_url', '')
    validated = data.get('validated', False)
    reviewed = data.get('reviewed', False)
    
    with FuturesDB() as db:
        success = db.update_trade_details(trade_id, chart_url=chart_url, notes=notes,
                                         confirmed_valid=validated, reviewed=reviewed)
    
    return jsonify({'success': success})

@trades_bp.context_processor
def utility_processor():
    """Add helper functions to the template context."""
    def get_row_class(pnl):
        if pnl is None:
            return ''
        return 'positive' if pnl > 0 else 'negative' if pnl < 0 else ''

    def get_side_class(side):
        if not side:
            return ''
        return f'side-{side.lower()}'

    return dict(
        get_row_class=get_row_class,
        get_side_class=get_side_class
    )