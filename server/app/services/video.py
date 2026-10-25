"""Video helpers: metadata probing, poster frames, placeholder and temp cleanup.

FFmpeg/ffprobe are external binaries. Everything here degrades gracefully when
they are missing: metadata stays empty and posters fall back to one shared image.
"""

import json
import os
import shutil
import subprocess
import threading
import time
import uuid

from flask import current_app

DEFAULT_VIDEO_EXTENSIONS = '.mp4,.m4v,.webm,.mov,.mkv,.avi,.wmv,.flv'

_PROBE_FAILURE_TTL = 600
_probe_failure_cache = {}
_probe_cache_lock = threading.Lock()

_POSTER_FAILURE_TTL = 600
_poster_failure_cache = {}
_poster_cache_lock = threading.Lock()

# FFmpeg poster extraction is CPU heavy per file; serialize it so scanning,
# prebuild and on-demand requests cannot stack up concurrent processes.
_poster_semaphore = threading.Semaphore(1)

_placeholder_lock = threading.Lock()

_SUBPROCESS_FLAGS = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}

_CONTAINER_ALIASES = {'m4v': 'mp4', 'm4a': 'mp4'}

VIDEO_MIME_TYPES = {
    '.mp4': 'video/mp4',
    '.m4v': 'video/mp4',
    '.webm': 'video/webm',
    '.mov': 'video/quicktime',
    '.mkv': 'video/x-matroska',
    '.avi': 'video/x-msvideo',
    '.wmv': 'video/x-ms-wmv',
    '.flv': 'video/x-flv',
}


def video_mimetype(path):
    """Explicit MIME for video containers; None when the extension is unknown."""
    return VIDEO_MIME_TYPES.get(os.path.splitext(path)[1].lower())


def is_placeholder_path(path):
    """True when the path points at the shared video placeholder."""
    if not path:
        return False
    placeholder_dir = os.path.join(current_app.config['CACHE_DIR'], 'placeholder')
    return os.path.normcase(os.path.abspath(path)).startswith(
        os.path.normcase(os.path.abspath(placeholder_dir))
    )


def video_extensions():
    raw = current_app.config.get('SCAN_VIDEO_EXTENSIONS', DEFAULT_VIDEO_EXTENSIONS)
    return {ext.strip().lower() for ext in str(raw).split(',') if ext.strip()}


def is_video_file(filename):
    return os.path.splitext(filename)[1].lower() in video_extensions()


def container_name(path):
    """Short container name from the file extension (avoids ffprobe's comma list)."""
    ext = os.path.splitext(path)[1].lstrip('.').lower()
    if not ext:
        return None
    return _CONTAINER_ALIASES.get(ext, ext)[:10]


def _binary_path(config_key, default):
    return str(current_app.config.get(config_key, default) or default)


def _binary_available(path):
    if os.path.isabs(path) or os.path.sep in path:
        return os.path.isfile(path)
    return shutil.which(path) is not None


def check_binaries():
    """Report whether the configured FFmpeg/ffprobe executables can be found."""
    ffmpeg = _binary_path('FFMPEG_PATH', 'ffmpeg')
    ffprobe = _binary_path('FFPROBE_PATH', 'ffprobe')
    return {
        'ffmpeg': _binary_available(ffmpeg),
        'ffprobe': _binary_available(ffprobe),
        'ffmpeg_path': ffmpeg,
        'ffprobe_path': ffprobe,
    }


def _config_timeout(key, default):
    try:
        return float(current_app.config.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _rotation_from_stream(stream):
    """Rotation in degrees, normalised to 0/90/180/270."""
    for item in stream.get('side_data_list') or []:
        if isinstance(item, dict) and 'rotation' in item:
            try:
                return abs(int(float(item['rotation']))) % 360
            except (TypeError, ValueError):
                return 0
    tags = stream.get('tags') or {}
    try:
        return abs(int(float(tags.get('rotate', 0)))) % 360
    except (TypeError, ValueError):
        return 0


def _positive_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def probe_video(path, timeout=None):
    """Return width/height/duration/codecs for a video; empty dict when probing fails."""
    if not os.path.exists(path):
        return {}

    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0
    cache_key = (os.path.normcase(os.path.normpath(path)), mtime)
    now = time.time()

    with _probe_cache_lock:
        failed_at = _probe_failure_cache.get(cache_key)
        if failed_at and now - failed_at < _PROBE_FAILURE_TTL:
            return {}

    ffprobe = _binary_path('FFPROBE_PATH', 'ffprobe')
    if not _binary_available(ffprobe):
        return {}

    timeout = timeout or _config_timeout('VIDEO_PROBE_TIMEOUT', 10)
    command = [
        ffprobe, '-v', 'error', '-print_format', 'json',
        '-show_format', '-show_streams', path,
    ]

    try:
        result = subprocess.run(
            command, capture_output=True, timeout=timeout,
            text=True, encoding='utf-8', errors='replace', **_SUBPROCESS_FLAGS
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"ffprobe failed for {path}: {e}")
        _remember_probe_failure(cache_key, now)
        return {}

    if result.returncode != 0:
        print(f"ffprobe exited with {result.returncode} for {path}: {(result.stderr or '').strip()[:200]}")
        _remember_probe_failure(cache_key, now)
        return {}

    try:
        payload = json.loads(result.stdout or '{}')
    except ValueError:
        _remember_probe_failure(cache_key, now)
        return {}

    streams = payload.get('streams') or []
    video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
    if not video_stream:
        _remember_probe_failure(cache_key, now)
        return {}
    audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)

    width = int(video_stream.get('width') or 0)
    height = int(video_stream.get('height') or 0)
    if _rotation_from_stream(video_stream) in (90, 270):
        width, height = height, width

    duration = _positive_float((payload.get('format') or {}).get('duration'))
    if duration is None:
        duration = _positive_float(video_stream.get('duration'))

    return {
        'width': width,
        'height': height,
        'duration': round(duration, 3) if duration is not None else None,
        'format': container_name(path),
        'video_codec': (video_stream.get('codec_name') or '')[:20] or None,
        'audio_codec': ((audio_stream or {}).get('codec_name') or '')[:20] or None,
    }


