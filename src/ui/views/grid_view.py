from __future__ import annotations

from PySide6.QtCore import QMimeData, QModelIndex, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QListView

from src.ui.models.wallpaper_model import WallpaperListModel


WALLPAPER_IDS_MIME = "application/x-wallmanager-wallpaper-ids"


class WallpaperGridView(QListView):
    open_requested = Signal(object)
    quick_preview_requested = Signal(object)
    current_proxy_index_changed = Signal(object)
    context_menu_requested = Signal(object)
    thumbnail_zoom_requested = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setWrapping(True)
        self.setSpacing(14)
        self.setIconSize(self.iconSize().expandedTo(self.iconSize()))
        self.setGridSize(self.gridSize())
        self.setWordWrap(True)
        self.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setMouseTracking(True)
        self.customContextMenuRequested.connect(self.context_menu_requested.emit)
        self.setDragEnabled(True)
        self.activated.connect(self.open_requested.emit)
        self.doubleClicked.connect(self.open_requested.emit)

    def currentChanged(self, current: QModelIndex, previous: QModelIndex) -> None:
        super().currentChanged(current, previous)
        self.current_proxy_index_changed.emit(current)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            current = self.currentIndex()
            if current.isValid():
                self.open_requested.emit(current)
                return
        if event.key() == Qt.Key.Key_Space:
            current = self.currentIndex()
            if current.isValid():
                self.quick_preview_requested.emit(current)
                return
        super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.thumbnail_zoom_requested.emit(1 if event.angleDelta().y() > 0 else -1)
            event.accept()
            return
        super().wheelEvent(event)

    def startDrag(self, supportedActions) -> None:
        model = self.model()
        if model is None:
            return
        ids: list[int] = []
        for index in self.selectionModel().selectedIndexes():
            wallpaper_id = model.data(index, WallpaperListModel.IdRole)
            if isinstance(wallpaper_id, int):
                ids.append(wallpaper_id)
        unique_ids = list(dict.fromkeys(ids))
        if not unique_ids:
            return
        mime_data = QMimeData()
        mime_data.setData(WALLPAPER_IDS_MIME, ",".join(str(item) for item in unique_ids).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        current = self.currentIndex()
        icon = model.data(current, Qt.ItemDataRole.DecorationRole)
        if icon is not None:
            pixmap = icon.pixmap(self.iconSize())
            if not pixmap.isNull():
                drag.setPixmap(pixmap)
        drag.exec(supportedActions, Qt.DropAction.MoveAction)
