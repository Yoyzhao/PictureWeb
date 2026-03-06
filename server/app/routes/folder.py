from flask import Blueprint, request, jsonify, g, current_app
from app.utils.db import get_db
from app.services.scanner import scan_folder
from app.routes.auth import login_required, get_current_user
import os
import shutil
# from send2trash import send2trash
import uuid
from threading import Thread

bp = Blueprint('folder', __name__, url_prefix='/api/folders')

def run_scan_async(app, path, folder_id):
    with app.app_context():
        try:
            scan_folder(path, folder_id)
        except Exception as e:
            print(f"Background scan error: {e}")

def extract_folder_name(path):
    # Normalize path
    path = path.replace('\\', '/').rstrip('/')
    if not path:
        return "Root"
    # For Windows drive like C:
    if len(path) == 2 and path[1] == ':':
        return path
    name = os.path.basename(path)
    return name or path

@bp.route('/<int:id>', methods=['DELETE'])
@login_required
def delete_folder(id):
    if g.user['role'] != 'admin':
        return jsonify({'error': 'Only admins can delete folders'}), 403
        
    hard_delete = request.args.get('hard', 'false').lower() == 'true'
    db = get_db()
    
    folder = db.execute("SELECT path FROM folders WHERE id = ?", (id,)).fetchone()
    if not folder:
        return jsonify({'error': 'Folder not found'}), 404
        
    path = folder['path']
    
    try:
        if hard_delete:
            if os.path.exists(path):
                # Move the entire folder to application-level trash for safety
                trash_dir = current_app.config.get('TRASH_DIR', os.path.join(current_app.root_path, '..', 'data', 'trash'))
                if not os.path.exists(trash_dir):
                    os.makedirs(trash_dir)
                
                # We don't record the whole folder in the trash table for now, 
                # just the files inside to keep it simple, or just move the folder.
                # Let's just move the folder to a unique name in trash.
                trash_folder_name = f"folder_{uuid.uuid4()}_{os.path.basename(path.rstrip('/\\\\'))}"
                trash_path = os.path.join(trash_dir, trash_folder_name)
                shutil.move(path, trash_path)
        
        # 1. Delete related thumbnails from disk
        images = db.execute("SELECT id FROM images WHERE folder_id = ?", (id,)).fetchall()
        for img in images:
            thumbnails = db.execute("SELECT file_path FROM thumbnails WHERE image_id = ?", (img['id'],)).fetchall()
            for thumb in thumbnails:
                if os.path.exists(thumb['file_path']):
                    try:
                        os.remove(thumb['file_path'])
                    except:
                        pass
        
        # 2. Delete from DB (Cascade will handle images and thumbnails records if configured, 
        # but let's be explicit if not sure about foreign key constraints in current DB)
        db.execute("DELETE FROM thumbnails WHERE image_id IN (SELECT id FROM images WHERE folder_id = ?)", (id,))
        db.execute("DELETE FROM images WHERE folder_id = ?", (id,))
        db.execute("DELETE FROM folders WHERE id = ?", (id,))
        db.execute("DELETE FROM permissions WHERE folder_id = ?", (id,))
        
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('', methods=['GET'])
def get_folders():
    db = get_db()
    user = get_current_user()
    
    if user and user['role'] == 'admin':
        # Admin can see all folders
        folders = db.execute("SELECT id, path, name, user_id, is_public, scan_status, scan_total, scan_processed, scan_error, created_at, updated_at FROM folders").fetchall()
    elif user:
        # Regular users can see public folders OR folders they have 'read' permission for
        query = """
            SELECT DISTINCT f.id, f.path, f.name, f.user_id, f.is_public, f.scan_status, f.scan_total, f.scan_processed, f.scan_error, f.created_at, f.updated_at 
            FROM folders f
            LEFT JOIN permissions p ON f.id = p.folder_id
            WHERE f.is_public = 1 OR (p.user_id = ? AND p.permission_type = 'read')
        """
        folders = db.execute(query, (user['id'],)).fetchall()
    else:
        # Anonymous users can only see public folders
        folders = db.execute("SELECT id, path, name, user_id, is_public, scan_status, scan_total, scan_processed, scan_error, created_at, updated_at FROM folders WHERE is_public = 1").fetchall()
        
    result = []
    for f in folders:
        d = dict(f)
        # Serialize datetime
        if d.get('created_at') and hasattr(d['created_at'], 'isoformat'):
            d['created_at'] = d['created_at'].isoformat()
        if d.get('updated_at') and hasattr(d['updated_at'], 'isoformat'):
            d['updated_at'] = d['updated_at'].isoformat()
        result.append(d)
        
    return jsonify(result)

@bp.route('', methods=['POST'])
@login_required
def add_folder():
    if g.user['role'] == 'guest':
        return jsonify({'error': 'Guest users cannot add folders'}), 403
        
    data = request.get_json()
    path = data.get('path')
    name = data.get('name') or extract_folder_name(path)
    is_public = data.get('is_public', False)
    
    if not path or not os.path.exists(path):
        return jsonify({'error': 'Invalid path'}), 400
        
    db = get_db()
    try:
        # Check if folder already exists
        existing = db.execute("SELECT id FROM folders WHERE path = ?", (path,)).fetchone()
        if existing:
             return jsonify({'error': 'Folder already exists', 'id': existing['id']}), 409

        # Add folder with initial status 'pending'
        cursor = db.execute(
            "INSERT INTO folders (path, name, user_id, is_public, scan_status) VALUES (?, ?, ?, ?, ?)",
            (path, name, g.user['id'], 1 if is_public else 0, 'pending')
        )
        folder_id = cursor.lastrowid
        db.commit()
        
        # Trigger scan async
        app = current_app._get_current_object()
        thread = Thread(target=run_scan_async, args=(app, path, folder_id))
        thread.start()
        
        return jsonify({'id': folder_id, 'path': path, 'name': name, 'message': 'Folder added, scan started in background'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:id>', methods=['PATCH'])
@login_required
def update_folder(id):
    if g.user['role'] != 'admin':
        return jsonify({'error': 'Only admins can update folders'}), 403
        
    data = request.get_json()
    db = get_db()
    
    updates = []
    params = []
    
    if 'name' in data:
        updates.append("name = ?")
        params.append(data['name'])
    
    if 'path' in data:
        path = data['path']
        if not os.path.exists(path):
            return jsonify({'error': 'Invalid path'}), 400
        updates.append("path = ?")
        params.append(path)
        
    if 'is_public' in data:
        updates.append("is_public = ?")
        params.append(1 if data['is_public'] else 0)
        
    if not updates:
        return jsonify({'error': 'No updates provided'}), 400
        
    params.append(id)
    try:
        db.execute(f"UPDATE folders SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", params)
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:id>/scan', methods=['POST'])
@login_required
def rescan_folder(id):
    if g.user['role'] == 'guest':
        return jsonify({'error': 'Guest users cannot scan folders'}), 403
        
    db = get_db()
    folder = db.execute("SELECT path, scan_status FROM folders WHERE id = ?", (id,)).fetchone()
    
    if not folder:
        return jsonify({'error': 'Folder not found'}), 404
        
    if folder['scan_status'] == 'scanning':
        return jsonify({'error': 'Scan already in progress'}), 409
        
    try:
        # Trigger scan async
        app = current_app._get_current_object()
        thread = Thread(target=run_scan_async, args=(app, folder['path'], id))
        thread.start()
        
        return jsonify({'success': True, 'message': 'Scan started in background'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