def _remember_probe_failure(cache_key, timestamp):
    with _probe_cache_lock:
        _probe_failure_cache[cache_key] = timestamp


def poster_time(duration):
    """Poster position: 10% into the video, capped at 10s, at least 0.5s."""
    try:
        duration = float(duration or 0)
    except (TypeError, ValueError):
        duration = 0
    if duration <= 0:
        return 0.0
    if duration < 1:
        return 0.0
    return min(max(duration * 0.1, 0.5), 10.0)


def temp_dir():
    path = os.path.join(current_app.config['CACHE_DIR'], 'tmp')
    os.makedirs(path, exist_ok=True)
    return path


def extract_poster_frame(source_path, duration, timeout=None):
    """Write one frame to a temp JPEG using fast seek. Returns the temp path or None.

    The caller owns the returned file and must delete it in a finally block.
    """
    if not os.path.exists(source_path):
        return None

    ffmpeg = _binary_path('FFMPEG_PATH', 'ffmpeg')
    if not _binary_available(ffmpeg):
        return None

    timeout = timeout or _config_timeout('VIDEO_THUMBNAIL_TIMEOUT', 20)
    target = os.path.join(temp_dir(), f"poster-{uuid.uuid4().hex}.jpg")

    # Try the calculated position first, then safer fallbacks for odd containers.
    attempts = []
    primary = poster_time(duration)
    for value in (primary, 1.0, 0.0):
        if value not in attempts:
            attempts.append(value)

    for seek in attempts:
        command = [
            ffmpeg, '-v', 'error', '-nostdin',
            '-ss', f"{seek:.3f}", '-i', source_path,
            '-frames:v', '1', '-an', '-sn', '-q:v', '2', '-y', target,
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, timeout=timeout,
                text=True, encoding='utf-8', errors='replace', **_SUBPROCESS_FLAGS
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            print(f"ffmpeg poster extract failed for {source_path} at {seek}s: {e}")
            continue

        if result.returncode == 0 and os.path.exists(target) and os.path.getsize(target) > 0:
            return target

        if os.path.exists(target):
            try:
                os.remove(target)
            except OSError:
                pass

    return None


def remove_file_quietly(path):
    if not path:
        return
    try:
        os.remove(path)
    except OSError:
        pass


def cleanup_video_temp(max_age_seconds=3600):
    """Remove leftover poster frames from cache/tmp (startup + maintenance)."""
    path = os.path.join(current_app.config['CACHE_DIR'], 'tmp')
    if not os.path.isdir(path):
        return 0

    now = time.time()
    removed = 0
    for name in os.listdir(path):
        if not name.startswith('poster-'):
            continue
        full = os.path.join(path, name)
        try:
            if now - os.path.getmtime(full) < max_age_seconds:
                continue
            os.remove(full)
            removed += 1
        except OSError:
            continue
    return removed


def placeholder_poster():
    """Single shared placeholder used when a poster cannot be generated."""
    path = os.path.join(current_app.config['CACHE_DIR'], 'placeholder', 'video.jpg')
    if os.path.exists(path):
        return path

    with _placeholder_lock:
        if os.path.exists(path):
            return path
        try:
            from PIL import Image, ImageDraw

            os.makedirs(os.path.dirname(path), exist_ok=True)
            width, height = 800, 450
            image = Image.new('RGB', (width, height), (24, 28, 36))
            draw = ImageDraw.Draw(image)
            centre_x, centre_y, radius = width / 2, height / 2, 56
            draw.polygon(
                [(centre_x - radius * 0.55, centre_y - radius),
                 (centre_x - radius * 0.55, centre_y + radius),
                 (centre_x + radius, centre_y)],
                fill=(140, 150, 168)
            )
            image.save(path, 'JPEG', quality=85)
            return path
        except Exception as e:
            print(f"Failed to create video placeholder: {e}")
            return None


def try_acquire_poster_slot(timeout=0.5):
    """Acquire the single poster slot without blocking a request thread."""
    return _poster_semaphore.acquire(timeout=timeout)


def acquire_poster_slot():
    """Blocking acquire for background prebuild paths. Returns True on success."""
    _poster_semaphore.acquire()
    return True


def release_poster_slot():
    try:
        _poster_semaphore.release()
    except ValueError:
        pass


def poster_failure_cached(key):
    with _poster_cache_lock:
        failed_at = _poster_failure_cache.get(key)
        if not failed_at:
            return False
        if time.time() - failed_at >= _POSTER_FAILURE_TTL:
            _poster_failure_cache.pop(key, None)
            return False
        return True


def mark_poster_failure(key):
    with _poster_cache_lock:
        _poster_failure_cache[key] = time.time()
