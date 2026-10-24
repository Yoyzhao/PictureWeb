from flask import Blueprint, request, jsonify, g, current_app
from app.utils.db import get_db
from app.services.scanner import scan_folder
from app.services.thumbnail import clear_image_thumbnails
from app.routes.auth import login_required, get_current_user
import os
import shutil
import sqlite3
import uuid
from threading import Thread

bp = Blueprint('folder', __name__, url_prefix='/api/folders')

# Statuses owned by a running background scan; folder edits/deletes must wait for them.
BUSY_SCAN_STATUSES = ('pending', 'scanning')


def run_scan_async(app, path, folder_id):
    with app.app_context():
        try:
            scan_folder(path, folder_id)
        except Exception as e:
            print(f"Background scan error: {e}")


def _normalize_path(path):
    return os.path.normpath(os.path.expanduser(str(path).strip()))


def _path_key(path):
    """Case/separator-insensitive cache key for a path on the current OS."""
    return os.path.normcase(os.path.normpath(path))


def _is_within(child, parent):
    """True when child is parent itself or lives inside parent."""
    child_key = _path_key(child)
    parent_key = _path_key(parent)
    try:
        return os.path.commonpath([child_key, parent_key]) == parent_key
    except ValueError:
        # Different drives on Windows have no common path.
        return False


def _validate_folder_path(raw_path):
    if not raw_path or not str(raw_path).strip():
        return None, 'Folder path is required'
    path = _normalize_path(raw_path)
    if not os.path.isabs(path):
        return None, 'Folder path must be absolute'
    if not os.path.exists(path):
        return None, 'Folder path does not exist'
    if not os.path.isdir(path):
        return None, 'Folder path is not a directory'
    return path, None


def _find_path_conflict(db, path, exclude_id=None):
    """
    Reject duplicated or overlapping folders.

    images.file_path is globally unique, so a nested folder would silently lose
    its files to whichever folder was scanned first.
    """
    for row in db.execute("SELECT id, path, name FROM folders"):
        if exclude_id is not None and row['id'] == exclude_id:
            continue
        if _path_key(row['path']) == _path_key(path):
            return 'duplicate', row
        if _is_within(path, row['path']) or _is_within(row['path'], path):
            return 'overlap', row
    return None, None


def _conflict_response(kind, row):
    if kind == 'duplicate':
        return jsonify({'error': 'Folder already exists', 'id': row['id']}), 409
    return jsonify({
        'error': f'Folder overlaps existing folder "{row["name"]}"; nested folders cannot be indexed separately'
    }), 409


def extract_folder_name(path):
    normalized = _normalize_path(path)
    drive, tail = os.path.splitdrive(normalized)
    name = os.path.basename(tail.rstrip('\\/'))
    return name or drive or normalized


def _is_dangerous_delete_path(path):
    """Refuse to move a filesystem root or a directory containing application data."""
    target = _path_key(path)
    drive, _ = os.path.splitdrive(_normalize_path(path))
    root = os.path.abspath(os.sep if not drive else drive + os.sep)
    if target == _path_key(root):
        return True

    project_root = os.path.abspath(os.path.join(current_app.root_path, '..'))
    protected = [
        project_root,
        current_app.config.get('DB_PATH'),
        current_app.config.get('CACHE_DIR'),
        current_app.config.get('TRASH_DIR'),
    ]
    return any(candidate and _is_within(candidate, path) for candidate in protected)


def _remove_thumbnail_files(db, image_id):
    thumbnails = db.execute("SELECT file_path FROM thumbnails WHERE image_id = ?", (image_id,)).fetchall()
    for thumb in thumbnails:
        if thumb['file_path'] and os.path.exists(thumb['file_path']):
            try:
                os.remove(thumb['file_path'])
            except OSError:
                pass
    # Also remove cache entries whose DB record was lost or used a legacy format.
    clear_image_thumbnails(image_id)


