from flask import Blueprint, render_template, request, jsonify
from scripts.TradingLog_db import FuturesDB
from utils.logging_config import get_logger

logger = get_logger(__name__)
execution_analysis_bp = Blueprint('execution_analysis', __name__)

@execution_analysis_bp.route('/reports/execution-quality')
def execution_quality():
    """Execution quality analysis report"""
    try:
        # Get filter parameters
        account = request.args.get('account')
        instrument = request.args.get('instrument')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        with FuturesDB() as db:
            # Get execution quality analysis
            analysis_data = db.get_execution_quality_analysis(
                account=account,
                instrument=instrument,
                start_date=start_date,
                end_date=end_date
            )
            
            # Get accounts and instruments for filters
            accounts = db.get_unique_accounts()
            instruments = db.get_unique_instruments()
            
        return render_template('reports/execution_quality.html',
                             analysis_data=analysis_data,
                             accounts=accounts,
                             instruments=instruments,
                             filters={
                                 'account': account,
                                 'instrument': instrument,
                                 'start_date': start_date,
                                 'end_date': end_date
                             })
    except Exception as e:
        logger.error(f"Error loading execution quality analysis: {e}")
        return render_template('error.html', error="Failed to load execution quality analysis"), 500

@execution_analysis_bp.route('/reports/timing-analysis')
def timing_analysis():
    """Trading timing patterns analysis"""
    try:
        # Get filter parameters
        account = request.args.get('account')
        instrument = request.args.get('instrument')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        with FuturesDB() as db:
            # Get execution quality analysis (includes timing data)
            analysis_data = db.get_execution_quality_analysis(
                account=account,
                instrument=instrument,
                start_date=start_date,
                end_date=end_date
            )
            
            # Get accounts and instruments for filters
            accounts = db.get_unique_accounts()
            instruments = db.get_unique_instruments()
            
        return render_template('reports/timing_analysis.html',
                             analysis_data=analysis_data,
                             accounts=accounts,
                             instruments=instruments,
                             filters={
                                 'account': account,
                                 'instrument': instrument,
                                 'start_date': start_date,
                                 'end_date': end_date
                             })
    except Exception as e:
        logger.error(f"Error loading timing analysis: {e}")
        return render_template('error.html', error="Failed to load timing analysis"), 500

@execution_analysis_bp.route('/reports/position-sizing')
def position_sizing():
    """Position sizing analysis"""
    try:
        # Get filter parameters
        account = request.args.get('account')
        instrument = request.args.get('instrument')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        with FuturesDB() as db:
            # Get execution quality analysis (includes position sizing data)
            analysis_data = db.get_execution_quality_analysis(
                account=account,
                instrument=instrument,
                start_date=start_date,
                end_date=end_date
            )
            
            # Get accounts and instruments for filters
            accounts = db.get_unique_accounts()
            instruments = db.get_unique_instruments()
            
        return render_template('reports/position_sizing.html',
                             analysis_data=analysis_data,
                             accounts=accounts,
                             instruments=instruments,
                             filters={
                                 'account': account,
                                 'instrument': instrument,
                                 'start_date': start_date,
                                 'end_date': end_date
                             })
    except Exception as e:
        logger.error(f"Error loading position sizing analysis: {e}")
        return render_template('error.html', error="Failed to load position sizing analysis"), 500

@execution_analysis_bp.route('/api/execution-quality/hourly-data')
def api_hourly_data():
    """API endpoint for hourly performance data"""
    try:
        # Get parameters
        account = request.args.get('account')
        instrument = request.args.get('instrument')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        with FuturesDB() as db:
            analysis_data = db.get_execution_quality_analysis(
                account=account,
                instrument=instrument,
                start_date=start_date,
                end_date=end_date
            )
            
        return jsonify(analysis_data.get('hourly_performance', []))
    except Exception as e:
        logger.error(f"Error getting hourly data: {e}")
        return jsonify({'error': str(e)}), 500

