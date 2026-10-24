from flask import Blueprint, request, jsonify, send_file, abort, g, current_app
from app.utils.db import get_db
from app.services.thumbnail import generate_thumbnail, generate_thumbnail_from_path, clear_trash_thumbnails
from app.routes.auth import get_current_user, login_required
from datetime import datetime
import base64
import os
import shutil
import uuid
import json
# from send2trash import send2trash

bp = Blueprint('image', __name__, url_prefix='/api/images')


def encode_cursor(payload):
    raw = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def decode_cursor(token):
    if not token:
        return None
    try:
        padded = token + '=' * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode('ascii'))
        payload = json.loads(raw.decode('utf-8'))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def cursor_value(row, sort_by):
    if sort_by == 'modified_time':
        value = row['modified_time']
        if value is None:
            return ''
        return value.strftime('%Y-%m-%d %H:%M:%S.%f') if hasattr(value, 'strftime') else str(value)
    if sort_by == 'file_size':
        return int(row['file_size'] or 0)
    return str(row['file_name'] or '')


def _folder_access(db, user, folder_id, permission_type='read'):
    """Admin and folder owner have full access; read also allows public folders."""
    if user and user['role'] == 'admin':
        return True
    if not folder_id:
        return False

    folder = db.execute("SELECT user_id, is_public FROM folders WHERE id = ?", (folder_id,)).fetchone()
    if not folder:
        return False
    if permission_type == 'read' and folder['is_public']:
        return True
    if not user:
        return False
    if folder['user_id'] == user['id']:
        return True

    if permission_type == 'read':
        perm = db.execute(
            """
            SELECT 1 FROM permissions
            WHERE user_id = ? AND folder_id = ?
              AND permission_type IN ('read', 'write', 'delete', 'rename')
            """,
            (user['id'], folder_id)
        ).fetchone()
    else:
        perm = db.execute(
            "SELECT 1 FROM permissions WHERE user_id = ? AND folder_id = ? AND permission_type = ?",
            (user['id'], folder_id, permission_type)
        ).fetchone()
    return perm is not None


def _image_access(db, user, image_id, permission_type='read'):
    image = db.execute("SELECT id, folder_id FROM images WHERE id = ?", (image_id,)).fetchone()
    if not image:
        return None, False
    return image, _folder_access(db, user, image['folder_id'], permission_type)


def _path_in_use(db, path):
    """A target path is unavailable if it exists on disk or is still referenced in DB."""
    if os.path.exists(path):
        return True
    db_path = path.replace('\\', '/')
    return db.execute("SELECT 1 FROM images WHERE file_path = ?", (db_path,)).fetchone() is not None

@bp.route('/<int:id>/favorite', methods=['POST'])
@login_required
def toggle_favorite(id):
    if g.user['role'] == 'guest':
        return jsonify({'error': 'Guest users cannot favorite images'}), 403
        
    db = get_db()
    user_id = g.user['id']

    image, allowed = _image_access(db, g.user, id, 'read')
    if not image:
        return jsonify({'error': 'Image not found'}), 404
    if not allowed:
        return jsonify({'error': 'Permission denied'}), 403

    # Check if already favorited
    fav = db.execute(
        "SELECT 1 FROM user_favorites WHERE user_id = ? AND image_id = ?",
        (user_id, id)
    ).fetchone()
    
    if fav:
        db.execute(
            "DELETE FROM user_favorites WHERE user_id = ? AND image_id = ?",
            (user_id, id)
        )
        is_favorite = False
    else:
        db.execute(
            "INSERT OR IGNORE INTO user_favorites (user_id, image_id) VALUES (?, ?)",
            (user_id, id)
        )
        is_favorite = True
        
    db.commit()
    return jsonify({'success': True, 'is_favorite': is_favorite})

