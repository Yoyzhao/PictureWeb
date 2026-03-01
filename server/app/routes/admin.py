from flask import Blueprint, request, jsonify, current_app, g
from app.utils.db import get_db
from werkzeug.security import generate_password_hash
import yaml
import os
import shutil
from app.routes.auth import login_required

bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# --- Helper to get directory size ---
def get_dir_size(path):
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_file():
                        total += entry.stat().st_size
                    elif entry.is_dir():
                        total += get_dir_size(entry.path)
                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError, FileNotFoundError):
        pass
    return total

@bp.before_request
@login_required
def require_admin():
    if not hasattr(g, 'user') or not g.user:
        return jsonify({'error': 'Unauthorized'}), 401
    if g.user['role'] != 'admin':
        return jsonify({'error': 'Admin permission required'}), 403

# --- Cache Management ---

@bp.route('/cache/stats', methods=['GET'])
def get_cache_stats():
    try:
        cache_dir = current_app.config.get('CACHE_DIR')
        if not cache_dir:
            return jsonify({'size': 0, 'size_human': '0.00 MB', 'path': None, 'error': 'CACHE_DIR not configured'})
            
        if not os.path.exists(cache_dir):
            return jsonify({'size': 0, 'size_human': '0.00 MB', 'path': cache_dir, 'error': 'Cache directory does not exist'})
        
        size = get_dir_size(cache_dir)
        return jsonify({
            'size': size,
            'size_human': f"{size / (1024*1024):.2f} MB",
            'path': cache_dir
        })
    except Exception as e:
        current_app.logger.error(f"Error getting cache stats: {str(e)}")
        return jsonify({'error': str(e), 'size': 0, 'size_human': 'Error'}), 500

@bp.route('/cache/clear', methods=['POST'])
def clear_cache():
    cache_dir = current_app.config.get('CACHE_DIR')
    if not cache_dir or not os.path.exists(cache_dir):
        return jsonify({'success': True, 'message': 'Cache directory not found'})
    
    try:
        # Clear subdirectories but keep the root cache dir
        for item in os.listdir(cache_dir):
            item_path = os.path.join(cache_dir, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
            except (OSError, PermissionError):
                continue # Skip files in use
        
        # Also clear the thumbnails table in DB
        db = get_db()
        db.execute("DELETE FROM thumbnails")
        db.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.error(f"Error clearing cache: {str(e)}")
        return jsonify({'error': str(e)}), 500

# --- User Management ---

@bp.route('/users', methods=['GET'])
def get_users():
    db = get_db()
    users = db.execute("SELECT id, username, role, created_at FROM users").fetchall()
    return jsonify([dict(user) for user in users])

@bp.route('/users', methods=['POST'])
def add_user():
    db = get_db()
    data = request.json
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
        
    try:
        db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), role)
        )
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/users/<int:id>', methods=['PATCH'])
def update_user(id):
    db = get_db()
    data = request.json
    
    updates = []
    params = []
    
    if 'role' in data:
        updates.append("role = ?")
        params.append(data['role'])
    
    if 'password' in data:
        updates.append("password_hash = ?")
        params.append(generate_password_hash(data['password']))
        
    if not updates:
        return jsonify({'error': 'No updates provided'}), 400
        
    params.append(id)
    query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
    db.execute(query, params)
    db.commit()
    return jsonify({'success': True})

@bp.route('/users/<int:id>', methods=['DELETE'])
def delete_user(id):
    db = get_db()
    # Don't allow deleting the last admin or the guest user
    user = db.execute("SELECT username, role FROM users WHERE id = ?", (id,)).fetchone()
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    if user['username'] == 'admin' or user['username'] == 'guest':
        return jsonify({'error': 'Cannot delete system users'}), 400
        
    db.execute("DELETE FROM users WHERE id = ?", (id,))
    db.commit()
    return jsonify({'success': True})

# --- Folder & Permission Management ---

