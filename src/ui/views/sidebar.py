from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QLabel, QLineEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from src.domain.enums import SmartCollection
from src.domain.models import Folder
from src.i18n import smart_collection_label, tr
from src.ui.views.grid_view import WALLPAPER_IDS_MIME


class SidebarTreeWidget(QTreeWidget):
    wallpaper_drop_requested = Signal(list, object)
    item_context_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.item_context_requested.emit)

    def dragEnterEvent(self, event) -> None:
        if self._drop_target_selection(event.position().toPoint()) is not None and event.mimeData().hasFormat(WALLPAPER_IDS_MIME):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if self._drop_target_selection(event.position().toPoint()) is not None and event.mimeData().hasFormat(WALLPAPER_IDS_MIME):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        target_selection = self._drop_target_selection(event.position().toPoint())
        if target_selection is None or not event.mimeData().hasFormat(WALLPAPER_IDS_MIME):
            super().dropEvent(event)
            return
        raw = bytes(event.mimeData().data(WALLPAPER_IDS_MIME)).decode("utf-8")
        ids = [int(part) for part in raw.split(",") if part.strip()]
        if ids:
            self.wallpaper_drop_requested.emit(ids, Path(target_selection[1]))
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def _drop_target_selection(self, point) -> tuple[str, str | None] | None:
        item = self.itemAt(point)
        if item is None:
            return None
        selection = item.data(0, Qt.ItemDataRole.UserRole)
        if not selection or selection[0] != "folder" or not selection[1]:
            return None
        return selection


