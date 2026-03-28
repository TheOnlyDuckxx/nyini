from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping

from src.domain.models import ScanResult, Wallpaper
from src.infrastructure.db.repositories import utc_now_iso
from src.infrastructure.imaging.hashing import compute_sha256
from src.infrastructure.imaging.metadata import SUPPORTED_EXTENSIONS, extract_media_metadata
from src.infrastructure.imaging.thumbnails import ThumbnailManager


ProgressCallback = Callable[[int, int, str], None]


class LibraryScanner:
    def __init__(self, thumbnail_manager: ThumbnailManager) -> None:
        self.thumbnail_manager = thumbnail_manager

    def iter_image_paths(self, root_dir: Path) -> list[Path]:
        if not root_dir.exists():
            return []
        return sorted(
            path
            for path in root_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )

    def scan(
        self,
        root_dir: Path,
        *,
        existing_index: Mapping[str, Wallpaper] | None = None,
        progress_callback: ProgressCallback | None = None,
        compute_hashes: bool = False,
    ) -> ScanResult:
        result = ScanResult()
        existing_index = existing_index or {}
        image_paths = self.iter_image_paths(root_dir)
        total = len(image_paths)

        for position, image_path in enumerate(image_paths, start=1):
            if progress_callback is not None:
                progress_callback(position, total, str(image_path))

            existing = existing_index.get(str(image_path))
            try:
                wallpaper, reused = self.scan_path(
                    image_path,
                    existing=existing,
                    compute_hashes=compute_hashes,
                )
                result.wallpapers.append(wallpaper)
                if reused:
                    result.reused_count += 1
                elif existing is None:
                    result.imported_count += 1
                else:
                    result.updated_count += 1
            except Exception as exc:
                result.errors.append(f"{image_path}: {exc}")
        return result

    def scan_path(
        self,
        image_path: Path,
        *,
        existing: Wallpaper | None = None,
        compute_hashes: bool = False,
    ) -> tuple[Wallpaper, bool]:
        stat = image_path.stat()
        thumbnail_path = self.thumbnail_manager.ensure_thumbnail(
            image_path,
            mtime=stat.st_mtime,
            size_bytes=stat.st_size,
        )
        unchanged = (
            existing is not None
            and existing.mtime == stat.st_mtime
            and existing.size_bytes == stat.st_size
        )
        if unchanged:
            if not thumbnail_path.exists():
                thumbnail_path = self.thumbnail_manager.ensure_thumbnail(
                    image_path,
                    mtime=stat.st_mtime,
                    size_bytes=stat.st_size,
                )
            existing.thumbnail_path = thumbnail_path
            existing.indexed_at = utc_now_iso()
            return existing, True

        metadata = extract_media_metadata(image_path)
        sha256 = existing.sha256 if existing and unchanged else None
        if compute_hashes and sha256 is None:
            sha256 = compute_sha256(image_path)
        wallpaper = Wallpaper(
            id=existing.id if existing else None,
            path=image_path,
            filename=image_path.name,
            extension=image_path.suffix.lower(),
            folder_id=existing.folder_id if existing else None,
            folder_path=image_path.parent,
            width=metadata.width,
            height=metadata.height,
            orientation=metadata.orientation,
            aspect_ratio=metadata.aspect_ratio,
            size_bytes=metadata.size_bytes,
            mtime=metadata.mtime,
            ctime=metadata.ctime,
            media_kind=metadata.media_kind,
            sha256=sha256,
            is_favorite=existing.is_favorite if existing else False,
            rating=existing.rating if existing else 0,
            notes=existing.notes if existing else "",
            added_at=existing.added_at if existing else utc_now_iso(),
            indexed_at=utc_now_iso(),
            last_viewed_at=existing.last_viewed_at if existing else None,
            times_viewed=existing.times_viewed if existing else 0,
            tags=existing.tags if existing else (),
            thumbnail_path=thumbnail_path,
            brightness=metadata.brightness,
            avg_color=metadata.avg_color,
            duration_seconds=metadata.duration_seconds,
            provenance=existing.provenance if existing else None,
        )
        return wallpaper, False
