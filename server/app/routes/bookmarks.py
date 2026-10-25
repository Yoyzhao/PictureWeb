from datetime import datetime

from flask import Blueprint, request, jsonify, g

from app.utils.db import get_db
from app.routes.auth import login_required
from app.routes.image import (
    ALLOWED_SORT_FIELDS,
    _image_access,
    fetch_image_window,
    parse_media_filter,
    serialize_image,
)

bp = Blueprint('bookmarks', __name__, url_prefix='/api/bookmarks')


def _normalize_context(data):
    try:
        folder_id = int(data.get('folder_id') or 0)
    except (TypeError, ValueError):
        folder_id = 0
    is_favorites = 1 if data.get('is_favorites') in (True, 1, '1', 'true') else 0
    search_query = (data.get('search_query') or '').strip()[:200]
    sort_by = data.get('sort_by') or 'modified_time'
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = 'modified_time'
    sort_order = (data.get('sort_order') or 'DESC').upper()
    if sort_order not in ('ASC', 'DESC'):
        sort_order = 'DESC'
    media_filter = parse_media_filter(data.get('media_filter'))
    if media_filter is False:
        media_filter = None
    return folder_id, is_favorites, search_query, sort_by, sort_order, media_filter or 'all'


def _anchor_snapshot(db, image_id):
    row = db.execute(
        "SELECT id, file_name, modified_time, file_size FROM images WHERE id = ?",
        (image_id,)
    ).fetchone()
    if not row:
        return None
    modified = row['modified_time']
    if hasattr(modified, 'strftime'):
        modified = modified.strftime('%Y-%m-%d %H:%M:%S.%f')
    elif modified:
        modified = str(modified)
    return {
        'id': row['id'],
        'file_name': row['file_name'],
        'modified_time': modified,
        'file_size': row['file_size'],
    }


def _validate_anchor(db, user, anchor_id, folder_id, is_favorites, media_filter='all'):
    image, allowed = _image_access(db, user, anchor_id, 'read')
    if not image:
        return 'Image not found', 404
    if not allowed:
        return 'Permission denied', 403
    if folder_id and image['folder_id'] != folder_id:
        return 'Image does not belong to the selected folder', 400
    if media_filter in ('image', 'video'):
        row = db.execute("SELECT media_type FROM images WHERE id = ?", (anchor_id,)).fetchone()
        if row and (row['media_type'] or 'image') != media_filter:
            return 'Image does not match the selected media filter', 400
    if is_favorites:
        favorite = db.execute(
            "SELECT 1 FROM user_favorites WHERE user_id = ? AND image_id = ?",
            (user['id'], anchor_id)
        ).fetchone()
        if not favorite:
            return 'Image is not in favorites', 400
    return None, None


def _bookmark_dict(row):
    data = dict(row)
    data['is_favorites'] = bool(data.get('is_favorites'))
    data['anchor_exists'] = bool(data.get('anchor_exists'))
    for key in ('created_at', 'updated_at'):
        value = data.get(key)
        if value is not None and hasattr(value, 'isoformat'):
            data[key] = value.isoformat()
    return data


def _fetch_bookmark_row(db, user_id, bookmark_id):
    return db.execute(
        """
        SELECT b.*, f.name AS folder_name, i.file_name AS image_file_name,
               i.media_type AS anchor_media_type, i.duration AS anchor_duration,
               (i.id IS NOT NULL) AS anchor_exists
        FROM image_bookmarks b
        LEFT JOIN folders f ON b.folder_id = f.id
        LEFT JOIN images i ON b.anchor_image_id = i.id
        WHERE b.id = ? AND b.user_id = ?
        """,
        (bookmark_id, user_id)
    ).fetchone()


