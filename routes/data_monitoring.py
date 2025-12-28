"""
Data Monitoring Routes
Provides monitoring dashboard and alerts for OHLC data coverage
"""

from flask import Blueprint, render_template, jsonify, request
from datetime import datetime, timedelta
import logging
from scripts.automated_data_sync import get_data_sync_status, force_data_sync
from scripts.TradingLog_db import FuturesDB

data_monitoring_bp = Blueprint('data_monitoring', __name__)
logger = logging.getLogger(__name__)


# Lazy import to avoid circular dependencies
def get_data_completeness_service():
    """Get DataCompletenessService instance"""
    from services.data_completeness_service import get_data_completeness_service as get_service
    return get_service()


# Import ohlc_service lazily
ohlc_service = None
def get_ohlc_service():
    """Get OHLCDataService instance lazily"""
    global ohlc_service
    if ohlc_service is None:
        try:
            from services.data_service import OHLCDataService
            ohlc_service = OHLCDataService()
        except Exception as e:
            logger.error(f"Failed to import OHLCDataService: {e}")
    return ohlc_service

@data_monitoring_bp.route('/monitoring')
def monitoring_dashboard():
    """Data monitoring dashboard"""
    try:
        # Get overall system status
        sync_status = get_data_sync_status()

        return render_template('monitoring/dashboard.html',
                             sync_status=sync_status,
                             page_title="Data Monitoring Dashboard")

    except Exception as e:
        logger.error(f"Error loading monitoring dashboard: {e}")
        return f"Error loading monitoring dashboard: {e}", 500


@data_monitoring_bp.route('/monitoring/data-completeness')
def data_completeness_dashboard():
    """OHLC Data Completeness monitoring dashboard"""
    try:
        return render_template('monitoring/data_completeness.html',
                             page_title="OHLC Data Completeness")
    except Exception as e:
        logger.error(f"Error loading data completeness dashboard: {e}")
        return f"Error loading data completeness dashboard: {e}", 500

