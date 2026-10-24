from flask import Blueprint, request, jsonify, g, current_app
from app.utils.db import get_db
from werkzeug.security import check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from functools import wraps

bp = Blueprint('auth', __name__, url_prefix='/api/auth')

TOKEN_SALT = 'picgallery-auth-token'


def _token_serializer():
    """Token serializer bound to SECRET_KEY from .env (never hardcoded)."""
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=TOKEN_SALT)


def generate_token(user_id):
    return _token_serializer().dumps({'uid': int(user_id)})


def get_current_user():
    auth_header = request.headers.get('Authorization')
    token = None
    
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ', 1)[1].strip()
    else:
        # Also check query parameter for cases like image <img> tags
        token = request.args.get('token')
        
    if not token:
        return None

    try:
        payload = _token_serializer().loads(
            token,
            max_age=int(current_app.config.get('TOKEN_MAX_AGE_SECONDS', 604800))
        )
        user_id = int(payload['uid'])
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
        return None

    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


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
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username:
        return jsonify({'error': 'Username is required'}), 400
    
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    
    if user and (user['username'] == 'guest' or check_password_hash(user['password_hash'], password)):
        token = generate_token(user['id'])
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
