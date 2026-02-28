from flask import Blueprint, request, jsonify, current_app
from app.utils.db import get_db
import yaml
import os
from werkzeug.security import generate_password_hash

bp = Blueprint('admin', __name__, url_prefix='/api/admin')

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
    folders = db.execute("SELECT * FROM folders").fetchall()
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
            current_app.config[key] = value
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
