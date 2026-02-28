from flask import Blueprint, request, jsonify, send_file, abort
from app.utils.db import get_db
from app.services.thumbnail import generate_thumbnail
import os
import shutil
from send2trash import send2trash

bp = Blueprint('image', __name__, url_prefix='/api/images')

@bp.route('/batch/move', methods=['POST'])
def batch_move_images():
    data = request.json
    image_ids = data.get('image_ids', [])
    target_folder_id = data.get('target_folder_id')
    
    if not image_ids or not target_folder_id:
        return jsonify({'error': 'Missing parameters'}), 400
        
    db = get_db()
    target_folder = db.execute("SELECT path FROM folders WHERE id = ?", (target_folder_id,)).fetchone()
    if not target_folder:
        return jsonify({'error': 'Target folder not found'}), 404
        
    target_path_base = target_folder['path']
    success_count = 0
    errors = []
    
    for img_id in image_ids:
        image = db.execute("SELECT file_path, file_name FROM images WHERE id = ?", (img_id,)).fetchone()
        if not image:
            errors.append(f"Image {img_id} not found")
            continue
            
        old_path = os.path.normpath(image['file_path'])
        new_path = os.path.normpath(os.path.join(target_path_base, image['file_name']))
        
        # If file already exists in target, add a suffix
        if os.path.exists(new_path):
            name, ext = os.path.splitext(image['file_name'])
            counter = 1
            while os.path.exists(new_path):
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
            success_count += 1
        except Exception as e:
            errors.append(f"Failed to move {image['file_name']}: {str(e)}")
            
    db.commit()
    return jsonify({
        'success': True, 
        'moved': success_count, 
        'errors': errors
    })

@bp.route('/batch/delete', methods=['POST'])
def batch_delete_images():
    data = request.json
    image_ids = data.get('image_ids', [])
    
    if not image_ids:
        return jsonify({'error': 'Missing image_ids'}), 400
        
    db = get_db()
    success_count = 0
    errors = []
    
    for img_id in image_ids:
        image = db.execute("SELECT file_path FROM images WHERE id = ?", (img_id,)).fetchone()
        if not image:
            errors.append(f"Image {img_id} not found")
            continue
            
        file_path = os.path.normpath(image['file_path'])
        
        try:
            # Move to trash
            if os.path.exists(file_path):
                send2trash(file_path)
            else:
                errors.append(f"File not found on disk: {file_path}")
            
            # Delete from DB
            db.execute("DELETE FROM images WHERE id = ?", (img_id,))
            
            # Delete related thumbnails from disk and DB
            thumbnails = db.execute("SELECT file_path FROM thumbnails WHERE image_id = ?", (img_id,)).fetchall()
            for thumb in thumbnails:
                thumb_path = os.path.normpath(thumb['file_path'])
                if os.path.exists(thumb_path):
                    try:
                        os.remove(thumb_path)
                    except:
                        pass
            db.execute("DELETE FROM thumbnails WHERE image_id = ?", (img_id,))
            
            success_count += 1
        except Exception as e:
            errors.append(f"Failed to delete {file_path}: {str(e)}")
            
    db.commit()
    return jsonify({
        'success': True, 
        'deleted': success_count, 
        'errors': errors
    })

@bp.route('', methods=['GET'])
def get_images():
    db = get_db()
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    offset = (page - 1) * per_page
    
    # Filtering
    folder_id = request.args.get('folder_id', type=int)
    is_favorite = request.args.get('is_favorite', type=str)
    sort_by = request.args.get('sort_by', 'modified_time')
    sort_order = request.args.get('sort_order', 'DESC')
    q = request.args.get('q', type=str)
    
    # Validate sort_by to prevent SQL injection
    allowed_sort_fields = ['modified_time', 'file_name', 'file_size']
    if sort_by not in allowed_sort_fields:
        sort_by = 'modified_time'
    
    # Validate sort_order
    if sort_order.upper() not in ['ASC', 'DESC']:
        sort_order = 'DESC'
    
    query = "SELECT * FROM images"
    conditions = []
    params = []
    
    if folder_id:
        conditions.append("folder_id = ?")
        params.append(folder_id)
        
    if is_favorite == 'true':
        conditions.append("is_favorite = 1")
    elif is_favorite == 'false':
        conditions.append("is_favorite = 0")
        
    if q:
        conditions.append("file_name LIKE ?")
        search_term = f"%{q}%"
        params.append(search_term)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    # Count total
    count_query = f"SELECT COUNT(*) FROM ({query})"
    total = db.execute(count_query, params).fetchone()[0]
    
    # Sorting
    query += f" ORDER BY {sort_by} {sort_order}"
    
    # Pagination
    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    
    images = db.execute(query, params).fetchall()
    
    return jsonify({
        'data': [dict(img) for img in images],
        'total': total,
        'page': page,
        'per_page': per_page
    })

@bp.route('/<int:id>', methods=['GET'])
def get_image(id):
    db = get_db()
    image = db.execute("SELECT * FROM images WHERE id = ?", (id,)).fetchone()
    if not image:
        return jsonify({'error': 'Image not found'}), 404
    return jsonify(dict(image))

@bp.route('/<int:id>', methods=['PATCH'])
def update_image(id):
    db = get_db()
    data = request.json
    
    if 'is_favorite' in data:
        db.execute("UPDATE images SET is_favorite = ? WHERE id = ?", (1 if data['is_favorite'] else 0, id))
        db.commit()
        
    return jsonify({'success': True})

@bp.route('/<int:id>/thumbnail', methods=['GET'])
def get_image_thumbnail(id):
    size_type = request.args.get('size', 'small')
    thumb_path = generate_thumbnail(id, size_type)
    
    if thumb_path and os.path.exists(thumb_path):
        return send_file(thumb_path)
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
        
    return send_file(file_path)

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
        download_name=image['file_name']
    )
