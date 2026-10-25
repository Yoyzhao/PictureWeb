-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('admin', 'user', 'guest')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Folders table
CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    user_id INTEGER,
    is_public BOOLEAN DEFAULT FALSE,
    scan_status VARCHAR(20) DEFAULT 'none' CHECK (scan_status IN ('none', 'pending', 'scanning', 'completed', 'failed')),
    scan_total INTEGER DEFAULT 0,
    scan_processed INTEGER DEFAULT 0,
    scan_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_folders_path ON folders(path);
CREATE INDEX IF NOT EXISTS idx_folders_user_id ON folders(user_id);
CREATE INDEX IF NOT EXISTS idx_folders_public ON folders(is_public);

-- Images table (also stores videos; media_type distinguishes them)
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size INTEGER,
    modified_time TIMESTAMP,
    width INTEGER,
    height INTEGER,
    format VARCHAR(10),
    media_type VARCHAR(10) NOT NULL DEFAULT 'image',
    duration REAL,
    video_codec VARCHAR(20),
    audio_codec VARCHAR(20),
    folder_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (folder_id) REFERENCES folders(id)
);

CREATE INDEX IF NOT EXISTS idx_images_file_path ON images(file_path);
CREATE INDEX IF NOT EXISTS idx_images_folder_id ON images(folder_id);
CREATE INDEX IF NOT EXISTS idx_images_modified_time ON images(modified_time);
CREATE INDEX IF NOT EXISTS idx_images_folder_modified ON images(folder_id, modified_time);
CREATE INDEX IF NOT EXISTS idx_images_file_name ON images(file_name);
CREATE INDEX IF NOT EXISTS idx_images_file_size ON images(file_size);
-- idx_images_media_type is created in migrate_db() after old databases gain the column.

-- User Favorites table
CREATE TABLE IF NOT EXISTS user_favorites (
    user_id INTEGER NOT NULL,
    image_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, image_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_favorites_user_id ON user_favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_user_favorites_image_id ON user_favorites(image_id);

-- Tags table
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Image Tags relation table
CREATE TABLE IF NOT EXISTS image_tags (
    image_id INTEGER,
    tag_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (image_id, tag_id),
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- Thumbnails table
CREATE TABLE IF NOT EXISTS thumbnails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL,
    size_type VARCHAR(20) NOT NULL,
    file_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    UNIQUE(image_id, size_type)
);

CREATE INDEX IF NOT EXISTS idx_thumbnails_image_id ON thumbnails(image_id);

-- Permissions table
CREATE TABLE IF NOT EXISTS permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    folder_id INTEGER NOT NULL,
    permission_type VARCHAR(20) NOT NULL CHECK (permission_type IN ('read', 'write', 'delete', 'rename')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE,
    UNIQUE(user_id, folder_id, permission_type)
);

-- Viewing-position bookmarks (anchor image + view context)
CREATE TABLE IF NOT EXISTS image_bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    kind VARCHAR(10) NOT NULL DEFAULT 'manual' CHECK (kind IN ('manual', 'auto')),
    name VARCHAR(100) NOT NULL,
    folder_id INTEGER NOT NULL DEFAULT 0,       -- 0 = all accessible photos
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
-- idx_image_bookmarks_auto is created in migrate_db() after old databases gain media_filter.

-- Trash table
CREATE TABLE IF NOT EXISTS trash (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER,
    original_path TEXT NOT NULL,
    trash_path TEXT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    user_id INTEGER NOT NULL,
    metadata TEXT, -- JSON stored metadata (favorites, tags, etc.)
    deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_trash_user_id ON trash(user_id);
CREATE INDEX IF NOT EXISTS idx_trash_deleted_at ON trash(deleted_at);
