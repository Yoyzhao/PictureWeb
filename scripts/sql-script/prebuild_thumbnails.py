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
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        processed = prebuild_thumbnails(
            folder_id=args.folder,
            limit=args.limit,
            size_type=args.size
        )

    print(f"Thumbnail prebuild finished: {processed} images attempted.")


if __name__ == '__main__':
    main()
