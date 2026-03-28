from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import re
import shutil
import sqlite3

from src.config.paths import AppPaths
from src.config.settings import AppSettings, SettingsManager
from src.domain.enums import MediaKind, SmartCollection, WallpaperSourceKind
from src.domain.models import (
    DownloadRecord,
    DuplicateGroup,
    GowallPreviewResult,
    GowallStatus,
    GowallTheme,
    LibraryStats,
    ScanSummary,
    TrashRecord,
    Wallpaper,
    WallpaperBackendStatus,
    WallpaperProvenance,
    VideoWallpaperBackendStatus,
    WallhavenSearchPage,
    WallhavenSearchRequest,
    WallhavenSearchResult,
    WallhavenStatus,
)
from src.infrastructure.db.connection import connect, initialize_database
from src.infrastructure.db.repositories import WallpaperRepository
from src.infrastructure.filesystem.mover import FileMover
from src.infrastructure.filesystem.scanner import LibraryScanner, ProgressCallback
from src.infrastructure.gowall.client import GowallClient
from src.infrastructure.filesystem.trash import TrashManager
from src.infrastructure.imaging.hashing import compute_sha256
from src.infrastructure.imaging.thumbnails import ThumbnailManager
from src.infrastructure.wallhaven.client import WallhavenClient
from src.infrastructure.wallpaper.backend import (
    VideoWallpaperBackend,
    WallpaperBackend,
    resolve_video_wallpaper_backend,
    resolve_wallpaper_backend,
)
from src.i18n import set_language


