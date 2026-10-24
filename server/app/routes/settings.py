from flask import Blueprint, jsonify, current_app

bp = Blueprint('settings', __name__, url_prefix='/api/settings')


@bp.route('', methods=['GET'])
def get_public_settings():
    """Client-safe settings only; admin-only configuration stays under /api/admin/settings."""
    return jsonify({
        'HOTKEYS': current_app.config.get('HOTKEYS', {}),
        'ENABLE_PRELOAD': bool(current_app.config.get('ENABLE_PRELOAD', True))
    })
