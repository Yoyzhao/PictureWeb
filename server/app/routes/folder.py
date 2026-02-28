from flask import Blueprint, request, jsonify, g
from app.utils.db import get_db
from app.services.scanner import scan_folder
from app.routes.auth import login_required
import os

bp = Blueprint('folder', __name__, url_prefix='/api/folders')

@bp.route('', methods=['GET'])
def get_folders():
    db = get_db()
    folders = db.execute("SELECT * FROM folders").fetchall()
    return jsonify([dict(f) for f in folders])

@bp.route('', methods=['POST'])
@login_required
def add_folder():
    if g.user['role'] == 'guest':
        return jsonify({'error': 'Guest users cannot add folders'}), 403
        
    data = request.get_json()
    path = data.get('path')
    name = data.get('name', os.path.basename(path))
    
    if not path or not os.path.exists(path):
        return jsonify({'error': 'Invalid path'}), 400
        
    db = get_db()
    try:
        # Check if folder already exists
        existing = db.execute("SELECT id FROM folders WHERE path = ?", (path,)).fetchone()
        if existing:
             return jsonify({'error': 'Folder already exists', 'id': existing['id']}), 409

        # Add folder
        cursor = db.execute(
            "INSERT INTO folders (path, name, user_id) VALUES (?, ?, ?)",
            (path, name, g.user['id'])
        )
        folder_id = cursor.lastrowid
        db.commit()
        
        # Trigger scan (async ideally, but sync for now)
        scan_folder(path, folder_id)
        
        return jsonify({'id': folder_id, 'path': path, 'name': name, 'message': 'Folder added and scanned'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:id>/scan', methods=['POST'])
@login_required
def rescan_folder(id):
    if g.user['role'] == 'guest':
        return jsonify({'error': 'Guest users cannot scan folders'}), 403
        
    db = get_db()
    folder = db.execute("SELECT path FROM folders WHERE id = ?", (id,)).fetchone()
    
    if not folder:
        return jsonify({'error': 'Folder not found'}), 404
        
    try:
        result = scan_folder(folder['path'], id)
        return jsonify({
            'message': '扫描完成',
            'processed': result['processed'],
            'removed': result['removed'],
            'total': result['total_current']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
