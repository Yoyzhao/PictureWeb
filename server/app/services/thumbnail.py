import os
import threading
import time
from PIL import Image
from flask import current_app
from app.utils.db import get_db
from app.services.video import (
    acquire_poster_slot,
    check_binaries,
    extract_poster_frame,
    is_video_file,
    mark_poster_failure,
    placeholder_poster,
    poster_failure_cached,
    probe_video,
    release_poster_slot,
    remove_file_quietly,
    try_acquire_poster_slot,
)

# Bound on-demand video poster attempts so a request thread never queues behind FFmpeg.
ON_DEMAND_POSTER_WAIT = 0.5
# Queued jobs give FFmpeg more room but still give up instead of piling up threads.
QUEUED_POSTER_WAIT = 10.0

_pending_poster_jobs = set()
_pending_poster_lock = threading.Lock()


def _normalize_size_type(size_type):
    """Whitelist thumbnail size names; also prevents path traversal via ?size=."""
    return size_type if size_type in ('small', 'medium') else 'small'


def _thumbnail_settings():
    """Return (quality, format, extension) from app config."""
    quality = current_app.config.get('THUMBNAIL_QUALITY', 80)
    try:
        quality = int(quality)
    except (ValueError, TypeError):
        quality = 80

    fmt = str(current_app.config.get('THUMBNAIL_FORMAT', 'webp')).lower()
    if fmt not in ('webp', 'jpeg', 'jpg'):
        fmt = 'webp'
    return quality, ('jpeg' if fmt in ('jpeg', 'jpg') else 'webp'), ('jpg' if fmt in ('jpeg', 'jpg') else 'webp')


def get_thumbnail_path(image_id, size_type, subdir=None, for_write=False):
    """
    Get the path to the thumbnail file.

    Prefer the configured format; when reading, fall back to the legacy .jpg
    cache so existing thumbnails are served without regeneration.
    """
    cache_dir = current_app.config['CACHE_DIR']
    folder = subdir or size_type
    _, _, ext = _thumbnail_settings()
    target = os.path.join(cache_dir, folder, f"{image_id}.{ext}")

    if for_write:
        return target

    if os.path.exists(target):
        return target

    legacy_ext = 'jpg' if ext == 'webp' else 'webp'
    legacy = os.path.join(cache_dir, folder, f"{image_id}.{legacy_ext}")
    if os.path.exists(legacy):
        return legacy

    return target


def _save_thumbnail(file_path, thumb_path, size_type):
    """Resize and save a thumbnail using the configured format."""
    quality, fmt, _ = _thumbnail_settings()

    thumb_dir = os.path.dirname(thumb_path)
    if not os.path.exists(thumb_dir):
        os.makedirs(thumb_dir)

    if size_type == 'small':
        size = (300, 300)
    elif size_type == 'medium':
        size = (800, 800)
    else:
        size = (300, 300)

    with Image.open(file_path) as img:
        # JPEG 可用 draft 在解码阶段降采样，避免为 300/800px 缩略图解码上亿像素大图。
        if img.format == 'JPEG' and size_type in ('small', 'medium'):
            try:
                img.draft('RGB', size)
            except Exception:
                pass

        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')

        img.thumbnail(size)

        if fmt == 'webp':
            img.save(thumb_path, 'WEBP', quality=quality, method=4)
        else:
            img.save(thumb_path, 'JPEG', quality=quality)

    return thumb_path


def _save_video_poster(source_path, thumb_path, size_type, duration):
    """Extract one frame with FFmpeg, then resize/save it through Pillow."""
    frame_path = extract_poster_frame(source_path, duration)
    if not frame_path:
        return None
    try:
        return _save_thumbnail(frame_path, thumb_path, size_type)
    finally:
        # Never leave temp frames behind, even when the save fails.
        remove_file_quietly(frame_path)


def _schedule_poster_job(app, image_id, size_type):
    """Queue one poster job per (image, size); dedupe repeated list requests."""
    key = (image_id, size_type)
    with _pending_poster_lock:
        if key in _pending_poster_jobs:
            return False
        _pending_poster_jobs.add(key)

    def runner():
        try:
            with app.app_context():
                generate_thumbnail(image_id, size_type, background=False, queued=True)
        except Exception as e:
            print(f"Background poster generation failed for image {image_id}: {e}")
        finally:
            with _pending_poster_lock:
                _pending_poster_jobs.discard(key)

    threading.Thread(target=runner, daemon=True, name=f'poster-{image_id}-{size_type}').start()
    return True