@bp.route('/batch/move', methods=['POST'])
@login_required
def batch_move_images():
    if g.user['role'] == 'guest':
        return jsonify({'error': 'Guest users cannot move images'}), 403
        
    data = request.json
    image_ids = data.get('image_ids', [])
    target_folder_id = data.get('target_folder_id')
    
    if not image_ids or not target_folder_id:
        return jsonify({'error': 'Missing parameters'}), 400
        
    db = get_db()
    target_folder = db.execute("SELECT id, path FROM folders WHERE id = ?", (target_folder_id,)).fetchone()
    if not target_folder:
        return jsonify({'error': 'Target folder not found'}), 404
    if not _folder_access(db, g.user, target_folder_id, 'write'):
        return jsonify({'error': 'Permission denied for target folder'}), 403

    target_path_base = os.path.normpath(target_folder['path'])
    if not os.path.isdir(target_path_base):
        return jsonify({'error': 'Target folder path does not exist on disk'}), 400

    success_ids = []
    errors = []

    for img_id in image_ids:
        image = db.execute("SELECT id, folder_id, file_path, file_name FROM images WHERE id = ?", (img_id,)).fetchone()
        if not image:
            errors.append(f"Image {img_id} not found")
            continue
        if not _folder_access(db, g.user, image['folder_id'], 'write'):
            errors.append(f"Permission denied for image {img_id}")
            continue

        old_path = os.path.normpath(image['file_path'])
        if os.path.normcase(os.path.dirname(old_path)) == os.path.normcase(target_path_base):
            errors.append(f"Image {img_id} is already in the target folder")
            continue

        new_path = os.path.normpath(os.path.join(target_path_base, image['file_name']))

        # If file already exists (on disk or in DB), add a suffix
        if _path_in_use(db, new_path):
            name, ext = os.path.splitext(image['file_name'])
            counter = 1
            while _path_in_use(db, new_path):
                new_path = os.path.normpath(os.path.join(target_path_base, f"{name}_{counter}{ext}"))
                counter += 1

        try:
            # Physical move
            if not os.path.exists(old_path):
                errors.append(f"File not found on disk: {old_path}")
                continue

            shutil.move(old_path, new_path)
            # Normalize path back for DB consistency (forward slashes)
            db_path = new_path.replace('\\', '/')

            # Update DB
            db.execute(
                "UPDATE images SET folder_id = ?, file_path = ?, file_name = ? WHERE id = ?",
                (target_folder_id, db_path, os.path.basename(new_path), img_id)
            )
            success_ids.append(img_id)
        except Exception as e:
            errors.append(f"Failed to move {image['file_name']}: {str(e)}")

    db.commit()
    return jsonify({
        'success': True,
        'moved': len(success_ids),
        'moved_ids': success_ids,
        'errors': errors
    })

