"""
Profile Management Routes
Handles user profile CRUD operations and import/export functionality
"""
from flask import Blueprint, request, jsonify, send_file, make_response
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import tempfile
import logging
from werkzeug.utils import secure_filename
from TradingLog_db import FuturesDB

profiles_bp = Blueprint('profiles', __name__)
logger = logging.getLogger(__name__)

# Maximum file size for uploads (5MB)
MAX_UPLOAD_SIZE = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {'json'}

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_profile_data(profile_data: Dict[str, Any]) -> tuple:
    """
    Validate profile data structure for import
    Returns (is_valid, error_message)
    """
    required_fields = ['profile_name', 'settings_snapshot']
    
    # Check required fields
    for field in required_fields:
        if field not in profile_data:
            return False, f"Missing required field: {field}"
    
    # Validate profile_name
    if not isinstance(profile_data['profile_name'], str) or not profile_data['profile_name'].strip():
        return False, "profile_name must be a non-empty string"
    
    # Validate settings_snapshot
    if not isinstance(profile_data['settings_snapshot'], dict):
        return False, "settings_snapshot must be a dictionary"
    
    # Optional: Validate settings_snapshot structure
    settings = profile_data['settings_snapshot']
    if 'chart_settings' in settings:
        if not isinstance(settings['chart_settings'], dict):
            return False, "chart_settings must be a dictionary"
    
    return True, ""

def ensure_unique_profile_name(profile_name: str, user_id: int = 1) -> str:
    """
    Ensure profile name is unique by adding suffix if needed
    Returns a unique profile name
    """
    with FuturesDB() as db:
        original_name = profile_name
        counter = 1
        
        while db.get_user_profile_by_name(profile_name, user_id):
            if counter == 1:
                profile_name = f"{original_name} (imported)"
            else:
                profile_name = f"{original_name} (imported {counter})"
            counter += 1
        
        return profile_name

