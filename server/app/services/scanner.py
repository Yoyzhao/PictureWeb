import os
import time
from datetime import datetime
from PIL import Image
from flask import current_app
from app.utils.db import get_db

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}

def is_image_file(filename):
    extensions = current_app.config.get('SCAN_EXTENSIONS', '.jpg,.jpeg,.png,.gif,.bmp,.webp,.tiff').lower().split(',')
    ext = os.path.splitext(filename)[1].lower()
    return ext in extensions

def scan_folder(folder_path, folder_id):
    """
    Scan a folder and add images to the database.
    Supports recursive scanning based on configuration.
    """
    db = get_db()
    count = 0
    recursive = current_app.config.get('SCAN_RECURSIVE', True)
    
    print(f"Scanning folder: {folder_path} (ID: {folder_id}), Recursive: {recursive}")
    
    if recursive:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                count += process_file(db, root, file, folder_id)
    else:
        # Only scan the top-level directory
        try:
            files = os.listdir(folder_path)
            for file in files:
                file_path = os.path.join(folder_path, file)
                if os.path.isfile(file_path):
                    count += process_file(db, folder_path, file, folder_id)
        except Exception as e:
            print(f"Error listing directory {folder_path}: {e}")
            
    # --- Cleanup Step ---
    # Find all images currently in DB for this folder
    cur = db.execute("SELECT id, file_path FROM images WHERE folder_id = ?", (folder_id,))
    db_images = cur.fetchall()
    
    removed_count = 0
    for img in db_images:
        # Check if file still exists on disk
        if not os.path.exists(os.path.normpath(img['file_path'])):
            # Remove from DB
            db.execute("DELETE FROM images WHERE id = ?", (img['id'],))
            # Also remove associated thumbnails
            db.execute("DELETE FROM thumbnails WHERE image_id = ?", (img['id'],))
            removed_count += 1
            
    db.commit()
    print(f"Scan complete. Processed {count} images. Removed {removed_count} missing images.")
    return {
        'processed': count,
        'removed': removed_count,
        'total_current': db.execute("SELECT COUNT(*) FROM images WHERE folder_id = ?", (folder_id,)).fetchone()[0]
    }

def process_file(db, root, file, folder_id):
    """Process a single file and add/update in database. Returns 1 if processed, 0 otherwise."""
    if not is_image_file(file):
        return 0
        
    file_path = os.path.join(root, file)
    # Normalize path separators to forward slashes for consistency
    file_path = file_path.replace('\\', '/')
    
    try:
        # Check if image already exists
        cur = db.execute("SELECT id, modified_time FROM images WHERE file_path = ?", (file_path,))
        existing = cur.fetchone()
        
        stat = os.stat(file_path)
        # Convert timestamp to datetime object
        modified_time = datetime.fromtimestamp(stat.st_mtime)
        file_size = stat.st_size
        
        if existing:
            # Update if modified
            existing_mtime = existing['modified_time']
            
            # Compare timestamps
            if existing_mtime != modified_time:
                # Get image dimensions
                try:
                    with Image.open(file_path) as img:
                        width, height = img.size
                        fmt = img.format
                except Exception:
                    width, height = 0, 0
                    fmt = 'UNKNOWN'
                
                db.execute(
                    """
                    UPDATE images 
                    SET file_size = ?, modified_time = ?, width = ?, height = ?, format = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (file_size, modified_time, width, height, fmt, existing['id'])
                )
                return 1
        else:
            # Insert new image
            try:
                with Image.open(file_path) as img:
                    width, height = img.size
                    fmt = img.format
            except Exception as e:
                print(f"Error reading image {file_path}: {e}")
                width, height = 0, 0
                fmt = 'UNKNOWN'
            
            db.execute(
                """
                INSERT INTO images (file_path, file_name, file_size, modified_time, width, height, format, folder_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (file_path, file, file_size, modified_time, width, height, fmt, folder_id)
            )
            return 1
            
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        
    return 0