class SidebarPanel(QWidget):
    selection_changed = Signal(object)
    context_menu_requested = Signal(object)
    wallpaper_drop_requested = Signal(object, object)

    def __init__(self) -> None:
        super().__init__()
        self._stats = (0, 0, 0, 0)
        self.stats_label = QLabel()
        self.favorites_label = QLabel()
        self.unviewed_label = QLabel()
        self.duplicates_label = QLabel()
        for label in (self.stats_label, self.favorites_label, self.unviewed_label, self.duplicates_label):
            label.setObjectName("sidebarStatBadge")
        self.filter_input = QLineEdit()
        self.tree = SidebarTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemSelectionChanged.connect(self._emit_selection)
        self.tree.item_context_requested.connect(self.context_menu_requested.emit)
        self.tree.wallpaper_drop_requested.connect(self.wallpaper_drop_requested.emit)
        self.filter_input.textChanged.connect(self._apply_tree_filter)

        layout = QVBoxLayout(self)
        layout.addWidget(self.stats_label)
        layout.addWidget(self.favorites_label)
        layout.addWidget(self.unviewed_label)
        layout.addWidget(self.duplicates_label)
        layout.addWidget(self.filter_input)
        layout.addWidget(self.tree, stretch=1)
        self.refresh_language()

    def refresh_language(self) -> None:
        self.filter_input.setPlaceholderText(tr("Filtrer dossiers et collections"))
        self.update_stats(*self._stats)

    def populate(self, root_dir, folders: list[Folder], *, selected_key: tuple[str, str | None] | None = None) -> None:
        with QSignalBlocker(self.tree):
            self.tree.clear()
            all_item = QTreeWidgetItem([tr("Toute la bibliotheque")])
            all_item.setData(0, Qt.ItemDataRole.UserRole, ("all", None))
            self.tree.addTopLevelItem(all_item)

            collections_item = QTreeWidgetItem([tr("Collections intelligentes")])
            self.tree.addTopLevelItem(collections_item)
            collection_items: list[QTreeWidgetItem] = []
            for collection in (
                SmartCollection.FAVORITES,
                SmartCollection.VIDEOS,
                SmartCollection.PORTRAITS,
                SmartCollection.LANDSCAPES,
                SmartCollection.SQUARES,
                SmartCollection.NEVER_VIEWED,
                SmartCollection.TOP_RATED,
                SmartCollection.DUPLICATES,
                SmartCollection.DARK,
                SmartCollection.ANIME,
                SmartCollection.MINIMAL,
                SmartCollection.UNTAGGED,
                SmartCollection.RECENT,
                SmartCollection.INBOX,
            ):
                item = QTreeWidgetItem([smart_collection_label(collection)])
                item.setData(0, Qt.ItemDataRole.UserRole, ("collection", collection.value))
                collections_item.addChild(item)
                collection_items.append(item)

            folders_root_item = QTreeWidgetItem([root_dir.name or str(root_dir)])
            folders_root_item.setData(0, Qt.ItemDataRole.UserRole, ("folder", str(root_dir)))
            self.tree.addTopLevelItem(folders_root_item)

            items_by_key: dict[tuple[str, ...], QTreeWidgetItem] = {(): folders_root_item}
            relevant = [folder for folder in folders if folder.path != root_dir]
            for folder in relevant:
                try:
                    parts = folder.path.relative_to(root_dir).parts
                except ValueError:
                    continue
                parent_key: tuple[str, ...] = ()
                for index, part in enumerate(parts, start=1):
                    key = parts[:index]
                    if key in items_by_key:
                        parent_key = key
                        continue
                    item = QTreeWidgetItem([part])
                    folder_path = root_dir.joinpath(*key)
                    item.setData(0, Qt.ItemDataRole.UserRole, ("folder", str(folder_path)))
                    items_by_key[parent_key].addChild(item)
                    items_by_key[key] = item
                    parent_key = key

            self.tree.expandToDepth(2)

            selected_item = all_item
            if selected_key is not None:
                for item in [all_item, *collection_items, folders_root_item, *items_by_key.values()]:
                    if item.data(0, Qt.ItemDataRole.UserRole) == selected_key:
                        selected_item = item
                        break
            self.tree.setCurrentItem(selected_item)

        self._emit_selection()
        self._apply_tree_filter(self.filter_input.text())

    def update_stats(self, total: int, favorites: int, unviewed: int, duplicates: int) -> None:
        self._stats = (total, favorites, unviewed, duplicates)
        self.stats_label.setText(tr("{count} wallpapers", count=total))
        self.favorites_label.setText(tr("{count} favoris", count=favorites))
        self.unviewed_label.setText(tr("{count} non vus", count=unviewed))
        self.duplicates_label.setText(tr("{count} doublons", count=duplicates))

    def selection_at(self, point) -> tuple[str, str | None] | None:
        item = self.tree.itemAt(point)
        if item is None:
            return None
        selection = item.data(0, Qt.ItemDataRole.UserRole)
        return selection if selection else None

    def select_key(self, key: tuple[str, str | None]) -> None:
        for item in self._iter_items():
            if item.data(0, Qt.ItemDataRole.UserRole) == key:
                self.tree.setCurrentItem(item)
                self._emit_selection()
                return

    def _iter_items(self):
        stack = [self.tree.topLevelItem(index) for index in range(self.tree.topLevelItemCount())]
        while stack:
            item = stack.pop(0)
            if item is None:
                continue
            yield item
            for index in range(item.childCount()):
                stack.append(item.child(index))

    def _apply_tree_filter(self, text: str) -> None:
        query = text.strip().casefold()
        with QSignalBlocker(self.tree):
            for index in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(index)
                if item is None:
                    continue
                self._filter_item(item, query)
        if query:
            self.tree.expandAll()
        else:
            self.tree.expandToDepth(2)

    def _filter_item(self, item: QTreeWidgetItem, query: str) -> bool:
        label = item.text(0).casefold()
        direct_match = not query or query in label
        child_match = False
        for index in range(item.childCount()):
            child = item.child(index)
            if child is not None and self._filter_item(child, query):
                child_match = True
        visible = direct_match or child_match
        item.setHidden(not visible)
        return visible

    def _emit_selection(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            self.selection_changed.emit(("all", None))
            return
        selection = item.data(0, Qt.ItemDataRole.UserRole)
        if not selection:
            selection = ("all", None)
        self.selection_changed.emit(selection)
