"""Remove orphaned thumbnail/poster cache files that the database no longer references.

Covers cache/{small,medium} (indexed media) and cache/trash/{small,medium}
(trash items). Only files named <id>.<jpg|webp> are considered, so custom
placeholders and uploads inside the cache directory are left alone.

Usage:
    python scripts/sql-script/prune_cache.py            # dry run (default)
    python scripts/sql-script/prune_cache.py --apply    # delete orphans
"""

import argparse
import os
import sys

# scripts/sql-script/prune_cache.py -> project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVER_DIR = os.path.join(PROJECT_ROOT, 'server')
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from app import create_app
from app.utils.db import get_db

CACHE_EXTENSIONS = ('.jpg', '.webp')


def _id_set(db, table):
    return {str(row[0]) for row in db.execute(f"SELECT id FROM {table}").fetchall()}


def _scan_directory(directory, valid_keys):
    orphans = []
    if not os.path.isdir(directory):
        return orphans

    for name in os.listdir(directory):
        stem, ext = os.path.splitext(name)
        if ext.lower() not in CACHE_EXTENSIONS:
            continue
        if not stem.isdigit() or stem in valid_keys:
            continue
        orphans.append(os.path.join(directory, name))
    return orphans


def main():
    parser = argparse.ArgumentParser(description='Delete cache files with no matching DB row.')
    parser.add_argument('--apply', action='store_true', help='Actually delete files (default is dry run)')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        db = get_db()
        cache_dir = app.config['CACHE_DIR']
        image_ids = _id_set(db, 'images')
        trash_ids = _id_set(db, 'trash')

        targets = [
            (os.path.join(cache_dir, 'small'), image_ids),
            (os.path.join(cache_dir, 'medium'), image_ids),
            (os.path.join(cache_dir, 'trash', 'small'), trash_ids),
            (os.path.join(cache_dir, 'trash', 'medium'), trash_ids),
        ]

        total = 0
        for directory, valid_keys in targets:
            orphans = _scan_directory(directory, valid_keys)
            total += len(orphans)
            print(f"{directory}: {len(orphans)} orphan file(s)")
            for path in orphans[:5]:
                print(f"  - {path}")
            if args.apply:
                for path in orphans:
                    try:
                        os.remove(path)
                    except OSError as e:
                        print(f"  failed to remove {path}: {e}")

        if args.apply:
            print(f"Removed {total} orphan file(s).")
        else:
            print(f"Dry run: {total} orphan file(s) found. Re-run with --apply to delete.")


if __name__ == '__main__':
    main()
