"""
Data Monitoring Routes
Provides monitoring dashboard and alerts for OHLC data coverage
"""

from flask import Blueprint, render_template, jsonify, request
from datetime import datetime, timedelta
import logging
from automated_data_sync import get_data_sync_status, force_data_sync
from TradingLog_db import FuturesDB

data_monitoring_bp = Blueprint('data_monitoring', __name__)
logger = logging.getLogger(__name__)

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