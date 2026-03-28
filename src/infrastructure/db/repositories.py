from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from src.domain.enums import MediaKind, Orientation, SmartCollection, SortField, WallpaperSourceKind
from src.domain.models import DownloadRecord, DuplicateGroup, Folder, OperationLogEntry, Wallpaper, WallpaperProvenance


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class WallpaperRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    @contextmanager
    def transaction(self):
        try:
            self.connection.execute("BEGIN")
            yield
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def _row_to_wallpaper(self, row: sqlite3.Row) -> Wallpaper:
        tag_blob = row["tags_blob"] or ""
        tags = tuple(tag for tag in tag_blob.split("||") if tag)
        thumbnail_path = row["thumbnail_path"]
        folder_path = row["folder_path"]
        provenance: WallpaperProvenance | None = None
        provenance_kind = row["provenance_source_kind"]
        if provenance_kind:
            metadata: dict = {}
            raw_metadata = row["provenance_metadata_json"]
            if raw_metadata:
                try:
                    loaded = json.loads(raw_metadata)
                except json.JSONDecodeError:
                    loaded = {}
                if isinstance(loaded, dict):
                    metadata = loaded
            provenance = WallpaperProvenance(
                source_kind=WallpaperSourceKind(str(provenance_kind)),
                source_provider=row["provenance_source_provider"],
                remote_id=row["provenance_remote_id"],
                source_url=row["provenance_source_url"],
                author_name=row["provenance_author_name"],
                license_name=row["provenance_license_name"],
                imported_at=row["provenance_imported_at"],
                generator_tool=row["provenance_generator_tool"],
                parent_wallpaper_id=row["provenance_parent_wallpaper_id"],
                metadata=metadata,
            )
        return Wallpaper(
            id=row["id"],
            path=Path(row["path"]),
            filename=row["filename"],
            extension=row["extension"] or "",
            media_kind=MediaKind(row["media_kind"] or MediaKind.IMAGE.value),
            folder_id=row["folder_id"],
            folder_path=Path(folder_path) if folder_path else None,
            width=row["width"],
            height=row["height"],
            orientation=Orientation(row["orientation"] or Orientation.UNKNOWN.value),
            aspect_ratio=row["aspect_ratio"],
            size_bytes=row["size_bytes"] or 0,
            mtime=row["mtime"] or 0,
            ctime=row["ctime"] or 0,
            sha256=row["sha256"],
            is_favorite=bool(row["is_favorite"]),
            rating=row["rating"] or 0,
            notes=row["notes"] or "",
            added_at=row["added_at"],
            indexed_at=row["indexed_at"],
            last_viewed_at=row["last_viewed_at"],
            times_viewed=row["times_viewed"] or 0,
            tags=tags,
            thumbnail_path=Path(thumbnail_path) if thumbnail_path else None,
            brightness=row["brightness"],
            avg_color=row["avg_color"],
            duration_seconds=row["duration_seconds"],
            provenance=provenance,
        )

    def list_wallpapers(self, root_dir: Path | None = None) -> list[Wallpaper]:
        rows = self.connection.execute(
            f"{self._wallpaper_select_sql(root_dir is not None)} GROUP BY w.id ORDER BY w.mtime DESC, w.filename COLLATE NOCASE ASC",
            self._root_dir_params(root_dir),
        ).fetchall()
        return [self._row_to_wallpaper(row) for row in rows]

    def count_wallpapers(self, root_dir: Path | None = None) -> int:
        query = "SELECT COUNT(*) AS count FROM wallpapers w"
        params: list[object] = []
        if root_dir is not None:
            query += " WHERE w.path LIKE ?"
            params.append(f"{root_dir}%")
        row = self.connection.execute(query, params).fetchone()
        return int(row["count"]) if row is not None else 0

    def list_wallpapers_page(self, *, root_dir: Path | None = None, limit: int = 200, offset: int = 0) -> list[Wallpaper]:
        query = (
            f"{self._wallpaper_select_sql(root_dir is not None)} "
            "GROUP BY w.id ORDER BY w.mtime DESC, w.filename COLLATE NOCASE ASC LIMIT ? OFFSET ?"
        )
        rows = self.connection.execute(query, [*self._root_dir_params(root_dir), max(1, limit), max(0, offset)]).fetchall()
        return [self._row_to_wallpaper(row) for row in rows]

    def search_wallpapers(
        self,
        *,
        root_dir: Path | None = None,
        search_text: str = "",
        orientation: Orientation | None = None,
        favorites_only: bool = False,
        minimum_rating: int = 0,
        sort_field: SortField = SortField.MTIME,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Wallpaper]:
        where: list[str] = []
        params: list[object] = []
        if root_dir is not None:
            where.append("w.path LIKE ?")
            params.append(f"{root_dir}%")
        if search_text.strip():
            like_value = f"%{search_text.strip()}%"
            where.append(
                """
                (
                    w.filename LIKE ? COLLATE NOCASE
                    OR w.path LIKE ? COLLATE NOCASE
                    OR w.notes LIKE ? COLLATE NOCASE
                    OR EXISTS (
                        SELECT 1
                        FROM wallpaper_tags wt2
                        JOIN tags t2 ON t2.id = wt2.tag_id
                        WHERE wt2.wallpaper_id = w.id AND t2.name LIKE ? COLLATE NOCASE
                    )
                )
                """
            )
            params.extend([like_value, like_value, like_value, like_value])
        if orientation is not None:
            where.append("w.orientation = ?")
            params.append(orientation.value)
        if favorites_only:
            where.append("w.is_favorite = 1")
        if minimum_rating > 0:
            where.append("w.rating >= ?")
            params.append(max(0, min(5, minimum_rating)))

        query = self._wallpaper_select_sql(include_root_filter=False)
        if where:
            query += " WHERE " + " AND ".join(part.strip() for part in where)
        query += f" GROUP BY w.id ORDER BY {self._sort_clause(sort_field)}"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([max(1, limit), max(0, offset)])
        rows = self.connection.execute(query, params).fetchall()
        return [self._row_to_wallpaper(row) for row in rows]

    def list_wallpapers_for_collection(
        self,
        collection: SmartCollection,
        *,
        root_dir: Path | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Wallpaper]:
        query = self._wallpaper_select_sql(include_root_filter=False)
        where: list[str] = []
        params: list[object] = []
        if root_dir is not None:
            where.append("w.path LIKE ?")
            params.append(f"{root_dir}%")
        collection_clause = self._collection_clause(collection)
        if collection_clause:
            where.append(collection_clause)
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " GROUP BY w.id ORDER BY w.mtime DESC, w.filename COLLATE NOCASE ASC"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([max(1, limit), max(0, offset)])
        rows = self.connection.execute(query, params).fetchall()
        return [self._row_to_wallpaper(row) for row in rows]

    def get_scan_index(self, root_dir: Path) -> dict[str, Wallpaper]:
        return {str(item.path): item for item in self.list_wallpapers(root_dir)}

    def get_wallpaper(self, wallpaper_id: int) -> Wallpaper | None:
        row = self.connection.execute(
            """
            SELECT
                w.*,
                f.path AS folder_path,
                GROUP_CONCAT(t.name, '||') AS tags_blob,
                p.source_kind AS provenance_source_kind,
                p.source_provider AS provenance_source_provider,
                p.remote_id AS provenance_remote_id,
                p.source_url AS provenance_source_url,
                p.author_name AS provenance_author_name,
                p.license_name AS provenance_license_name,
                p.imported_at AS provenance_imported_at,
                p.generator_tool AS provenance_generator_tool,
                p.parent_wallpaper_id AS provenance_parent_wallpaper_id,
                p.metadata_json AS provenance_metadata_json
            FROM wallpapers w
            LEFT JOIN folders f ON f.id = w.folder_id
            LEFT JOIN wallpaper_tags wt ON wt.wallpaper_id = w.id
            LEFT JOIN tags t ON t.id = wt.tag_id
            LEFT JOIN wallpaper_provenance p ON p.wallpaper_id = w.id
            WHERE w.id = ?
            GROUP BY w.id
            """,
            (wallpaper_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_wallpaper(row)

    def get_wallpaper_by_path(self, path: Path) -> Wallpaper | None:
        row = self.connection.execute(
            """
            SELECT
                w.*,
                f.path AS folder_path,
                GROUP_CONCAT(t.name, '||') AS tags_blob,
                p.source_kind AS provenance_source_kind,
                p.source_provider AS provenance_source_provider,
                p.remote_id AS provenance_remote_id,
                p.source_url AS provenance_source_url,
                p.author_name AS provenance_author_name,
                p.license_name AS provenance_license_name,
                p.imported_at AS provenance_imported_at,
                p.generator_tool AS provenance_generator_tool,
                p.parent_wallpaper_id AS provenance_parent_wallpaper_id,
                p.metadata_json AS provenance_metadata_json
            FROM wallpapers w
            LEFT JOIN folders f ON f.id = w.folder_id
            LEFT JOIN wallpaper_tags wt ON wt.wallpaper_id = w.id
            LEFT JOIN tags t ON t.id = wt.tag_id
            LEFT JOIN wallpaper_provenance p ON p.wallpaper_id = w.id
            WHERE w.path = ?
            GROUP BY w.id
            """,
            (str(path),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_wallpaper(row)

    def list_folders(self, root_dir: Path | None = None) -> list[Folder]:
        query = "SELECT id, path, name, parent_id FROM folders"
        params: list[object] = []
        if root_dir is not None:
            query += " WHERE path LIKE ?"
            params.append(f"{root_dir}%")
        query += " ORDER BY path COLLATE NOCASE ASC"
        rows = self.connection.execute(query, params).fetchall()
        return [
            Folder(
                id=row["id"],
                path=Path(row["path"]),
                name=row["name"],
                parent_id=row["parent_id"],
            )
            for row in rows
        ]

    def list_tags(self) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT name
            FROM tags
            ORDER BY name COLLATE NOCASE ASC
            """
        ).fetchall()
        return [str(row["name"]) for row in rows]

    def ensure_folder(self, path: Path) -> int | None:
        path = path.expanduser().resolve()
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

        row = self.connection.execute("SELECT id FROM folders WHERE path = ?", (str(path),)).fetchone()
        if row is not None:
            return int(row["id"])

        parent_id: int | None = None
        if path.parent != path:
            existing_parent = self.connection.execute(
                "SELECT id FROM folders WHERE path = ?",
                (str(path.parent),),
            ).fetchone()
            if existing_parent is None:
                parent_id = self.ensure_folder(path.parent)
            else:
                parent_id = int(existing_parent["id"])

        cursor = self.connection.execute(
            "INSERT INTO folders(path, name, parent_id) VALUES(?, ?, ?)",
            (str(path), path.name or str(path), parent_id),
        )
        return int(cursor.lastrowid)

    def replace_tags(self, wallpaper_id: int, tags: tuple[str, ...] | list[str]) -> None:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in tags:
            tag = raw.strip()
            if not tag:
                continue
            lowered = tag.casefold()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(tag)

        self.connection.execute("DELETE FROM wallpaper_tags WHERE wallpaper_id = ?", (wallpaper_id,))
        for tag in normalized:
            self.connection.execute("INSERT OR IGNORE INTO tags(name) VALUES(?)", (tag,))
            tag_row = self.connection.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()
            if tag_row is None:
                continue
            self.connection.execute(
                "INSERT OR IGNORE INTO wallpaper_tags(wallpaper_id, tag_id) VALUES(?, ?)",
                (wallpaper_id, int(tag_row["id"])),
            )

    def upsert_wallpaper(self, wallpaper: Wallpaper) -> Wallpaper:
        folder_id = self.ensure_folder(wallpaper.path.parent)
        now = utc_now_iso()
        added_at = wallpaper.added_at or now
        indexed_at = wallpaper.indexed_at or now
        self.connection.execute(
            """
            INSERT INTO wallpapers(
                path,
                filename,
                extension,
                media_kind,
                folder_id,
                width,
                height,
                orientation,
                aspect_ratio,
                size_bytes,
                mtime,
                ctime,
                sha256,
                is_favorite,
                rating,
                notes,
                added_at,
                indexed_at,
                last_viewed_at,
                times_viewed,
                thumbnail_path,
                brightness,
                avg_color,
                duration_seconds
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                filename = excluded.filename,
                extension = excluded.extension,
                media_kind = excluded.media_kind,
                folder_id = excluded.folder_id,
                width = excluded.width,
                height = excluded.height,
                orientation = excluded.orientation,
                aspect_ratio = excluded.aspect_ratio,
                size_bytes = excluded.size_bytes,
                mtime = excluded.mtime,
                ctime = excluded.ctime,
                sha256 = COALESCE(excluded.sha256, wallpapers.sha256),
                added_at = COALESCE(wallpapers.added_at, excluded.added_at),
                indexed_at = excluded.indexed_at,
                thumbnail_path = excluded.thumbnail_path,
                brightness = excluded.brightness,
                avg_color = excluded.avg_color,
                duration_seconds = excluded.duration_seconds
            """,
            (
                str(wallpaper.path),
                wallpaper.filename,
                wallpaper.extension,
                wallpaper.media_kind.value,
                folder_id,
                wallpaper.width,
                wallpaper.height,
                wallpaper.orientation.value,
                wallpaper.aspect_ratio,
                wallpaper.size_bytes,
                wallpaper.mtime,
                wallpaper.ctime,
                wallpaper.sha256,
                int(wallpaper.is_favorite),
                wallpaper.rating,
                wallpaper.notes,
                added_at,
                indexed_at,
                wallpaper.last_viewed_at,
                wallpaper.times_viewed,
                str(wallpaper.thumbnail_path) if wallpaper.thumbnail_path else None,
                wallpaper.brightness,
                wallpaper.avg_color,
                wallpaper.duration_seconds,
            ),
        )
        row = self.connection.execute("SELECT id FROM wallpapers WHERE path = ?", (str(wallpaper.path),)).fetchone()
        if row is None:
            raise RuntimeError(f"Unable to upsert wallpaper: {wallpaper.path}")
        wallpaper_id = int(row["id"])
        self.replace_tags(wallpaper_id, wallpaper.tags)
        refreshed = self.get_wallpaper(wallpaper_id)
        if refreshed is None:
            raise RuntimeError(f"Unable to reload wallpaper: {wallpaper.path}")
        return refreshed

    def ensure_local_provenance(self, wallpaper_id: int, *, imported_at: str | None = None) -> None:
        self.connection.execute(
            """
            INSERT OR IGNORE INTO wallpaper_provenance(
                wallpaper_id,
                source_kind,
                source_provider,
                imported_at,
                metadata_json
            )
            VALUES(?, ?, ?, COALESCE(?, ?), '{}')
            """,
            (wallpaper_id, WallpaperSourceKind.LOCAL.value, "filesystem", imported_at, utc_now_iso()),
        )

    def upsert_provenance(self, wallpaper_id: int, provenance: WallpaperProvenance) -> None:
        self.connection.execute(
            """
            INSERT INTO wallpaper_provenance(
                wallpaper_id,
                source_kind,
                source_provider,
                remote_id,
                source_url,
                author_name,
                license_name,
                imported_at,
                generator_tool,
                parent_wallpaper_id,
                metadata_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(wallpaper_id) DO UPDATE SET
                source_kind = excluded.source_kind,
                source_provider = excluded.source_provider,
                remote_id = excluded.remote_id,
                source_url = excluded.source_url,
                author_name = excluded.author_name,
                license_name = excluded.license_name,
                imported_at = excluded.imported_at,
                generator_tool = excluded.generator_tool,
                parent_wallpaper_id = excluded.parent_wallpaper_id,
                metadata_json = excluded.metadata_json
            """,
            (
                wallpaper_id,
                provenance.source_kind.value,
                provenance.source_provider,
                provenance.remote_id,
                provenance.source_url,
                provenance.author_name,
                provenance.license_name,
                provenance.imported_at or utc_now_iso(),
                provenance.generator_tool,
                provenance.parent_wallpaper_id,
                json.dumps(provenance.metadata or {}, ensure_ascii=False, sort_keys=True),
            ),
        )

    def find_wallpaper_by_remote(self, provider: str, remote_id: str) -> Wallpaper | None:
        row = self.connection.execute(
            """
            SELECT w.id
            FROM wallpapers w
            JOIN wallpaper_provenance p ON p.wallpaper_id = w.id
            WHERE p.source_provider = ? AND p.remote_id = ?
            LIMIT 1
            """,
            (provider, remote_id),
        ).fetchone()
        if row is None:
            return None
        return self.get_wallpaper(int(row["id"]))

    def delete_missing_wallpapers(self, root_dir: Path, valid_paths: set[str]) -> int:
        rows = self.connection.execute(
            "SELECT id, path FROM wallpapers WHERE path LIKE ?",
            (f"{root_dir}%",),
        ).fetchall()
        removed = 0
        for row in rows:
            path = row["path"]
            if path in valid_paths:
                continue
            self.connection.execute("DELETE FROM wallpapers WHERE id = ?", (int(row["id"]),))
            removed += 1
        return removed

    def set_favorite(self, wallpaper_id: int, value: bool) -> Wallpaper:
        self.connection.execute(
            "UPDATE wallpapers SET is_favorite = ? WHERE id = ?",
            (int(value), wallpaper_id),
        )
        refreshed = self.get_wallpaper(wallpaper_id)
        if refreshed is None:
            raise KeyError(wallpaper_id)
        return refreshed

    def update_wallpaper_details(
        self,
        wallpaper_id: int,
        *,
        tags: tuple[str, ...] | list[str],
        notes: str,
        rating: int,
    ) -> Wallpaper:
        self.connection.execute(
            "UPDATE wallpapers SET notes = ?, rating = ? WHERE id = ?",
            (notes, max(0, min(5, rating)), wallpaper_id),
        )
        self.replace_tags(wallpaper_id, tags)
        refreshed = self.get_wallpaper(wallpaper_id)
        if refreshed is None:
            raise KeyError(wallpaper_id)
        return refreshed

    def mark_viewed(self, wallpaper_id: int) -> Wallpaper:
        self.connection.execute(
            """
            UPDATE wallpapers
            SET times_viewed = times_viewed + 1,
                last_viewed_at = ?
            WHERE id = ?
            """,
            (utc_now_iso(), wallpaper_id),
        )
        refreshed = self.get_wallpaper(wallpaper_id)
        if refreshed is None:
            raise KeyError(wallpaper_id)
        return refreshed

    def set_hash(self, wallpaper_id: int, sha256: str) -> Wallpaper:
        self.connection.execute(
            "UPDATE wallpapers SET sha256 = ? WHERE id = ?",
            (sha256, wallpaper_id),
        )
        refreshed = self.get_wallpaper(wallpaper_id)
        if refreshed is None:
            raise KeyError(wallpaper_id)
        return refreshed

    def move_wallpaper(self, wallpaper_id: int, new_path: Path) -> Wallpaper:
        folder_id = self.ensure_folder(new_path.parent)
        self.connection.execute(
            """
            UPDATE wallpapers
            SET path = ?, filename = ?, folder_id = ?, extension = ?, indexed_at = ?
            WHERE id = ?
            """,
            (str(new_path), new_path.name, folder_id, new_path.suffix.lower(), utc_now_iso(), wallpaper_id),
        )
        refreshed = self.get_wallpaper(wallpaper_id)
        if refreshed is None:
            raise KeyError(wallpaper_id)
        return refreshed

    def delete_wallpaper(self, wallpaper_id: int) -> None:
        self.connection.execute("DELETE FROM wallpapers WHERE id = ?", (wallpaper_id,))

    def restore_wallpaper(self, wallpaper: Wallpaper) -> Wallpaper:
        folder_id = self.ensure_folder(wallpaper.path.parent)
        self.connection.execute(
            """
            INSERT INTO wallpapers(
                id,
                path,
                filename,
                extension,
                media_kind,
                folder_id,
                width,
                height,
                orientation,
                aspect_ratio,
                size_bytes,
                mtime,
                ctime,
                sha256,
                is_favorite,
                rating,
                notes,
                added_at,
                indexed_at,
                last_viewed_at,
                times_viewed,
                thumbnail_path,
                brightness,
                avg_color,
                duration_seconds
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                wallpaper.id,
                str(wallpaper.path),
                wallpaper.filename,
                wallpaper.extension,
                wallpaper.media_kind.value,
                folder_id,
                wallpaper.width,
                wallpaper.height,
                wallpaper.orientation.value,
                wallpaper.aspect_ratio,
                wallpaper.size_bytes,
                wallpaper.mtime,
                wallpaper.ctime,
                wallpaper.sha256,
                int(wallpaper.is_favorite),
                wallpaper.rating,
                wallpaper.notes,
                wallpaper.added_at,
                wallpaper.indexed_at or utc_now_iso(),
                wallpaper.last_viewed_at,
                wallpaper.times_viewed,
                str(wallpaper.thumbnail_path) if wallpaper.thumbnail_path else None,
                wallpaper.brightness,
                wallpaper.avg_color,
                wallpaper.duration_seconds,
            ),
        )
        self.replace_tags(wallpaper.id or 0, wallpaper.tags)
        if wallpaper.provenance is not None:
            self.upsert_provenance(wallpaper.id or 0, wallpaper.provenance)
        refreshed = self.get_wallpaper(wallpaper.id or 0)
        if refreshed is None:
            raise RuntimeError("Unable to restore wallpaper")
        return refreshed

    def log_download(
        self,
        *,
        provider: str,
        remote_id: str | None,
        source_url: str | None,
        destination_path: Path | None,
        wallpaper_id: int | None,
        status: str,
        payload: dict | None = None,
    ) -> DownloadRecord:
        cursor = self.connection.execute(
            """
            INSERT INTO download_history(
                provider,
                remote_id,
                source_url,
                destination_path,
                wallpaper_id,
                status,
                created_at,
                payload_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                provider,
                remote_id,
                source_url,
                None if destination_path is None else str(destination_path),
                wallpaper_id,
                status,
                utc_now_iso(),
                json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
            ),
        )
        row = self.connection.execute(
            """
            SELECT id, provider, remote_id, source_url, destination_path, wallpaper_id, status, created_at, payload_json
            FROM download_history
            WHERE id = ?
            """,
            (int(cursor.lastrowid),),
        ).fetchone()
        if row is None:
            raise RuntimeError("Unable to log download history")
        return DownloadRecord(
            id=int(row["id"]),
            provider=str(row["provider"]),
            remote_id=row["remote_id"],
            source_url=row["source_url"],
            destination_path=Path(row["destination_path"]) if row["destination_path"] else None,
            wallpaper_id=row["wallpaper_id"],
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            payload_json=str(row["payload_json"]),
        )

    def log_operation(self, action: str, wallpaper_id: int | None = None, payload: dict | None = None) -> None:
        self.connection.execute(
            "INSERT INTO operations_log(action, wallpaper_id, payload_json, created_at) VALUES(?, ?, ?, ?)",
            (
                action,
                wallpaper_id,
                json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
                utc_now_iso(),
            ),
        )

    def list_operations(self, limit: int = 200) -> list[OperationLogEntry]:
        rows = self.connection.execute(
            """
            SELECT id, action, wallpaper_id, payload_json, created_at
            FROM operations_log
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            OperationLogEntry(
                id=int(row["id"]),
                action=row["action"],
                wallpaper_id=row["wallpaper_id"],
                payload_json=row["payload_json"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def list_duplicate_groups(self) -> list[DuplicateGroup]:
        rows = self.connection.execute(
            """
            SELECT sha256, GROUP_CONCAT(id) AS ids_blob
            FROM wallpapers
            WHERE sha256 IS NOT NULL AND sha256 != ''
            GROUP BY sha256
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC, sha256 ASC
            """
        ).fetchall()
        groups: list[DuplicateGroup] = []
        for row in rows:
            groups.append(
                DuplicateGroup(
                    sha256=row["sha256"],
                    wallpaper_ids=tuple(int(item) for item in row["ids_blob"].split(",") if item),
                )
            )
        return groups

    def _wallpaper_select_sql(self, include_root_filter: bool) -> str:
        query = """
            SELECT
                w.*,
                f.path AS folder_path,
                GROUP_CONCAT(t.name, '||') AS tags_blob,
                p.source_kind AS provenance_source_kind,
                p.source_provider AS provenance_source_provider,
                p.remote_id AS provenance_remote_id,
                p.source_url AS provenance_source_url,
                p.author_name AS provenance_author_name,
                p.license_name AS provenance_license_name,
                p.imported_at AS provenance_imported_at,
                p.generator_tool AS provenance_generator_tool,
                p.parent_wallpaper_id AS provenance_parent_wallpaper_id,
                p.metadata_json AS provenance_metadata_json
            FROM wallpapers w
            LEFT JOIN folders f ON f.id = w.folder_id
            LEFT JOIN wallpaper_tags wt ON wt.wallpaper_id = w.id
            LEFT JOIN tags t ON t.id = wt.tag_id
            LEFT JOIN wallpaper_provenance p ON p.wallpaper_id = w.id
        """
        if include_root_filter:
            query += " WHERE w.path LIKE ?"
        return query

    def _root_dir_params(self, root_dir: Path | None) -> list[object]:
        return [f"{root_dir}%"] if root_dir is not None else []

    def _sort_clause(self, sort_field: SortField) -> str:
        return {
            SortField.NAME: "w.filename COLLATE NOCASE ASC",
            SortField.SIZE: "w.size_bytes DESC, w.filename COLLATE NOCASE ASC",
            SortField.ORIENTATION: "w.orientation ASC, w.filename COLLATE NOCASE ASC",
            SortField.FAVORITE: "w.is_favorite DESC, w.rating DESC, w.filename COLLATE NOCASE ASC",
            SortField.RATING: "w.rating DESC, w.filename COLLATE NOCASE ASC",
            SortField.VIEWS: "w.times_viewed DESC, w.filename COLLATE NOCASE ASC",
            SortField.BRIGHTNESS: "w.brightness ASC, w.filename COLLATE NOCASE ASC",
        }.get(sort_field, "w.mtime DESC, w.filename COLLATE NOCASE ASC")

    def _collection_clause(self, collection: SmartCollection) -> str:
        return {
            SmartCollection.FAVORITES: "w.is_favorite = 1",
            SmartCollection.VIDEOS: "w.media_kind = 'video'",
            SmartCollection.PORTRAITS: "w.orientation = 'portrait'",
            SmartCollection.LANDSCAPES: "w.orientation = 'landscape'",
            SmartCollection.SQUARES: "w.orientation = 'square'",
            SmartCollection.NEVER_VIEWED: "w.times_viewed = 0",
            SmartCollection.TOP_RATED: "w.rating >= 4",
            SmartCollection.DUPLICATES: "w.sha256 IN (SELECT sha256 FROM wallpapers WHERE sha256 IS NOT NULL AND sha256 != '' GROUP BY sha256 HAVING COUNT(*) > 1)",
            SmartCollection.DARK: "w.brightness IS NOT NULL AND w.brightness < 96",
            SmartCollection.ANIME: "(LOWER(w.filename) LIKE '%anime%' OR LOWER(w.filename) LIKE '%manga%' OR LOWER(w.notes) LIKE '%anime%' OR LOWER(w.notes) LIKE '%manga%')",
            SmartCollection.MINIMAL: "(LOWER(w.filename) LIKE '%minimal%' OR LOWER(w.filename) LIKE '%clean%' OR LOWER(w.filename) LIKE '%simple%' OR LOWER(w.notes) LIKE '%minimal%' OR LOWER(w.notes) LIKE '%clean%' OR LOWER(w.notes) LIKE '%simple%')",
            SmartCollection.UNTAGGED: "NOT EXISTS (SELECT 1 FROM wallpaper_tags wt2 WHERE wt2.wallpaper_id = w.id)",
            SmartCollection.RECENT: "w.added_at IS NOT NULL",
            SmartCollection.INBOX: "LOWER(w.path) LIKE '%inbox%'",
        }.get(collection, "")
