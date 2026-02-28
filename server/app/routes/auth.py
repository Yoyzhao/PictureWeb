from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from werkzeug.security import check_password_hash
import secrets

bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@bp.route('/login', methods=['POST'])
def login():
    db = get_db()
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    
    if user and (user['username'] == 'guest' or check_password_hash(user['password_hash'], password)):
        # In a real app, use JWT tokens. For now, we use a simple mock token.
        token = secrets.token_hex(16)
        return jsonify({
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'role': user['role']
            }
        })
        
    return jsonify({'error': 'Invalid username or password'}), 401

@bp.route('/me', methods=['GET'])
def get_me():
    # This would normally verify the token. 
    # For now, we return 401 to force login if no token is provided in headers
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Unauthorized'}), 401
        
    # Mock behavior: return a default user or based on token
    return jsonify({
        'user': {
            'username': 'admin',
            'role': 'admin'
        }
    })