def purge_folder_records(db, folder_id):
    """
    Remove a folder's index and all dependent records.

    SQLite foreign_keys is disabled in this app, so ON DELETE CASCADE never runs.
    """
    images = db.execute("SELECT id FROM images WHERE folder_id = ?", (folder_id,)).fetchall()
    for image in images:
        _remove_thumbnail_files(db, image['id'])

    db.execute("DELETE FROM user_favorites WHERE image_id IN (SELECT id FROM images WHERE folder_id = ?)", (folder_id,))
    db.execute("DELETE FROM image_tags WHERE image_id IN (SELECT id FROM images WHERE folder_id = ?)", (folder_id,))
    db.execute("DELETE FROM thumbnails WHERE image_id IN (SELECT id FROM images WHERE folder_id = ?)", (folder_id,))
    db.execute("DELETE FROM images WHERE folder_id = ?", (folder_id,))
    # Bookmarks bound to this folder have no view to restore afterwards.
    db.execute("DELETE FROM image_bookmarks WHERE folder_id = ?", (folder_id,))
    db.execute("DELETE FROM permissions WHERE folder_id = ?", (folder_id,))
    db.execute("DELETE FROM folders WHERE id = ?", (folder_id,))


def _start_scan(folder_path, folder_id):
    app = current_app._get_current_object()
    thread = Thread(target=run_scan_async, args=(app, folder_path, folder_id))
    thread.start()


@bp.route('/<int:id>', methods=['DELETE'])
@login_required
def delete_folder(id):
    if g.user['role'] != 'admin':
        return jsonify({'error': 'Only admins can delete folders'}), 403

    hard_delete = request.args.get('hard', 'false').lower() == 'true'
    db = get_db()

    folder = db.execute("SELECT path, scan_status FROM folders WHERE id = ?", (id,)).fetchone()
    if not folder:
        return jsonify({'error': 'Folder not found'}), 404

    if folder['scan_status'] in BUSY_SCAN_STATUSES:
        return jsonify({'error': 'Folder is being scanned; try again after it finishes'}), 409

    path = folder['path']
    if hard_delete and _is_dangerous_delete_path(path):
        return jsonify({'error': 'Refusing to delete a filesystem root or a directory containing application data'}), 400

    moved_to = None
    if hard_delete and os.path.exists(path):
        try:
            # Move the entire folder to application-level trash for safety.
            trash_dir = current_app.config.get('TRASH_DIR', os.path.join(current_app.root_path, '..', 'data', 'trash'))
            os.makedirs(trash_dir, exist_ok=True)
            trash_folder_name = f"folder_{uuid.uuid4()}_{os.path.basename(_normalize_path(path))}"
            moved_to = os.path.join(trash_dir, trash_folder_name)
            shutil.move(path, moved_to)
        except Exception as e:
            return jsonify({'error': f'Failed to move folder to trash: {str(e)}'}), 500

    try:
        purge_folder_records(db, id)
        db.commit()
    except Exception as e:
        db.rollback()
        # Keep the physical folder where it was if the index cleanup did not complete.
        if moved_to and os.path.exists(moved_to) and not os.path.exists(path):
            try:
                shutil.move(moved_to, path)
            except Exception:
                pass
        return jsonify({'error': str(e)}), 500

    return jsonify({'success': True})


@bp.route('', methods=['GET'])
def get_folders():
    db = get_db()
    user = get_current_user()

    if user and user['role'] == 'admin':
        # Admin can see all folders
        folders = db.execute("SELECT id, path, name, user_id, is_public, scan_status, scan_total, scan_processed, scan_error, created_at, updated_at FROM folders").fetchall()
    elif user:
        # Regular users can see their own folders, public folders, or folders with read permission
        query = """
            SELECT DISTINCT f.id, f.path, f.name, f.user_id, f.is_public, f.scan_status, f.scan_total, f.scan_processed, f.scan_error, f.created_at, f.updated_at 
            FROM folders f
            LEFT JOIN permissions p ON f.id = p.folder_id
            WHERE f.user_id = ? OR f.is_public = 1 OR (p.user_id = ? AND p.permission_type IN ('read', 'write', 'delete', 'rename'))
        """
        folders = db.execute(query, (user['id'], user['id'])).fetchall()
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

    data = request.get_json(silent=True) or {}
    path, error = _validate_folder_path(data.get('path'))
    if error:
        return jsonify({'error': error}), 400

    name = (data.get('name') or '').strip()[:255] or extract_folder_name(path)
    is_public = bool(data.get('is_public', False))

    db = get_db()
    kind, conflict = _find_path_conflict(db, path)
    if kind:
        return _conflict_response(kind, conflict)

    try:
        # Add folder with initial status 'pending'
        cursor = db.execute(
            "INSERT INTO folders (path, name, user_id, is_public, scan_status) VALUES (?, ?, ?, ?, ?)",
            (path, name, g.user['id'], 1 if is_public else 0, 'pending')
        )
        folder_id = cursor.lastrowid
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify({'error': 'Folder already exists'}), 409
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500

    _start_scan(path, folder_id)
    return jsonify({'id': folder_id, 'path': path, 'name': name, 'message': 'Folder added, scan started in background'}), 201


