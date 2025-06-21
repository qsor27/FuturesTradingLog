"""
Position Routes - Handle position-based views and operations
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from position_service import PositionService
from TradingLog_db import FuturesDB
import logging
import os
import glob
import json

positions_bp = Blueprint('positions', __name__)
logger = logging.getLogger('positions')


@positions_bp.route('/')
def positions_dashboard():
    """Main positions dashboard showing aggregated positions instead of individual trades"""
    # Get filter parameters
    sort_by = request.args.get('sort_by', 'entry_time')
    sort_order = request.args.get('sort_order', 'DESC')
    account_filter = request.args.get('account')
    instrument_filter = request.args.get('instrument')
    status_filter = request.args.get('status')  # 'open', 'closed', or None for all
    
    # Get pagination parameters
    try:
        page = max(1, int(request.args.get('page', 1)))
        page_size = int(request.args.get('page_size', 50))
    except (ValueError, TypeError):
        page = 1
        page_size = 50
    
    # Validate page_size
    allowed_page_sizes = [10, 25, 50, 100]
    if page_size not in allowed_page_sizes:
        page_size = 50
    
    with PositionService() as pos_service:
        # Get positions
        positions, total_count, total_pages = pos_service.get_positions(
            page_size=page_size,
            page=page,
            account=account_filter,
            instrument=instrument_filter,
            status=status_filter,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # Get statistics
        position_stats = pos_service.get_position_statistics(account=account_filter)
    
    # Get unique values for filters
    with FuturesDB() as db:
        accounts = db.get_unique_accounts()
        instruments = db.get_unique_instruments()
    
    # Ensure page is within valid range
    if page > total_pages and total_pages > 0:
        return redirect(url_for('positions.positions_dashboard',
            page=total_pages,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            account=account_filter,
            instrument=instrument_filter,
            status=status_filter
        ))
    
    return render_template(
        'positions/dashboard.html',
        positions=positions,
        stats=position_stats,
        sort_by=sort_by,
        sort_order=sort_order,
        accounts=accounts,
        instruments=instruments,
        selected_account=account_filter,
        selected_instrument=instrument_filter,
        selected_status=status_filter,
        current_page=page,
        total_pages=total_pages,
        page_size=page_size,
        total_count=total_count
    )


@positions_bp.route('/<int:position_id>')
def position_detail(position_id):
    """Position detail page showing all executions that make up the position"""
    with PositionService() as pos_service:
        position = pos_service.get_position_by_id(position_id)
    
    if not position:
        return render_template('error.html', 
                             error_message="Position not found",
                             error_code=404), 404
    
    # Calculate additional metrics for the detail view
    if position['executions']:
        # Calculate execution timing analysis
        executions = position['executions']
        position['first_execution'] = min(ex['entry_time'] for ex in executions)
        position['last_execution'] = max(ex['exit_time'] for ex in executions if ex['exit_time'])
        
        # Calculate position duration if closed
        if position['position_status'] == 'closed' and position['exit_time']:
            from datetime import datetime
            try:
                entry_dt = datetime.fromisoformat(position['entry_time'].replace('Z', '+00:00'))
                exit_dt = datetime.fromisoformat(position['exit_time'].replace('Z', '+00:00'))
                duration = exit_dt - entry_dt
                position['duration_minutes'] = duration.total_seconds() / 60
                position['duration_display'] = f"{duration.days}d {duration.seconds//3600}h {(duration.seconds%3600)//60}m"
            except:
                position['duration_minutes'] = 0
                position['duration_display'] = "Unknown"
        
        # Calculate R:R ratio for closed positions
        if position['position_status'] == 'closed':
            total_pnl = position['total_dollars_pnl']
            commission = position['total_commission']
            
            if total_pnl > 0 and commission > 0:
                # Winner: Reward / Risk
                position['reward_risk_ratio'] = round(total_pnl / commission, 2)
                position['rr_display'] = f"{position['reward_risk_ratio']}:1"
            elif total_pnl < 0 and commission > 0:
                # Loser: Risk / Reward  
                risk_ratio = abs(total_pnl) / commission
                position['reward_risk_ratio'] = round(1 / risk_ratio, 2) if risk_ratio > 0 else 0
                position['rr_display'] = f"1:{round(risk_ratio, 2)}"
            else:
                position['reward_risk_ratio'] = 0
                position['rr_display'] = "N/A"
    
    return render_template('positions/detail.html', position=position)


@positions_bp.route('/rebuild', methods=['POST'])
def rebuild_positions():
    """Rebuild all positions from existing trades data"""
    try:
        with PositionService() as pos_service:
            result = pos_service.rebuild_positions_from_trades()
        
        return jsonify({
            'success': True,
            'message': f"Successfully rebuilt {result['positions_created']} positions from {result['trades_processed']} trades",
            'positions_created': result['positions_created'],
            'trades_processed': result['trades_processed']
        })
        
    except Exception as e:
        logger.error(f"Error rebuilding positions: {e}")
        return jsonify({
            'success': False,
            'message': f"Error rebuilding positions: {str(e)}"
        }), 500


@positions_bp.route('/api/statistics')
def api_position_statistics():
    """API endpoint for position statistics"""
    account = request.args.get('account')
    
    try:
        with PositionService() as pos_service:
            stats = pos_service.get_position_statistics(account=account)
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting position statistics: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@positions_bp.route('/api/executions/<int:position_id>')
def api_position_executions(position_id):
    """API endpoint to get execution details for a position"""
    try:
        with PositionService() as pos_service:
            position = pos_service.get_position_by_id(position_id)
        
        if not position:
            return jsonify({
                'success': False,
                'message': 'Position not found'
            }), 404
        
        return jsonify({
            'success': True,
            'position': position,
            'executions': position.get('executions', [])
        })
        
    except Exception as e:
        logger.error(f"Error getting position executions: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@positions_bp.route('/debug')
def debug_positions():
    """Debug page to examine position building logic"""
    from TradingLog_db import FuturesDB
    
    # Get recent trades for debugging
    with FuturesDB() as db:
        db.cursor.execute("""
            SELECT * FROM trades 
            ORDER BY entry_time DESC 
            LIMIT 20
        """)
        recent_trades = [dict(row) for row in db.cursor.fetchall()]
        
        # Get unique account/instrument combinations
        db.cursor.execute("""
            SELECT DISTINCT account, instrument, COUNT(*) as trade_count
            FROM trades 
            GROUP BY account, instrument
            ORDER BY trade_count DESC
        """)
        account_instruments = [dict(row) for row in db.cursor.fetchall()]
    
    return render_template('positions/debug.html', 
                         recent_trades=recent_trades,
                         account_instruments=account_instruments)


@positions_bp.route('/debug/<account>/<instrument>')
def debug_account_instrument(account, instrument):
    """Debug specific account/instrument combination"""
    from TradingLog_db import FuturesDB
    
    with FuturesDB() as db:
        # Get all trades for this account/instrument
        db.cursor.execute("""
            SELECT * FROM trades 
            WHERE account = ? AND instrument = ?
            ORDER BY entry_time, exit_time
        """, (account, instrument))
        trades = [dict(row) for row in db.cursor.fetchall()]
    
    # Test position building with detailed logging
    with PositionService() as pos_service:
        # Enable debug logging
        import logging
        position_logger = logging.getLogger('position_service')
        position_logger.setLevel(logging.INFO)
        
        # Add a handler to capture logs for display
        log_handler = logging.StreamHandler()
        position_logger.addHandler(log_handler)
        
        # Build positions for this specific combination
        positions = pos_service._build_positions_from_execution_flow(trades, account, instrument)
    
    return jsonify({
        'account': account,
        'instrument': instrument,
        'trade_count': len(trades),
        'trades': trades,
        'positions_built': len(positions),
        'positions': positions
    })


@positions_bp.route('/delete', methods=['POST'])
def delete_positions():
    """Delete selected positions and their associated executions"""
    try:
        data = request.get_json()
        
        if not data or 'position_ids' not in data:
            return jsonify({
                'success': False,
                'message': 'No position IDs provided'
            }), 400
        
        position_ids = data['position_ids']
        
        if not position_ids:
            return jsonify({
                'success': False,
                'message': 'No position IDs provided'
            }), 400
        
        # Convert to integers and validate
        try:
            position_ids = [int(pid) for pid in position_ids]
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'message': 'Invalid position ID format'
            }), 400
        
        with PositionService() as pos_service:
            deleted_count = pos_service.delete_positions(position_ids)
        
        return jsonify({
            'success': True,
            'message': f'Successfully deleted {deleted_count} position{"s" if deleted_count != 1 else ""}',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        logger.error(f"Error deleting positions: {e}")
        return jsonify({
            'success': False,
            'message': f'Error deleting positions: {str(e)}'
        }), 500


@positions_bp.route('/list-csv-files')
def list_csv_files():
    """List available CSV files for re-import"""
    try:
        from config import config
        data_dir = config.data_dir
        
        # Look for CSV files in data directory
        csv_pattern = os.path.join(data_dir, "*.csv")
        csv_files = glob.glob(csv_pattern)
        
        # Get just the filenames
        filenames = [os.path.basename(f) for f in csv_files]
        filenames.sort(reverse=True)  # Most recent first
        
        return jsonify({
            'success': True,
            'files': filenames,
            'count': len(filenames)
        })
        
    except Exception as e:
        logger.error(f"Error listing CSV files: {e}")
        return jsonify({
            'success': False,
            'message': f'Error listing CSV files: {str(e)}'
        }), 500


@positions_bp.route('/reimport-csv', methods=['POST'])
def reimport_csv():
    """Re-import trades from a selected CSV file"""
    try:
        data = request.get_json()
        
        if not data or 'filename' not in data:
            return jsonify({
                'success': False,
                'message': 'No filename provided'
            }), 400
        
        filename = data['filename']
        
        if not filename:
            return jsonify({
                'success': False,
                'message': 'No filename provided'
            }), 400
        
        # Security check - ensure filename contains no path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({
                'success': False,
                'message': 'Invalid filename'
            }), 400
        
        from config import config
        data_dir = config.data_dir
        csv_path = os.path.join(data_dir, filename)
        
        # Verify file exists
        if not os.path.exists(csv_path):
            return jsonify({
                'success': False,
                'message': f'File not found: {filename}'
            }), 404
        
        # Process the raw NinjaTrader CSV file first
        import pandas as pd
        from ExecutionProcessing import process_trades
        
        # Load multipliers
        multipliers_path = config.data_dir / 'config' / 'instrument_multipliers.json'
        with open(multipliers_path, 'r') as f:
            multipliers = json.load(f)
        
        # Read and process the raw CSV
        df = pd.read_csv(csv_path)
        print(f"Read {len(df)} raw executions from {filename}")
        
        # Process the trades
        processed_trades = process_trades(df, multipliers)
        print(f"Processed into {len(processed_trades)} completed trades")
        
        if not processed_trades:
            return jsonify({
                'success': False,
                'message': 'No completed trades found in CSV file'
            }), 400
        
        # Create a processed DataFrame for import
        processed_df = pd.DataFrame(processed_trades)
        
        # Save processed file temporarily
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            processed_df.to_csv(temp_file.name, index=False)
            temp_csv_path = temp_file.name
        
        try:
            # Import the processed CSV file
            with FuturesDB() as db:
                success = db.import_csv(temp_csv_path)
            
            if success:
                # Rebuild positions after successful import
                with PositionService() as pos_service:
                    result = pos_service.rebuild_positions_from_trades()
                
                return jsonify({
                    'success': True,
                    'message': f'Successfully processed and imported {len(processed_trades)} trades from {filename}. Rebuilt {result["positions_created"]} positions.',
                    'trades_imported': len(processed_trades),
                    'positions_created': result['positions_created'],
                    'trades_processed': result['trades_processed']
                })
            else:
                return jsonify({
                    'success': False,
                    'message': f'Failed to import processed trades from {filename}'
                }), 500
        finally:
            # Clean up temporary file
            os.unlink(temp_csv_path)
        
    except Exception as e:
        logger.error(f"Error re-importing CSV: {e}")
        return jsonify({
            'success': False,
            'message': f'Error re-importing CSV: {str(e)}'
        }), 500