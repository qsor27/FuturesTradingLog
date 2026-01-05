"""
Execution Review Routes - For reviewing and correcting trade executions
"""
from flask import Blueprint, render_template, request, jsonify
from scripts.TradingLog_db import FuturesDB
from services.enhanced_position_service_v2 import EnhancedPositionServiceV2
import logging

logger = logging.getLogger(__name__)

execution_review_bp = Blueprint('execution_review', __name__, url_prefix='/executions')


@execution_review_bp.route('/review')
def review_executions():
    """Display execution review screen with filtering"""
    try:
        with FuturesDB() as db:
            accounts = db.get_unique_accounts()
            instruments = db.get_unique_instruments()

        return render_template('executions/review.html',
                             accounts=accounts,
                             instruments=instruments)
    except Exception as e:
        logger.error(f"Error loading execution review page: {e}")
        return render_template('error.html',
                             error="Error loading review page",
                             message=str(e)), 500


@execution_review_bp.route('/api/list')
def list_executions():
    """API endpoint to get executions with filtering and running quantity calculation"""
    try:
        account = request.args.get('account', '')
        instrument = request.args.get('instrument', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')

        with FuturesDB() as db:
            # Build query with filters
            query = """
                SELECT id, instrument, account, side_of_market, quantity,
                       entry_price, exit_price, entry_time, entry_execution_id
                FROM trades
                WHERE (deleted = 0 OR deleted IS NULL)
            """
            params = []

            if account:
                query += " AND account = ?"
                params.append(account)
            if instrument:
                query += " AND instrument = ?"
                params.append(instrument)
            if start_date:
                query += " AND DATE(entry_time) >= ?"
                params.append(start_date)
            if end_date:
                query += " AND DATE(entry_time) <= ?"
                params.append(end_date)

            query += " ORDER BY entry_time ASC"

            db.cursor.execute(query, params)
            rows = db.cursor.fetchall()

            # Calculate running quantity for each execution
            executions = []
            running_qty = 0

            for row in rows:
                trade = dict(row)
                side = trade['side_of_market']
                qty = trade['quantity']

                # Calculate signed quantity change
                if side in ['Buy', 'BuyToCover', 'Long']:
                    signed_change = qty
                elif side in ['Sell', 'SellShort', 'Short']:
                    signed_change = -qty
                else:
                    signed_change = 0

                prev_qty = running_qty
                running_qty += signed_change

                # Detect potential issues
                issue = None
                if prev_qty < 0 and side == 'Sell':
                    # Adding to short - might be intentional or might be wrong
                    issue = 'Adding to short position'
                elif prev_qty > 0 and side in ['Buy', 'BuyToCover']:
                    # Adding to long - might be intentional or might be wrong
                    issue = 'Adding to long position'
                elif prev_qty == 0 and side == 'BuyToCover':
                    issue = 'BuyToCover with no position'
                elif prev_qty == 0 and side == 'SellShort':
                    issue = 'SellShort with no position'

                # Get display price (prefer exit_price for exits, entry_price for entries)
                price = trade['exit_price'] if trade['exit_price'] else trade['entry_price']

                executions.append({
                    'id': trade['id'],
                    'instrument': trade['instrument'],
                    'account': trade['account'],
                    'side_of_market': side,
                    'quantity': qty,
                    'price': price,
                    'entry_time': trade['entry_time'],
                    'running_qty': running_qty,
                    'issue': issue,
                    'execution_id': trade['entry_execution_id']
                })

            return jsonify({
                'success': True,
                'executions': executions,
                'count': len(executions),
                'final_quantity': running_qty
            })

    except Exception as e:
        logger.error(f"Error listing executions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@execution_review_bp.route('/api/update', methods=['POST'])
def update_executions():
    """Batch update executions (side_of_market, quantity, price)"""
    try:
        data = request.get_json()
        updates = data.get('updates', [])

        if not updates:
            return jsonify({'success': False, 'error': 'No updates provided'}), 400

        with FuturesDB() as db:
            updated_count = 0
            affected_positions = set()

            for update in updates:
                trade_id = update.get('id')
                if not trade_id:
                    continue

                # Get current trade to track affected positions
                trade = db.get_trade_by_id(trade_id)
                if trade:
                    affected_positions.add((trade['account'], trade['instrument']))

                # Build update query
                set_clauses = []
                params = []

                if 'side_of_market' in update:
                    set_clauses.append("side_of_market = ?")
                    params.append(update['side_of_market'])

                if 'quantity' in update:
                    set_clauses.append("quantity = ?")
                    params.append(update['quantity'])

                if 'price' in update:
                    # Update both entry and exit price based on side
                    side = update.get('side_of_market', trade['side_of_market'] if trade else '')
                    if side in ['Buy', 'SellShort', 'Long']:
                        set_clauses.append("entry_price = ?")
                    else:
                        set_clauses.append("exit_price = ?")
                    params.append(update['price'])

                if set_clauses:
                    params.append(trade_id)
                    query = f"UPDATE trades SET {', '.join(set_clauses)} WHERE id = ?"
                    db.cursor.execute(query, params)
                    updated_count += 1

            db.conn.commit()

            return jsonify({
                'success': True,
                'updated_count': updated_count,
                'affected_positions': list(affected_positions)
            })

    except Exception as e:
        logger.error(f"Error updating executions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@execution_review_bp.route('/api/delete', methods=['POST'])
def delete_executions():
    """Delete selected executions"""
    try:
        data = request.get_json()
        trade_ids = data.get('trade_ids', [])

        if not trade_ids:
            return jsonify({'success': False, 'error': 'No trades to delete'}), 400

        with FuturesDB() as db:
            # Get affected positions before deletion
            affected_positions = set()
            for trade_id in trade_ids:
                trade = db.get_trade_by_id(trade_id)
                if trade:
                    affected_positions.add((trade['account'], trade['instrument']))

            # Delete trades
            placeholders = ','.join('?' * len(trade_ids))
            db.cursor.execute(f"DELETE FROM trades WHERE id IN ({placeholders})", trade_ids)
            deleted_count = db.cursor.rowcount
            db.conn.commit()

            return jsonify({
                'success': True,
                'deleted_count': deleted_count,
                'affected_positions': list(affected_positions)
            })

    except Exception as e:
        logger.error(f"Error deleting executions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@execution_review_bp.route('/api/rebuild-positions', methods=['POST'])
def rebuild_positions():
    """Rebuild positions for specified account/instrument pairs"""
    try:
        data = request.get_json()
        affected_positions = data.get('affected_positions', [])

        with EnhancedPositionServiceV2() as service:
            if affected_positions:
                # Rebuild specific account/instrument pairs
                for account, instrument in affected_positions:
                    service.rebuild_positions_for_account_instrument(account, instrument)
                message = f"Rebuilt positions for {len(affected_positions)} account/instrument pairs"
            else:
                # Rebuild all positions
                result = service.rebuild_positions_from_trades()
                message = f"Rebuilt {result.get('positions_created', 0)} positions from {result.get('trades_processed', 0)} trades"

        return jsonify({
            'success': True,
            'message': message
        })

    except Exception as e:
        logger.error(f"Error rebuilding positions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
