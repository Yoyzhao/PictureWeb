import os
from datetime import datetime
from PIL import Image
from flask import current_app
from app.utils.db import get_db
from app.services.thumbnail import clear_image_thumbnails, start_folder_thumbnail_prebuild
from app.services.video import container_name, is_video_file, probe_video

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}


def is_image_file(filename):
    extensions = current_app.config.get('SCAN_EXTENSIONS', '.jpg,.jpeg,.png,.gif,.bmp,.webp,.tiff').lower().split(',')
    ext = os.path.splitext(filename)[1].lower()
    return ext in extensions


def media_type_of(filename):
    """Return 'image', 'video' or None for files outside the configured extensions."""
    if is_image_file(filename):
        return 'image'
    if is_video_file(filename):
        return 'video'
    return None


def _file_key(path):
    """Case/separator-insensitive key so a rescan does not churn existing rows."""
    return os.path.normcase(os.path.normpath(path))


def _folder_exists(db, folder_id):
    return db.execute("SELECT 1 FROM folders WHERE id = ?", (folder_id,)).fetchone() is not None


def _remove_thumbnail_files(db, image_id):
    thumbnails = db.execute("SELECT file_path FROM thumbnails WHERE image_id = ?", (image_id,)).fetchall()
    for thumb in thumbnails:
        if thumb['file_path'] and os.path.exists(thumb['file_path']):
            try:
                os.remove(thumb['file_path'])
            except OSError:
                pass
    clear_image_thumbnails(image_id)


def _remove_stale_images(db, folder_id, scanned_keys):
    """
    Delete index rows that the current walk did not find.

    Comparing against the walked set (instead of checking file existence) also
    reconciles a changed folder path or a recursive/non-recursive switch, where
    stale rows may still point at files that exist outside the current scan.
    """
    removed = 0
    rows = db.execute("SELECT id, file_path FROM images WHERE folder_id = ?", (folder_id,)).fetchall()

    for image in rows:
        if _file_key(image['file_path']) in scanned_keys:
            continue

        image_id = image['id']
        _remove_thumbnail_files(db, image_id)
        # foreign_keys is disabled, so dependents must be removed explicitly.
        db.execute("DELETE FROM user_favorites WHERE image_id = ?", (image_id,))
        db.execute("DELETE FROM image_tags WHERE image_id = ?", (image_id,))
        db.execute("DELETE FROM thumbnails WHERE image_id = ?", (image_id,))
        db.execute("DELETE FROM images WHERE id = ?", (image_id,))
        removed += 1

    return removed


def scan_folder(folder_path, folder_id):
    """
    Scan a folder and add images to the database.
    Supports recursive scanning based on configuration.
    """
    db = get_db()

    # 1. Update status to 'scanning'; abort if the folder was removed before the thread ran.
    cursor = db.execute(
        "UPDATE folders SET scan_status = 'scanning', scan_total = 0, scan_processed = 0, scan_error = NULL WHERE id = ?",
        (folder_id,)
    )
    db.commit()
    if cursor.rowcount == 0:
        print(f"Scan aborted: folder {folder_id} no longer exists")
        return {'processed': 0, 'removed': 0, 'total_current': 0}

    count = 0
    removed_count = 0
    recursive = current_app.config.get('SCAN_RECURSIVE', True)
    scanned_keys = set()

    try:
        print(f"Scanning folder: {folder_path} (ID: {folder_id}), Recursive: {recursive}")

        # 2. Pre-count files for progress bar
        media_files = []
        if recursive:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if media_type_of(file):
                        media_files.append((root, file))
                        scanned_keys.add(_file_key(os.path.join(root, file)))
        else:
            try:
                files = os.listdir(folder_path)
                for file in files:
                    file_path = os.path.join(folder_path, file)
                    if os.path.isfile(file_path) and media_type_of(file):
                        media_files.append((folder_path, file))
                        scanned_keys.add(_file_key(file_path))
            except Exception as e:
                print(f"Error listing directory {folder_path}: {e}")

        total_files = len(media_files)
        db.execute("UPDATE folders SET scan_total = ? WHERE id = ?", (total_files, folder_id))
        db.commit()

        # 3. Process files and update progress
        for i, (root, file) in enumerate(media_files):
            if not _folder_exists(db, folder_id):
                print(f"Scan aborted: folder {folder_id} was deleted while scanning")
                return {'processed': count, 'removed': 0, 'total_current': 0}

            count += process_file(db, root, file, folder_id)

            # Update progress every 10 files or at the end
            if (i + 1) % 10 == 0 or (i + 1) == total_files:
                db.execute("UPDATE folders SET scan_processed = ? WHERE id = ?", (i + 1, folder_id))
                db.commit()

        # --- Cleanup Step ---
        removed_count = _remove_stale_images(db, folder_id, scanned_keys)

        # 4. Final update
        db.execute("UPDATE folders SET scan_status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (folder_id,))
        db.commit()

        print(f"Scan complete. Processed {count} media files. Removed {removed_count} missing files.")

        # Generate missing small thumbnails in the background so first browsing is not thumbnail-bound.
        if current_app.config.get('THUMBNAIL_PREGENERATE', True):
            start_folder_thumbnail_prebuild(current_app._get_current_object(), folder_id)

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
    """Process a single image/video file and add or update its row. Returns 1 if indexed."""
    media_type = media_type_of(file)
    if not media_type:
        return 0

    file_path = os.path.join(root, file)
    # Normalize path separators to forward slashes for consistency
    file_path = file_path.replace('\\', '/')

    try:
        # Check if the file already exists
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
                metadata = _read_metadata(file_path, media_type)

                db.execute(
                    """
                    UPDATE images
                    SET file_size = ?, modified_time = ?, width = ?, height = ?, format = ?,
                        media_type = ?, duration = ?, video_codec = ?, audio_codec = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (file_size, modified_time, metadata['width'], metadata['height'],
                     metadata['format'], media_type, metadata['duration'],
                     metadata['video_codec'], metadata['audio_codec'], existing['id'])
                )
                # A changed video needs a fresh poster frame; drop the cached cover.
                if media_type == 'video':
                    _remove_thumbnail_files(db, existing['id'])
                return 1
        else:
            # Insert new media row
            metadata = _read_metadata(file_path, media_type)

            db.execute(
                """
                INSERT INTO images (file_path, file_name, file_size, modified_time, width, height,
                                    format, media_type, duration, video_codec, audio_codec, folder_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (file_path, file, file_size, modified_time, metadata['width'], metadata['height'],
                 metadata['format'], media_type, metadata['duration'],
                 metadata['video_codec'], metadata['audio_codec'], folder_id)
            )
            return 1

    except Exception as e:
        print(f"Error processing file {file_path}: {e}")

    return 0


def _read_metadata(file_path, media_type):
    """Return the media columns shared by images and videos."""
    if media_type == 'video':
        probed = probe_video(file_path)
        return {
            'width': probed.get('width') or 0,
            'height': probed.get('height') or 0,
            'format': probed.get('format') or container_name(file_path) or 'UNKNOWN',
            'duration': probed.get('duration'),
            'video_codec': probed.get('video_codec'),
            'audio_codec': probed.get('audio_codec'),
        }

    try:
        with Image.open(file_path) as img:
            width, height = img.size
            fmt = img.format
    except Exception as e:
        print(f"Error reading image {file_path}: {e}")
        width, height = 0, 0
        fmt = 'UNKNOWN'

    return {
        'width': width,
        'height': height,
        'format': fmt,
        'duration': None,
        'video_codec': None,
        'audio_codec': None,
    }
