from flask import Blueprint, request, jsonify, g
from app.utils.db import get_db
from werkzeug.security import check_password_hash
import secrets
from functools import wraps

bp = Blueprint('auth', __name__, url_prefix='/api/auth')

def get_current_user():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None
    
    # In a real app, verify JWT. For now, we use simple mock tokens.
    db = get_db()
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        
        # Backward compatibility for existing hardcoded tokens
        if token == 'admin-token':
            return db.execute("SELECT * FROM users WHERE username = 'admin'").fetchone()
        elif token == 'guest-token':
            return db.execute("SELECT * FROM users WHERE username = 'guest'").fetchone()
            
        # New token format: token-{id}
        if token.startswith('token-'):
            try:
                user_id = int(token.split('-')[1])
                return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            except:
                pass
                
    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({'error': 'Unauthorized'}), 401
        g.user = user
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/login', methods=['POST'])
def login():
    db = get_db()
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    
    if user and (user['username'] == 'guest' or check_password_hash(user['password_hash'], password)):
        # Mock token for prototype
        # Use a simple format: "user-{id}-{role}" to allow getting user without DB lookup if needed, 
        # but here we just use it to find the user.
        token = f"token-{user['id']}"
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
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    return jsonify({
        'user': {
            'id': user['id'],
            'username': user['username'],
            'role': user['role']
        }
    })
