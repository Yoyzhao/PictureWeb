import argparse
import os
import sys

# scripts/sql-script/prebuild_thumbnails.py -> project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVER_DIR = os.path.join(PROJECT_ROOT, 'server')
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from app import create_app
from app.services.thumbnail import prebuild_thumbnails


def main():
    parser = argparse.ArgumentParser(description='Pre-generate missing thumbnails for the local library.')
    parser.add_argument('--folder', type=int, default=None, help='Only prebuild one folder id')
    parser.add_argument('--limit', type=int, default=None, help='Maximum number of images to process')
    parser.add_argument('--size', choices=['small', 'medium'], default='small', help='Thumbnail size type')
    parser.add_argument('--rebuild', action='store_true', help='Regenerate existing thumbnails (format migration)')
    parser.add_argument('--media', choices=['image', 'video', 'all'], default='all',
                        help='Restrict to images, videos, or both (video posters need FFmpeg)')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        processed = prebuild_thumbnails(
            folder_id=args.folder,
            limit=args.limit,
            size_type=args.size,
            force=args.rebuild,
            media=None if args.media == 'all' else args.media
        )

    print(f"Thumbnail prebuild finished: {processed} media files attempted.")


if __name__ == '__main__':
    main()
