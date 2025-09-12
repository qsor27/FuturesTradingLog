"""
Position Routes - Handle position-based views and operations
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from services.enhanced_position_service_v2 import EnhancedPositionServiceV2 as PositionService
from scripts.TradingLog_db import FuturesDB
from services.position_overlap_integration import rebuild_positions_with_overlap_prevention
from services.position_overlap_prevention import PositionOverlapPrevention
from services.position_overlap_analysis import PositionOverlapAnalyzer
import logging
import os
import glob
import json
from datetime import datetime

# Import the chart execution extensions
import scripts.TradingLog_db_extension

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
        result = pos_service.get_positions(
            page_size=page_size,
            page=page,
            account=account_filter,
            instrument=instrument_filter,
            status=status_filter
        )
        
        positions = result['positions']
        total_count = result['total_count']
        total_pages = result['total_pages']
        
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
        # Get all positions and find the one with matching ID
        result = pos_service.get_positions(page_size=1000)  # Get enough to find the position
        positions = result['positions']
        position = next((p for p in positions if p['id'] == position_id), None)
        
        if not position:
            return render_template('error.html', 
                                 error_message="Position not found",
                                 error_code=404), 404
        
        # Get the executions that make up this position
        executions = pos_service.get_position_executions(position_id)
        position['executions'] = executions
        
        # Debug logging
        logger.info(f"Position {position_id} details: execution_count={position.get('execution_count')}, actual_executions={len(executions)}")
        logger.info(f"Executions found: {[{'id': e.get('id'), 'side': e.get('side_of_market'), 'qty': e.get('quantity')} for e in executions[:5]]}")  # First 5 only
    
    # Calculate additional metrics for the detail view
    # Use existing position data for timing analysis
    position['first_execution'] = position['entry_time']
    position['last_execution'] = position.get('exit_time')
    
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


@positions_bp.route('/rebuild-enhanced', methods=['POST'])
def rebuild_positions_enhanced():
    """Rebuild all positions with comprehensive validation and overlap prevention"""
    try:
        result = rebuild_positions_with_overlap_prevention()
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': f"Successfully rebuilt {result['positions_created']} positions from {result['groups_processed']} instrument groups",
                'positions_created': result['positions_created'],
                'groups_processed': result['groups_processed'],
                'warnings': result.get('warnings', []),
                'validation_enabled': True
            })
        else:
            return jsonify({
                'success': False,
                'message': f"Rebuild failed: {result.get('error', 'Unknown error')}",
                'errors': result.get('errors', [])
            }), 500
        
    except Exception as e:
        logger.error(f"Error rebuilding positions with enhanced validation: {e}")
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


@positions_bp.route('/api/<int:position_id>/executions-chart')
def api_position_executions_chart(position_id):
    """API endpoint to get execution data formatted for chart arrow display"""
    try:
        # Get query parameters
        timeframe = request.args.get('timeframe', '1h')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Validate timeframe
        valid_timeframes = ['1m', '5m', '1h']
        if timeframe not in valid_timeframes:
            return jsonify({
                'success': False,
                'error': f'Invalid timeframe. Must be one of: {valid_timeframes}'
            }), 400
        
        with FuturesDB() as db:
            chart_data = db.get_position_executions_for_chart_cached(position_id, timeframe, start_date, end_date)
        
        if not chart_data:
            return jsonify({
                'success': False,
                'error': 'Position not found'
            }), 404
        
        return jsonify({
            'success': True,
            **chart_data
        })
        
    except Exception as e:
        logger.error(f"Error getting position execution chart data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/debug')
def debug_positions():
    """Debug page to examine position building logic"""
    from scripts.TradingLog_db import FuturesDB
    
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
    from scripts.TradingLog_db import FuturesDB
    
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
    """DEPRECATED: List available CSV files for re-import. Use /api/csv/available-files instead."""
    logger.warning("DEPRECATED: /positions/list-csv-files called. Use /api/csv/available-files instead.")
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
    """DEPRECATED: Re-import trades from a selected CSV file. Use /api/csv/reprocess instead."""
    logger.warning("DEPRECATED: /positions/reimport-csv called. Use /api/csv/reprocess instead.")
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
        
        # Import raw executions directly without pre-processing into completed trades
        import pandas as pd
        
        # Read the raw CSV with robust parsing for malformed files
        try:
            df = pd.read_csv(csv_path, 
                           encoding='utf-8-sig',  # Handle BOM characters  
                           on_bad_lines='skip',   # Skip malformed lines
                           skipinitialspace=True) # Handle extra spaces
        except Exception as e:
            try:
                # Fallback: use Python engine for more robust parsing
                df = pd.read_csv(csv_path,
                               encoding='utf-8-sig', 
                               engine='python',
                               on_bad_lines='skip')
            except Exception as e2:
                return jsonify({
                    'success': False,
                    'message': f'Unable to parse CSV: {str(e2)}'
                }), 400
        print(f"Read {len(df)} raw executions from {filename}")
        
        # Import raw executions directly to database
        with FuturesDB() as db:
            success = db.import_raw_executions(csv_path)
        
        if success:
            # Rebuild positions after successful import
            with PositionService() as pos_service:
                result = pos_service.rebuild_positions_from_trades()
            
            return jsonify({
                'success': True,
                'message': f'Successfully imported {len(df)} executions from {filename}. Rebuilt {result["positions_created"]} positions.',
                'executions_imported': len(df),
                'positions_created': result['positions_created'],
                'trades_processed': result['trades_processed']
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Failed to import executions from {filename}'
            }), 500
        
    except Exception as e:
        logger.error(f"Error re-importing CSV: {e}")
        return jsonify({
            'success': False,
            'message': f'Error re-importing CSV: {str(e)}'
        }), 500


# Position Validation API Endpoints

@positions_bp.route('/api/validation/prevention-report')
def get_prevention_report():
    """Generate comprehensive position overlap prevention report"""
    try:
        account = request.args.get('account')
        instrument = request.args.get('instrument')
        
        with PositionOverlapPrevention() as validator:
            report = validator.generate_prevention_report(account=account, instrument=instrument)
            
        return jsonify({
            'success': True,
            'report': report,
            'report_type': 'prevention_report',
            'filters': {
                'account': account,
                'instrument': instrument
            }
        })
        
    except Exception as e:
        logger.error(f"Error generating prevention report: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/validation/overlap-analysis')
def get_overlap_analysis():
    """Generate comprehensive overlap analysis report"""
    try:
        with PositionOverlapAnalyzer() as analyzer:
            report = analyzer.generate_overlap_report()
            
        return jsonify({
            'success': True,
            'report': report,
            'report_type': 'overlap_analysis'
        })
        
    except Exception as e:
        logger.error(f"Error generating overlap analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/validation/current-positions')
def get_current_positions_validation():
    """Validate current positions and return structured data"""
    try:
        with PositionOverlapAnalyzer() as analyzer:
            analysis = analyzer.analyze_current_positions()
            
        return jsonify({
            'success': True,
            'analysis': analysis,
            'validation_type': 'current_positions'
        })
        
    except Exception as e:
        logger.error(f"Error validating current positions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/validation/boundary-validation')
def get_boundary_validation():
    """Validate position boundaries and return structured data"""
    try:
        with PositionOverlapAnalyzer() as analyzer:
            validation = analyzer.validate_position_boundaries()
            
        return jsonify({
            'success': True,
            'validation': validation,
            'validation_type': 'boundary_validation'
        })
        
    except Exception as e:
        logger.error(f"Error validating position boundaries: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/validation/summary')
def get_validation_summary():
    """Get comprehensive validation summary combining multiple checks"""
    try:
        account = request.args.get('account')
        instrument = request.args.get('instrument')
        
        with PositionOverlapAnalyzer() as analyzer:
            current_analysis = analyzer.analyze_current_positions()
            boundary_validation = analyzer.validate_position_boundaries()
            
        with PositionOverlapPrevention() as validator:
            # Get basic validation data for summary
            pass
            
        summary = {
            'total_positions': current_analysis.get('total_positions', 0),
            'groups_analyzed': current_analysis.get('groups_analyzed', 0),
            'overlaps_found': current_analysis.get('overlaps_found', 0),
            'boundary_violations': boundary_validation.get('boundary_violations', 0),
            'has_issues': current_analysis.get('overlaps_found', 0) > 0 or boundary_validation.get('boundary_violations', 0) > 0,
            'validation_timestamp': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'summary': summary,
            'details': {
                'current_positions': current_analysis,
                'boundary_validation': boundary_validation
            }
        })
        
    except Exception as e:
        logger.error(f"Error generating validation summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/validation/health')
def get_validation_health():
    """Quick health check for validation system"""
    try:
        health_status = {
            'validation_system': 'available',
            'overlap_prevention': 'active',
            'enhanced_position_service': 'active',
            'endpoints': [
                '/api/validation/prevention-report',
                '/api/validation/overlap-analysis',
                '/api/validation/current-positions',
                '/api/validation/boundary-validation',
                '/api/validation/summary',
                '/api/validation/health'
            ]
        }
        
        return jsonify({
            'success': True,
            'status': 'healthy',
            'health': health_status
        })
        
    except Exception as e:
        logger.error(f"Error checking validation health: {e}")
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e)
        }), 500

