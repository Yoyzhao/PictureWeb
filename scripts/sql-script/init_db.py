import os
import sys

# scripts/sql-script/init_db.py -> project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVER_DIR = os.path.join(PROJECT_ROOT, 'server')
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from app import create_app
from app.utils.db import init_db, reset_admin_password, rebuild_fts


def main():
    reset = '--reset-admin-password' in sys.argv[1:]
    rebuild_search = '--rebuild-search-index' in sys.argv[1:]
    app = create_app()
    with app.app_context():
        init_db()
        if reset:
            username = reset_admin_password()
            print(f"Admin password reset from .env for user: {username}")
        if rebuild_search:
            ok = rebuild_fts()
            print("Search index rebuilt." if ok else "Search index rebuild failed (FTS5 unavailable).")
    print("Database initialized successfully.")


if __name__ == '__main__':
    main()
