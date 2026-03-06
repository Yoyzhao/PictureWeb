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

    return g.db

def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

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
    
    # Check if admin user exists, if not create one
    # This is a basic check to ensure we have at least one user
    try:
        cur = db.execute("SELECT * FROM users WHERE username = ?", ('admin',))
        if cur.fetchone() is None:
            # Default password for admin: admin123 (In production, use hashed passwords!)
            # For simplicity in prototype, we store plain text or simple hash
            # Ideally use werkzeug.security.generate_password_hash
            from werkzeug.security import generate_password_hash
            db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ('admin', generate_password_hash('admin123'), 'admin')
            )
            
            # Create guest user if anonymous access is enabled
            if current_app.config.get('ANONYMOUS_ACCESS', True):
                db.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    ('guest', '', 'guest')
                )
                
            db.commit()
            print("Initialized database with default users.")
    except Exception as e:
        print(f"Error initializing default data: {e}")

def init_app(app):
    app.teardown_appcontext(close_db)
    
    # Add a CLI command to initialize the database
    @app.cli.command('init-db')
    def init_db_command():
        """Clear the existing data and create new tables."""
        init_db()
        print('Initialized the database.')
