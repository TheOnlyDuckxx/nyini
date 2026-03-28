from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.domain.models import Wallpaper
from src.i18n import tr, yes_no


@dataclass(slots=True)
class DuplicateReviewGroup:
    sha256: str
    wallpapers: list[Wallpaper]


def duplicate_keep_score(wallpaper: Wallpaper) -> float:
    width = wallpaper.width or 0
    height = wallpaper.height or 0
    pixels = width * height
    aspect = wallpaper.aspect_ratio or 0.0
    widescreen_distance = min(abs(aspect - (16 / 9)), abs(aspect - (9 / 16))) if aspect else 2.0
    ratio_bonus = max(0.0, 200_000.0 - widescreen_distance * 100_000.0)
    return pixels + (wallpaper.rating * 5_000_000.0) + (wallpaper.times_viewed * 750_000.0) + (2_500_000.0 if wallpaper.is_favorite else 0.0) + ratio_bonus


class DuplicateReviewDialog(QDialog):
    def __init__(self, groups: list[DuplicateReviewGroup], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Revue des doublons"))
        self.resize(1180, 720)
        self.groups = groups
        self.selected_ids_to_delete: list[int] = []
        self._active_group_index: int | None = None
        self._delete_state: dict[str, set[int]] = {
            group.sha256: {
                wallpaper.id
                for wallpaper in group.wallpapers
                if wallpaper.id is not None and wallpaper.id != self._recommended_wallpaper(group).id
            }
            for group in groups
        }

        self.group_list = QListWidget()
        self.group_list.currentRowChanged.connect(self._set_group_index)

        self.recommendation_label = QLabel(tr("Aucun doublon"))
        self.recommendation_label.setWordWrap(True)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [tr("Suppr."), tr("Apercu"), tr("Fichier"), tr("Resolution"), tr("Note"), tr("Vues"), tr("Favori"), tr("Score")]
        )
        self.table.horizontalHeader().setStretchLastSection(True)

        self.keep_recommended_button = QPushButton(tr("Conserver recommande"))
        self.clear_checks_button = QPushButton(tr("Tout decocher"))
        self.delete_button = QPushButton(tr("Supprimer coches"))
        self.keep_recommended_button.clicked.connect(self._select_recommended_strategy)
        self.clear_checks_button.clicked.connect(self._clear_checks)
        self.delete_button.clicked.connect(self._accept_with_selection)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel(tr("Groupes")))
        left_layout.addWidget(self.group_list)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(self.recommendation_label)
        right_layout.addWidget(self.table, stretch=1)
        actions = QHBoxLayout()
        actions.addWidget(self.keep_recommended_button)
        actions.addWidget(self.clear_checks_button)
        actions.addStretch(1)
        actions.addWidget(self.delete_button)
        right_layout.addLayout(actions)

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([280, 900])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        self._populate_groups()

    def _populate_groups(self) -> None:
        for group in self.groups:
            recommended = self._recommended_wallpaper(group)
            label = tr("{filename} ({count} fichiers)", filename=recommended.filename, count=len(group.wallpapers))
            item = QListWidgetItem(label)
            item.setData(256, group.sha256)
            self.group_list.addItem(item)
        if self.groups:
            self.group_list.setCurrentRow(0)

    def _set_group_index(self, row: int) -> None:
        if self._active_group_index is not None:
            self._store_group_state(self._active_group_index)
        if row < 0 or row >= len(self.groups):
            self.table.setRowCount(0)
            self._active_group_index = None
            return
        self._active_group_index = row
        group = self.groups[row]
        recommended = self._recommended_wallpaper(group)
        self.recommendation_label.setText(
            tr(
                "Recommandation: conserver `{filename}` (score {score}) et verifier les autres avant suppression.",
                filename=recommended.filename,
                score=f"{duplicate_keep_score(recommended):.0f}",
            )
        )
        self.table.setRowCount(len(group.wallpapers))
        delete_ids = self._delete_state[group.sha256]
        for row_index, wallpaper in enumerate(group.wallpapers):
            check_item = QTableWidgetItem()
            check_item.setFlags(check_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            should_delete = wallpaper.id is not None and wallpaper.id in delete_ids
            check_item.setCheckState(Qt.CheckState.Checked if should_delete else Qt.CheckState.Unchecked)
            check_item.setData(Qt.ItemDataRole.UserRole, wallpaper.id)
            self.table.setItem(row_index, 0, check_item)

            icon_item = QTableWidgetItem()
            icon_item.setIcon(self._preview_icon(wallpaper))
            self.table.setItem(row_index, 1, icon_item)
            self.table.setItem(row_index, 2, QTableWidgetItem(wallpaper.filename))
            resolution = f"{wallpaper.width or '-'} x {wallpaper.height or '-'}"
            self.table.setItem(row_index, 3, QTableWidgetItem(resolution))
            self.table.setItem(row_index, 4, QTableWidgetItem(str(wallpaper.rating)))
            self.table.setItem(row_index, 5, QTableWidgetItem(str(wallpaper.times_viewed)))
            self.table.setItem(row_index, 6, QTableWidgetItem(yes_no(wallpaper.is_favorite)))
            self.table.setItem(row_index, 7, QTableWidgetItem(f"{duplicate_keep_score(wallpaper):.0f}"))
        self.table.resizeColumnsToContents()

    def _preview_icon(self, wallpaper: Wallpaper) -> QIcon:
        if wallpaper.thumbnail_path and wallpaper.thumbnail_path.exists():
            return QIcon(str(wallpaper.thumbnail_path))
        pixmap = QPixmap(96, 96)
        pixmap.fill()
        return QIcon(pixmap)

    def _recommended_wallpaper(self, group: DuplicateReviewGroup) -> Wallpaper:
        return max(group.wallpapers, key=duplicate_keep_score)

    def _store_group_state(self, index: int) -> None:
        if index < 0 or index >= len(self.groups):
            return
        group = self.groups[index]
        delete_ids: set[int] = set()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None or item.checkState() != Qt.CheckState.Checked:
                continue
            wallpaper_id = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(wallpaper_id, int):
                delete_ids.add(wallpaper_id)
        self._delete_state[group.sha256] = delete_ids

    def _store_current_group_state(self) -> None:
        if self._active_group_index is None:
            return
        self._store_group_state(self._active_group_index)

    def _select_recommended_strategy(self) -> None:
        index = self.group_list.currentRow()
        if index < 0 or index >= len(self.groups):
            return
        group = self.groups[index]
        recommended_id = self._recommended_wallpaper(group).id
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None:
                continue
            wallpaper_id = item.data(Qt.ItemDataRole.UserRole)
            should_delete = wallpaper_id is not None and wallpaper_id != recommended_id
            item.setCheckState(Qt.CheckState.Checked if should_delete else Qt.CheckState.Unchecked)
        self._store_current_group_state()

    def _clear_checks(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Unchecked)
        self._store_current_group_state()

    def _accept_with_selection(self) -> None:
        self._store_current_group_state()
        ids: list[int] = []
        for group in self.groups:
            ids.extend(sorted(self._delete_state[group.sha256]))
        self.selected_ids_to_delete = list(dict.fromkeys(ids))
        self.accept()