@profiles_bp.route('/api/v2/profiles', methods=['GET'])
def get_profiles():
    """Get all user profiles"""
    try:
        user_id = request.args.get('user_id', 1, type=int)
        
        with FuturesDB() as db:
            profiles = db.get_user_profiles(user_id)
            
            # Parse settings_snapshot JSON for each profile
            for profile in profiles:
                if profile.get('settings_snapshot'):
                    try:
                        profile['settings_snapshot'] = json.loads(profile['settings_snapshot'])
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in profile {profile['id']}: {profile['settings_snapshot']}")
                        profile['settings_snapshot'] = {}
            
            return jsonify({
                'success': True,
                'profiles': profiles,
                'count': len(profiles)
            })
    
    except Exception as e:
        logger.error(f"Error getting profiles: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@profiles_bp.route('/api/v2/profiles/<int:profile_id>', methods=['GET'])
def get_profile(profile_id):
    """Get a specific user profile"""
    try:
        with FuturesDB() as db:
            profile = db.get_user_profile(profile_id)
            
            if not profile:
                return jsonify({
                    'success': False,
                    'error': 'Profile not found'
                }), 404
            
            # Parse settings_snapshot JSON
            if profile.get('settings_snapshot'):
                try:
                    profile['settings_snapshot'] = json.loads(profile['settings_snapshot'])
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in profile {profile_id}: {profile['settings_snapshot']}")
                    profile['settings_snapshot'] = {}
            
            return jsonify({
                'success': True,
                'profile': profile
            })
    
    except Exception as e:
        logger.error(f"Error getting profile {profile_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@profiles_bp.route('/api/v2/profiles/<int:profile_id>/export', methods=['GET'])
def export_profile(profile_id):
    """Export a single profile as JSON download"""
    try:
        with FuturesDB() as db:
            profile = db.get_user_profile(profile_id)
            
            if not profile:
                return jsonify({
                    'success': False,
                    'error': 'Profile not found'
                }), 404
            
            # Parse settings_snapshot JSON
            if profile.get('settings_snapshot'):
                try:
                    profile['settings_snapshot'] = json.loads(profile['settings_snapshot'])
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in profile {profile_id}: {profile['settings_snapshot']}")
                    profile['settings_snapshot'] = {}
            
            # Prepare export data (exclude database-specific fields)
            export_data = {
                'profile_name': profile['profile_name'],
                'description': profile.get('description', ''),
                'settings_snapshot': profile['settings_snapshot'],
                'exported_at': datetime.now().isoformat(),
                'export_version': '1.0'
            }
            
            # Create JSON response
            json_data = json.dumps(export_data, indent=2)
            
            # Create filename
            safe_name = secure_filename(profile['profile_name'])
            filename = f"profile_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            # Create response with proper headers
            response = make_response(json_data)
            response.headers['Content-Type'] = 'application/json'
            response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            logger.info(f"Exported profile {profile_id} as {filename}")
            
            return response
    
    except Exception as e:
        logger.error(f"Error exporting profile {profile_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@profiles_bp.route('/api/v2/profiles/import', methods=['POST'])
def import_profile():
    """Import profile from uploaded JSON file"""
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file uploaded'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Only JSON files are allowed.'
            }), 400
        
        # Check file size
        if len(file.read()) > MAX_UPLOAD_SIZE:
            return jsonify({
                'success': False,
                'error': 'File too large. Maximum size is 5MB.'
            }), 400
        
        # Reset file pointer
        file.seek(0)
        
        # Read and parse JSON
        try:
            file_content = file.read().decode('utf-8')
            profile_data = json.loads(file_content)
        except json.JSONDecodeError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid JSON format: {str(e)}'
            }), 400
        except UnicodeDecodeError:
            return jsonify({
                'success': False,
                'error': 'Invalid file encoding. Please use UTF-8.'
            }), 400
        
        # Validate profile data structure
        is_valid, error_message = validate_profile_data(profile_data)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': f'Invalid profile data: {error_message}'
            }), 400
        
        # Get user_id from request
        user_id = request.form.get('user_id', 1, type=int)
        
        # Handle name conflicts
        original_name = profile_data['profile_name']
        unique_name = ensure_unique_profile_name(original_name, user_id)
        
        # Create profile in database
        with FuturesDB() as db:
            profile_id = db.create_user_profile(
                profile_name=unique_name,
                settings_snapshot=profile_data['settings_snapshot'],
                description=profile_data.get('description', ''),
                user_id=user_id
            )
            
            if profile_id:
                logger.info(f"Successfully imported profile: {unique_name} (ID: {profile_id})")
                
                return jsonify({
                    'success': True,
                    'message': 'Profile imported successfully',
                    'profile_id': profile_id,
                    'profile_name': unique_name,
                    'name_changed': unique_name != original_name,
                    'original_name': original_name if unique_name != original_name else None
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to create profile in database'
                }), 500
    
    except Exception as e:
        logger.error(f"Error importing profile: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@profiles_bp.route('/api/v2/profiles', methods=['POST'])
def create_profile():
    """Create a new user profile"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['profile_name', 'settings_snapshot']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        user_id = data.get('user_id', 1)
        
        with FuturesDB() as db:
            # Check if profile name already exists
            existing_profile = db.get_user_profile_by_name(data['profile_name'], user_id)
            if existing_profile:
                return jsonify({
                    'success': False,
                    'error': 'Profile name already exists'
                }), 400
            
            profile_id = db.create_user_profile(
                profile_name=data['profile_name'],
                settings_snapshot=data['settings_snapshot'],
                description=data.get('description', ''),
                is_default=data.get('is_default', False),
                user_id=user_id
            )
            
            if profile_id:
                return jsonify({
                    'success': True,
                    'message': 'Profile created successfully',
                    'profile_id': profile_id
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to create profile'
                }), 500
    
    except Exception as e:
        logger.error(f"Error creating profile: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@profiles_bp.route('/api/v2/profiles/<int:profile_id>', methods=['PUT'])
def update_profile(profile_id):
    """Update an existing user profile"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        with FuturesDB() as db:
            # Check if profile exists
            existing_profile = db.get_user_profile(profile_id)
            if not existing_profile:
                return jsonify({
                    'success': False,
                    'error': 'Profile not found'
                }), 404
            
            # Check for name conflicts if name is being changed
            if 'profile_name' in data and data['profile_name'] != existing_profile['profile_name']:
                name_conflict = db.get_user_profile_by_name(data['profile_name'], existing_profile['user_id'])
                if name_conflict:
                    return jsonify({
                        'success': False,
                        'error': 'Profile name already exists'
                    }), 400
            
            success = db.update_user_profile(
                profile_id=profile_id,
                profile_name=data.get('profile_name'),
                settings_snapshot=data.get('settings_snapshot'),
                description=data.get('description'),
                is_default=data.get('is_default')
            )
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Profile updated successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to update profile'
                }), 500
    
    except Exception as e:
        logger.error(f"Error updating profile {profile_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@profiles_bp.route('/api/v2/profiles/<int:profile_id>', methods=['DELETE'])
def delete_profile(profile_id):
    """Delete a user profile"""
    try:
        with FuturesDB() as db:
            # Check if profile exists
            existing_profile = db.get_user_profile(profile_id)
            if not existing_profile:
                return jsonify({
                    'success': False,
                    'error': 'Profile not found'
                }), 404
            
            success = db.delete_user_profile(profile_id)
            
            if success:
                logger.info(f"Deleted profile {profile_id}: {existing_profile['profile_name']}")
                return jsonify({
                    'success': True,
                    'message': 'Profile deleted successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to delete profile'
                }), 500
    
    except Exception as e:
        logger.error(f"Error deleting profile {profile_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@profiles_bp.route('/api/v2/profiles/default', methods=['GET'])
def get_default_profile():
    """Get the default user profile"""
    try:
        user_id = request.args.get('user_id', 1, type=int)
        
        with FuturesDB() as db:
            profile = db.get_default_user_profile(user_id)
            
            if not profile:
                return jsonify({
                    'success': False,
                    'error': 'No default profile found'
                }), 404
            
            # Parse settings_snapshot JSON
            if profile.get('settings_snapshot'):
                try:
                    profile['settings_snapshot'] = json.loads(profile['settings_snapshot'])
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in default profile: {profile['settings_snapshot']}")
                    profile['settings_snapshot'] = {}
            
            return jsonify({
                'success': True,
                'profile': profile
            })
    
    except Exception as e:
        logger.error(f"Error getting default profile: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@profiles_bp.route('/api/v2/profiles/bulk-export', methods=['POST'])
def bulk_export_profiles():
    """Export multiple profiles as a single JSON file"""
    try:
        data = request.get_json() or {}
        profile_ids = data.get('profile_ids', [])
        user_id = data.get('user_id', 1)
        
        if not profile_ids:
            return jsonify({
                'success': False,
                'error': 'No profile IDs provided'
            }), 400
        
        with FuturesDB() as db:
            profiles = []
            for profile_id in profile_ids:
                profile = db.get_user_profile(profile_id)
                if profile:
                    # Parse settings_snapshot JSON
                    if profile.get('settings_snapshot'):
                        try:
                            profile['settings_snapshot'] = json.loads(profile['settings_snapshot'])
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in profile {profile_id}: {profile['settings_snapshot']}")
                            profile['settings_snapshot'] = {}
                    
                    # Prepare export data
                    export_profile = {
                        'profile_name': profile['profile_name'],
                        'description': profile.get('description', ''),
                        'settings_snapshot': profile['settings_snapshot']
                    }
                    profiles.append(export_profile)
            
            if not profiles:
                return jsonify({
                    'success': False,
                    'error': 'No valid profiles found'
                }), 404
            
            # Create bulk export data
            export_data = {
                'profiles': profiles,
                'exported_at': datetime.now().isoformat(),
                'export_version': '1.0',
                'export_type': 'bulk',
                'profile_count': len(profiles)
            }
            
            # Create JSON response
            json_data = json.dumps(export_data, indent=2)
            
            # Create filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"profiles_bulk_export_{timestamp}.json"
            
            # Create response with proper headers
            response = make_response(json_data)
            response.headers['Content-Type'] = 'application/json'
            response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            logger.info(f"Bulk exported {len(profiles)} profiles as {filename}")
            
            return response
    
    except Exception as e:
        logger.error(f"Error in bulk export: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@profiles_bp.route('/api/v2/profiles/validate', methods=['POST'])
def validate_import_file():
    """Validate an uploaded profile file without importing it"""
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file uploaded'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Only JSON files are allowed.'
            }), 400
        
        # Check file size
        if len(file.read()) > MAX_UPLOAD_SIZE:
            return jsonify({
                'success': False,
                'error': 'File too large. Maximum size is 5MB.'
            }), 400
        
        # Reset file pointer
        file.seek(0)
        
        # Read and parse JSON
        try:
            file_content = file.read().decode('utf-8')
            profile_data = json.loads(file_content)
        except json.JSONDecodeError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid JSON format: {str(e)}'
            }), 400
        except UnicodeDecodeError:
            return jsonify({
                'success': False,
                'error': 'Invalid file encoding. Please use UTF-8.'
            }), 400
        
        # Determine if it's a single profile or bulk export
        if 'profiles' in profile_data:
            # Bulk export format
            profiles = profile_data.get('profiles', [])
            validation_results = []
            
            for i, profile in enumerate(profiles):
                is_valid, error_message = validate_profile_data(profile)
                validation_results.append({
                    'index': i,
                    'profile_name': profile.get('profile_name', 'Unknown'),
                    'valid': is_valid,
                    'error': error_message if not is_valid else None
                })
            
            valid_count = sum(1 for result in validation_results if result['valid'])
            
            return jsonify({
                'success': True,
                'file_type': 'bulk',
                'total_profiles': len(profiles),
                'valid_profiles': valid_count,
                'validation_results': validation_results,
                'all_valid': valid_count == len(profiles)
            })
        else:
            # Single profile format
            is_valid, error_message = validate_profile_data(profile_data)
            
            return jsonify({
                'success': True,
                'file_type': 'single',
                'profile_name': profile_data.get('profile_name', 'Unknown'),
                'valid': is_valid,
                'error': error_message if not is_valid else None
            })
    
    except Exception as e:
        logger.error(f"Error validating import file: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500