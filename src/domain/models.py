from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from src.domain.enums import MediaKind, Orientation, WallpaperSourceKind


@dataclass(slots=True, frozen=True)
class WallpaperProvenance:
    source_kind: WallpaperSourceKind
    source_provider: str | None = None
    remote_id: str | None = None
    source_url: str | None = None
    author_name: str | None = None
    license_name: str | None = None
    imported_at: str | None = None
    generator_tool: str | None = None
    parent_wallpaper_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Folder:
    id: int | None
    path: Path
    name: str
    parent_id: int | None = None


@dataclass(slots=True)
class Wallpaper:
    id: int | None
    path: Path
    filename: str
    extension: str
    folder_id: int | None
    folder_path: Path | None
    width: int | None
    height: int | None
    orientation: Orientation
    aspect_ratio: float | None
    size_bytes: int
    mtime: float
    ctime: float
    media_kind: MediaKind = MediaKind.IMAGE
    sha256: str | None = None
    is_favorite: bool = False
    rating: int = 0
    notes: str = ""
    added_at: str | None = None
    indexed_at: str | None = None
    last_viewed_at: str | None = None
    times_viewed: int = 0
    tags: tuple[str, ...] = ()
    thumbnail_path: Path | None = None
    brightness: float | None = None
    avg_color: str | None = None
    duration_seconds: float | None = None
    provenance: WallpaperProvenance | None = None

    @property
    def searchable_text(self) -> str:
        provenance_values: list[str] = []
        if self.provenance is not None:
            provenance_values.extend(
                [
                    self.provenance.source_kind.value,
                    self.provenance.source_provider or "",
                    self.provenance.source_url or "",
                    self.provenance.author_name or "",
                    self.provenance.license_name or "",
                    self.provenance.generator_tool or "",
                ]
            )
        values = [
            self.filename,
            str(self.path),
            self.notes,
            self.media_kind.value,
            self.orientation.value,
            " ".join(self.tags),
            self.avg_color or "",
            *provenance_values,
        ]
        return " ".join(part for part in values if part).lower()


@dataclass(slots=True)
class OperationLogEntry:
    id: int
    action: str
    wallpaper_id: int | None
    payload_json: str
    created_at: str


@dataclass(slots=True, frozen=True)
class DownloadRecord:
    id: int
    provider: str
    remote_id: str | None
    source_url: str | None
    destination_path: Path | None
    wallpaper_id: int | None
    status: str
    created_at: str
    payload_json: str


@dataclass(slots=True)
class TrashRecord:
    original_path: Path
    trashed_path: Path
    info_path: Path
    deletion_date: str


@dataclass(slots=True)
class ScanResult:
    wallpapers: list[Wallpaper] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    imported_count: int = 0
    updated_count: int = 0
    reused_count: int = 0


@dataclass(slots=True)
class ScanSummary:
    scanned_count: int
    imported_count: int
    updated_count: int
    reused_count: int
    removed_count: int
    inbox_imported_count: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class DuplicateGroup:
    sha256: str
    wallpaper_ids: tuple[int, ...]


@dataclass(slots=True)
class LibraryStats:
    total: int
    favorites: int
    unviewed: int
    duplicates: int
    folders: int


@dataclass(slots=True, frozen=True)
class LibrarySelection:
    kind: str
    value: str | None = None
    label: str = ""


@dataclass(slots=True, frozen=True)
class WallpaperBackendOption:
    backend_id: str
    display_name: str
    available: bool
    reason: str


@dataclass(slots=True, frozen=True)
class WallpaperBackendStatus:
    preferred_id: str
    active_id: str
    active_display_name: str
    available: bool
    session_type: str
    desktop_environment: str
    message: str
    options: tuple[WallpaperBackendOption, ...] = ()


@dataclass(slots=True, frozen=True)
class VideoWallpaperBackendStatus:
    active_id: str
    active_display_name: str
    available: bool
    session_type: str
    desktop_environment: str
    message: str


@dataclass(slots=True, frozen=True)
class GowallStatus:
    installed: bool
    version: str | None
    executable_path: Path | None
    message: str


@dataclass(slots=True, frozen=True)
class GowallTheme:
    id: str
    display_name: str
    source_kind: Literal["gowall_name", "json_file"]
    theme_arg: str
    origin_label: str


@dataclass(slots=True, frozen=True)
class GowallPreviewResult:
    theme_id: str
    preview_path: Path
    display_name: str


@dataclass(slots=True, frozen=True)
class WallhavenStatus:
    available: bool
    api_key_configured: bool
    message: str
    rate_limit_per_minute: int = 45


@dataclass(slots=True, frozen=True)
class WallhavenSearchRequest:
    query: str = ""
    page: int = 1
    purity: str = "100"
    ratios: str = ""
    atleast: str = ""
    blacklist: str = ""


@dataclass(slots=True, frozen=True)
class WallhavenSearchResult:
    wallhaven_id: str
    wallhaven_url: str
    short_url: str
    image_url: str
    preview_url: str
    source_url: str | None
    uploader: str | None
    category: str
    purity: str
    resolution: str
    ratio: str
    width: int | None
    height: int | None
    file_size: int | None
    file_type: str | None
    created_at: str | None
    tags: tuple[str, ...] = ()
    colors: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class WallhavenSearchPage:
    request: WallhavenSearchRequest
    results: tuple[WallhavenSearchResult, ...]
    current_page: int
    last_page: int
    total: int