@bp.route('/folders', methods=['GET'])
def get_folders():
    db = get_db()
    query = """
        SELECT id, path, name, user_id, is_public, 
               scan_status, scan_total, scan_processed, scan_error,
               created_at, updated_at 
        FROM folders
    """
    folders = db.execute(query).fetchall()
    return jsonify([dict(f) for f in folders])

@bp.route('/folders/<int:id>', methods=['DELETE'])
def delete_folder(id):
    db = get_db()
    try:
        # Check if folder exists
        folder = db.execute("SELECT id, path FROM folders WHERE id = ?", (id,)).fetchone()
        if not folder:
            return jsonify({'error': 'Folder not found'}), 404
            
        # Delete images first (this will cascade delete thumbnails/tags in DB)
        db.execute("DELETE FROM images WHERE folder_id = ?", (id,))
        
        # Delete the folder record (this will cascade delete permissions in DB)
        db.execute("DELETE FROM folders WHERE id = ?", (id,))
        
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/permissions', methods=['GET'])
def get_all_permissions():
    db = get_db()
    query = """
        SELECT p.id, p.user_id, p.folder_id, p.permission_type, 
               u.username, f.name as folder_name
        FROM permissions p
        JOIN users u ON p.user_id = u.id
        JOIN folders f ON p.folder_id = f.id
    """
    perms = db.execute(query).fetchall()
    return jsonify([dict(p) for p in perms])

@bp.route('/permissions', methods=['POST'])
def add_permission():
    db = get_db()
    data = request.json
    user_id = data.get('user_id')
    folder_id = data.get('folder_id')
    permission_types = data.get('permission_types', [])
    
    if not all([user_id, folder_id]) or not permission_types:
        return jsonify({'error': 'Missing required fields'}), 400
        
    # Check user role
    user = db.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    if user['role'] in ('admin', 'guest'):
        return jsonify({'error': f"Cannot assign permissions to {user['role']} role"}), 403
        
    try:
        for p_type in permission_types:
            # Using INSERT OR IGNORE to handle duplicates gracefully
            db.execute(
                "INSERT OR IGNORE INTO permissions (user_id, folder_id, permission_type) VALUES (?, ?, ?)",
                (user_id, folder_id, p_type)
            )
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/permissions/<int:id>', methods=['DELETE'])
def delete_permission(id):
    db = get_db()
    
    # Check permission owner role before deleting
    perm = db.execute("SELECT user_id FROM permissions WHERE id = ?", (id,)).fetchone()
    if perm:
        user = db.execute("SELECT role FROM users WHERE id = ?", (perm['user_id'],)).fetchone()
        if user and user['role'] in ('admin', 'guest'):
             return jsonify({'error': f"Cannot modify permissions for {user['role']} role"}), 403
             
    db.execute("DELETE FROM permissions WHERE id = ?", (id,))
    db.commit()
    return jsonify({'success': True})

# --- System Settings ---

@bp.route('/settings', methods=['GET'])
def get_settings():
    try:
        # project_root is 4 levels up from server/app/routes/admin.py
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        config_path = os.path.join(project_root, 'config.yaml')
        if not os.path.exists(config_path):
            return jsonify({'error': f'Config file not found at {config_path}'}), 404
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/settings', methods=['POST'])
def update_settings():
    try:
        data = request.json
        # project_root is 4 levels up from server/app/routes/admin.py
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        config_path = os.path.join(project_root, 'config.yaml')
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, default_flow_style=False)
            
        # Reload config in current app (simplified)
        for key, value in data.items():
            # Resolve relative paths relative to project root
            if key in ['DB_PATH', 'CACHE_DIR'] and not os.path.isabs(value):
                value = os.path.abspath(os.path.join(project_root, value))
            # Ensure THUMBNAIL_QUALITY is an integer
            if key == 'THUMBNAIL_QUALITY' and value is not None:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    pass
            current_app.config[key] = value
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
