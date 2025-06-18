from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
import json
import os
from config import config

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings')
def settings():
    """Display settings page with instrument multipliers"""
    multipliers_file = config.data_dir / 'config' / 'instrument_multipliers.json'
    
    # Load existing multipliers
    multipliers = {}
    if multipliers_file.exists():
        try:
            with open(multipliers_file, 'r') as f:
                multipliers = json.load(f)
        except Exception as e:
            flash(f'Error loading multipliers: {e}', 'error')
    
    return render_template('settings.html', multipliers=multipliers)

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