from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
import json
import os
from config import config
from TradingLog_db import FuturesDB

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings')
def settings():
    """Display settings page with instrument multipliers and chart settings"""
    multipliers_file = config.data_dir / 'config' / 'instrument_multipliers.json'
    
    # Load existing multipliers
    multipliers = {}
    if multipliers_file.exists():
        try:
            with open(multipliers_file, 'r') as f:
                multipliers = json.load(f)
        except Exception as e:
            flash(f'Error loading multipliers: {e}', 'error')
    
    # Load chart settings
    chart_settings = {}
    try:
        with FuturesDB() as db:
            chart_settings = db.get_chart_settings()
    except Exception as e:
        flash(f'Error loading chart settings: {e}', 'error')
        # Provide defaults if error
        chart_settings = {
            'default_timeframe': '1h',
            'default_data_range': '1week',
            'volume_visibility': True
        }
    
    return render_template('settings.html', multipliers=multipliers, chart_settings=chart_settings)

@settings_bp.route('/settings/multipliers', methods=['POST'])
def update_multipliers():
    """Update instrument multipliers"""
    try:
        # Get the JSON data from the request
        data = request.get_json()
        
        if not data or 'multipliers' not in data:
            return jsonify({'success': False, 'error': 'Invalid data format'}), 400
        
        multipliers = data['multipliers']
        
        # Validate multipliers
        for instrument, multiplier in multipliers.items():
            try:
                float(multiplier)
            except ValueError:
                return jsonify({'success': False, 'error': f'Invalid multiplier for {instrument}: {multiplier}'}), 400
        
        # Ensure config directory exists
        config_dir = config.data_dir / 'config'
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Save multipliers to file
        multipliers_file = config_dir / 'instrument_multipliers.json'
        with open(multipliers_file, 'w') as f:
            json.dump(multipliers, f, indent=2)
        
        return jsonify({'success': True, 'message': 'Multipliers updated successfully'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/settings/multipliers/<instrument>', methods=['DELETE'])
def delete_multiplier(instrument):
    """Delete a specific instrument multiplier"""
    try:
        multipliers_file = config.data_dir / 'config' / 'instrument_multipliers.json'
        
        if not multipliers_file.exists():
            return jsonify({'success': False, 'error': 'Multipliers file not found'}), 404
        
        # Load existing multipliers
        with open(multipliers_file, 'r') as f:
            multipliers = json.load(f)
        
        if instrument in multipliers:
            del multipliers[instrument]
            
            # Save updated multipliers
            with open(multipliers_file, 'w') as f:
                json.dump(multipliers, f, indent=2)
            
            return jsonify({'success': True, 'message': f'Multiplier for {instrument} deleted'})
        else:
            return jsonify({'success': False, 'error': f'Multiplier for {instrument} not found'}), 404
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/api/v1/settings/chart', methods=['GET'])
def get_chart_settings():
    """Get chart settings for API access"""
    try:
        with FuturesDB() as db:
            settings = db.get_chart_settings()
            return jsonify({
                'success': True,
                'settings': settings
            })
    except Exception as e:
        return jsonify({
            'success': False, 
            'error': str(e),
            'settings': {
                'default_timeframe': '1h',
                'default_data_range': '1week',
                'volume_visibility': True
            }
        }), 500

@settings_bp.route('/api/v1/settings/chart', methods=['PUT'])
def update_chart_settings():
    """Update chart settings via API"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Invalid data format'}), 400
        
        # Extract settings with validation
        default_timeframe = data.get('default_timeframe')
        default_data_range = data.get('default_data_range')
        volume_visibility = data.get('volume_visibility')
        
        # Validate at least one setting is provided
        if all(v is None for v in [default_timeframe, default_data_range, volume_visibility]):
            return jsonify({'success': False, 'error': 'No settings provided to update'}), 400
        
        with FuturesDB() as db:
            success = db.update_chart_settings(
                default_timeframe=default_timeframe,
                default_data_range=default_data_range,
                volume_visibility=volume_visibility
            )
            
            if success:
                # Get updated settings to return
                updated_settings = db.get_chart_settings()
                return jsonify({
                    'success': True,
                    'message': 'Chart settings updated successfully',
                    'settings': updated_settings
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to update chart settings'}), 500
    
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/settings/chart', methods=['POST'])
def update_chart_settings_form():
    """Update chart settings from web form"""
    try:
        # Get form data
        default_timeframe = request.form.get('default_timeframe')
        default_data_range = request.form.get('default_data_range')
        volume_visibility = request.form.get('volume_visibility') == 'on'
        
        with FuturesDB() as db:
            success = db.update_chart_settings(
                default_timeframe=default_timeframe,
                default_data_range=default_data_range,
                volume_visibility=volume_visibility
            )
            
            if success:
                flash('Chart settings updated successfully!', 'success')
            else:
                flash('Error updating chart settings', 'error')
    
    except ValueError as e:
        flash(f'Invalid chart settings: {e}', 'error')
    except Exception as e:
        flash(f'Error updating chart settings: {e}', 'error')
    
    return redirect(url_for('settings.settings'))