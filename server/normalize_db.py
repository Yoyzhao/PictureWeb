import sqlite3
import os
import yaml

# Read config to get DB_PATH
config_path = 'config.yaml'
db_path = 'data/picgallery.db' # default
if os.path.exists(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        db_path = config.get('DB_PATH', db_path)

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
