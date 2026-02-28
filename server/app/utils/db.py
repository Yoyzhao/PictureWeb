import sqlite3
import os
from flask import current_app, g

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

def init_db():
    db = get_db()
    
    # Read schema.sql from models directory
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'schema.sql')
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        db.executescript(f.read())
    
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
