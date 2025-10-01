"""
Routes for managing user-configurable instrument groups
"""

from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from database_manager import DatabaseManager
from services.instrument_management_service import InstrumentManagementService
import logging

logger = logging.getLogger(__name__)

instrument_bp = Blueprint('instruments', __name__)


@instrument_bp.route('/api/instrument-groups', methods=['GET'])
def get_instrument_groups():
    """Get all instrument groups"""
    try:
        with DatabaseManager() as db:
            service = InstrumentManagementService(db)
            groups = service.get_all_groups()
            
            # Convert to JSON-serializable format
            groups_data = {}
            for name, group in groups.items():
                groups_data[name] = {
                    'name': group.name,
                    'description': group.description,
                    'instruments': group.instruments,
                    'is_active': group.is_active
                }
            
            return jsonify({
                'success': True,
                'groups': groups_data
            })
    
    except Exception as e:
        logger.error(f"Error getting instrument groups: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@instrument_bp.route('/api/instrument-groups/<group_name>', methods=['GET'])
def get_instrument_group(group_name):
    """Get specific instrument group"""
    try:
        with DatabaseManager() as db:
            service = InstrumentManagementService(db)
            instruments = service.get_instrument_group(group_name)
            
            return jsonify({
                'success': True,
                'group_name': group_name,
                'instruments': instruments
            })
    
    except Exception as e:
        logger.error(f"Error getting instrument group {group_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@instrument_bp.route('/api/instrument-groups/<group_name>', methods=['POST'])
def update_instrument_group(group_name):
    """Update instrument group"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        instruments = data.get('instruments', [])
        description = data.get('description')
        
        if not instruments:
            return jsonify({
                'success': False,
                'error': 'Instruments list cannot be empty'
            }), 400
        
        with DatabaseManager() as db:
            service = InstrumentManagementService(db)
            success = service.set_instrument_group(group_name, instruments, description)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Instrument group {group_name} updated successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to update instrument group'
                }), 500
    
    except Exception as e:
        logger.error(f"Error updating instrument group {group_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@instrument_bp.route('/api/instrument-groups/<group_name>', methods=['DELETE'])
def delete_instrument_group(group_name):
    """Delete custom instrument group"""
    try:
        with DatabaseManager() as db:
            service = InstrumentManagementService(db)
            success = service.delete_group(group_name)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Instrument group {group_name} deleted successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to delete instrument group (may be a default group)'
                }), 400
    
    except Exception as e:
        logger.error(f"Error deleting instrument group {group_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@instrument_bp.route('/settings/instruments')
def instrument_settings():
    """Render instrument management settings page"""
    try:
        with DatabaseManager() as db:
            service = InstrumentManagementService(db)
            groups = service.get_all_groups()
            
            return render_template(
                'settings/instruments.html',
                groups=groups,
                title='Instrument Management'
            )
    
    except Exception as e:
        logger.error(f"Error loading instrument settings: {e}")
        flash(f'Error loading instrument settings: {e}', 'error')
        return redirect(url_for('main.index'))


@instrument_bp.route('/settings/instruments/create', methods=['POST'])
def create_instrument_group():
    """Create new custom instrument group"""
    try:
        group_name = request.form.get('group_name', '').strip()
        description = request.form.get('description', '').strip()
        instruments_str = request.form.get('instruments', '').strip()
        
        if not group_name or not instruments_str:
            flash('Group name and instruments are required', 'error')
            return redirect(url_for('instruments.instrument_settings'))
        
        # Parse instruments from comma-separated string
        instruments = [inst.strip().upper() for inst in instruments_str.split(',') if inst.strip()]
        
        if not instruments:
            flash('At least one instrument is required', 'error')
            return redirect(url_for('instruments.instrument_settings'))
        
        with DatabaseManager() as db:
            service = InstrumentManagementService(db)
            success = service.set_instrument_group(group_name, instruments, description)
            
            if success:
                flash(f'Instrument group "{group_name}" created successfully', 'success')
            else:
                flash('Failed to create instrument group', 'error')
    
    except Exception as e:
        logger.error(f"Error creating instrument group: {e}")
        flash(f'Error creating instrument group: {e}', 'error')
    
    return redirect(url_for('instruments.instrument_settings'))