@execution_analysis_bp.route('/api/execution-quality/position-size-data')
def api_position_size_data():
    """API endpoint for position size analysis data"""
    try:
        # Get parameters
        account = request.args.get('account')
        instrument = request.args.get('instrument')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        with FuturesDB() as db:
            analysis_data = db.get_execution_quality_analysis(
                account=account,
                instrument=instrument,
                start_date=start_date,
                end_date=end_date
            )
            
        return jsonify(analysis_data.get('position_size_analysis', []))
    except Exception as e:
        logger.error(f"Error getting position size data: {e}")
        return jsonify({'error': str(e)}), 500

@execution_analysis_bp.route('/api/execution-quality/hold-time-data')
def api_hold_time_data():
    """API endpoint for hold time analysis data"""
    try:
        # Get parameters
        account = request.args.get('account')
        instrument = request.args.get('instrument')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        with FuturesDB() as db:
            analysis_data = db.get_execution_quality_analysis(
                account=account,
                instrument=instrument,
                start_date=start_date,
                end_date=end_date
            )
            
        return jsonify(analysis_data.get('hold_time_analysis', []))
    except Exception as e:
        logger.error(f"Error getting hold time data: {e}")
        return jsonify({'error': str(e)}), 500

@execution_analysis_bp.route('/api/executions/<int:position_id>')
def get_position_executions(position_id):
    """API endpoint for position execution arrow data"""
    try:
        # Use PositionService to get position data (same as position detail page)
        from services.enhanced_position_service_v2 import EnhancedPositionServiceV2 as PositionService
        
        with PositionService() as pos_service:
            # Get all positions and find the one with matching ID
            result = pos_service.get_positions(page_size=1000)  # Get enough to find the position
            positions = result['positions']
            position = next((p for p in positions if p['id'] == position_id), None)
            
            if not position:
                return jsonify({
                    'success': False,
                    'error': 'Position not found',
                    'position_id': position_id,
                    'executions': []
                }), 404
            
            # Transform position data for chart arrow rendering
            arrow_data = []
            
            # Create entry arrow
            if position.get('entry_time') and position.get('average_entry_price'):
                arrow_data.append({
                    'execution_id': f"{position_id}_entry",
                    'position_id': position_id,
                    'timestamp': position['entry_time'],
                    'price': float(position['average_entry_price']),
                    'quantity': int(position.get('total_quantity', 0)),
                    'side': 'Buy' if 'Long' in position.get('position_type', '') else 'Sell',
                    'type': 'entry',
                    'commission': float(position.get('total_commission', 0)) / 2,  # Split commission between entry/exit
                    'pnl': 0.0  # Entry always has 0 P&L
                })
            
            # Create exit arrow (if position is closed)
            if position.get('position_status') == 'closed' and position.get('exit_time') and position.get('average_exit_price'):
                arrow_data.append({
                    'execution_id': f"{position_id}_exit",
                    'position_id': position_id,
                    'timestamp': position['exit_time'],
                    'price': float(position['average_exit_price']),
                    'quantity': -int(position.get('total_quantity', 0)),  # Negative for exit
                    'side': 'Sell' if 'Long' in position.get('position_type', '') else 'Buy',
                    'type': 'exit',
                    'commission': float(position.get('total_commission', 0)) / 2,  # Split commission
                    'pnl': float(position.get('total_dollars_pnl', 0))
                })
            
            return jsonify({
                'success': True,
                'position_id': position_id,
                'executions': arrow_data,
                'count': len(arrow_data),
                'position_summary': {
                    'instrument': position.get('instrument'),
                    'position_type': position.get('position_type'),
                    'quantity': position.get('total_quantity'),
                    'net_pnl': position.get('total_dollars_pnl'),
                    'position_status': position.get('position_status')
                }
            })
            
    except Exception as e:
        logger.error(f"Error getting position executions {position_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'position_id': position_id,
            'executions': []
        }), 500