@data_monitoring_bp.route('/api/monitoring/alerts')
def get_monitoring_alerts():
    """Get current data monitoring alerts"""
    try:
        alerts = []
        
        # Get sync status
        sync_status = get_data_sync_status()
        
        # Check for instruments needing sync
        for instrument, status in sync_status.get('instrument_status', {}).items():
            if status.get('needs_sync', False):
                critical_gaps = status.get('critical_gaps', [])
                
                for gap in critical_gaps:
                    severity = 'critical' if gap['days_behind'] > 3 else 'warning'
                    alerts.append({
                        'id': f"{instrument}_{gap['timeframe']}",
                        'severity': severity,
                        'type': 'data_gap',
                        'instrument': instrument,
                        'timeframe': gap['timeframe'],
                        'days_behind': gap['days_behind'],
                        'message': f"{instrument} {gap['timeframe']} data is {gap['days_behind']} days behind",
                        'timestamp': datetime.now().isoformat(),
                        'action_url': f"/api/data-sync/force/startup"
                    })
        
        # Check if sync system is running
        if not sync_status.get('is_running', False):
            alerts.append({
                'id': 'sync_system_down',
                'severity': 'critical',
                'type': 'system_down',
                'message': 'Automated data sync system is not running',
                'timestamp': datetime.now().isoformat(),
                'action_url': '/api/data-sync/force/startup'
            })
        
        # Check last sync time
        last_sync = sync_status.get('last_sync', {})
        if last_sync and 'timestamp' in last_sync:
            last_sync_time = datetime.fromisoformat(last_sync['timestamp'])
            hours_since_sync = (datetime.now() - last_sync_time).total_seconds() / 3600
            
            if hours_since_sync > 4:  # No sync in 4+ hours
                alerts.append({
                    'id': 'stale_sync',
                    'severity': 'warning',
                    'type': 'stale_data',
                    'message': f'Last data sync was {hours_since_sync:.1f} hours ago',
                    'timestamp': datetime.now().isoformat(),
                    'action_url': '/api/data-sync/force/hourly'
                })
        
        return jsonify({
            'success': True,
            'alerts': alerts,
            'alert_count': len(alerts),
            'critical_count': len([a for a in alerts if a['severity'] == 'critical']),
            'warning_count': len([a for a in alerts if a['severity'] == 'warning'])
        })
        
    except Exception as e:
        logger.error(f"Error getting monitoring alerts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@data_monitoring_bp.route('/api/monitoring/health-summary')
def get_health_summary():
    """Get overall health summary for monitoring"""
    try:
        sync_status = get_data_sync_status()
        
        # Calculate health metrics
        total_instruments = sync_status.get('total_instruments', 0)
        instruments_needing_sync = len([
            inst for inst, status in sync_status.get('instrument_status', {}).items()
            if status.get('needs_sync', False)
        ])
        
        health_score = 100
        if total_instruments > 0:
            sync_percentage = ((total_instruments - instruments_needing_sync) / total_instruments) * 100
            health_score = max(0, sync_percentage)
        
        # Determine overall status
        if health_score >= 95:
            overall_status = 'excellent'
            status_color = 'green'
        elif health_score >= 80:
            overall_status = 'good'
            status_color = 'yellow'
        elif health_score >= 60:
            overall_status = 'degraded'
            status_color = 'orange'
        else:
            overall_status = 'critical'
            status_color = 'red'
        
        return jsonify({
            'success': True,
            'health_score': round(health_score, 1),
            'overall_status': overall_status,
            'status_color': status_color,
            'total_instruments': total_instruments,
            'instruments_current': total_instruments - instruments_needing_sync,
            'instruments_needing_sync': instruments_needing_sync,
            'sync_system_running': sync_status.get('is_running', False),
            'last_sync': sync_status.get('last_sync', {}),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting health summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@data_monitoring_bp.route('/api/monitoring/resolve-alert/<alert_id>', methods=['POST'])
def resolve_alert(alert_id):
    """Resolve a monitoring alert by triggering appropriate action"""
    try:
        # Parse alert ID to determine action
        if alert_id == 'sync_system_down' or alert_id == 'stale_sync':
            # Trigger startup sync
            result = force_data_sync('startup')
            
            return jsonify({
                'success': True,
                'message': 'Startup data sync triggered',
                'result': result
            })
        
        elif '_' in alert_id:  # instrument_timeframe format
            instrument = alert_id.split('_')[0]
            
            # Trigger sync for specific instrument
            from background_services import gap_filling_service
            results = gap_filling_service.force_gap_fill(instrument, days_back=14)
            
            return jsonify({
                'success': True,
                'message': f'Gap filling triggered for {instrument}',
                'results': results
            })
        
        else:
            return jsonify({
                'success': False,
                'error': 'Unknown alert type'
            }), 400
        
    except Exception as e:
        logger.error(f"Error resolving alert {alert_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@data_monitoring_bp.route('/api/monitoring/data-coverage/<instrument>')
def get_instrument_coverage(instrument):
    """Get detailed data coverage for a specific instrument"""
    try:
        with FuturesDB() as db:
            # Get trade activity for this instrument
            trades_query = db.execute_query("""
                SELECT MIN(entry_time) as first_trade, 
                       MAX(entry_time) as last_trade,
                       COUNT(*) as total_trades
                FROM trades 
                WHERE instrument LIKE ?
            """, (f"%{instrument}%",))
            
            trade_info = trades_query[0] if trades_query else (None, None, 0)
            
            # Get OHLC coverage
            coverage_query = db.execute_query("""
                SELECT timeframe, 
                       COUNT(*) as record_count,
                       MIN(timestamp) as earliest_data,
                       MAX(timestamp) as latest_data
                FROM ohlc_data 
                WHERE instrument = ?
                GROUP BY timeframe
                ORDER BY timeframe
            """, (instrument,))
            
            coverage_data = []
            for tf, count, earliest_ts, latest_ts in coverage_query:
                earliest_date = datetime.fromtimestamp(earliest_ts) if earliest_ts else None
                latest_date = datetime.fromtimestamp(latest_ts) if latest_ts else None
                
                coverage_data.append({
                    'timeframe': tf,
                    'record_count': count,
                    'earliest_date': earliest_date.isoformat() if earliest_date else None,
                    'latest_date': latest_date.isoformat() if latest_date else None,
                    'days_behind': (datetime.now() - latest_date).days if latest_date else 999
                })
        
        return jsonify({
            'success': True,
            'instrument': instrument,
            'trade_info': {
                'first_trade': trade_info[0],
                'last_trade': trade_info[1],
                'total_trades': trade_info[2]
            },
            'coverage_data': coverage_data
        })

    except Exception as e:
        logger.error(f"Error getting coverage for {instrument}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# Data Completeness Monitoring API Endpoints
# =============================================================================

@data_monitoring_bp.route('/api/monitoring/completeness-matrix')
def get_completeness_matrix():
    """
    Get the data completeness matrix for all instruments and timeframes.
    Returns status (complete/partial/missing) for each instrument/timeframe combination.
    """
    try:
        service = get_data_completeness_service()
        result = service.get_completeness_matrix()

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"Error getting completeness matrix: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_monitoring_bp.route('/api/monitoring/gap-details/<instrument>/<timeframe>')
def get_gap_details(instrument, timeframe):
    """
    Get detailed gap information for a specific instrument and timeframe.
    Returns record count, expected minimum, status, and repair availability.
    """
    try:
        service = get_data_completeness_service()
        details = service.get_gap_details(instrument, timeframe)

        # Check if the response indicates an invalid request
        if details.get('status') == 'invalid' or details.get('error'):
            return jsonify({
                'success': False,
                'error': details.get('error', 'Invalid instrument or timeframe')
            }), 400

        return jsonify({
            'success': True,
            'data': details
        })

    except Exception as e:
        logger.error(f"Error getting gap details for {instrument}/{timeframe}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_monitoring_bp.route('/api/monitoring/repair-gap', methods=['POST'])
def repair_gap():
    """
    Trigger a repair operation to fill gaps for a specific instrument/timeframe.
    Request body: {"instrument": "ES", "timeframe": "15m"}
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400

        instrument = data.get('instrument')
        timeframe = data.get('timeframe')

        if not instrument:
            return jsonify({
                'success': False,
                'error': 'Instrument is required'
            }), 400

        if not timeframe:
            return jsonify({
                'success': False,
                'error': 'Timeframe is required'
            }), 400

        # Get OHLC service and trigger sync
        ohlc_svc = get_ohlc_service()
        if ohlc_svc is None:
            return jsonify({
                'success': False,
                'error': 'OHLC service is not available'
            }), 500

        # Sync for the specific instrument and timeframe
        # Pass base instrument - the service handles Yahoo symbol conversion
        sync_result = ohlc_svc.sync_instruments(
            instruments=[instrument],
            timeframes=[timeframe]
        )

        # Invalidate cache after repair
        completeness_service = get_data_completeness_service()
        completeness_service.invalidate_cache()

        return jsonify({
            'success': True,
            'data': {
                'instrument': instrument,
                'timeframe': timeframe,
                'records_added': sync_result.get('candles_added', 0),
                'duration_seconds': sync_result.get('duration_seconds', 0)
            }
        })

    except Exception as e:
        logger.error(f"Error repairing gap: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_monitoring_bp.route('/api/monitoring/sync-health')
def get_sync_health():
    """
    Get sync health history showing recent sync operations and success rates.
    Query param: days (default: 7) - number of days of history to return
    """
    try:
        # Parse days parameter with default of 7
        days_param = request.args.get('days', '7')
        try:
            days = int(days_param)
        except ValueError:
            days = 7  # Use default if invalid

        service = get_data_completeness_service()
        history = service.get_sync_health_history(days=days)

        return jsonify({
            'success': True,
            'data': history
        })

    except Exception as e:
        logger.error(f"Error getting sync health: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500