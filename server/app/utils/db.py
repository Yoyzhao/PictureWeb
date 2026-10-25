import sqlite3
import os
import datetime
from flask import current_app, g

# --- Custom Timestamp Converter to handle ISO formats with 'T' ---
def convert_timestamp_iso(val):
    if not val:
        return None
    try:
        s = val.decode('utf-8')
        # Handle both space and T as separator
        return datetime.datetime.fromisoformat(s.replace(' ', 'T'))
    except Exception:
        return None

# Register the converter for TIMESTAMP and DATETIME
sqlite3.register_converter("TIMESTAMP", convert_timestamp_iso)
sqlite3.register_converter("DATETIME", convert_timestamp_iso)

def get_db():
    if 'db' not in g:
        db_path = current_app.config['DB_PATH']
        # Ensure the directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

        # Read-friendly defaults for a local library; WAL improves concurrent read/write behavior.
        try:
            g.db.execute("PRAGMA journal_mode=WAL")
            g.db.execute("PRAGMA synchronous=NORMAL")
            g.db.execute("PRAGMA cache_size=-20000")
            g.db.execute("PRAGMA temp_store=MEMORY")
        except sqlite3.DatabaseError:
            pass

    return g.db

def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

def ensure_fts(db):
    """Create the trigram FTS5 index and keep it in sync with the images table."""
    try:
        db.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS images_fts USING fts5(
                file_name,
                content='images',
                content_rowid='id',
                tokenize='trigram'
            );

            CREATE TRIGGER IF NOT EXISTS images_fts_ai AFTER INSERT ON images BEGIN
                INSERT INTO images_fts(rowid, file_name) VALUES (new.id, new.file_name);
            END;

            CREATE TRIGGER IF NOT EXISTS images_fts_ad AFTER DELETE ON images BEGIN
                INSERT INTO images_fts(images_fts, rowid, file_name)
                VALUES ('delete', old.id, old.file_name);
            END;

            CREATE TRIGGER IF NOT EXISTS images_fts_au AFTER UPDATE OF file_name ON images BEGIN
                INSERT INTO images_fts(images_fts, rowid, file_name)
                VALUES ('delete', old.id, old.file_name);
                INSERT INTO images_fts(rowid, file_name) VALUES (new.id, new.file_name);
            END;
        """)

        # External-content FTS tables report the content table row count, so inspect docsize
        # to detect an index that has not been populated yet.
        fts_count = db.execute("SELECT COUNT(*) FROM images_fts_docsize").fetchone()[0]
        image_count = db.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        if fts_count != image_count:
            print(f"Rebuilding FTS index ({image_count} rows, indexed {fts_count})...")
            db.execute("INSERT INTO images_fts(images_fts) VALUES('rebuild')")

        db.commit()
        current_app.config['FTS5_ENABLED'] = True
    except Exception as e:
        # Older SQLite builds may not include FTS5; search falls back to LIKE.
        current_app.config['FTS5_ENABLED'] = False
        print(f"FTS5 unavailable, falling back to LIKE search: {e}")


def rebuild_fts():
    """Force a full rebuild of the search index (maintenance/CLI use)."""
    db = get_db()
    try:
        db.execute("INSERT INTO images_fts(images_fts) VALUES('rebuild')")
        db.commit()
        return True
    except Exception as e:
        print(f"FTS rebuild failed: {e}")
        return False


def migrate_db(db):
    """
    Check and perform database migrations.
    This ensures that existing databases get updated with new columns/tables.
    """
    try:
        # 1. 检查并创建 trash 表（如果完全不存在）
        db.execute("""
            CREATE TABLE IF NOT EXISTS trash (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER,
                original_path TEXT NOT NULL,
                trash_path TEXT NOT NULL,
                file_name VARCHAR(255) NOT NULL,
                user_id INTEGER NOT NULL,
                metadata TEXT,
                deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # 2. 检查并补全 metadata 字段（如果表存在但字段缺失）
        cursor = db.execute("PRAGMA table_info(trash)")
        columns = [row['name'] for row in cursor.fetchall()]
        
        if columns and 'metadata' not in columns:
            print("Migrating database: Adding 'metadata' column to 'trash' table...")
            db.execute("ALTER TABLE trash ADD COLUMN metadata TEXT")
            db.commit()
            print("Migration successful.")

        # 3. Supporting indexes for folder sorting/search-heavy queries at 100k scale.
        db.executescript("""
            CREATE INDEX IF NOT EXISTS idx_images_folder_modified ON images(folder_id, modified_time);
            CREATE INDEX IF NOT EXISTS idx_images_file_name ON images(file_name);
            CREATE INDEX IF NOT EXISTS idx_images_file_size ON images(file_size);
            CREATE INDEX IF NOT EXISTS idx_folders_public ON folders(is_public);
        """)

        # 3.1 Viewing-position bookmarks. CREATE IF NOT EXISTS keeps existing libraries compatible.
        db.executescript("""
            CREATE TABLE IF NOT EXISTS image_bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                kind VARCHAR(10) NOT NULL DEFAULT 'manual' CHECK (kind IN ('manual', 'auto')),
                name VARCHAR(100) NOT NULL,
                folder_id INTEGER NOT NULL DEFAULT 0,
                is_favorites INTEGER NOT NULL DEFAULT 0,
                search_query TEXT NOT NULL DEFAULT '',
                media_filter VARCHAR(10) NOT NULL DEFAULT 'all',
                sort_by VARCHAR(20) NOT NULL DEFAULT 'modified_time',
                sort_order VARCHAR(4) NOT NULL DEFAULT 'DESC',
                anchor_image_id INTEGER NOT NULL,
                anchor_modified_time TEXT,
                anchor_file_name TEXT,
                anchor_file_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_image_bookmarks_user ON image_bookmarks(user_id, kind, updated_at);
        """)

        # 3.2 Media model (M4): videos share the images table, existing rows stay images.
        image_columns = [row['name'] for row in db.execute("PRAGMA table_info(images)").fetchall()]
        for column, definition in (
            ('media_type', "VARCHAR(10) NOT NULL DEFAULT 'image'"),
            ('duration', 'REAL'),
            ('video_codec', 'VARCHAR(20)'),
            ('audio_codec', 'VARCHAR(20)'),
        ):
            if column not in image_columns:
                print(f"Migrating database: Adding '{column}' column to 'images' table...")
                db.execute(f"ALTER TABLE images ADD COLUMN {column} {definition}")

        bookmark_columns = [row['name'] for row in db.execute("PRAGMA table_info(image_bookmarks)").fetchall()]
        if 'media_filter' not in bookmark_columns:
            print("Migrating database: Adding 'media_filter' column to 'image_bookmarks' table...")
            db.execute("ALTER TABLE image_bookmarks ADD COLUMN media_filter VARCHAR(10) NOT NULL DEFAULT 'all'")

        # The automatic resume position is global per user: one row that always
        # carries the latest view context. Old databases may hold one row per
        # (folder, favorites, search, media) combination, so consolidate first.
        db.execute("DROP INDEX IF EXISTS idx_image_bookmarks_auto")
        db.execute("""
            DELETE FROM image_bookmarks
            WHERE kind = 'auto' AND id NOT IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY user_id ORDER BY updated_at DESC, id DESC
                    ) AS rn
                    FROM image_bookmarks
                    WHERE kind = 'auto'
                ) WHERE rn = 1
            )
        """)
        db.executescript("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_image_bookmarks_auto
                ON image_bookmarks(user_id)
                WHERE kind = 'auto';
            CREATE INDEX IF NOT EXISTS idx_images_media_type ON images(media_type);
        """)

        # Scan workers live in memory threads. After a restart no worker can finish,
        # so leaving the status busy would block rescan and folder deletion forever.
        db.execute("""
            UPDATE folders
            SET scan_status = 'failed',
                scan_error = '上次扫描被服务重启中断，请重新扫描'
            WHERE scan_status IN ('pending', 'scanning')
        """)
        db.commit()

        # 4. Full-text index for filename search (falls back to LIKE if unavailable).
        ensure_fts(db)

    except Exception as e:
        print(f"Migration error: {e}")

def init_db():
    db = get_db()
    
    # Read schema.sql from models directory
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'schema.sql')
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        db.executescript(f.read())
    
    # Run migrations for existing database
    migrate_db(db)
    
    # Check if admin user exists, if not create one from .env values.
    try:
        admin_username = (current_app.config.get('DEFAULT_ADMIN_USERNAME') or '').strip()
        admin_password = current_app.config.get('DEFAULT_ADMIN_PASSWORD') or ''

        if admin_username and admin_password:
            cur = db.execute("SELECT 1 FROM users WHERE username = ?", (admin_username,))
            if cur.fetchone() is None:
                from werkzeug.security import generate_password_hash
                db.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    (admin_username, generate_password_hash(admin_password), 'admin')
                )
                print(f"Initialized default admin user: {admin_username}")
        else:
            print("DEFAULT_ADMIN_USERNAME/DEFAULT_ADMIN_PASSWORD not configured; skipped default admin creation.")

        # Guest is a system account for anonymous read access; create it independently.
        if current_app.config.get('ANONYMOUS_ACCESS', True):
            cur = db.execute("SELECT 1 FROM users WHERE username = 'guest'")
            if cur.fetchone() is None:
                db.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    ('guest', '', 'guest')
                )
                print("Initialized guest user.")

        db.commit()
    except Exception as e:
        print(f"Error initializing default data: {e}")


def reset_admin_password():
    """Sync the configured admin password from .env into the database."""
    db = get_db()
    username = (current_app.config.get('DEFAULT_ADMIN_USERNAME') or '').strip()
    password = current_app.config.get('DEFAULT_ADMIN_PASSWORD') or ''

    if not username or not password:
        raise RuntimeError(
            'DEFAULT_ADMIN_USERNAME and DEFAULT_ADMIN_PASSWORD must be set in .env before resetting the admin password.'
        )

    from werkzeug.security import generate_password_hash
    password_hash = generate_password_hash(password)
    user = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()

    if user:
        db.execute(
            "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (password_hash, user['id'])
        )
    else:
        db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, 'admin')
        )

    db.commit()
    return username

def init_app(app):
    app.teardown_appcontext(close_db)
    
    # Add a CLI command to initialize the database
    @app.cli.command('init-db')
    def init_db_command():
        """Clear the existing data and create new tables."""
        init_db()
        print('Initialized the database.')
