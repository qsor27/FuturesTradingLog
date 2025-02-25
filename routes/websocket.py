from flask_socketio import SocketIO, emit
from flask import request, current_app
from market_data.ninja_reader import NinjaMarketData
from datetime import datetime
import threading
import time
import logging

logger = logging.getLogger(__name__)
socketio = SocketIO()
active_subscriptions = {}

def init_websocket(app):
    """Initialize WebSocket with the Flask app"""
    socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')
    logger.info("WebSocket initialized")

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connection_status', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")
    # Remove client from all subscriptions
    for instrument in list(active_subscriptions.keys()):
        if request.sid in active_subscriptions[instrument]['clients']:
            active_subscriptions[instrument]['clients'].remove(request.sid)
            if not active_subscriptions[instrument]['clients']:
                del active_subscriptions[instrument]

@socketio.on('subscribe')
def handle_subscribe(data):
    """Handle client subscription to an instrument"""
    try:
        instrument = data['instrument']
        logger.info(f"Subscribe request for {instrument} from {request.sid}")
        
        if instrument not in active_subscriptions:
            active_subscriptions[instrument] = {
                'clients': set(),
                'last_update': None,
                'thread': None
            }
            
        active_subscriptions[instrument]['clients'].add(request.sid)
        
        # Start streaming if not already started
        if not active_subscriptions[instrument]['thread']:
            start_data_stream(instrument)
            
        emit('subscription_status', {
            'status': 'subscribed',
            'instrument': instrument
        })
        
    except Exception as e:
        logger.error(f"Error in subscribe handler: {str(e)}")
        emit('error', {'message': str(e)})

@socketio.on('unsubscribe')
def handle_unsubscribe(data):
    """Handle client unsubscription"""
    try:
        instrument = data['instrument']
        logger.info(f"Unsubscribe request for {instrument} from {request.sid}")
        
        if instrument in active_subscriptions:
            if request.sid in active_subscriptions[instrument]['clients']:
                active_subscriptions[instrument]['clients'].remove(request.sid)
                
            if not active_subscriptions[instrument]['clients']:
                if active_subscriptions[instrument]['thread']:
                    # Thread will stop on next iteration
                    del active_subscriptions[instrument]
                    
        emit('subscription_status', {
            'status': 'unsubscribed',
            'instrument': instrument
        })
        
    except Exception as e:
        logger.error(f"Error in unsubscribe handler: {str(e)}")
        emit('error', {'message': str(e)})

def start_data_stream(instrument):
    """Start streaming data for an instrument"""
    def stream_data():
        logger.info(f"Starting data stream for {instrument}")
        ninja_reader = current_app.ninja_reader
        
        while instrument in active_subscriptions:
            try:
                now = datetime.now()
                # Get latest minute of data
                df = ninja_reader.get_data_around_time(
                    symbol=instrument,
                    timestamp=now,
                    minutes_before=0,
                    minutes_after=1
                )
                
                if df is not None and not df.empty:
                    # Format for chart
                    chart_data = ninja_reader.format_for_chart(df)
                    if chart_data:
                        latest_bar = chart_data[-1]
                        
                        # Check if this is new data
                        if (active_subscriptions[instrument]['last_update'] != 
                            latest_bar['time']):
                            
                            logger.debug(f"New data for {instrument}: {latest_bar}")
                            
                            # Emit to all subscribed clients
                            socketio.emit('market_data', {
                                'instrument': instrument,
                                'data': latest_bar
                            }, room=list(active_subscriptions[instrument]['clients']))
                            
                            active_subscriptions[instrument]['last_update'] = \
                                latest_bar['time']
                                
            except Exception as e:
                logger.error(f"Error streaming data for {instrument}: {str(e)}")
                
            time.sleep(1)  # Poll every second
            
        logger.info(f"Stopping data stream for {instrument}")
            
    # Start the streaming thread
    thread = threading.Thread(target=stream_data)
    thread.daemon = True
    thread.start()
    
    active_subscriptions[instrument]['thread'] = thread