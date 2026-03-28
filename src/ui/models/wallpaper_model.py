from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

from src.domain.enums import MediaKind, Orientation, SmartCollection, SortField, WallpaperSourceKind
from src.domain.models import Wallpaper


class WallpaperListModel(QAbstractListModel):
    WallpaperRole = Qt.ItemDataRole.UserRole + 1
    IdRole = WallpaperRole + 1
    OrientationRole = WallpaperRole + 2
    FavoriteRole = WallpaperRole + 3
    RatingRole = WallpaperRole + 4
    SearchableRole = WallpaperRole + 5
    PathRole = WallpaperRole + 6
    SourceRole = WallpaperRole + 7

    def __init__(self) -> None:
        super().__init__()
        self._wallpapers: list[Wallpaper] = []
        self._icon_cache: dict[str, QIcon] = {}
        self._placeholder_icon: QIcon | None = None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._wallpapers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        wallpaper = self._wallpapers[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return wallpaper.filename
        if role == Qt.ItemDataRole.DecorationRole:
            return self._icon_for(wallpaper)
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{wallpaper.filename}\n{wallpaper.path}"
        if role == Qt.ItemDataRole.FontRole and wallpaper.is_favorite:
            font = QFont()
            font.setBold(True)
            return font
        if role == Qt.ItemDataRole.ForegroundRole and wallpaper.is_favorite:
            return QColor("#ffd36a")
        if role == self.WallpaperRole:
            return wallpaper
        if role == self.IdRole:
            return wallpaper.id
        if role == self.OrientationRole:
            return wallpaper.orientation.value
        if role == self.FavoriteRole:
            return wallpaper.is_favorite
        if role == self.RatingRole:
            return wallpaper.rating
        if role == self.SearchableRole:
            return wallpaper.searchable_text
        if role == self.PathRole:
            return str(wallpaper.path)
        if role == self.SourceRole:
            if wallpaper.provenance is None:
                return WallpaperSourceKind.LOCAL.value
            return wallpaper.provenance.source_kind.value
        return None

    def set_wallpapers(self, wallpapers: list[Wallpaper]) -> None:
        self.beginResetModel()
        self._wallpapers = wallpapers
        self._icon_cache.clear()
        self.endResetModel()

    def wallpapers(self) -> list[Wallpaper]:
        return list(self._wallpapers)

    def wallpaper_at(self, row: int) -> Wallpaper | None:
        if 0 <= row < len(self._wallpapers):
            return self._wallpapers[row]
        return None

    def wallpaper_from_index(self, index: QModelIndex) -> Wallpaper | None:
        if not index.isValid():
            return None
        return self.wallpaper_at(index.row())

    def wallpaper_by_id(self, wallpaper_id: int) -> Wallpaper | None:
        for wallpaper in self._wallpapers:
            if wallpaper.id == wallpaper_id:
                return wallpaper
        return None

    def source_index_for_id(self, wallpaper_id: int) -> QModelIndex:
        for row, wallpaper in enumerate(self._wallpapers):
            if wallpaper.id == wallpaper_id:
                return self.index(row, 0)
        return QModelIndex()

    def update_wallpaper(self, wallpaper: Wallpaper) -> None:
        for row, current in enumerate(self._wallpapers):
            if current.id != wallpaper.id:
                continue
            self._wallpapers[row] = wallpaper
            self.dataChanged.emit(self.index(row, 0), self.index(row, 0))
            if wallpaper.thumbnail_path:
                self._icon_cache.pop(str(wallpaper.thumbnail_path), None)
            return

    def _icon_for(self, wallpaper: Wallpaper) -> QIcon:
        thumbnail_path = wallpaper.thumbnail_path
        if thumbnail_path and thumbnail_path.exists():
            cache_key = str(thumbnail_path)
            icon = self._icon_cache.get(cache_key)
            if icon is None:
                icon = QIcon(str(thumbnail_path))
                self._icon_cache[cache_key] = icon
            return icon
        return self._placeholder()

    def _placeholder(self) -> QIcon:
        if self._placeholder_icon is not None:
            return self._placeholder_icon
        pixmap = QPixmap(256, 256)
        pixmap.fill(QColor("#1f2329"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("#7d8590"))
        painter.drawRect(0, 0, 255, 255)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "No Preview")
        painter.end()
        self._placeholder_icon = QIcon(pixmap)
        return self._placeholder_icon


class WallpaperFilterProxyModel(QSortFilterProxyModel):
    def __init__(self) -> None:
        super().__init__()
        self.search_text = ""
        self.favorites_only = False
        self.orientation_filter: Orientation | None = None
        self.folder_filter: Path | None = None
        self.collection_filter: SmartCollection | None = None
        self.minimum_rating = 0
        self.sort_field = SortField.MTIME
        self.duplicate_ids: set[int] = set()
        self.source_filter: str | None = None
        self.setDynamicSortFilter(True)

    def set_search_text(self, value: str) -> None:
        self.search_text = value.strip().lower()
        self._refilter()

    def set_favorites_only(self, value: bool) -> None:
        self.favorites_only = value
        self._refilter()

    def set_orientation_filter(self, value: Orientation | None) -> None:
        self.orientation_filter = value
        self._refilter()

    def set_folder_filter(self, value: Path | None) -> None:
        self.folder_filter = value
        self._refilter()

    def set_collection_filter(self, value: SmartCollection | None) -> None:
        self.collection_filter = value
        self._refilter()

    def set_minimum_rating(self, value: int) -> None:
        self.minimum_rating = max(0, min(5, value))
        self._refilter()

    def set_duplicate_ids(self, value: set[int]) -> None:
        self.duplicate_ids = value
        self._refilter()

    def set_source_filter(self, value: str | None) -> None:
        self.source_filter = value or None
        self._refilter()

    def set_sort_field(self, value: SortField) -> None:
        self.sort_field = value
        self.invalidate()

    def _refilter(self) -> None:
        self.beginFilterChange()
        self.endFilterChange()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return False
        index = model.index(source_row, 0, source_parent)
        wallpaper = model.data(index, WallpaperListModel.WallpaperRole)
        if wallpaper is None:
            return False
        if self.search_text and self.search_text not in wallpaper.searchable_text:
            return False
        if self.favorites_only and not wallpaper.is_favorite:
            return False
        if self.orientation_filter and wallpaper.orientation != self.orientation_filter:
            return False
        if self.folder_filter and not str(wallpaper.path).startswith(str(self.folder_filter)):
            return False
        if wallpaper.rating < self.minimum_rating:
            return False
        if self.source_filter and not self._matches_source_filter(wallpaper):
            return False
        if self.collection_filter and not self._matches_collection(wallpaper, self.collection_filter):
            return False
        return True

    def _matches_source_filter(self, wallpaper: Wallpaper) -> bool:
        source_kind = (
            wallpaper.provenance.source_kind.value
            if wallpaper.provenance is not None
            else WallpaperSourceKind.LOCAL.value
        )
        return {
            "local": source_kind == WallpaperSourceKind.LOCAL.value,
            "wallhaven": source_kind == WallpaperSourceKind.WALLHAVEN.value,
            "manual": source_kind == WallpaperSourceKind.MANUAL_IMPORT.value,
            "gowall": source_kind == WallpaperSourceKind.GOWALL_GENERATED.value,
            "derived": source_kind == WallpaperSourceKind.DERIVED_EDIT.value,
        }.get(self.source_filter, True)

    def _matches_collection(self, wallpaper: Wallpaper, collection: SmartCollection) -> bool:
        searchable = wallpaper.searchable_text
        if collection == SmartCollection.FAVORITES:
            return wallpaper.is_favorite
        if collection == SmartCollection.VIDEOS:
            return wallpaper.media_kind is MediaKind.VIDEO
        if collection == SmartCollection.PORTRAITS:
            return wallpaper.orientation == Orientation.PORTRAIT
        if collection == SmartCollection.LANDSCAPES:
            return wallpaper.orientation == Orientation.LANDSCAPE
        if collection == SmartCollection.SQUARES:
            return wallpaper.orientation == Orientation.SQUARE
        if collection == SmartCollection.NEVER_VIEWED:
            return wallpaper.times_viewed == 0
        if collection == SmartCollection.TOP_RATED:
            return wallpaper.rating >= 4
        if collection == SmartCollection.DUPLICATES:
            return wallpaper.id in self.duplicate_ids
        if collection == SmartCollection.DARK:
            return wallpaper.brightness is not None and wallpaper.brightness < 96
        if collection == SmartCollection.ANIME:
            return any(token in searchable for token in ("anime", "manga"))
        if collection == SmartCollection.MINIMAL:
            return any(token in searchable for token in ("minimal", "clean", "simple"))
        if collection == SmartCollection.UNTAGGED:
            return not wallpaper.tags
        if collection == SmartCollection.RECENT:
            return wallpaper.added_at is not None
        if collection == SmartCollection.INBOX:
            return "inbox" in str(wallpaper.path).casefold()
        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return super().lessThan(left, right)
        left_item: Wallpaper = model.data(left, WallpaperListModel.WallpaperRole)
        right_item: Wallpaper = model.data(right, WallpaperListModel.WallpaperRole)
        if self.sort_field == SortField.NAME:
            return left_item.filename.casefold() < right_item.filename.casefold()
        if self.sort_field == SortField.SIZE:
            return left_item.size_bytes < right_item.size_bytes
        if self.sort_field == SortField.ORIENTATION:
            return left_item.orientation.value < right_item.orientation.value
        if self.sort_field == SortField.FAVORITE:
            return int(left_item.is_favorite) < int(right_item.is_favorite)
        if self.sort_field == SortField.RATING:
            return left_item.rating < right_item.rating
        if self.sort_field == SortField.VIEWS:
            return left_item.times_viewed < right_item.times_viewed
        if self.sort_field == SortField.BRIGHTNESS:
            left_brightness = left_item.brightness if left_item.brightness is not None else 255.0
            right_brightness = right_item.brightness if right_item.brightness is not None else 255.0
            return left_brightness < right_brightness
        return left_item.mtime < right_item.mtime