@bp.route('/batch/delete', methods=['POST'])
@login_required
def batch_delete_images():
    if g.user['role'] == 'guest':
        return jsonify({'error': 'Guest users cannot delete images'}), 403
        
    data = request.json
    image_ids = data.get('image_ids', [])
    
    if not image_ids:
        return jsonify({'error': 'Missing image_ids'}), 400
        
    db = get_db()
    success_ids = []
    missing_ids = []
    thrashed_count = 0
    errors = []

    trash_dir = current_app.config.get('TRASH_DIR', os.path.join(current_app.root_path, '..', 'data', 'trash'))
    if not os.path.exists(trash_dir):
        os.makedirs(trash_dir)

    for img_id in image_ids:
        image = db.execute("SELECT * FROM images WHERE id = ?", (img_id,)).fetchone()
        if not image:
            errors.append(f"Image {img_id} not found")
            continue
        if not _folder_access(db, g.user, image['folder_id'], 'delete'):
            errors.append(f"Permission denied for image {img_id}")
            continue

        file_path = os.path.normpath(image['file_path'])
        thumbnails = db.execute("SELECT file_path FROM thumbnails WHERE image_id = ?", (img_id,)).fetchall()

        try:
            # Application-level trash
            if os.path.exists(file_path):
                # Use a UUID to avoid name collisions in trash
                trash_filename = f"{uuid.uuid4()}{os.path.splitext(image['file_name'])[1]}"
                trash_path = os.path.join(trash_dir, trash_filename)
                
                shutil.move(file_path, trash_path)
                
                # Collect metadata (favorites, tags)
                favorites = db.execute("SELECT user_id FROM user_favorites WHERE image_id = ?", (img_id,)).fetchall()
                tags = db.execute("SELECT tag_id FROM image_tags WHERE image_id = ?", (img_id,)).fetchall()
                
                # Convert datetime to string for JSON serialization
                modified_time = image['modified_time']
                if hasattr(modified_time, 'isoformat'):
                    modified_time = modified_time.isoformat()
                
                metadata = {
                    'folder_id': image['folder_id'],
                    'file_size': image['file_size'],
                    'modified_time': modified_time,
                    'width': image['width'],
                    'height': image['height'],
                    'format': image['format'],
                    'favorites': [f['user_id'] for f in favorites],
                    'tags': [t['tag_id'] for t in tags]
                }
                
                # Record in trash table
                db.execute(
                    "INSERT INTO trash (image_id, original_path, trash_path, file_name, user_id, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                    (img_id, file_path.replace('\\', '/'), trash_path.replace('\\', '/'), image['file_name'], g.user['id'], json.dumps(metadata))
                )
                thrashed_count += 1
            else:
                # Stale DB record: remove it, but do not report it as moved to trash.
                missing_ids.append(img_id)

            # Delete related thumbnails from disk (query already captured above)
            for thumb in thumbnails:
                thumb_path = os.path.normpath(thumb['file_path'])
                base_path = os.path.splitext(thumb_path)[0]
                for candidate in (base_path + '.webp', base_path + '.jpg'):
                    if os.path.exists(candidate):
                        try:
                            os.remove(candidate)
                        except Exception:
                            pass

            # Explicit cleanup: SQLite foreign_keys is not enabled in this app,
            # so ON DELETE CASCADE will not run automatically.
            db.execute("DELETE FROM user_favorites WHERE image_id = ?", (img_id,))
            db.execute("DELETE FROM image_tags WHERE image_id = ?", (img_id,))

            # Delete from DB (The cascade will handle thumbnails, tags, favorites)
            db.execute("DELETE FROM images WHERE id = ?", (img_id,))
            db.execute("DELETE FROM thumbnails WHERE image_id = ?", (img_id,))
            success_ids.append(img_id)
        except Exception as e:
            errors.append(f"Failed to delete {file_path}: {str(e)}")

    db.commit()
    return jsonify({
        'success': True,
        'deleted': len(success_ids),
        'deleted_ids': success_ids,
        'trashed': thrashed_count,
        'missing_ids': missing_ids,
        'errors': errors
    })

@bp.route('/trash/items', methods=['GET'])
@login_required
def get_trash_items():
    db = get_db()
    # Admins see all trash, users see only their own
    if g.user['role'] == 'admin':
        trash_items = db.execute("SELECT t.*, u.username FROM trash t JOIN users u ON t.user_id = u.id ORDER BY deleted_at DESC").fetchall()
    else:
        trash_items = db.execute("SELECT * FROM trash WHERE user_id = ? ORDER BY deleted_at DESC", (g.user['id'],)).fetchall()
        
    result = []
    for item in trash_items:
        d = dict(item)
        # Serialize datetime
        if d.get('deleted_at') and hasattr(d['deleted_at'], 'isoformat'):
            d['deleted_at'] = d['deleted_at'].isoformat()
            
        # Parse metadata to get width/height for waterfall layout
        if d.get('metadata'):
            try:
                meta = json.loads(d['metadata'])
                d['width'] = meta.get('width', 0)
                d['height'] = meta.get('height', 0)
            except:
                d['width'] = 0
                d['height'] = 0
        else:
            d['width'] = 0
            d['height'] = 0
        result.append(d)
        
    return jsonify(result)

