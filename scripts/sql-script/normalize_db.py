import os
import sqlite3
import yaml

# scripts/sql-script/normalize_db.py -> project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
config_path = os.path.join(PROJECT_ROOT, 'config.yaml')
db_path = os.path.join(PROJECT_ROOT, 'data', 'db', 'database.db')

if os.path.exists(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        db_path = config.get('DB_PATH', db_path)

if not os.path.isabs(db_path):
    db_path = os.path.abspath(os.path.join(PROJECT_ROOT, db_path))

print(f"Normalizing database at: {db_path}")
db = sqlite3.connect(db_path)

tables = ['images', 'folders', 'users', 'trash', 'user_favorites', 'tags', 'image_tags', 'thumbnails', 'permissions']
for table in tables:
    try:
        # Check columns for this table
        cursor = db.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        
        timestamp_cols = [c for c in columns if any(x in c for x in ['time', 'at'])]
        for col in timestamp_cols:
            print(f"Normalizing {table}.{col}...")
            # REPLACE 'T' with ' ' for all values that contain 'T'
            db.execute(f"UPDATE {table} SET {col} = REPLACE({col}, 'T', ' ') WHERE {col} LIKE '%T%'")
    except Exception as e:
        print(f"Skipping table {table}: {e}")

db.commit()
db.close()
print("Normalization complete.")
