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
    
    # 1. Update status to 'scanning'
    db.execute(
        "UPDATE folders SET scan_status = 'scanning', scan_total = 0, scan_processed = 0, scan_error = NULL WHERE id = ?", 
        (folder_id,)
    )
    db.commit()
    
    count = 0
    removed_count = 0
    recursive = current_app.config.get('SCAN_RECURSIVE', True)
    
    try:
        print(f"Scanning folder: {folder_path} (ID: {folder_id}), Recursive: {recursive}")
        
        # 2. Pre-count files for progress bar
        image_files = []
        if recursive:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if is_image_file(file):
                        image_files.append((root, file))
        else:
            try:
                files = os.listdir(folder_path)
                for file in files:
                    file_path = os.path.join(folder_path, file)
                    if os.path.isfile(file_path) and is_image_file(file):
                        image_files.append((folder_path, file))
            except Exception as e:
                print(f"Error listing directory {folder_path}: {e}")
        
        total_files = len(image_files)
        db.execute("UPDATE folders SET scan_total = ? WHERE id = ?", (total_files, folder_id))
        db.commit()
        
        # 3. Process files and update progress
        for i, (root, file) in enumerate(image_files):
            count += process_file(db, root, file, folder_id)
            
            # Update progress every 10 files or at the end
            if (i + 1) % 10 == 0 or (i + 1) == total_files:
                db.execute("UPDATE folders SET scan_processed = ? WHERE id = ?", (i + 1, folder_id))
                db.commit()
                
        # --- Cleanup Step ---
        # Find all images currently in DB for this folder
        cur = db.execute("SELECT id, file_path FROM images WHERE folder_id = ?", (folder_id,))
        db_images = cur.fetchall()
        
        for img in db_images:
            # Check if file still exists on disk
            if not os.path.exists(os.path.normpath(img['file_path'])):
                # Remove from DB
                db.execute("DELETE FROM images WHERE id = ?", (img['id'],))
                # Also remove associated thumbnails
                db.execute("DELETE FROM thumbnails WHERE image_id = ?", (img['id'],))
                removed_count += 1
        
        # 4. Final update
        db.execute("UPDATE folders SET scan_status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (folder_id,))
        db.commit()
        
        print(f"Scan complete. Processed {count} images. Removed {removed_count} missing images.")
        
        return {
            'processed': count,
            'removed': removed_count,
            'total_current': db.execute("SELECT COUNT(*) FROM images WHERE folder_id = ?", (folder_id,)).fetchone()[0]
        }
        
    except Exception as e:
        db.execute("UPDATE folders SET scan_status = 'failed', scan_error = ? WHERE id = ?", (str(e), folder_id))
        db.commit()
        raise e

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