def _generate_video_thumbnail(image_id, source_path, duration, write_path, existing_path,
                              size_type, background, queued):
    """Poster for a video row; falls back to the shared placeholder image."""
    failure_key = (image_id, size_type)
    if poster_failure_cached(failure_key):
        return placeholder_poster()

    if not check_binaries()['ffmpeg']:
        mark_poster_failure(failure_key)
        return placeholder_poster()

    if background:
        acquired = acquire_poster_slot()
    elif queued:
        acquired = try_acquire_poster_slot(QUEUED_POSTER_WAIT)
    else:
        acquired = try_acquire_poster_slot(ON_DEMAND_POSTER_WAIT)

    if not acquired:
        # A request thread must never wait behind FFmpeg; hand the work to a background worker.
        if not background and not queued:
            _schedule_poster_job(current_app._get_current_object(), image_id, size_type)
        return placeholder_poster()

    try:
        saved = _save_video_poster(source_path, write_path, size_type, duration)
    except Exception as e:
        print(f"Error generating video poster for {source_path}: {e}")
        saved = None
    finally:
        release_poster_slot()

    if not saved:
        mark_poster_failure(failure_key)
        return placeholder_poster()

    if existing_path != write_path and os.path.exists(existing_path):
        remove_file_quietly(existing_path)

    try:
        db = get_db()
        db.execute(
            """
            INSERT INTO thumbnails (image_id, size_type, file_path) VALUES (?, ?, ?)
            ON CONFLICT(image_id, size_type) DO UPDATE SET file_path = excluded.file_path
            """,
            (image_id, size_type, saved)
        )
        db.commit()
    except Exception as e:
        print(f"Error saving video poster record: {e}")

    return saved


def generate_thumbnail(image_id, size_type='small', force=False, background=False, queued=False):
    """
    Generate a thumbnail for the given image or video poster.
    size_type: 'small' (300px), 'medium' (800px)
    force: regenerate even when a thumbnail already exists (format migration).
    background: block on the FFmpeg slot (prebuild worker).
    queued: background retry with a bounded wait; never spawns another job.
    Default (on-demand) returns the placeholder when the slot stays busy.
    """
    db = get_db()
    image = db.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()

    if not image:
        return None

    size_type = _normalize_size_type(size_type)
    file_path = image['file_path']
    if not os.path.exists(file_path):
        return None

    is_video = image['media_type'] == 'video' if 'media_type' in image.keys() else is_video_file(file_path)

    thumb_path = get_thumbnail_path(image_id, size_type)

    # If already exists, return it (unless we want to force regenerate)
    if os.path.exists(thumb_path) and not force:
        return thumb_path

    existing_path = thumb_path
    thumb_path = get_thumbnail_path(image_id, size_type, for_write=True)

    if is_video:
        return _generate_video_thumbnail(
            image_id, file_path, image['duration'] if 'duration' in image.keys() else None,
            thumb_path, existing_path, size_type, background, queued
        )

    try:
        _save_thumbnail(file_path, thumb_path, size_type)

        # Remove a legacy thumbnail with a different extension after migration.
        if existing_path != thumb_path and os.path.exists(existing_path):
            try:
                os.remove(existing_path)
            except OSError:
                pass

        # Record in DB (upsert keeps the path in sync when the format changes)
        try:
            db.execute(
                """
                INSERT INTO thumbnails (image_id, size_type, file_path) VALUES (?, ?, ?)
                ON CONFLICT(image_id, size_type) DO UPDATE SET file_path = excluded.file_path
                """,
                (image_id, size_type, thumb_path)
            )
            db.commit()
        except Exception as e:
            print(f"Error saving thumbnail record: {e}")

        return thumb_path
    except Exception as e:
        print(f"Error generating thumbnail for {file_path}: {e}")
        return None


