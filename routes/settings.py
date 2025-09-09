from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
import json
import os
from config import config
from scripts.TradingLog_db import FuturesDB

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


# Enhanced Settings Categories API endpoints

@settings_bp.route('/api/v2/settings/categorized', methods=['GET'])
def get_categorized_settings():
    """Get all settings in categorized format"""
    try:
        # Get chart settings from database
        chart_settings = {}
        with FuturesDB() as db:
            chart_settings = db.get_chart_settings()
        
        # Get instrument multipliers from JSON file
        instrument_multipliers = {}
        multipliers_file = config.data_dir / 'config' / 'instrument_multipliers.json'
        if multipliers_file.exists():
            try:
                with open(multipliers_file, 'r') as f:
                    instrument_multipliers = json.load(f)
            except Exception as e:
                # Log error but continue with empty multipliers
                pass
        
        # Build categorized settings structure
        categorized = {
            'chart': {
                'default_timeframe': chart_settings.get('default_timeframe', '1h'),
                'default_data_range': chart_settings.get('default_data_range', '1week'),
                'volume_visibility': chart_settings.get('volume_visibility', True),
                'last_updated': chart_settings.get('last_updated')
            },
            'trading': {
                'instrument_multipliers': instrument_multipliers
            },
            'notifications': {
                # Future category - placeholder for now
            }
        }
        
        return jsonify({
            'success': True,
            'settings': categorized,
            'timestamp': chart_settings.get('last_updated')
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'settings': {
                'chart': {
                    'default_timeframe': '1h',
                    'default_data_range': '1week',
                    'volume_visibility': True
                },
                'trading': {
                    'instrument_multipliers': {}
                },
                'notifications': {}
            }
        }), 500


@settings_bp.route('/api/v2/settings/categorized', methods=['PUT'])
def update_categorized_settings():
    """Update categorized settings and sync with active profile"""
    try:
        data = request.get_json()
        
        if not data or 'settings' not in data:
            return jsonify({
                'success': False,
                'error': 'Invalid data format. Expected: {"settings": {...}}'
            }), 400
        
        settings = data['settings']
        updated_sections = []
        
        # Update chart settings if provided
        if 'chart' in settings:
            chart_data = settings['chart']
            chart_updates = {}
            
            # Extract chart settings with validation
            if 'default_timeframe' in chart_data:
                chart_updates['default_timeframe'] = chart_data['default_timeframe']
            if 'default_data_range' in chart_data:
                chart_updates['default_data_range'] = chart_data['default_data_range'] 
            if 'volume_visibility' in chart_data:
                chart_updates['volume_visibility'] = chart_data['volume_visibility']
            
            if chart_updates:
                with FuturesDB() as db:
                    success = db.update_chart_settings(**chart_updates)
                    if success:
                        updated_sections.append('chart')
                    else:
                        return jsonify({
                            'success': False,
                            'error': 'Failed to update chart settings'
                        }), 500
        
        # Update instrument multipliers if provided
        if 'trading' in settings and 'instrument_multipliers' in settings['trading']:
            multipliers = settings['trading']['instrument_multipliers']
            
            # Validate multipliers
            for instrument, multiplier in multipliers.items():
                try:
                    float(multiplier)
                except (ValueError, TypeError):
                    return jsonify({
                        'success': False,
                        'error': f'Invalid multiplier for {instrument}: {multiplier}'
                    }), 400
            
            # Save multipliers to file
            try:
                config_dir = config.data_dir / 'config'
                config_dir.mkdir(parents=True, exist_ok=True)
                
                multipliers_file = config_dir / 'instrument_multipliers.json'
                with open(multipliers_file, 'w') as f:
                    json.dump(multipliers, f, indent=2)
                    
                updated_sections.append('trading')
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'Failed to save instrument multipliers: {str(e)}'
                }), 500
        
        # Update active profile settings_snapshot if profile integration is enabled
        try:
            _update_active_profile_settings(settings)
        except Exception as e:
            # Log error but don't fail the request
            pass
        
        # Get updated settings to return
        updated_settings = {}
        try:
            with FuturesDB() as db:
                chart_settings = db.get_chart_settings()
                updated_settings['chart'] = chart_settings
        except Exception:
            pass
        
        try:
            multipliers_file = config.data_dir / 'config' / 'instrument_multipliers.json'
            if multipliers_file.exists():
                with open(multipliers_file, 'r') as f:
                    updated_settings['trading'] = {'instrument_multipliers': json.load(f)}
        except Exception:
            pass
        
        return jsonify({
            'success': True,
            'message': f'Settings updated successfully: {", ".join(updated_sections)}',
            'updated_sections': updated_sections,
            'settings': updated_settings
        })
    
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _update_active_profile_settings(settings):
    """Update active profile's settings_snapshot with new settings"""
    try:
        # Get the default/active profile
        with FuturesDB() as db:
            profile = db.get_default_user_profile(user_id=1)
            
            if profile:
                # Parse existing settings_snapshot
                existing_settings = {}
                if profile.get('settings_snapshot'):
                    try:
                        existing_settings = json.loads(profile['settings_snapshot'])
                    except json.JSONDecodeError:
                        existing_settings = {}
                
                # Update with new settings (merge)
                for category, category_settings in settings.items():
                    if category not in existing_settings:
                        existing_settings[category] = {}
                    
                    if category == 'chart':
                        existing_settings[category].update(category_settings)
                    elif category == 'trading':
                        existing_settings[category].update(category_settings)
                    elif category == 'notifications':
                        existing_settings[category].update(category_settings)
                
                # Update profile with merged settings
                success = db.update_user_profile(
                    profile_id=profile['id'],
                    settings_snapshot=existing_settings
                )
                
                if success:
                    print(f"Updated active profile settings for profile {profile['id']}")
    
    except Exception as e:
        print(f"Error updating active profile settings: {e}")
        # Don't propagate error - this is a nice-to-have feature