@bp.route('/trash/<int:id>/thumbnail', methods=['GET'])
@login_required
def get_trash_thumbnail(id):
    db = get_db()
    trash_item = db.execute("SELECT * FROM trash WHERE id = ?", (id,)).fetchone()
    if not trash_item:
        abort(404)
        
    if g.user['role'] != 'admin' and trash_item['user_id'] != g.user['id']:
        abort(403)
        
    # Generate thumbnail from the file in trash
    size = request.args.get('size', 'medium')
    try:
        thumb_path = generate_thumbnail_from_path(trash_item['trash_path'], id, size)
        if not thumb_path:
            raise FileNotFoundError('thumbnail generation failed')
        return send_file(thumb_path, max_age=3600, conditional=True)
    except Exception as e:
        current_app.logger.error(f"Thumbnail generation failed for trash item {id}: {e}")
        # Fallback to original if thumbnail fails
        if os.path.exists(trash_item['trash_path']):
            return send_file(trash_item['trash_path'], max_age=3600, conditional=True)
        abort(404)

@bp.route('/trash/restore', methods=['POST'])
@login_required
def restore_trash_images():
    data = request.json
    trash_ids = data.get('trash_ids', [])
    
    if not trash_ids:
        return jsonify({'error': 'Missing trash_ids'}), 400
        
    db = get_db()
    restored_ids = []
    errors = []

    for t_id in trash_ids:
        trash_item = db.execute("SELECT * FROM trash WHERE id = ?", (t_id,)).fetchone()
        if not trash_item:
            errors.append(f"Trash item {t_id} not found")
            continue
            
        # Check permissions
        if g.user['role'] != 'admin' and trash_item['user_id'] != g.user['id']:
            errors.append(f"Permission denied for item {t_id}")
            continue

        metadata = json.loads(trash_item['metadata']) if trash_item['metadata'] else {}
        folder_id = metadata.get('folder_id')
        if folder_id and not db.execute("SELECT 1 FROM folders WHERE id = ?", (folder_id,)).fetchone():
            errors.append(f"Original folder no longer exists for item {t_id}")
            continue
        if not _folder_access(db, g.user, folder_id, 'write'):
            errors.append(f"Permission denied for original folder of item {t_id}")
            continue

        trash_path = os.path.normpath(trash_item['trash_path'])
        original_path = os.path.normpath(trash_item['original_path'])
        
        try:
            if os.path.exists(trash_path):
                # Ensure directory exists
                os.makedirs(os.path.dirname(original_path), exist_ok=True)
                
                # If the path is already occupied (disk or DB), find a new name
                if _path_in_use(db, original_path):
                    name, ext = os.path.splitext(trash_item['file_name'])
                    counter = 1
                    while _path_in_use(db, original_path):
                        original_path = os.path.normpath(os.path.join(os.path.dirname(original_path), f"{name}_{counter}{ext}"))
                        counter += 1
                
                shutil.move(trash_path, original_path)

                # Convert modified_time string back to datetime if possible
                mod_time = metadata.get('modified_time')
                if isinstance(mod_time, str):
                    try:
                        mod_time = datetime.fromisoformat(mod_time.replace(' ', 'T'))
                    except Exception:
                        mod_time = None
                if not mod_time:
                    mod_time = datetime.fromtimestamp(os.path.getmtime(original_path))

                file_size = metadata.get('file_size')
                if file_size is None:
                    file_size = os.path.getsize(original_path)

                # Re-insert into images table (works even if metadata was missing)
                cursor = db.execute(
                    "INSERT INTO images (file_path, file_name, file_size, modified_time, width, height, format, folder_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (original_path.replace('\\', '/'), os.path.basename(original_path),
                     file_size, mod_time,
                     metadata.get('width', 0) or 0, metadata.get('height', 0) or 0,
                     metadata.get('format') or os.path.splitext(original_path)[1].lstrip('.').lower(),
                     folder_id)
                )
                new_image_id = cursor.lastrowid

                # Restore favorites
                for user_id in metadata.get('favorites', []):
                    db.execute("INSERT OR IGNORE INTO user_favorites (user_id, image_id) VALUES (?, ?)", (user_id, new_image_id))
                    
                # Restore tags
                for tag_id in metadata.get('tags', []):
                    db.execute("INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)", (new_image_id, tag_id))

                db.execute("DELETE FROM trash WHERE id = ?", (t_id,))
                clear_trash_thumbnails(t_id)
                restored_ids.append(t_id)
            else:
                errors.append(f"Trash file not found: {trash_path}")
                db.execute("DELETE FROM trash WHERE id = ?", (t_id,)) # Clean up broken record
        except Exception as e:
            errors.append(f"Failed to restore {trash_item['file_name']}: {str(e)}")
            
    db.commit()
    return jsonify({
        'success': True,
        'restored': len(restored_ids),
        'restored_ids': restored_ids,
        'errors': errors
    })