@bp.route('', methods=['GET'])
@login_required
def list_bookmarks():
    db = get_db()
    rows = db.execute(
        """
        SELECT b.*, f.name AS folder_name, i.file_name AS image_file_name,
               i.media_type AS anchor_media_type, i.duration AS anchor_duration,
               (i.id IS NOT NULL) AS anchor_exists
        FROM image_bookmarks b
        LEFT JOIN folders f ON b.folder_id = f.id
        LEFT JOIN images i ON b.anchor_image_id = i.id
        WHERE b.user_id = ?
        ORDER BY CASE b.kind WHEN 'auto' THEN 0 ELSE 1 END, b.updated_at DESC, b.id DESC
        LIMIT 200
        """,
        (g.user['id'],)
    ).fetchall()
    return jsonify([_bookmark_dict(row) for row in rows])


@bp.route('', methods=['POST'])
@login_required
def create_bookmark():
    if g.user['role'] == 'guest':
        return jsonify({'error': 'Guest users cannot create bookmarks'}), 403

    db = get_db()
    data = request.get_json(silent=True) or {}
    try:
        anchor_id = int(data.get('anchor_image_id'))
    except (TypeError, ValueError):
        return jsonify({'error': 'anchor_image_id is required'}), 400

    folder_id, is_favorites, search_query, sort_by, sort_order, media_filter = _normalize_context(data)
    error, status = _validate_anchor(db, g.user, anchor_id, folder_id, is_favorites, media_filter)
    if error:
        return jsonify({'error': error}), status

    # The same image in the same view is one position; avoid duplicates from double clicks.
    existing = db.execute(
        """
        SELECT id FROM image_bookmarks
        WHERE user_id = ? AND kind = 'manual' AND folder_id = ? AND is_favorites = ?
          AND search_query = ? AND media_filter = ? AND anchor_image_id = ?
        """,
        (g.user['id'], folder_id, is_favorites, search_query, media_filter, anchor_id)
    ).fetchone()
    if existing:
        row = _fetch_bookmark_row(db, g.user['id'], existing['id'])
        return jsonify(_bookmark_dict(row)), 200

    snapshot = _anchor_snapshot(db, anchor_id)
    name = (data.get('name') or '').strip()[:100]
    if not name:
        folder = db.execute("SELECT name FROM folders WHERE id = ?", (folder_id,)).fetchone() if folder_id else None
        label = '收藏夹' if is_favorites else (folder['name'] if folder else '所有照片')
        if search_query:
            label += f' · {search_query}'
        name = f'{label} · {datetime.now().strftime("%Y-%m-%d %H:%M")}'

    cursor = db.execute(
        """
        INSERT INTO image_bookmarks
            (user_id, kind, name, folder_id, is_favorites, search_query, media_filter, sort_by, sort_order,
             anchor_image_id, anchor_modified_time, anchor_file_name, anchor_file_size)
        VALUES (?, 'manual', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (g.user['id'], name, folder_id, is_favorites, search_query, media_filter, sort_by, sort_order,
         anchor_id, snapshot['modified_time'], snapshot['file_name'], snapshot['file_size'])
    )
    db.commit()

    row = _fetch_bookmark_row(db, g.user['id'], cursor.lastrowid)
    return jsonify(_bookmark_dict(row)), 201


@bp.route('/auto', methods=['POST'])
@login_required
def save_auto_bookmark():
    """Upsert the automatic resume position for a view (folder/favorites/search)."""
    if g.user['role'] == 'guest':
        return jsonify({'error': 'Guest users cannot create bookmarks'}), 403

    db = get_db()
    data = request.get_json(silent=True) or {}
    try:
        anchor_id = int(data.get('anchor_image_id'))
    except (TypeError, ValueError):
        return jsonify({'error': 'anchor_image_id is required'}), 400

    folder_id, is_favorites, search_query, sort_by, sort_order, media_filter = _normalize_context(data)
    error, status = _validate_anchor(db, g.user, anchor_id, folder_id, is_favorites, media_filter)
    if error:
        return jsonify({'error': error}), status

    snapshot = _anchor_snapshot(db, anchor_id)
    # One automatic record per user: it always stores the most recent view context.
    existing = db.execute(
        "SELECT id FROM image_bookmarks WHERE user_id = ? AND kind = 'auto'",
        (g.user['id'],)
    ).fetchone()

    if existing:
        db.execute(
            """
            UPDATE image_bookmarks
            SET folder_id = ?, is_favorites = ?, search_query = ?, media_filter = ?,
                sort_by = ?, sort_order = ?, anchor_image_id = ?, anchor_modified_time = ?,
                anchor_file_name = ?, anchor_file_size = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (folder_id, is_favorites, search_query, media_filter, sort_by, sort_order,
             anchor_id, snapshot['modified_time'], snapshot['file_name'], snapshot['file_size'],
             existing['id'])
        )
        bookmark_id = existing['id']
    else:
        cursor = db.execute(
            """
            INSERT INTO image_bookmarks
                (user_id, kind, name, folder_id, is_favorites, search_query, media_filter, sort_by, sort_order,
                 anchor_image_id, anchor_modified_time, anchor_file_name, anchor_file_size)
            VALUES (?, 'auto', '上次浏览', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (g.user['id'], folder_id, is_favorites, search_query, media_filter, sort_by, sort_order,
             anchor_id, snapshot['modified_time'], snapshot['file_name'], snapshot['file_size'])
        )
        bookmark_id = cursor.lastrowid

    db.commit()
    return jsonify({'success': True, 'id': bookmark_id})


@bp.route('/<int:id>', methods=['PATCH'])
@login_required
def update_bookmark(id):
    db = get_db()
    row = db.execute(
        "SELECT id FROM image_bookmarks WHERE id = ? AND user_id = ?",
        (id, g.user['id'])
    ).fetchone()
    if not row:
        return jsonify({'error': 'Bookmark not found'}), 404

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()[:100]
    if not name:
        return jsonify({'error': 'name is required'}), 400

    db.execute(
        "UPDATE image_bookmarks SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (name, id)
    )
    db.commit()
    return jsonify(_bookmark_dict(_fetch_bookmark_row(db, g.user['id'], id)))


@bp.route('/<int:id>', methods=['DELETE'])
@login_required
def delete_bookmark(id):
    db = get_db()
    row = db.execute(
        "SELECT id FROM image_bookmarks WHERE id = ? AND user_id = ?",
        (id, g.user['id'])
    ).fetchone()
    if not row:
        return jsonify({'error': 'Bookmark not found'}), 404

    db.execute("DELETE FROM image_bookmarks WHERE id = ?", (id,))
    db.commit()
    return jsonify({'success': True})


@bp.route('/<int:id>/restore', methods=['GET'])
@login_required
def restore_bookmark(id):
    """Return the saved view context plus a keyset window around the anchor image."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM image_bookmarks WHERE id = ? AND user_id = ?",
        (id, g.user['id'])
    ).fetchone()
    if not row:
        return jsonify({'error': 'Bookmark not found'}), 404

    sort_by = row['sort_by'] if row['sort_by'] in ALLOWED_SORT_FIELDS else 'modified_time'
    sort_order = row['sort_order'] if row['sort_order'] in ('ASC', 'DESC') else 'DESC'
    if sort_by == 'modified_time':
        fallback_value = row['anchor_modified_time']
    elif sort_by == 'file_name':
        fallback_value = row['anchor_file_name']
    else:
        fallback_value = row['anchor_file_size']

    before = min(max(request.args.get('before', 40, type=int), 0), 100)
    after = min(max(request.args.get('after', 80, type=int), 1), 200)
    is_favorite = 'true' if row['is_favorites'] else None
    media_filter = row['media_filter'] if 'media_filter' in row.keys() else 'all'
    if media_filter not in ('image', 'video'):
        media_filter = None

    result = fetch_image_window(
        db, g.user, row['folder_id'] or None, is_favorite, row['search_query'],
        sort_by, sort_order, row['anchor_image_id'], fallback_value=fallback_value,
        before=before, after=after, media_type=media_filter
    )

    return jsonify({
        'context': {
            'folder_id': row['folder_id'],
            'is_favorites': bool(row['is_favorites']),
            'search_query': row['search_query'],
            'sort_by': sort_by,
            'sort_order': sort_order,
            'media_filter': media_filter or 'all',
        },
        'data': [serialize_image(item) for item in result['data']],
        'total': result['total'],
        'next_cursor': result['next_cursor'],
        'anchor': result['anchor'],
    })