@settings_bp.route('/api/v2/settings/validate', methods=['POST'])
def validate_categorized_settings():
    """Validate categorized settings structure without saving"""
    try:
        data = request.get_json()
        
        if not data or 'settings' not in data:
            return jsonify({
                'success': False,
                'error': 'Invalid data format. Expected: {"settings": {...}}'
            }), 400
        
        settings = data['settings']
        validation_results = {}
        
        # Validate chart settings
        if 'chart' in settings:
            chart_validation = _validate_chart_settings(settings['chart'])
            validation_results['chart'] = chart_validation
        
        # Validate trading settings
        if 'trading' in settings:
            trading_validation = _validate_trading_settings(settings['trading'])
            validation_results['trading'] = trading_validation
        
        # Check if all validations passed
        all_valid = all(result.get('valid', False) for result in validation_results.values())
        
        return jsonify({
            'success': True,
            'valid': all_valid,
            'validation_results': validation_results
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _validate_chart_settings(chart_settings):
    """Validate chart settings structure and values"""
    try:
        errors = []
        
        # Validate timeframe
        if 'default_timeframe' in chart_settings:
            valid_timeframes = ['1m', '3m', '5m', '15m', '1h', '4h', '1d']
            if chart_settings['default_timeframe'] not in valid_timeframes:
                errors.append(f"Invalid timeframe. Must be one of {valid_timeframes}")
        
        # Validate data range
        if 'default_data_range' in chart_settings:
            valid_ranges = ['1day', '3days', '1week', '2weeks', '1month', '3months', '6months']
            if chart_settings['default_data_range'] not in valid_ranges:
                errors.append(f"Invalid data range. Must be one of {valid_ranges}")
        
        # Validate volume visibility
        if 'volume_visibility' in chart_settings:
            if not isinstance(chart_settings['volume_visibility'], bool):
                errors.append("volume_visibility must be a boolean")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    except Exception as e:
        return {
            'valid': False,
            'errors': [str(e)]
        }


def _validate_trading_settings(trading_settings):
    """Validate trading settings structure and values"""
    try:
        errors = []
        
        # Validate instrument multipliers
        if 'instrument_multipliers' in trading_settings:
            multipliers = trading_settings['instrument_multipliers']
            
            if not isinstance(multipliers, dict):
                errors.append("instrument_multipliers must be a dictionary")
            else:
                for instrument, multiplier in multipliers.items():
                    try:
                        float(multiplier)
                    except (ValueError, TypeError):
                        errors.append(f"Invalid multiplier for {instrument}: {multiplier}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    except Exception as e:
        return {
            'valid': False,
            'errors': [str(e)]
        }