@bp.route('/trash/clear', methods=['POST'])
@login_required
def clear_trash_images():
    data = request.json
    trash_ids = data.get('trash_ids', []) # If empty, clear all for user
    
    db = get_db()
    deleted_ids = []
    errors = []
    success_count = 0
    
    if trash_ids:
        items_to_delete = []
        for t_id in trash_ids:
            item = db.execute("SELECT * FROM trash WHERE id = ?", (t_id,)).fetchone()
            if item:
                if g.user['role'] == 'admin' or item['user_id'] == g.user['id']:
                    items_to_delete.append(item)
    else:
        if g.user['role'] == 'admin':
            items_to_delete = db.execute("SELECT * FROM trash").fetchall()
        else:
            items_to_delete = db.execute("SELECT * FROM trash WHERE user_id = ?", (g.user['id'],)).fetchall()
            
    for item in items_to_delete:
        trash_path = os.path.normpath(item['trash_path'])
        try:
            if os.path.exists(trash_path):
                os.remove(trash_path)
            db.execute("DELETE FROM trash WHERE id = ?", (item['id'],))
            clear_trash_thumbnails(item['id'])
            success_count += 1
            deleted_ids.append(item['id'])
        except Exception as e:
            errors.append(f"Failed to permanently delete {item['file_name']}: {str(e)}")
            
    db.commit()
    return jsonify({
        'success': True,
        'deleted': success_count,
        'deleted_ids': deleted_ids,
        'errors': errors
    })