@bp.route('/<int:id>', methods=['PATCH'])
@login_required
def update_folder(id):
    if g.user['role'] != 'admin':
        return jsonify({'error': 'Only admins can update folders'}), 403

    data = request.get_json(silent=True) or {}
    db = get_db()
    folder = db.execute("SELECT path, scan_status FROM folders WHERE id = ?", (id,)).fetchone()
    if not folder:
        return jsonify({'error': 'Folder not found'}), 404

    updates = []
    params = []
    path_changed = False

    if 'name' in data:
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': 'Folder name is required'}), 400
        updates.append("name = ?")
        params.append(name[:255])

    if 'path' in data:
        new_path, error = _validate_folder_path(data['path'])
        if error:
            return jsonify({'error': error}), 400
        if _path_key(new_path) != _path_key(folder['path']):
            if folder['scan_status'] in BUSY_SCAN_STATUSES:
                return jsonify({'error': 'Folder is being scanned; try again after it finishes'}), 409
            kind, conflict = _find_path_conflict(db, new_path, exclude_id=id)
            if kind:
                return _conflict_response(kind, conflict)
            # A path change makes the existing index stale; rescan to reconcile it.
            updates.append("path = ?")
            params.append(new_path)
            updates.append("scan_status = 'pending'")
            updates.append("scan_total = 0")
            updates.append("scan_processed = 0")
            updates.append("scan_error = NULL")
            path_changed = True

    if 'is_public' in data:
        updates.append("is_public = ?")
        params.append(1 if data['is_public'] else 0)

    if not updates:
        return jsonify({'error': 'No updates provided'}), 400

    params.append(id)
    try:
        db.execute(f"UPDATE folders SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", params)
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify({'error': 'Folder already exists'}), 409
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500

    if path_changed:
        new_path = db.execute("SELECT path FROM folders WHERE id = ?", (id,)).fetchone()['path']
        _start_scan(new_path, id)

    return jsonify({'success': True, 'rescan_started': path_changed})


@bp.route('/<int:id>/scan', methods=['POST'])
@login_required
def rescan_folder(id):
    if g.user['role'] == 'guest':
        return jsonify({'error': 'Guest users cannot scan folders'}), 403

    db = get_db()
    folder = db.execute("SELECT path, user_id, scan_status FROM folders WHERE id = ?", (id,)).fetchone()
    if not folder:
        return jsonify({'error': 'Folder not found'}), 404

    if folder['scan_status'] in BUSY_SCAN_STATUSES:
        return jsonify({'error': 'Scan already in progress'}), 409

    if g.user['role'] != 'admin' and folder['user_id'] != g.user['id']:
        permission = db.execute(
            "SELECT 1 FROM permissions WHERE user_id = ? AND folder_id = ? AND permission_type = 'write'",
            (g.user['id'], id)
        ).fetchone()
        if not permission:
            return jsonify({'error': 'Permission denied for this folder'}), 403

    path, error = _validate_folder_path(folder['path'])
    if error:
        return jsonify({'error': error}), 400

    # Claim the scan atomically so two concurrent requests cannot both start one.
    cursor = db.execute(
        """
        UPDATE folders
        SET scan_status = 'pending', scan_total = 0, scan_processed = 0, scan_error = NULL
        WHERE id = ? AND scan_status NOT IN ('pending', 'scanning')
        """,
        (id,)
    )
    db.commit()
    if cursor.rowcount == 0:
        return jsonify({'error': 'Scan already in progress'}), 409

    _start_scan(folder['path'], id)
    return jsonify({'success': True, 'message': 'Scan started in background'})