class WallManagerService:
    def __init__(
        self,
        *,
        paths: AppPaths,
        settings_manager: SettingsManager,
        settings: AppSettings,
        connection: sqlite3.Connection,
        repository: WallpaperRepository,
        scanner: LibraryScanner,
        mover: FileMover,
        trash_manager: TrashManager,
        wallpaper_backend: WallpaperBackend,
        wallpaper_backend_status: WallpaperBackendStatus,
        video_wallpaper_backend: VideoWallpaperBackend,
        video_wallpaper_backend_status: VideoWallpaperBackendStatus,
        gowall_client: GowallClient,
        wallhaven_client: WallhavenClient,
    ) -> None:
        self.paths = paths
        self.settings_manager = settings_manager
        self.settings = settings
        self.connection = connection
        self.repository = repository
        self.scanner = scanner
        self.mover = mover
        self.trash_manager = trash_manager
        self.wallpaper_backend = wallpaper_backend
        self.wallpaper_backend_status = wallpaper_backend_status
        self.video_wallpaper_backend = video_wallpaper_backend
        self.video_wallpaper_backend_status = video_wallpaper_backend_status
        self.gowall_client = gowall_client
        self.wallhaven_client = wallhaven_client

    @classmethod
    def create(cls, library_root: Path | None = None) -> "WallManagerService":
        paths = AppPaths.default(library_root=library_root)
        paths.ensure_directories()
        settings_manager = SettingsManager(paths)
        settings = settings_manager.load()
        set_language(settings.language)
        paths.library_root = settings.library_root
        paths.ensure_directories()
        settings.inbox_root.mkdir(parents=True, exist_ok=True)
        connection = connect(paths.db_path)
        initialize_database(connection)
        repository = WallpaperRepository(connection)
        thumbnail_manager = ThumbnailManager(paths.thumbnails_dir, size=settings.thumbnail_size)
        scanner = LibraryScanner(thumbnail_manager)
        mover = FileMover()
        trash_manager = TrashManager(paths.trash_files_dir, paths.trash_info_dir)
        wallpaper_backend, wallpaper_backend_status = resolve_wallpaper_backend(settings.wallpaper_backend)
        video_wallpaper_backend, video_wallpaper_backend_status = resolve_video_wallpaper_backend(paths.mpvpaper_state_path)
        gowall_client = GowallClient(paths.gowall_previews_dir, paths.gowall_themes_dir)
        wallhaven_client = WallhavenClient(paths.wallhaven_cache_dir)
        return cls(
            paths=paths,
            settings_manager=settings_manager,
            settings=settings,
            connection=connection,
            repository=repository,
            scanner=scanner,
            mover=mover,
            trash_manager=trash_manager,
            wallpaper_backend=wallpaper_backend,
            wallpaper_backend_status=wallpaper_backend_status,
            video_wallpaper_backend=video_wallpaper_backend,
            video_wallpaper_backend_status=video_wallpaper_backend_status,
            gowall_client=gowall_client,
            wallhaven_client=wallhaven_client,
        )

    def close(self) -> None:
        self.connection.close()

    def scan_library(
        self,
        *,
        compute_hashes: bool | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ScanSummary:
        inbox_imported_count = 0
        if self.settings.auto_import_inbox:
            inbox_imported_count = self.import_inbox(rescan=False)
        compute_hashes = self.settings.compute_hashes_on_scan if compute_hashes is None else compute_hashes
        existing = self.repository.get_scan_index(self.settings.library_root)
        scan_result = self.scanner.scan(
            self.settings.library_root,
            existing_index=existing,
            progress_callback=progress_callback,
            compute_hashes=compute_hashes,
        )
        valid_paths = {str(item.path) for item in scan_result.wallpapers}
        with self.repository.transaction():
            for wallpaper in scan_result.wallpapers:
                stored = self.repository.upsert_wallpaper(wallpaper)
                if stored.id is not None:
                    self.repository.ensure_local_provenance(stored.id, imported_at=stored.added_at)
            removed_count = self.repository.delete_missing_wallpapers(self.settings.library_root, valid_paths)
            self.repository.log_operation(
                "scan",
                payload={
                    "scanned_count": len(scan_result.wallpapers),
                    "imported_count": scan_result.imported_count,
                    "updated_count": scan_result.updated_count,
                    "reused_count": scan_result.reused_count,
                    "removed_count": removed_count,
                    "inbox_imported_count": inbox_imported_count,
                    "errors": scan_result.errors,
                },
            )
        return ScanSummary(
            scanned_count=len(scan_result.wallpapers),
            imported_count=scan_result.imported_count,
            updated_count=scan_result.updated_count,
            reused_count=scan_result.reused_count,
            removed_count=removed_count,
            inbox_imported_count=inbox_imported_count,
            errors=scan_result.errors,
        )

    def list_wallpapers(self) -> list[Wallpaper]:
        return self.repository.list_wallpapers(self.settings.library_root)

    def count_wallpapers(self) -> int:
        return self.repository.count_wallpapers(self.settings.library_root)

    def list_wallpapers_page(self, *, limit: int = 200, offset: int = 0) -> list[Wallpaper]:
        return self.repository.list_wallpapers_page(root_dir=self.settings.library_root, limit=limit, offset=offset)

    def search_wallpapers(
        self,
        *,
        search_text: str = "",
        orientation=None,
        favorites_only: bool = False,
        minimum_rating: int = 0,
        sort_field=None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Wallpaper]:
        return self.repository.search_wallpapers(
            root_dir=self.settings.library_root,
            search_text=search_text,
            orientation=orientation,
            favorites_only=favorites_only,
            minimum_rating=minimum_rating,
            sort_field=self.settings.default_sort if sort_field is None else sort_field,
            limit=limit,
            offset=offset,
        )

    def list_folders(self):
        return self.repository.list_folders(self.settings.library_root)

    def list_operations(self, limit: int = 200):
        return self.repository.list_operations(limit)

    def list_tags(self) -> list[str]:
        return self.repository.list_tags()

    def persist_settings(self) -> None:
        self.settings_manager.save(self.settings)

    def update_settings(self, settings: AppSettings) -> None:
        settings.library_root = settings.library_root.expanduser()
        settings.inbox_root = settings.inbox_root.expanduser()
        settings.library_root.mkdir(parents=True, exist_ok=True)
        settings.inbox_root.mkdir(parents=True, exist_ok=True)
        self.paths.library_root = settings.library_root
        self.settings = settings
        set_language(settings.language)
        self.settings_manager.save(settings)
        self.scanner.thumbnail_manager = ThumbnailManager(self.paths.thumbnails_dir, size=settings.thumbnail_size)
        self.wallpaper_backend, self.wallpaper_backend_status = resolve_wallpaper_backend(settings.wallpaper_backend)
        self.video_wallpaper_backend, self.video_wallpaper_backend_status = resolve_video_wallpaper_backend(
            self.paths.mpvpaper_state_path
        )

    def import_inbox(self, *, rescan: bool = True) -> int:
        imported_count = self._import_inbox_files()
        if imported_count and rescan:
            self.scan_library()
        return imported_count

    def get_gowall_status(self) -> GowallStatus:
        return self.gowall_client.status()

    def get_wallhaven_status(self) -> WallhavenStatus:
        return self.wallhaven_client.status(self.settings.wallhaven_api_key)

    def get_wallpaper_backend_status(self) -> WallpaperBackendStatus:
        self.wallpaper_backend, self.wallpaper_backend_status = resolve_wallpaper_backend(self.settings.wallpaper_backend)
        return self.wallpaper_backend_status

    def get_video_wallpaper_backend_status(self) -> VideoWallpaperBackendStatus:
        self.video_wallpaper_backend, self.video_wallpaper_backend_status = resolve_video_wallpaper_backend(
            self.paths.mpvpaper_state_path
        )
        return self.video_wallpaper_backend_status

    def list_gowall_themes(self) -> list[GowallTheme]:
        return self.gowall_client.list_themes()

    def import_gowall_theme_json(self, path: Path, *, overwrite: bool = False) -> GowallTheme:
        theme = self.gowall_client.import_theme_json(path, overwrite=overwrite)
        self.repository.log_operation(
            "gowall_import_theme",
            payload={"path": str(path), "theme_id": theme.id, "display_name": theme.display_name},
        )
        self.connection.commit()
        return theme

    def generate_gowall_previews(
        self,
        wallpaper_id: int,
        theme_ids: list[str] | None = None,
    ) -> list[GowallPreviewResult]:
        wallpaper = self.get_wallpaper(wallpaper_id)
        themes = self.list_gowall_themes()
        if theme_ids is not None:
            requested = set(theme_ids)
            themes = [theme for theme in themes if theme.id in requested]
        return [self.gowall_client.ensure_preview(wallpaper, theme) for theme in themes]

    def search_wallhaven(self, request: WallhavenSearchRequest) -> WallhavenSearchPage:
        return self.wallhaven_client.search(request, api_key=self.settings.wallhaven_api_key)

    def download_wallhaven_results(self, result_ids: list[str]) -> list[Wallpaper]:
        imported: list[Wallpaper] = []
        target_root = self.settings.library_root / "Inbox" / "Wallhaven"
        with self.repository.transaction():
            for result_id in result_ids:
                existing = self.repository.find_wallpaper_by_remote("wallhaven", result_id)
                if existing is not None:
                    self.repository.log_download(
                        provider="wallhaven",
                        remote_id=result_id,
                        source_url=existing.provenance.source_url if existing.provenance else None,
                        destination_path=existing.path,
                        wallpaper_id=existing.id,
                        status="skipped_existing",
                        payload={"reason": "already_imported"},
                    )
                    imported.append(existing)
                    continue
                detail = self.wallhaven_client.fetch_wallpaper(result_id, api_key=self.settings.wallhaven_api_key)
                downloaded_path = self.wallhaven_client.download_image(detail, target_root)
                provenance = WallpaperProvenance(
                    source_kind=WallpaperSourceKind.WALLHAVEN,
                    source_provider="wallhaven",
                    remote_id=detail.wallhaven_id,
                    source_url=detail.source_url or detail.wallhaven_url,
                    author_name=detail.uploader,
                    license_name="unknown",
                    imported_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    generator_tool=None,
                    parent_wallpaper_id=None,
                    metadata={
                        "wallhaven_url": detail.wallhaven_url,
                        "short_url": detail.short_url,
                        "image_url": detail.image_url,
                        "preview_url": detail.preview_url,
                        "purity": detail.purity,
                        "category": detail.category,
                        "resolution": detail.resolution,
                        "ratio": detail.ratio,
                        "tags": list(detail.tags),
                        "colors": list(detail.colors),
                    },
                )
                stored = self._index_file(
                    downloaded_path,
                    tags=detail.tags,
                    provenance=provenance,
                )
                self.repository.log_download(
                    provider="wallhaven",
                    remote_id=detail.wallhaven_id,
                    source_url=detail.source_url or detail.wallhaven_url,
                    destination_path=stored.path,
                    wallpaper_id=stored.id,
                    status="imported",
                    payload={"wallhaven_url": detail.wallhaven_url, "image_url": detail.image_url},
                )
                self.repository.log_operation(
                    "wallhaven_download",
                    stored.id,
                    {
                        "remote_id": detail.wallhaven_id,
                        "destination": str(stored.path),
                        "wallhaven_url": detail.wallhaven_url,
                        "source_url": detail.source_url,
                    },
                )
                imported.append(stored)
        return imported

    def save_gowall_preview_as_wallpaper(self, wallpaper_id: int, theme_id: str) -> Wallpaper:
        wallpaper = self.get_wallpaper(wallpaper_id)
        theme = self.gowall_client.theme_by_id(theme_id)
        if theme is None:
            raise KeyError(theme_id)
        preview = self.gowall_client.ensure_preview(wallpaper, theme)
        destination_dir = self.settings.library_root / "Derived" / "Gowall"
        destination_path = self._unique_destination(
            destination_dir / f"{wallpaper.path.stem}-{self._slugify(theme.display_name)}.png"
        )
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(preview.preview_path, destination_path)
        provenance = WallpaperProvenance(
            source_kind=WallpaperSourceKind.GOWALL_GENERATED,
            source_provider="gowall",
            source_url=None,
            author_name=None,
            license_name="unknown",
            imported_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            generator_tool=f"gowall:{theme.display_name}",
            parent_wallpaper_id=wallpaper.id,
            metadata={
                "theme_id": theme.id,
                "theme_name": theme.display_name,
                "source_wallpaper_id": wallpaper.id,
                "source_path": str(wallpaper.path),
                "preview_path": str(preview.preview_path),
            },
        )
        with self.repository.transaction():
            stored = self._index_file(destination_path, provenance=provenance)
            self.repository.log_operation(
                "save_gowall_preview",
                stored.id,
                {
                    "source_wallpaper_id": wallpaper.id,
                    "source_path": str(wallpaper.path),
                    "saved_path": str(stored.path),
                    "theme_id": theme.id,
                    "theme_name": theme.display_name,
                },
            )
        return stored

    def _import_inbox_files(self) -> int:
        inbox_root = self.settings.inbox_root
        if not inbox_root.exists():
            return 0
        image_paths = self.scanner.iter_image_paths(inbox_root)
        if not image_paths:
            return 0
        imported_count = 0
        target_root = self.settings.library_root / "Inbox"
        with self.repository.transaction():
            for image_path in image_paths:
                try:
                    relative_parent = image_path.parent.relative_to(inbox_root)
                except ValueError:
                    relative_parent = Path()
                destination = target_root / relative_parent / image_path.name
                self.mover.move(image_path, destination)
                imported_count += 1
            self.repository.log_operation(
                "import_inbox",
                payload={"source": str(inbox_root), "count": imported_count},
            )
        return imported_count

    def _index_file(
        self,
        path: Path,
        *,
        tags: tuple[str, ...] | list[str] = (),
        provenance: WallpaperProvenance | None = None,
    ) -> Wallpaper:
        existing = self.repository.get_wallpaper_by_path(path)
        scanned, _reused = self.scanner.scan_path(
            path,
            existing=existing,
            compute_hashes=self.settings.compute_hashes_on_scan,
        )
        if tags:
            scanned.tags = tuple(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))
        stored = self.repository.upsert_wallpaper(scanned)
        if stored.id is None:
            raise RuntimeError(f"Unable to index wallpaper: {path}")
        if provenance is None:
            self.repository.ensure_local_provenance(stored.id, imported_at=stored.added_at)
        else:
            self.repository.upsert_provenance(stored.id, provenance)
        refreshed = self.repository.get_wallpaper(stored.id)
        if refreshed is None:
            raise RuntimeError(f"Unable to reload indexed wallpaper: {path}")
        return refreshed

    def _unique_destination(self, destination: Path) -> Path:
        if not destination.exists():
            return destination
        stem = destination.stem
        suffix = destination.suffix
        counter = 2
        while True:
            candidate = destination.with_name(f"{stem}-{counter}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        return slug or "derived"

    def ensure_hashes_for_library(self) -> int:
        wallpapers = [wallpaper for wallpaper in self.list_wallpapers() if not wallpaper.sha256]
        if not wallpapers:
            return 0
        updated = 0
        with self.repository.transaction():
            for wallpaper in wallpapers:
                sha256 = compute_sha256(wallpaper.path)
                self.repository.set_hash(wallpaper.id or 0, sha256)
                updated += 1
            self.repository.log_operation("hash_library", payload={"count": updated})
        return updated

    def list_duplicate_groups(self, *, ensure_hashes: bool = False) -> list[DuplicateGroup]:
        if ensure_hashes:
            self.ensure_hashes_for_library()
        return self.repository.list_duplicate_groups()

    def duplicate_wallpaper_ids(self, *, ensure_hashes: bool = False) -> set[int]:
        ids: set[int] = set()
        for group in self.list_duplicate_groups(ensure_hashes=ensure_hashes):
            ids.update(group.wallpaper_ids)
        return ids

    def library_stats(self) -> LibraryStats:
        wallpapers = self.list_wallpapers()
        duplicate_ids = self.duplicate_wallpaper_ids()
        return LibraryStats(
            total=len(wallpapers),
            favorites=sum(1 for wallpaper in wallpapers if wallpaper.is_favorite),
            unviewed=sum(1 for wallpaper in wallpapers if wallpaper.times_viewed == 0),
            duplicates=len(duplicate_ids),
            folders=len(self.list_folders()),
        )

    def wallpapers_for_collection(self, collection: SmartCollection) -> list[Wallpaper]:
        wallpapers = self.repository.list_wallpapers_for_collection(collection, root_dir=self.settings.library_root)
        if collection != SmartCollection.RECENT:
            return wallpapers
        now = datetime.now(timezone.utc)
        recent_cutoff = now - timedelta(days=14)
        return [
            wallpaper
            for wallpaper in wallpapers
            if wallpaper.added_at and datetime.fromisoformat(wallpaper.added_at) >= recent_cutoff
        ]

    def get_wallpaper(self, wallpaper_id: int) -> Wallpaper:
        wallpaper = self.repository.get_wallpaper(wallpaper_id)
        if wallpaper is None:
            raise KeyError(wallpaper_id)
        return wallpaper

    def set_favorite(self, wallpaper_id: int, value: bool) -> Wallpaper:
        wallpaper = self.repository.set_favorite(wallpaper_id, value)
        self.connection.commit()
        self.repository.log_operation("favorite", wallpaper_id, {"value": value})
        self.connection.commit()
        return wallpaper

    def toggle_favorite(self, wallpaper_id: int) -> Wallpaper:
        wallpaper = self.get_wallpaper(wallpaper_id)
        return self.set_favorite(wallpaper_id, not wallpaper.is_favorite)

    def update_wallpaper_details(
        self,
        wallpaper_id: int,
        *,
        tags: list[str] | tuple[str, ...],
        notes: str,
        rating: int,
    ) -> Wallpaper:
        wallpaper = self.repository.update_wallpaper_details(
            wallpaper_id,
            tags=tags,
            notes=notes,
            rating=rating,
        )
        self.repository.log_operation(
            "update_details",
            wallpaper_id,
            {"tags": list(tags), "rating": rating},
        )
        self.connection.commit()
        return wallpaper

    def mark_viewed(self, wallpaper_id: int) -> Wallpaper:
        wallpaper = self.repository.mark_viewed(wallpaper_id)
        self.connection.commit()
        return wallpaper

    def ensure_hash(self, wallpaper_id: int) -> Wallpaper:
        wallpaper = self.get_wallpaper(wallpaper_id)
        if wallpaper.sha256:
            return wallpaper
        sha256 = compute_sha256(wallpaper.path)
        wallpaper = self.repository.set_hash(wallpaper_id, sha256)
        self.connection.commit()
        return wallpaper

    def move_wallpaper_to_directory(
        self,
        wallpaper_id: int,
        destination_dir: Path,
        *,
        conflict_strategy: str = "unique",
    ) -> Wallpaper:
        wallpaper = self.get_wallpaper(wallpaper_id)
        destination_dir = destination_dir.expanduser()
        destination = destination_dir / wallpaper.filename
        return self.move_wallpaper_to_path(wallpaper_id, destination, conflict_strategy=conflict_strategy)

    def move_wallpaper_to_path(
        self,
        wallpaper_id: int,
        destination: Path,
        *,
        conflict_strategy: str = "unique",
    ) -> Wallpaper:
        wallpaper = self.get_wallpaper(wallpaper_id)
        final_path = self.mover.move(
            wallpaper.path,
            destination,
            ensure_unique=conflict_strategy == "unique",
            overwrite=conflict_strategy == "overwrite",
        )
        moved = self.repository.move_wallpaper(wallpaper_id, final_path)
        self.repository.log_operation(
            "move",
            wallpaper_id,
            {"from": str(wallpaper.path), "to": str(final_path), "conflict_strategy": conflict_strategy},
        )
        self.connection.commit()
        return moved

    def rename_wallpaper(
        self,
        wallpaper_id: int,
        template: str,
        *,
        index: int | None = None,
        conflict_strategy: str = "unique",
    ) -> Wallpaper:
        wallpaper = self.get_wallpaper(wallpaper_id)
        new_name = self.render_rename_template(wallpaper, template, index=index)
        destination = wallpaper.path.with_name(f"{new_name}{wallpaper.extension}")
        return self.move_wallpaper_to_path(wallpaper_id, destination, conflict_strategy=conflict_strategy)

    def render_rename_template(self, wallpaper: Wallpaper, template: str, *, index: int | None = None) -> str:
        added_date = ""
        if wallpaper.added_at:
            try:
                added_date = datetime.fromisoformat(wallpaper.added_at).strftime("%Y%m%d")
            except ValueError:
                added_date = ""
        values = {
            "stem": wallpaper.path.stem,
            "filename": wallpaper.filename,
            "rating": wallpaper.rating,
            "tags": "-".join(wallpaper.tags) if wallpaper.tags else "untagged",
            "width": wallpaper.width or "",
            "height": wallpaper.height or "",
            "orientation": wallpaper.orientation.value,
            "date": added_date,
            "index": "" if index is None else str(index),
        }
        raw = template.format(**values).strip()
        raw = raw.removesuffix(wallpaper.extension)
        if not raw:
            raw = wallpaper.path.stem
        return re.sub(r"[^A-Za-z0-9._ -]+", "_", raw).strip(" .") or wallpaper.path.stem

    def delete_wallpaper(self, wallpaper_id: int) -> tuple[Wallpaper, TrashRecord]:
        wallpaper = self.get_wallpaper(wallpaper_id)
        trash_record = self.trash_manager.trash(wallpaper.path)
        self.repository.delete_wallpaper(wallpaper_id)
        self.repository.log_operation(
            "trash",
            wallpaper_id,
            {"from": str(wallpaper.path), "trash_path": str(trash_record.trashed_path)},
        )
        self.connection.commit()
        return wallpaper, trash_record

    def restore_wallpaper(self, wallpaper: Wallpaper, trash_record: TrashRecord) -> Wallpaper:
        restored_path = self.trash_manager.restore(trash_record)
        restored_wallpaper = replace(
            wallpaper,
            path=restored_path,
            filename=restored_path.name,
            extension=restored_path.suffix.lower(),
            folder_path=restored_path.parent,
        )
        restored = self.repository.restore_wallpaper(restored_wallpaper)
        self.repository.log_operation(
            "restore",
            restored.id,
            {"to": str(restored.path), "from_trash": str(trash_record.trashed_path)},
        )
        self.connection.commit()
        return restored

    def apply_wallpaper(self, wallpaper_id: int, monitor: str | None = None) -> Wallpaper:
        wallpaper = self.get_wallpaper(wallpaper_id)
        if wallpaper.media_kind is MediaKind.VIDEO:
            self.video_wallpaper_backend.apply(
                wallpaper.path,
                preset=self.settings.mpvpaper_preset,
                monitor=monitor,
            )
        else:
            self.video_wallpaper_backend.stop()
            self.wallpaper_backend.apply(wallpaper.path, monitor=monitor)
        self.repository.log_operation(
            "apply_wallpaper",
            wallpaper_id,
            {
                "path": str(wallpaper.path),
                "monitor": monitor,
                "media_kind": wallpaper.media_kind.value,
                "video_preset": self.settings.mpvpaper_preset if wallpaper.media_kind is MediaKind.VIDEO else None,
            },
        )
        self.connection.commit()
        return wallpaper

    def apply_gowall_theme(self, wallpaper_id: int, theme_id: str, monitor: str | None = None) -> Path:
        wallpaper = self.get_wallpaper(wallpaper_id)
        theme = self.gowall_client.theme_by_id(theme_id)
        if theme is None:
            raise KeyError(theme_id)
        preview = self.gowall_client.ensure_preview(wallpaper, theme)
        self.video_wallpaper_backend.stop()
        self.wallpaper_backend.apply(preview.preview_path, monitor=monitor)
        self.repository.log_operation(
            "apply_gowall_theme",
            wallpaper_id,
            {
                "source_path": str(wallpaper.path),
                "applied_path": str(preview.preview_path),
                "theme_id": theme.id,
                "theme_name": theme.display_name,
                "monitor": monitor,
            },
        )
        self.connection.commit()
        return preview.preview_path

    def apply_random_wallpaper(self, wallpaper_ids: list[int]) -> Wallpaper:
        if not wallpaper_ids:
            raise RuntimeError("No wallpaper available in current selection")
        wallpaper_id = random.choice(wallpaper_ids)
        return self.apply_wallpaper(wallpaper_id)