@bp.route('', methods=['GET'])
def get_images():
    db = get_db()
    user = get_current_user()
    user_id = user['id'] if user else None
    
    # Pagination (cap page size to protect the server at 100k-image scale)
    page = max(request.args.get('page', 1, type=int), 1)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(max(per_page, 1), 200)
    offset = (page - 1) * per_page

    cursor_token = request.args.get('cursor', type=str)
    cursor = decode_cursor(cursor_token)
    if cursor_token and cursor is None:
        return jsonify({'error': 'Invalid cursor'}), 400
    
    # Filtering
    folder_id = request.args.get('folder_id', type=int)
    is_favorite = request.args.get('is_favorite', type=str)
    sort_by = request.args.get('sort_by', 'modified_time')
    sort_order = request.args.get('sort_order', 'DESC').upper()
    q = request.args.get('q', type=str)
    
    # Validate sort_by to prevent SQL injection
    allowed_sort_fields = ['modified_time', 'file_name', 'file_size']
    if sort_by not in allowed_sort_fields:
        sort_by = 'modified_time'
    
    # Validate sort_order
    if sort_order not in ['ASC', 'DESC']:
        sort_order = 'DESC'

    if cursor:
        if cursor.get('s') != sort_by or cursor.get('o') != sort_order:
            return jsonify({'error': 'Cursor does not match current sort'}), 400
        last_id = cursor.get('id')
        last_value = cursor.get('v')
        if not isinstance(last_id, int) or last_value is None:
            return jsonify({'error': 'Invalid cursor'}), 400
    
    # Base query with LEFT JOIN to get favorite status for the current user
    if user_id:
        query = """
            SELECT i.*, 
                   CASE WHEN uf.user_id IS NOT NULL THEN 1 ELSE 0 END as is_fav
            FROM images i
            LEFT JOIN user_favorites uf ON i.id = uf.image_id AND uf.user_id = ?
        """
        params = [user_id]
    else:
        query = "SELECT i.*, 0 as is_fav FROM images i"
        params = []
    
    conditions = []
    
    # Permission check: User must have access to the folder the image belongs to
    if not user or user['role'] != 'admin':
        # Non-admins can see their own folders, public folders and folders with read permission.
        user_id_val = user['id'] if user else -1
        conditions.append("""
            i.folder_id IN (
                SELECT id FROM folders WHERE user_id = ? OR is_public = 1
                UNION
                SELECT folder_id FROM permissions WHERE user_id = ?
                  AND permission_type IN ('read', 'write', 'delete', 'rename')
            )
        """)
        params.extend([user_id_val, user_id_val])

    if folder_id:
        conditions.append("i.folder_id = ?")
        params.append(folder_id)
        
    if is_favorite == 'true':
        # Anonymous users have no favorites; do not fall back to the full list.
        conditions.append("uf.user_id IS NOT NULL" if user_id else "1 = 0")
    elif is_favorite == 'false' and user_id:
        conditions.append("uf.user_id IS NULL")
        
    if q:
        term = q.strip()
        # FTS5 trigram supports substring search for 3+ characters; shorter terms fall back to LIKE.
        if term and current_app.config.get('FTS5_ENABLED') and len(term) >= 3:
            conditions.append("i.id IN (SELECT rowid FROM images_fts WHERE images_fts MATCH ?)")
            params.append('"' + term.replace('"', '""') + '"')
        else:
            conditions.append("i.file_name LIKE ?")
            params.append(f"%{q}%")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    # Count the full filtered set BEFORE applying the keyset boundary.
    count_sql = f"SELECT COUNT(*) FROM ({query})"
    total = db.execute(count_sql, params).fetchone()[0]

    # Keyset pagination avoids deep OFFSET scans at 100k scale.
    query_params = list(params)
    if cursor:
        operator = '<' if sort_order == 'DESC' else '>'
        keyset = f"(i.{sort_by} {operator} ? OR (i.{sort_by} = ? AND i.id {operator} ?))"
        query += (" AND " if conditions else " WHERE ") + keyset
        query_params.extend([last_value, last_value, last_id])

    query += f" ORDER BY i.{sort_by} {sort_order}, i.id {sort_order}"

    if cursor:
        query += " LIMIT ?"
        final_params = query_params + [per_page]
    else:
        query += " LIMIT ? OFFSET ?"
        final_params = query_params + [per_page, offset]

    images = db.execute(query, final_params).fetchall()

    next_cursor = None
    if images and len(images) == per_page:
        last = images[-1]
        next_cursor = encode_cursor({
            's': sort_by,
            'o': sort_order,
            'v': cursor_value(last, sort_by),
            'id': last['id']
        })
    
    # Process images to map is_fav to is_favorite
    result_data = []
    for img in images:
        img_dict = dict(img)
        # Serialize datetime
        if img_dict.get('modified_time') and hasattr(img_dict['modified_time'], 'isoformat'):
            img_dict['modified_time'] = img_dict['modified_time'].isoformat()
            
        # Map is_fav to is_favorite, defaulting to 0/False if not present
        img_dict['is_favorite'] = bool(img_dict.get('is_fav', 0))
        result_data.append(img_dict)
    
    return jsonify({
        'data': result_data,
        'total': total,
        'page': page,
        'per_page': per_page,
        'next_cursor': next_cursor
    })

