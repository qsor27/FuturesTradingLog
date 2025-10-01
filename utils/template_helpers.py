"""
Template helpers for JavaScript integration

Provides safe data serialization and injection helpers for the JSON Data Bridge architecture.
"""
import json
from datetime import datetime, date
from decimal import Decimal
from flask import current_app
from markupsafe import Markup


def safe_json(data):
    """
    Safely serialize data to JSON for JavaScript consumption
    
    Handles common Python types that need special serialization:
    - datetime/date objects -> ISO strings
    - Decimal objects -> floats
    - None -> null
    
    Args:
        data: Data to serialize
        
    Returns:
        Markup: Safe HTML-ready JSON string
    """
    def json_serializer(obj):
        """Custom JSON serializer for Python objects"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, '__dict__'):
            # Handle custom objects by converting to dict
            return obj.__dict__
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    try:
        json_string = json.dumps(data, default=json_serializer, ensure_ascii=False)
        return Markup(json_string)
    except TypeError as e:
        current_app.logger.error(f"JSON serialization error: {e}")
        return Markup('null')


def js_config(config_id, data):
    """
    Generate JSON config script for JavaScript modules
    
    Creates a script tag with type="application/json" containing the data,
    which can be safely parsed by JavaScript without Jinja2 conflicts.
    
    Args:
        config_id (str): Unique ID for the script tag
        data: Data to serialize and inject
        
    Returns:
        Markup: Safe HTML script tag
    """
    json_data = safe_json(data)
    script_tag = f'''<script type="application/json" id="{config_id}">
{json_data}
</script>'''
    return Markup(script_tag)


def js_module(module_path, defer=True):
    """
    Generate script tag for ES6 module loading
    
    Args:
        module_path (str): Path to the JavaScript module
        defer (bool): Whether to defer module loading
        
    Returns:
        Markup: Safe HTML script tag
    """
    defer_attr = ' defer' if defer else ''
    script_tag = f'<script type="module" src="{module_path}"{defer_attr}></script>'
    return Markup(script_tag)


def component_mount(component_type, config_id=None, element_id=None, css_class="", **kwargs):
    """
    Generate component mounting point with data attributes
    
    Args:
        component_type (str): Type of component (e.g., 'price-chart')
        config_id (str, optional): ID of JSON config script
        element_id (str, optional): ID for the component element
        css_class (str): Additional CSS classes
        **kwargs: Additional data attributes
        
    Returns:
        Markup: Safe HTML div element
    """
    attrs = [f'data-component="{component_type}"']
    
    if config_id:
        attrs.append(f'data-config-id="{config_id}"')
    
    if element_id:
        attrs.append(f'id="{element_id}"')
    
    if css_class:
        attrs.append(f'class="{css_class}"')
    
    # Add any additional data attributes
    for key, value in kwargs.items():
        if key.startswith('data_'):
            attr_name = key.replace('_', '-')
            attrs.append(f'{attr_name}="{value}"')
    
    attrs_string = ' '.join(attrs)
    return Markup(f'<div {attrs_string}></div>')


def chart_config(instrument, timeframe='1h', days=7, trade_id=None, height=400, **kwargs):
    """
    Generate chart configuration for price charts
    
    Args:
        instrument (str): Instrument symbol
        timeframe (str): Chart timeframe
        days (int): Number of days to display
        trade_id (int, optional): Trade ID for markers
        height (int): Chart height in pixels
        **kwargs: Additional chart options
        
    Returns:
        dict: Chart configuration
    """
    config = {
        'instrument': instrument,
        'timeframe': timeframe,
        'days': days,
        'height': height,
        **kwargs
    }
    
    if trade_id:
        config['tradeId'] = trade_id
    
    return config


def position_config(position_data, **kwargs):
    """
    Generate configuration for position components
    
    Args:
        position_data: Position data object
        **kwargs: Additional configuration
        
    Returns:
        dict: Position configuration
    """
    config = {
        'positionId': getattr(position_data, 'id', None),
        'instrument': getattr(position_data, 'instrument', ''),
        'account': getattr(position_data, 'account', ''),
        'positionType': getattr(position_data, 'position_type', ''),
        'status': getattr(position_data, 'position_status', ''),
        'totalQuantity': getattr(position_data, 'total_quantity', 0),
        'avgEntryPrice': getattr(position_data, 'avg_entry_price', 0),
        'avgExitPrice': getattr(position_data, 'avg_exit_price', 0),
        'totalPnL': getattr(position_data, 'total_dollars_pnl', 0),
        **kwargs
    }
    
    return config


def format_config_id(base_name, *identifiers):
    """
    Generate consistent configuration IDs
    
    Args:
        base_name (str): Base name for the config
        *identifiers: Additional identifiers to make ID unique
        
    Returns:
        str: Formatted configuration ID
    """
    parts = [base_name] + [str(id) for id in identifiers if id is not None]
    return '-'.join(parts) + '-config'


def api_endpoints(**endpoints):
    """
    Generate API endpoint configuration
    
    Args:
        **endpoints: Named API endpoints
        
    Returns:
        dict: API endpoint configuration
    """
    return {
        'apiEndpoints': endpoints
    }


def user_context(user_data=None):
    """
    Generate user context configuration
    
    Args:
        user_data: User data object
        
    Returns:
        dict: User context configuration
    """
    if not user_data:
        return {'user': None}
    
    return {
        'user': {
            'id': getattr(user_data, 'id', None),
            'username': getattr(user_data, 'username', ''),
            'preferences': getattr(user_data, 'preferences', {}),
        }
    }


def register_template_helpers(app):
    """
    Register all template helpers with Flask app
    
    Args:
        app: Flask application instance
    """
    app.jinja_env.globals.update({
        'safe_json': safe_json,
        'js_config': js_config,
        'js_module': js_module,
        'component_mount': component_mount,
        'chart_config': chart_config,
        'position_config': position_config,
        'format_config_id': format_config_id,
        'api_endpoints': api_endpoints,
        'user_context': user_context,
    })
    
    app.jinja_env.filters.update({
        'safe_json': safe_json,
    })