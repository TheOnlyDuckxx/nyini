from __future__ import annotations

from pathlib import Path
import sqlite3


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def initialize_database(connection: sqlite3.Connection, schema_path: Path | None = None) -> None:
    if schema_path is None:
        schema_path = Path(__file__).with_name("schema.sql")
    _ensure_migrations_table(connection)
    _apply_migrations(connection, schema_path)
    connection.commit()


def _ensure_migrations_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _apply_migrations(connection: sqlite3.Connection, schema_path: Path) -> None:
    applied_versions = {
        int(row["version"])
        for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version ASC").fetchall()
    }

    migrations: list[tuple[int, callable]] = [
        (1, lambda conn: conn.executescript(schema_path.read_text(encoding="utf-8"))),
        (2, _migration_add_image_analysis_columns),
        (3, _migration_add_provenance_and_download_history),
        (4, _migration_add_video_support),
    ]

    for version, migration in migrations:
        if version in applied_versions:
            continue
        migration(connection)
        connection.execute("INSERT INTO schema_migrations(version) VALUES(?)", (version,))


def _migration_add_image_analysis_columns(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(wallpapers)").fetchall()
    }
    for column_name, column_type in {
        "brightness": "REAL",
        "avg_color": "TEXT",
    }.items():
        if column_name in existing_columns:
            continue
        connection.execute(f"ALTER TABLE wallpapers ADD COLUMN {column_name} {column_type}")


def _migration_add_provenance_and_download_history(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
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
        CREATE INDEX IF NOT EXISTS idx_wallpaper_provenance_source_kind ON wallpaper_provenance(source_kind);
        CREATE INDEX IF NOT EXISTS idx_wallpaper_provenance_remote ON wallpaper_provenance(source_provider, remote_id);
        CREATE INDEX IF NOT EXISTS idx_download_history_created_at ON download_history(created_at DESC);
        """
    )
    connection.execute(
        """
        INSERT INTO wallpaper_provenance(
            wallpaper_id,
            source_kind,
            source_provider,
            imported_at,
            metadata_json
        )
        SELECT
            w.id,
            'local',
            'filesystem',
            COALESCE(w.added_at, w.indexed_at, CURRENT_TIMESTAMP),
            '{}'
        FROM wallpapers w
        LEFT JOIN wallpaper_provenance p ON p.wallpaper_id = w.id
        WHERE p.wallpaper_id IS NULL
        """
    )


def _migration_add_video_support(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(wallpapers)").fetchall()
    }
    if "media_kind" not in existing_columns:
        connection.execute("ALTER TABLE wallpapers ADD COLUMN media_kind TEXT NOT NULL DEFAULT 'image'")
    if "duration_seconds" not in existing_columns:
        connection.execute("ALTER TABLE wallpapers ADD COLUMN duration_seconds REAL")
    connection.execute("UPDATE wallpapers SET media_kind = COALESCE(NULLIF(media_kind, ''), 'image')")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_wallpapers_media_kind ON wallpapers(media_kind)")