@bp.route('/<int:id>', methods=['GET'])
def get_image(id):
    db = get_db()
    user = get_current_user()
    user_id = user['id'] if user else None
    
    if user_id:
        query = """
            SELECT i.*, 
                   CASE WHEN uf.user_id IS NOT NULL THEN 1 ELSE 0 END as is_fav
            FROM images i
            LEFT JOIN user_favorites uf ON i.id = uf.image_id AND uf.user_id = ?
            WHERE i.id = ?
        """
        image = db.execute(query, (user_id, id)).fetchone()
    else:
        image = db.execute("SELECT *, 0 as is_fav FROM images WHERE id = ?", (id,)).fetchone()
        
    if not image:
        return jsonify({'error': 'Image not found'}), 404
    if not _folder_access(db, user, image['folder_id'], 'read'):
        return jsonify({'error': 'Permission denied'}), 403
        
    img_dict = dict(image)
    # Serialize datetime
    if img_dict.get('modified_time') and hasattr(img_dict['modified_time'], 'isoformat'):
        img_dict['modified_time'] = img_dict['modified_time'].isoformat()
        
    img_dict['is_favorite'] = bool(img_dict.get('is_fav', 0))
    return jsonify(img_dict)

@bp.route('/<int:id>', methods=['PATCH'])
@login_required
def update_image(id):
    if g.user['role'] == 'guest':
        return jsonify({'error': 'Guest users cannot rename images'}), 403
        
    db = get_db()
    data = request.json
    
    image = db.execute("SELECT * FROM images WHERE id = ?", (id,)).fetchone()
    if not image:
        return jsonify({'error': 'Image not found'}), 404
    if not _folder_access(db, g.user, image['folder_id'], 'rename'):
        return jsonify({'error': 'Permission denied'}), 403
    if 'folder_id' in data:
        return jsonify({'error': 'Use /api/images/batch/move to change folders'}), 400
        
    fields = []
    params = []
    
    if 'file_name' in data:
        new_name = (data['file_name'] or '').strip()
        if not new_name or new_name in ('.', '..') or os.path.basename(new_name) != new_name:
            return jsonify({'error': 'Invalid file name'}), 400
        old_path = os.path.normpath(image['file_path'])
        folder_path = os.path.dirname(old_path)
        new_path = os.path.normpath(os.path.join(folder_path, new_name))
        
        # Check if new name already exists
        if os.path.exists(new_path) and old_path != new_path:
            return jsonify({'error': 'File with this name already exists'}), 400
            
        try:
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
                
                # Update DB fields
                fields.append("file_name = ?")
                params.append(new_name)
                fields.append("file_path = ?")
                params.append(new_path.replace('\\', '/'))
                fields.append("modified_time = ?")
                params.append(datetime.fromtimestamp(os.path.getmtime(new_path)))
            else:
                return jsonify({'error': 'File not found on disk'}), 404
        except Exception as e:
            return jsonify({'error': f"Failed to rename file: {str(e)}"}), 500
        
    if fields:
        params.append(id)
        query = f"UPDATE images SET {', '.join(fields)} WHERE id = ?"
        db.execute(query, params)
        db.commit()
        
    return jsonify({'success': True})

@bp.route('/<int:id>/thumbnail', methods=['GET'])
def get_image_thumbnail(id):
    size_type = request.args.get('size', 'small')
    thumb_path = generate_thumbnail(id, size_type)
    
    if thumb_path and os.path.exists(thumb_path):
        return send_file(thumb_path, max_age=86400, conditional=True)
    else:
        # Return a placeholder or 404
        return jsonify({'error': 'Thumbnail generation failed'}), 404

@bp.route('/<int:id>/raw', methods=['GET'])
def get_image_raw(id):
    db = get_db()
    image = db.execute("SELECT file_path FROM images WHERE id = ?", (id,)).fetchone()
    
    if not image:
        return jsonify({'error': 'Image not found'}), 404
        
    file_path = image['file_path']
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found on disk'}), 404
        
    return send_file(file_path, max_age=3600, conditional=True)

@bp.route('/<int:id>/download', methods=['GET'])
def download_image(id):
    db = get_db()
    image = db.execute("SELECT file_path, file_name FROM images WHERE id = ?", (id,)).fetchone()
    
    if not image:
        return jsonify({'error': 'Image not found'}), 404
        
    file_path = image['file_path']
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found on disk'}), 404
        
    return send_file(
        file_path,
        as_attachment=True,
        download_name=image['file_name'],
        max_age=3600,
        conditional=True
    )
