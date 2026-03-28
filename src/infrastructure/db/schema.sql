PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    parent_id INTEGER NULL REFERENCES folders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS wallpapers (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    extension TEXT,
    media_kind TEXT NOT NULL DEFAULT 'image' CHECK(media_kind IN ('image', 'video')),
    folder_id INTEGER NULL REFERENCES folders(id) ON DELETE SET NULL,
    width INTEGER,
    height INTEGER,
    orientation TEXT NOT NULL DEFAULT 'unknown',
    aspect_ratio REAL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    mtime REAL NOT NULL DEFAULT 0,
    ctime REAL NOT NULL DEFAULT 0,
    sha256 TEXT,
    is_favorite INTEGER NOT NULL DEFAULT 0,
    rating INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    added_at TEXT,
    indexed_at TEXT,
    last_viewed_at TEXT,
    times_viewed INTEGER NOT NULL DEFAULT 0,
    thumbnail_path TEXT,
    brightness REAL,
    avg_color TEXT,
    duration_seconds REAL
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS wallpaper_tags (
    wallpaper_id INTEGER NOT NULL REFERENCES wallpapers(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (wallpaper_id, tag_id)
);

CREATE TABLE IF NOT EXISTS operations_log (
    id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,
    wallpaper_id INTEGER NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wallpaper_provenance (
    wallpaper_id INTEGER PRIMARY KEY REFERENCES wallpapers(id) ON DELETE CASCADE,
    source_kind TEXT NOT NULL CHECK(source_kind IN ('local', 'wallhaven', 'manual_import', 'gowall_generated', 'derived_edit')),
    source_provider TEXT,
    remote_id TEXT,
    source_url TEXT,
    author_name TEXT,
    license_name TEXT,
    imported_at TEXT,
    generator_tool TEXT,
    parent_wallpaper_id INTEGER NULL REFERENCES wallpapers(id) ON DELETE SET NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS download_history (
    id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL,
    remote_id TEXT,
    source_url TEXT,
    destination_path TEXT,
    wallpaper_id INTEGER NULL REFERENCES wallpapers(id) ON DELETE SET NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wallpapers_folder_id ON wallpapers(folder_id);
CREATE INDEX IF NOT EXISTS idx_wallpapers_mtime ON wallpapers(mtime DESC);
CREATE INDEX IF NOT EXISTS idx_wallpapers_media_kind ON wallpapers(media_kind);
CREATE INDEX IF NOT EXISTS idx_wallpapers_size ON wallpapers(size_bytes DESC);
CREATE INDEX IF NOT EXISTS idx_wallpapers_favorite ON wallpapers(is_favorite);
CREATE INDEX IF NOT EXISTS idx_wallpapers_rating ON wallpapers(rating DESC);
CREATE INDEX IF NOT EXISTS idx_operations_created_at ON operations_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wallpaper_provenance_source_kind ON wallpaper_provenance(source_kind);
CREATE INDEX IF NOT EXISTS idx_wallpaper_provenance_remote ON wallpaper_provenance(source_provider, remote_id);
CREATE INDEX IF NOT EXISTS idx_download_history_created_at ON download_history(created_at DESC);
