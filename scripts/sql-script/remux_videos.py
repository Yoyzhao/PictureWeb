"""Losslessly remux browser-unsupported video containers to MP4 (no re-encode).

Only H.264 video with AAC/MP3 audio is handled: ``ffmpeg -c copy`` rewraps the
streams, so quality is unchanged and a 6.4GB FLV finishes in well under a minute.
HEVC/AV1 or incompatible audio needs a real transcode and is intentionally skipped.

Usage:
    python scripts/sql-script/remux_videos.py                 # dry run (default)
    python scripts/sql-script/remux_videos.py --apply         # write MP4 next to the source
    python scripts/sql-script/remux_videos.py --apply --output-dir D:/Converted
    python scripts/sql-script/remux_videos.py --apply --replace --yes   # delete source after verify
"""

import argparse
import json
import os
import subprocess
import sys
import time

# scripts/sql-script/remux_videos.py -> project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVER_DIR = os.path.join(PROJECT_ROOT, 'server')
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from app import create_app
from app.utils.db import get_db

# Containers that browsers generally cannot play directly.
UNSUPPORTED_CONTAINERS = {'flv', 'mkv', 'avi', 'wmv', 'mov'}
# MP4 streams that can be copied without re-encoding and remain browser-friendly.
MP4_VIDEO_CODECS = {'h264'}
MP4_AUDIO_CODECS = {'aac', 'mp3', '', None}

SUBPROCESS_FLAGS = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}


def _run(command, timeout):
    return subprocess.run(
        command, capture_output=True, timeout=timeout,
        text=True, encoding='utf-8', errors='replace', **SUBPROCESS_FLAGS
    )


def _binary(config_key, default):
    return str(config_value(config_key) or default)


def config_value(key):
    from flask import current_app
    return current_app.config.get(key)


def probe_video_codec(ffprobe, path, timeout=20):
    result = _run([
        ffprobe, '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=codec_name', '-of', 'json', path,
    ], timeout)
    if result.returncode != 0:
        return None
    try:
        streams = json.loads(result.stdout or '{}').get('streams') or []
    except ValueError:
        return None
    return (streams[0].get('codec_name') or '').lower() if streams else None


def target_path(row, output_dir, taken):
    stem = os.path.splitext(row['file_name'])[0]
    folder = output_dir or os.path.dirname(row['file_path'])
    candidate = os.path.join(folder, f"{stem}.mp4")
    counter = 1
    while os.path.exists(candidate) or os.path.normcase(candidate) in taken:
        candidate = os.path.join(folder, f"{stem}_{counter}.mp4")
        counter += 1
    return candidate


def remux(ffmpeg, source, target, timeout):
    command = [
        ffmpeg, '-v', 'error', '-nostdin', '-i', source,
        '-map', '0:v:0', '-map', '0:a?', '-c', 'copy',
        '-movflags', '+faststart', '-n', target,
    ]
    result = _run(command, timeout)
    if result.returncode != 0:
        message = (result.stderr or '').strip().splitlines()
        return False, message[-1] if message else f'exit {result.returncode}'
    return True, ''


def main():
    parser = argparse.ArgumentParser(description='Losslessly remux unsupported video containers to MP4.')
    parser.add_argument('--apply', action='store_true', help='Actually write MP4 files (default is dry run)')
    parser.add_argument('--folder', type=int, default=None, help='Only process one folder id')
    parser.add_argument('--limit', type=int, default=None, help='Maximum number of eligible files to process')
    parser.add_argument('--output-dir', default=None, help='Write MP4 here instead of next to the source')
    parser.add_argument('--replace', action='store_true', help='Delete the source file after the MP4 verifies')
    parser.add_argument('--yes', action='store_true', help='Required together with --replace')
    parser.add_argument('--timeout', type=int, default=1800, help='Per-file ffmpeg timeout in seconds')
    args = parser.parse_args()

    if args.replace and not args.apply:
        parser.error('--replace requires --apply')
    if args.replace and not args.yes:
        parser.error('--replace deletes source files; pass --yes to confirm')
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    app = create_app()
    with app.app_context():
        ffmpeg = _binary('FFMPEG_PATH', 'ffmpeg')
        ffprobe = _binary('FFPROBE_PATH', 'ffprobe')
        db = get_db()

        query = "SELECT id, file_name, file_path, format, video_codec, audio_codec, file_size FROM images WHERE media_type = 'video'"
        params = []
        if args.folder is not None:
            query += ' AND folder_id = ?'
            params.append(args.folder)
        rows = db.execute(query + ' ORDER BY id', params).fetchall()

        eligible = []
        skipped = []
        for row in rows:
            container = (row['format'] or '').lower()
            video_codec = (row['video_codec'] or '').lower()
            audio_codec = (row['audio_codec'] or '').lower() or None
            if container not in UNSUPPORTED_CONTAINERS:
                continue
            if video_codec not in MP4_VIDEO_CODECS:
                skipped.append((row, f"视频编码 {video_codec or '未知'} 需真转码"))
                continue
            if audio_codec not in MP4_AUDIO_CODECS:
                skipped.append((row, f"音轨 {audio_codec} 不兼容 MP4"))
                continue
            if not os.path.exists(row['file_path']):
                skipped.append((row, '源文件不存在'))
                continue
            eligible.append(row)

        if args.limit:
            eligible = eligible[:args.limit]

        print(f"candidates: {len(eligible)} | skipped: {len(skipped)} | apply: {args.apply}")
        for row, reason in skipped:
            print(f"  [skip] {row['file_name']} -> {reason}")

        total_bytes = 0
        done = 0
        failed = 0
        started_all = time.time()
        taken = set()

        for row in eligible:
            source = row['file_path']
            target = target_path(row, args.output_dir, taken)
            taken.add(os.path.normcase(target))
            print(f"  [remux] {source}")
            print(f"          -> {target}")

            if not args.apply:
                total_bytes += row['file_size'] or 0
                continue

            started = time.time()
            ok, message = remux(ffmpeg, source, target, args.timeout)
            elapsed = time.time() - started
            if not ok:
                print(f"          FAILED in {elapsed:.1f}s: {message}")
                failed += 1
                if os.path.exists(target):
                    try:
                        os.remove(target)
                    except OSError:
                        pass
                continue

            codec = probe_video_codec(ffprobe, target)
            if codec != 'h264':
                print(f"          VERIFY FAILED: video codec={codec or 'unknown'}")
                failed += 1
                try:
                    os.remove(target)
                except OSError:
                    pass
                continue

            size = os.path.getsize(target)
            total_bytes += size
            done += 1
            print(f"          OK in {elapsed:.1f}s, {size / (1024 * 1024):.1f} MB")

            if args.replace:
                try:
                    os.remove(source)
                    print('          source removed')
                except OSError as e:
                    print(f"          source removal failed: {e}")

        elapsed_all = time.time() - started_all
        print('---')
        print(f"processed: {done} | failed: {failed} | output: {total_bytes / (1024 ** 3):.2f} GB | {elapsed_all:.1f}s")
        if not args.apply:
            print('Dry run: nothing written. Re-run with --apply to remux.')
        else:
            print('Rescan the affected folders so the new MP4 files are indexed.')
            if args.replace:
                print('--replace was used: rescan also removes stale rows for deleted sources.')


if __name__ == '__main__':
    main()