def generate_thumbnail_from_path(source_path, cache_key, size_type='small'):
    """
    Generate a thumbnail for a file outside the images table (e.g. trash).
    Cache is written under cache/trash/<size_type>/<cache_key>.<ext> and is
    not recorded in the thumbnails table. Videos fall back to the shared
    placeholder instead of ever serving the video file itself.
    """
    if not os.path.exists(source_path):
        return None

    size_type = _normalize_size_type(size_type)
    subdir = os.path.join('trash', size_type)
    thumb_path = get_thumbnail_path(cache_key, size_type, subdir=subdir)

    if os.path.exists(thumb_path):
        return thumb_path

    thumb_path = get_thumbnail_path(cache_key, size_type, subdir=subdir, for_write=True)

    if is_video_file(source_path):
        failure_key = ('trash', cache_key, size_type)
        if poster_failure_cached(failure_key):
            return placeholder_poster()
        if not check_binaries()['ffmpeg']:
            mark_poster_failure(failure_key)
            return placeholder_poster()

        if not try_acquire_poster_slot(ON_DEMAND_POSTER_WAIT):
            return placeholder_poster()

        try:
            probed = probe_video(source_path)
            saved = _save_video_poster(source_path, thumb_path, size_type, probed.get('duration'))
        except Exception as e:
            print(f"Error generating trash poster for {source_path}: {e}")
            saved = None
        finally:
            release_poster_slot()

        if not saved:
            mark_poster_failure(failure_key)
            return placeholder_poster()
        return saved

    try:
        return _save_thumbnail(source_path, thumb_path, size_type)
    except Exception as e:
        print(f"Error generating trash thumbnail for {source_path}: {e}")
        return None


def clear_trash_thumbnails(cache_key):
    """Remove cached trash thumbnails in both current and legacy formats."""
    cache_dir = current_app.config['CACHE_DIR']
    for size_type in ('small', 'medium'):
        folder = os.path.join(cache_dir, 'trash', size_type)
        for ext in ('webp', 'jpg'):
            path = os.path.join(folder, f"{cache_key}.{ext}")
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


def clear_image_thumbnails(image_id):
    """Remove cached thumbnails for an image in all sizes and formats.

    Uses the cache key directly so records left by an older CACHE_DIR or file
    format do not keep orphan files on disk after the image row is deleted.
    """
    cache_dir = current_app.config['CACHE_DIR']
    for size_type in ('small', 'medium'):
        for ext in ('webp', 'jpg'):
            path = os.path.join(cache_dir, size_type, f"{image_id}.{ext}")
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


_prebuild_lock = threading.Lock()


def prebuild_thumbnails(folder_id=None, limit=None, size_type='small', force=False, media=None):
    """
    Generate missing thumbnails sequentially, ordered by image id.
    force=True regenerates existing thumbnails recorded in the DB
    (used for format migration, e.g. JPEG -> WebP).
    media: 'image' / 'video' narrows the rows; None covers both.
    Must be called inside a Flask app context. Returns the number of attempted images.
    """
    db = get_db()
    last_id = 0
    processed = 0
    media_clause = ' AND i.media_type = ?' if media else ''

    while True:
        if limit is not None and processed >= limit:
            break

        batch_size = 100 if limit is None else min(100, limit - processed)
        folder_clause = ' AND i.folder_id = ?' if folder_id is not None else ''

        if force:
            params = [size_type, last_id]
            if folder_id is not None:
                params.append(folder_id)
            if media:
                params.append(media)
            query = f"""
                SELECT t.id AS row_id, t.image_id AS image_id
                FROM thumbnails t
                JOIN images i ON i.id = t.image_id
                WHERE t.size_type = ? AND t.id > ? {folder_clause} {media_clause}
                ORDER BY t.id
                LIMIT ?
            """
        else:
            # 以当前 CACHE_DIR 的文件是否存在为准，而不是 thumbnails 表记录：
            # 历史记录的 file_path 可能指向旧缓存目录，按记录判断会漏生成。
            params = [last_id]
            if folder_id is not None:
                params.append(folder_id)
            if media:
                params.append(media)
            query = f"""
                SELECT i.id AS row_id, i.id AS image_id
                FROM images i
                WHERE i.id > ? {folder_clause} {media_clause}
                ORDER BY i.id
                LIMIT ?
            """

        rows = db.execute(query, params + [batch_size]).fetchall()

        if not rows:
            break

        for row in rows:
            image_id = row['image_id']
            if not force and os.path.exists(get_thumbnail_path(image_id, size_type)):
                processed += 1
                last_id = row['row_id']
                continue

            generate_thumbnail(image_id, size_type, force=force, background=True)
            processed += 1
            last_id = row['row_id']
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

                # Video posters run last, one FFmpeg slot at a time, and are optional.
                if current_app.config.get('VIDEO_THUMBNAIL_PREGENERATE', True) and check_binaries()['ffmpeg']:
                    videos = prebuild_thumbnails(folder_id=folder_id, size_type='small', media='video')
                    print(f"Video poster prebuild finished for folder {folder_id}: {videos} videos")
        except Exception as e:
            print(f"Thumbnail prebuild failed for folder {folder_id}: {e}")
        finally:
            _prebuild_lock.release()

    thread = threading.Thread(target=runner, daemon=True, name=f'thumb-prebuild-{folder_id}')
    thread.start()
    return True
