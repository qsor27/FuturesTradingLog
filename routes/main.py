from flask import Blueprint, render_template, request, jsonify, redirect, url_for, send_from_directory
from scripts.TradingLog_db import FuturesDB
from services.background_services import gap_filling_service, get_services_status
from services.data_service import ohlc_service
import os
import time
import shutil
import logging

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Main page now shows positions instead of individual trades"""
    # Redirect to positions dashboard for better organization
    return redirect(url_for('positions.positions_dashboard'))

@main_bp.route('/trades')
def trades_legacy():
    """Legacy trades view - individual trade executions (for debugging/admin)"""
    # Get all query parameters with defaults
    sort_by = request.args.get('sort_by', 'entry_time')
    sort_order = request.args.get('sort_order', 'DESC')
    account_filters = request.args.getlist('accounts')
    trade_result = request.args.get('trade_result')
    side_filter = request.args.get('side')
    
    # Get pagination parameters with proper error handling
    try:
        page = max(1, int(request.args.get('page', 1)))
        page_size = int(request.args.get('page_size', 50))
        cursor_id = request.args.get('cursor_id')
        cursor_time = request.args.get('cursor_time')
        cursor_id = int(cursor_id) if cursor_id else None
    except (ValueError, TypeError):
        page = 1
        page_size = 50
        cursor_id = None
        cursor_time = None
    
    # Validate page_size
    allowed_page_sizes = [10, 25, 50, 100]
    if page_size not in allowed_page_sizes:
        page_size = 50
    
    with FuturesDB() as db:
        accounts = db.get_unique_accounts()
        trades, total_count, total_pages, next_cursor_id, next_cursor_time = db.get_recent_trades(
            page_size=page_size,
            page=page,
            sort_by=sort_by,
            sort_order=sort_order,
            account=account_filters,
            trade_result=trade_result,
            side=side_filter,
            cursor_id=cursor_id,
            cursor_time=cursor_time
        )
    
    # Ensure page is within valid range
    if page > total_pages and total_pages > 0:
        page = total_pages
        return redirect(url_for('main.trades_legacy', 
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            account=account_filters,
            trade_result=trade_result,
            side=side_filter
        ))
    
    return render_template(
        'main.html', 
        trades=trades,
        sort_by=sort_by,
        sort_order=sort_order,
        accounts=accounts,
        selected_accounts=account_filters,
        selected_result=trade_result,
        selected_side=side_filter,
        current_page=page,
        total_pages=total_pages,
        page_size=page_size,
        total_count=total_count,
        next_cursor_id=next_cursor_id,
        next_cursor_time=next_cursor_time
    )

@main_bp.route('/delete-trades', methods=['POST'])
def delete_trades():
    try:
        data = request.get_json()
        trade_ids = data.get('trade_ids', [])
        
        if not trade_ids:
            return jsonify({'success': False, 'message': 'No trades selected'})
        
        # Get auto_update_positions parameter (default: true)
        auto_update_positions = data.get('auto_update_positions', True)
        
        # Get affected positions before deletion
        affected_positions = set()
        if auto_update_positions:
            with FuturesDB() as db:
                for trade_id in trade_ids:
                    trade = db.get_trade_by_id(trade_id)
                    if trade:
                        account = trade.get('account')
                        instrument = trade.get('instrument')
                        if account and instrument:
                            affected_positions.add((account, instrument))
        
        with FuturesDB() as db:
            success = db.delete_trades(trade_ids)
        
        response_data = {
            'success': success,
            'auto_update_positions': auto_update_positions
        }
        
        # Trigger automatic position updates if enabled and deletion was successful
        if success and auto_update_positions and affected_positions:
            try:
                from services.enhanced_position_service_v2 import EnhancedPositionServiceV2
                position_updates = {}
                
                with EnhancedPositionServiceV2() as position_service:
                    for account, instrument in affected_positions:
                        result = position_service.rebuild_positions_for_account_instrument(account, instrument)
                        position_updates[f"{account}/{instrument}"] = result
                        
                        logger.info(f"Triggered position update after deletion: {account}/{instrument}")
                
                response_data['position_updates'] = position_updates
                
            except Exception as pos_error:
                logger.error(f"Error triggering position updates after deletion: {pos_error}")
                response_data['position_update_warning'] = f"Position updates failed: {str(pos_error)}"
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error in delete_trades: {e}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/csv-manager')
def csv_manager():
    """DEPRECATED: Legacy CSV Management interface for batch import operations. Use /unified-csv-manager instead."""
    logger.warning("DEPRECATED: /csv-manager called. Use /unified-csv-manager with unified import system instead.")
    from config import config
    
    # Get list of CSV files in data directory and archive subdirectory
    data_dir = str(config.data_dir)
    csv_files = []
    
    try:
        # Check root data directory
        for filename in os.listdir(data_dir):
            if filename.endswith('.csv'):
                file_path = os.path.join(data_dir, filename)
                file_stats = os.stat(file_path)
                csv_files.append({
                    'filename': filename,
                    'path': file_path,
                    'size': file_stats.st_size,
                    'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(file_stats.st_mtime)),
                    'location': 'data'
                })
        
        # Check archive subdirectory
        archive_dir = os.path.join(data_dir, 'archive')
        if os.path.exists(archive_dir):
            for filename in os.listdir(archive_dir):
                if filename.endswith('.csv'):
                    file_path = os.path.join(archive_dir, filename)
                    file_stats = os.stat(file_path)
                    csv_files.append({
                        'filename': filename,
                        'path': file_path,
                        'size': file_stats.st_size,
                        'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(file_stats.st_mtime)),
                        'location': 'archive'
                    })
        
        # Sort by modification date (newest first)
        csv_files.sort(key=lambda x: x['modified'], reverse=True)
        
    except Exception as e:
        print(f"Error listing CSV files: {e}")
        csv_files = []
    
    return render_template('csv_manager.html', csv_files=csv_files, data_dir=data_dir)

@main_bp.route('/unified-csv-manager')
def unified_csv_manager():
    """Unified CSV Management interface using the new unified import system"""
    return render_template('unified_csv_manager.html')

def detect_csv_format(file_path):
    """Detect if CSV is NinjaTrader format or processed TradeLog format"""
    try:
        import pandas as pd
        df = pd.read_csv(file_path, nrows=1)  # Read just the header
        columns = set(df.columns)
        
        # Check for NinjaTrader execution format
        nt_columns = {'Instrument', 'Action', 'Quantity', 'Price', 'Time', 'ID', 'Account'}
        if nt_columns <= columns:
            return 'ninjatrade'
        
        # Check for processed TradeLog format  
        tradelog_columns = {'Instrument', 'Side of Market', 'Entry Price', 'Entry Time', 'Exit Time'}
        if tradelog_columns <= columns:
            return 'tradelog'
            
        return 'unknown'
    except Exception:
        return 'unknown'

def process_ninjatrade_file(file_path):
    """Process a NinjaTrader CSV file using ExecutionProcessing"""
    import tempfile
    import shutil
    import sys
    from config import config
    
    # Create a unique temporary filename in the data directory
    timestamp = int(time.time())
    temp_ninja_name = f"NinjaTrader_temp_{timestamp}.csv"
    temp_ninja_path = os.path.join(str(config.data_dir), temp_ninja_name)
    
    try:
        # Copy the file to data directory with NinjaTrader prefix
        shutil.copy2(file_path, temp_ninja_path)
        
        # Add scripts directory to path
        scripts_dir = os.path.join(os.getcwd(), 'scripts')
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        
        # Import and run ExecutionProcessing
        import ExecutionProcessing
        
        # The ExecutionProcessing script will process the file and create trade_log.csv
        success = ExecutionProcessing.main()
        
        if success:
            # Return path to the generated trade_log.csv 
            trade_log_path = os.path.join(str(config.data_dir), 'trade_log.csv')
            if os.path.exists(trade_log_path):
                return trade_log_path
        
        return None
            
    except Exception as e:
        print(f"Error processing NinjaTrader file: {e}")
        return None
    finally:
        # Clean up temporary file if it still exists
        if os.path.exists(temp_ninja_path):
            try:
                os.remove(temp_ninja_path)
            except:
                pass

@main_bp.route('/batch-import-csv', methods=['POST'])
def batch_import_csv():
    """DEPRECATED: Import multiple CSV files in batch. Use /api/csv/process-new-files instead."""
    logger.warning("DEPRECATED: /batch-import-csv called. Use /api/csv/process-new-files instead.")
    try:
        data = request.get_json()
        selected_files = data.get('selected_files', [])
        auto_process = data.get('auto_process', True)  # Auto-process NinjaTrader files
        
        if not selected_files:
            return jsonify({'success': False, 'message': 'No files selected for import'})
        
        from config import config
        data_dir = str(config.data_dir)
        
        results = []
        successful_imports = 0
        failed_imports = 0
        
        with FuturesDB() as db:
            for filename in selected_files:
                file_path = os.path.join(data_dir, filename)
                
                # Verify file exists and is safe to import
                if not os.path.exists(file_path) or not filename.endswith('.csv'):
                    results.append({
                        'filename': filename,
                        'success': False,
                        'message': 'File not found or invalid type'
                    })
                    failed_imports += 1
                    continue
                
                try:
                    # Detect file format
                    file_format = detect_csv_format(file_path)
                    processed_file = None
                    
                    if file_format == 'ninjatrade' and auto_process:
                        # Process NinjaTrader file first
                        processed_file = process_ninjatrade_file(file_path)
                        if processed_file:
                            import_path = processed_file
                            message_suffix = " (processed from NinjaTrader format)"
                        else:
                            results.append({
                                'filename': filename,
                                'success': False,
                                'message': 'Failed to process NinjaTrader format'
                            })
                            failed_imports += 1
                            continue
                    elif file_format == 'tradelog':
                        import_path = file_path
                        message_suffix = ""
                    else:
                        results.append({
                            'filename': filename,
                            'success': False,
                            'message': f'Unsupported file format: {file_format}'
                        })
                        failed_imports += 1
                        continue
                    
                    # Import the CSV file
                    success = db.import_csv(import_path)
                    
                    # Clean up temporary processed file
                    if processed_file and os.path.exists(processed_file):
                        import shutil
                        temp_dir = os.path.dirname(processed_file)
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    
                    if success:
                        results.append({
                            'filename': filename,
                            'success': True,
                            'message': f'Successfully imported{message_suffix}'
                        })
                        successful_imports += 1
                    else:
                        results.append({
                            'filename': filename,
                            'success': False,
                            'message': f'Import failed - check file format{message_suffix}'
                        })
                        failed_imports += 1
                        
                except Exception as e:
                    results.append({
                        'filename': filename,
                        'success': False,
                        'message': f'Import error: {str(e)}'
                    })
                    failed_imports += 1
        
        return jsonify({
            'success': True,
            'results': results,
            'summary': {
                'total_files': len(selected_files),
                'successful': successful_imports,
                'failed': failed_imports
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Batch import error: {str(e)}'
        })

@main_bp.route('/test_date_range.html')
def test_date_range():
    """Serve the date range test page"""
    return send_from_directory('.', 'test_date_range.html')

@main_bp.route('/test_chart_simple')
def test_chart_simple():
    """Serve the simple chart test page"""
    return render_template('test_chart_simple.html')

@main_bp.route('/charts')
def charts():
    """Charts page with dropdown to select different contracts"""
    try:
        with FuturesDB() as db:
            # Get instruments with OHLC data and comprehensive metadata
            db.cursor.execute("""
                SELECT 
                    instrument,
                    COUNT(DISTINCT timeframe) as timeframe_count,
                    GROUP_CONCAT(DISTINCT timeframe ORDER BY 
                        CASE timeframe
                            WHEN '1m' THEN 1
                            WHEN '5m' THEN 2
                            WHEN '15m' THEN 3
                            WHEN '1h' THEN 4
                            WHEN '4h' THEN 5
                            WHEN '1d' THEN 6
                            ELSE 7
                        END
                    ) as timeframes,
                    MIN(timestamp) as earliest_data,
                    MAX(timestamp) as latest_data,
                    COUNT(*) as total_records
                FROM ohlc_data 
                WHERE instrument IS NOT NULL
                GROUP BY instrument
                HAVING COUNT(*) >= 50  -- Filter out instruments with insufficient data
                ORDER BY instrument
            """)
            
            ohlc_instruments = []
            import time
            current_time = time.time()
            
            for row in db.cursor.fetchall():
                instrument, timeframe_count, timeframes, earliest, latest, total_records = row
                
                # Calculate data freshness (days since last update)
                days_since_update = (current_time - latest) / (24 * 3600) if latest else float('inf')
                
                ohlc_instruments.append({
                    'instrument': instrument,
                    'timeframe_count': timeframe_count,
                    'timeframes': timeframes.split(',') if timeframes else [],
                    'earliest_data': earliest,
                    'latest_data': latest,
                    'total_records': total_records,
                    'days_since_update': int(days_since_update),
                    'is_recent': days_since_update <= 7  # Data within last week
                })
            
            # Get trade instruments for additional context
            db.cursor.execute("""
                SELECT 
                    instrument,
                    COUNT(*) as trade_count
                FROM trades 
                WHERE instrument IS NOT NULL
                GROUP BY instrument
                ORDER BY instrument
            """)
            
            trade_instruments = [
                {'instrument': row[0], 'trade_count': row[1]} 
                for row in db.cursor.fetchall()
            ]
        
        return render_template('charts.html',
                             ohlc_instruments=ohlc_instruments,
                             trade_instruments=trade_instruments,
                             page_title='Price Charts')
        
    except Exception as e:
        import traceback
        print(f"Error in charts route: {e}")
        traceback.print_exc()
        # Return template with error message instead of crashing
        return render_template('charts.html', 
                             ohlc_instruments=[], 
                             trade_instruments=[],
                             error_message=f"Failed to load instruments: {str(e)}")

@main_bp.route('/symbols')
def symbols():
    """Symbols/Instruments page to view all available symbols with chart data"""
    try:
        with FuturesDB() as db:
            # Get instruments from both trades and OHLC data with stats
            db.cursor.execute("""
                SELECT 
                    instrument,
                    COUNT(DISTINCT timeframe) as timeframe_count,
                    MIN(timestamp) as first_data,
                    MAX(timestamp) as last_data,
                    COUNT(*) as total_records
                FROM ohlc_data 
                WHERE instrument IS NOT NULL
                GROUP BY instrument
                ORDER BY instrument
            """)
            
            ohlc_instruments = []
            for row in db.cursor.fetchall():
                instrument, timeframe_count, first_data, last_data, total_records = row
                ohlc_instruments.append({
                    'instrument': instrument,
                    'timeframe_count': timeframe_count,
                    'first_data': first_data,
                    'last_data': last_data,
                    'total_records': total_records
                })
            
            # Get instruments from trades
            db.cursor.execute("""
                SELECT 
                    instrument,
                    COUNT(*) as trade_count,
                    MIN(entry_time) as first_trade,
                    MAX(entry_time) as last_trade
                FROM trades 
                WHERE instrument IS NOT NULL
                GROUP BY instrument
                ORDER BY instrument
            """)
            
            trade_instruments = {}
            for row in db.cursor.fetchall():
                instrument, trade_count, first_trade, last_trade = row
                trade_instruments[instrument] = {
                    'trade_count': trade_count,
                    'first_trade': first_trade,
                    'last_trade': last_trade
                }
        
        return render_template('symbols.html',
                             ohlc_instruments=ohlc_instruments,
                             trade_instruments=trade_instruments)

    except Exception as e:
        print(f"Error in symbols route: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {e}", 500

@main_bp.route('/api/data-health')
def data_health_api():
    """API endpoint for data health monitoring"""
    try:
        instruments = request.args.getlist('instruments')
        if not instruments:
            # Default to common instruments
            instruments = ['MNQ', 'ES', 'YM', 'RTY', 'NQ', 'CL', 'GC']

        timeframes = request.args.getlist('timeframes')
        if not timeframes:
            timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']

        # Run health check
        health_report = ohlc_service.check_data_health(instruments, timeframes)

        # Calculate summary statistics
        total_checks = 0
        healthy_count = 0
        stale_count = 0
        no_data_count = 0
        error_count = 0

        for instrument_data in health_report.values():
            for tf_data in instrument_data.values():
                total_checks += 1
                status = tf_data.get('status', 'unknown')
                if status == 'healthy':
                    healthy_count += 1
                elif status == 'stale':
                    stale_count += 1
                elif status == 'no_data':
                    no_data_count += 1
                elif status == 'error':
                    error_count += 1

        summary = {
            'health_percentage': (healthy_count / total_checks * 100) if total_checks > 0 else 0,
            'total_checks': total_checks,
            'healthy_count': healthy_count,
            'stale_count': stale_count,
            'no_data_count': no_data_count,
            'error_count': error_count
        }

        return jsonify({
            'success': True,
            'summary': summary,
            'detailed_report': health_report
        })

    except Exception as e:
        logger.error(f"Error in data health API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/background-services/status')
def background_services_status():
    """API endpoint for background services status"""
    try:
        status = get_services_status()
        return jsonify({
            'success': True,
            'services': status
        })
    except Exception as e:
        logger.error(f"Error getting background services status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/background-services/health-check', methods=['POST'])
def trigger_health_check():
    """API endpoint to manually trigger a health check"""
    try:
        instruments = request.json.get('instruments') if request.is_json else None
        health_results = gap_filling_service.run_data_health_check(instruments)

        return jsonify({
            'success': True,
            'health_results': health_results
        })
    except Exception as e:
        logger.error(f"Error triggering health check: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/background-services/force-gap-fill', methods=['POST'])
def force_gap_fill():
    """API endpoint to manually trigger gap filling for specific instrument"""
    try:
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Request must be JSON'
            }), 400

        instrument = request.json.get('instrument')
        timeframes = request.json.get('timeframes', ['1m', '5m', '15m', '1h', '4h', '1d'])
        days_back = request.json.get('days_back', 7)

        if not instrument:
            return jsonify({
                'success': False,
                'error': 'instrument parameter is required'
            }), 400

        results = gap_filling_service.force_gap_fill(instrument, timeframes, days_back)

        return jsonify({
            'success': True,
            'results': results,
            'instrument': instrument,
            'timeframes_processed': len(timeframes)
        })

    except Exception as e:
        logger.error(f"Error in force gap fill: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/monitoring')
def monitoring_dashboard():
    """Data monitoring dashboard"""
    try:
        return render_template('monitoring_dashboard.html')
    except Exception as e:
        logger.error(f"Error loading monitoring dashboard: {e}")
        return f"Error: {e}", 500
