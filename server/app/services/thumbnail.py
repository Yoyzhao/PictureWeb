import os
import threading
import time
from PIL import Image
from flask import current_app
from app.utils.db import get_db

def get_thumbnail_path(image_id, size_type):
    """
    Get the path to the thumbnail file.
    """
    cache_dir = current_app.config['CACHE_DIR']
    # Create subdirectories based on image_id to avoid too many files in one folder
    # e.g. cache/small/00/01/123.jpg
    sub_dir = f"{image_id:08d}"
    # sub_dir = os.path.join(sub_dir[:2], sub_dir[2:4])
    
    # Simple structure for now: cache/size_type/image_id.jpg
    path = os.path.join(cache_dir, size_type, f"{image_id}.jpg")
    return path

def generate_thumbnail(image_id, size_type='small'):
    """
    Generate a thumbnail for the given image.
    size_type: 'small' (300px), 'medium' (800px)
    """
    db = get_db()
    image = db.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()
    
    if not image:
        return None
        
    file_path = image['file_path']
    if not os.path.exists(file_path):
        return None
        
    thumb_path = get_thumbnail_path(image_id, size_type)
    thumb_dir = os.path.dirname(thumb_path)
    
    if not os.path.exists(thumb_dir):
        os.makedirs(thumb_dir)
        
    # If already exists, return it (unless we want to force regenerate)
    if os.path.exists(thumb_path):
        return thumb_path
        
    try:
        with Image.open(file_path) as img:
            # Convert to RGB if necessary (e.g. for RGBA PNGs)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
                
            if size_type == 'small':
                size = (300, 300)
            elif size_type == 'medium':
                size = (800, 800)
            else:
                size = (300, 300)
                
            img.thumbnail(size)
            
            # Get quality setting and ensure it's an integer
            quality = current_app.config.get('THUMBNAIL_QUALITY', 80)
            try:
                quality = int(quality)
            except (ValueError, TypeError):
                quality = 80
                
            img.save(thumb_path, 'JPEG', quality=quality)
            
            # Record in DB
            try:
                db.execute(
                    "INSERT OR IGNORE INTO thumbnails (image_id, size_type, file_path) VALUES (?, ?, ?)",
                    (image_id, size_type, thumb_path)
                )
                db.commit()
            except Exception as e:
                print(f"Error saving thumbnail record: {e}")
                
            return thumb_path
    except Exception as e:
        print(f"Error generating thumbnail for {file_path}: {e}")
        return None


_prebuild_lock = threading.Lock()


def prebuild_thumbnails(folder_id=None, limit=None, size_type='small'):
    """
    Generate missing thumbnails sequentially, ordered by image id.
    Must be called inside a Flask app context. Returns the number of attempted images.
    """
    db = get_db()
    last_id = 0
    processed = 0

    while True:
        if limit is not None and processed >= limit:
            break

        batch_size = 100 if limit is None else min(100, limit - processed)
        params = [size_type, last_id]
        folder_clause = ''
        if folder_id is not None:
            folder_clause = ' AND i.folder_id = ?'
            params.append(folder_id)

        rows = db.execute(f"""
            SELECT i.id
            FROM images i
            LEFT JOIN thumbnails t ON t.image_id = i.id AND t.size_type = ?
            WHERE i.id > ? AND t.id IS NULL {folder_clause}
            ORDER BY i.id
            LIMIT ?
        """, params + [batch_size]).fetchall()

        if not rows:
            break

        for row in rows:
            generate_thumbnail(row['id'], size_type)
            processed += 1
            last_id = row['id']
            if processed % 100 == 0:
                print(f"Thumbnail prebuild progress: {processed}")

        # Yield briefly so request threads and scans are not starved.
        time.sleep(0.01)

    return processed


def start_folder_thumbnail_prebuild(app, folder_id):
    """Start one background prebuild worker; skip if another prebuild is running."""
    if not _prebuild_lock.acquire(blocking=False):
        print(f"Thumbnail prebuild already running; skipped folder {folder_id}")
        return False

    def runner():
        try:
            with app.app_context():
                processed = prebuild_thumbnails(folder_id=folder_id, size_type='small')
                print(f"Thumbnail prebuild finished for folder {folder_id}: {processed} images")
        except Exception as e:
            print(f"Thumbnail prebuild failed for folder {folder_id}: {e}")
        finally:
            _prebuild_lock.release()

    thread = threading.Thread(target=runner, daemon=True, name=f'thumb-prebuild-{folder_id}')
    thread.start()
    return True
