from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.application.services import WallManagerService
from src.domain.models import GowallPreviewResult, GowallStatus, GowallTheme, Wallpaper
from src.i18n import tr
from src.workers.gowall_preview_worker import GowallPreviewWorker
from src.workers.job_queue import BackgroundJobQueue


class GowallThemeDialog(QDialog):
    THEME_ID_ROLE = Qt.ItemDataRole.UserRole
    PREVIEW_PATH_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(
        self,
        service: WallManagerService,
        job_queue: BackgroundJobQueue,
        wallpaper: Wallpaper,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Themes Gowall"))
        self.resize(1320, 860)
        self.service = service
        self.job_queue = job_queue
        self.wallpaper = wallpaper
        self.gowall_status: GowallStatus = self.service.get_gowall_status()
        self.themes: list[GowallTheme] = []
        self.items_by_theme_id: dict[str, QListWidgetItem] = {}
        self.applied_output_path: Path | None = None
        self.saved_wallpaper = None
        self._current_job_id: str | None = None
        self._is_generating = False

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.progress_label = QLabel(tr("Aucune preview generee"))
        self.progress_label.setWordWrap(True)

        self.import_button = QPushButton(tr("Importer un theme JSON"))
        self.refresh_button = QPushButton(tr("Rafraichir les themes"))
        self.apply_button = QPushButton(tr("Appliquer"))
        self.save_button = QPushButton(tr("Sauvegarder dans la bibliotheque"))
        self.close_button = QPushButton(tr("Fermer"))
        self.import_button.clicked.connect(self.import_theme_json)
        self.refresh_button.clicked.connect(self.refresh_themes)
        self.apply_button.clicked.connect(self.apply_selected_theme)
        self.save_button.clicked.connect(self.save_selected_theme)
        self.close_button.clicked.connect(self.reject)
        self.apply_button.setEnabled(False)
        self.save_button.setEnabled(False)

        self.theme_list = QListWidget()
        self.theme_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.theme_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.theme_list.setMovement(QListWidget.Movement.Static)
        self.theme_list.setWrapping(True)
        self.theme_list.setWordWrap(True)
        self.theme_list.setSpacing(12)
        self.theme_list.setIconSize(QSize(240, 136))
        self.theme_list.setGridSize(QSize(270, 210))
        self.theme_list.currentItemChanged.connect(self._on_current_item_changed)
        self.theme_list.itemDoubleClicked.connect(lambda _item: self.apply_selected_theme())

        self.preview_label = QLabel(tr("Selectionne un theme"))
        self.preview_label.setObjectName("viewerCanvas")
        self.preview_label.setMinimumSize(420, 240)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_name_label = QLabel(tr("Aucun theme"))
        self.preview_name_label.setObjectName("detailsTitle")
        self.preview_meta_label = QLabel("")
        self.preview_meta_label.setWordWrap(True)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(self.status_label)
        left_layout.addWidget(self.progress_label)
        controls = QHBoxLayout()
        controls.addWidget(self.import_button)
        controls.addWidget(self.refresh_button)
        controls.addStretch(1)
        left_layout.addLayout(controls)
        left_layout.addWidget(self.theme_list, stretch=1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(self.preview_label)
        right_layout.addWidget(self.preview_name_label)
        right_layout.addWidget(self.preview_meta_label)
        right_layout.addStretch(1)
        right_actions = QHBoxLayout()
        right_actions.addStretch(1)
        right_actions.addWidget(self.apply_button)
        right_actions.addWidget(self.save_button)
        right_actions.addWidget(self.close_button)
        right_layout.addLayout(right_actions)

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([830, 460])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        self._reload_themes(generate=True)

    def refresh_themes(self) -> None:
        self._reload_themes(generate=True)

    def import_theme_json(self) -> None:
        path_str, _selected_filter = QFileDialog.getOpenFileName(
            self,
            tr("Importer un theme JSON"),
            str(Path.home()),
            tr("Themes JSON (*.json)"),
        )
        if not path_str:
            return
        source_path = Path(path_str)
        try:
            theme = self.service.import_gowall_theme_json(source_path)
        except FileExistsError as exc:
            destination = Path(exc.args[0])
            replace = QMessageBox.question(
                self,
                tr("Theme existant"),
                tr("Le theme `{theme_name}` existe deja. Le remplacer ?", theme_name=destination.stem),
            )
            if replace != QMessageBox.StandardButton.Yes:
                return
            theme = self.service.import_gowall_theme_json(source_path, overwrite=True)
        except Exception as exc:
            QMessageBox.critical(self, tr("Import impossible"), str(exc))
            return

        self._reload_themes(generate=False, selected_theme_id=theme.id)
        self._start_generation(theme_ids=[theme.id])

    def apply_selected_theme(self) -> None:
        item = self.theme_list.currentItem()
        if item is None or self.wallpaper.id is None:
            return
        theme_id = item.data(self.THEME_ID_ROLE)
        if not isinstance(theme_id, str):
            return
        try:
            self.applied_output_path = self.service.apply_gowall_theme(self.wallpaper.id, theme_id)
        except Exception as exc:
            QMessageBox.critical(self, tr("Application impossible"), str(exc))
            return
        self.accept()

    def save_selected_theme(self) -> None:
        item = self.theme_list.currentItem()
        if item is None or self.wallpaper.id is None:
            return
        theme_id = item.data(self.THEME_ID_ROLE)
        if not isinstance(theme_id, str):
            return
        try:
            self.saved_wallpaper = self.service.save_gowall_preview_as_wallpaper(self.wallpaper.id, theme_id)
        except Exception as exc:
            QMessageBox.critical(self, tr("Sauvegarde impossible"), str(exc))
            return
        self.accept()

    def _reload_themes(self, *, generate: bool, selected_theme_id: str | None = None) -> None:
        self.gowall_status = self.service.get_gowall_status()
        self.status_label.setText(self.gowall_status.message)
        self.import_button.setEnabled(self.gowall_status.installed and not self._is_generating)
        self.refresh_button.setEnabled(self.gowall_status.installed and not self._is_generating)
        self.theme_list.clear()
        self.items_by_theme_id.clear()
        self.themes = self.service.list_gowall_themes() if self.gowall_status.installed else []
        if not self.themes:
            self.progress_label.setText(tr("Aucun theme disponible"))
        for theme in self.themes:
            item = QListWidgetItem(f"{theme.display_name}\n{theme.origin_label}")
            item.setData(self.THEME_ID_ROLE, theme.id)
            cached = self.service.gowall_client.preview_path_for(self.wallpaper, theme)
            if cached.exists():
                item.setData(self.PREVIEW_PATH_ROLE, str(cached))
                item.setIcon(QIcon(str(cached)))
            else:
                item.setIcon(self._placeholder_icon())
            item.setToolTip(tr("{origin_label} · {name}", origin_label=theme.origin_label, name=theme.display_name))
            self.theme_list.addItem(item)
            self.items_by_theme_id[theme.id] = item

        if selected_theme_id and selected_theme_id in self.items_by_theme_id:
            self.theme_list.setCurrentItem(self.items_by_theme_id[selected_theme_id])
        elif self.theme_list.count() > 0:
            self.theme_list.setCurrentRow(0)
        else:
            self._set_preview_state(None, None)

        if generate and self.gowall_status.installed and self.themes:
            self._start_generation()

    def _start_generation(self, *, theme_ids: list[str] | None = None) -> None:
        if self._is_generating:
            return
        themes = self.themes
        if theme_ids is not None:
            requested = set(theme_ids)
            themes = [theme for theme in themes if theme.id in requested]
        if not themes:
            return
        self._is_generating = True
        self.import_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.progress_label.setText(tr("Generation de {count} preview(s)...", count=len(themes)))
        worker = GowallPreviewWorker(self.service.gowall_client, self.wallpaper, themes)
        worker.signals.preview_ready.connect(self._on_preview_ready)
        worker.signals.theme_failed.connect(self._on_theme_failed)
        worker.signals.progress.connect(self._on_generation_progress)
        worker.signals.finished.connect(self._on_generation_finished)
        worker.signals.failed.connect(self._on_generation_failed)
        self._current_job_id = self.job_queue.submit(
            "gowall-preview",
            worker,
            description=f"Previews Gowall: {self.wallpaper.filename}",
        )

    def _on_generation_progress(self, current: int, total: int, theme_name: str) -> None:
        message = tr("Preview {current}/{total}: {theme_name}", current=current, total=max(total, 1), theme_name=theme_name)
        self.progress_label.setText(message)
        if self._current_job_id is not None:
            self.job_queue.update_message(self._current_job_id, message)

    def _on_preview_ready(self, result: GowallPreviewResult) -> None:
        item = self.items_by_theme_id.get(result.theme_id)
        if item is None:
            return
        item.setData(self.PREVIEW_PATH_ROLE, str(result.preview_path))
        item.setIcon(QIcon(str(result.preview_path)))
        if item is self.theme_list.currentItem():
            theme = self._theme_for_item(item)
            self._set_preview_state(theme, result.preview_path)

    def _on_theme_failed(self, theme_id: str, message: str) -> None:
        item = self.items_by_theme_id.get(theme_id)
        if item is None:
            return
        item.setToolTip(f"{item.toolTip()}\n{tr('Erreur: {message}', message=message)}")

    def _on_generation_finished(self, payload: object) -> None:
        self._is_generating = False
        self.import_button.setEnabled(self.gowall_status.installed)
        self.refresh_button.setEnabled(self.gowall_status.installed)
        self.save_button.setEnabled(self.gowall_status.installed and self.theme_list.currentItem() is not None)
        errors = []
        if isinstance(payload, dict):
            errors = payload.get("errors", [])
        if errors:
            self.progress_label.setText(tr("Generation terminee avec {count} erreur(s)", count=len(errors)))
        else:
            self.progress_label.setText(tr("Generation terminee"))
        self._current_job_id = None

    def _on_generation_failed(self, message: str) -> None:
        self._is_generating = False
        self.import_button.setEnabled(self.gowall_status.installed)
        self.refresh_button.setEnabled(self.gowall_status.installed)
        self.save_button.setEnabled(self.gowall_status.installed and self.theme_list.currentItem() is not None)
        self.progress_label.setText(tr("Echec: {message}", message=message))
        self._current_job_id = None

    def _on_current_item_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        theme = self._theme_for_item(current)
        preview_path = None
        if current is not None:
            raw_preview_path = current.data(self.PREVIEW_PATH_ROLE)
            if isinstance(raw_preview_path, str):
                preview_path = Path(raw_preview_path)
        self._set_preview_state(theme, preview_path)

    def _set_preview_state(self, theme: GowallTheme | None, preview_path: Path | None) -> None:
        if theme is None:
            self.preview_label.setText(tr("Selectionne un theme"))
            self.preview_label.setPixmap(QPixmap())
            self.preview_name_label.setText(tr("Aucun theme"))
            self.preview_meta_label.setText(self.gowall_status.message)
            self.apply_button.setEnabled(False)
            self.save_button.setEnabled(False)
            return
        self.preview_name_label.setText(theme.display_name)
        if preview_path is not None and preview_path.exists():
            pixmap = QPixmap(str(preview_path))
            scaled = pixmap.scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_label.setText("")
            self.preview_label.setPixmap(scaled)
            self.preview_meta_label.setText(tr("{origin_label} · {name}", origin_label=theme.origin_label, name=preview_path.name))
        else:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(tr("Preview en attente"))
            self.preview_meta_label.setText(
                tr("{origin_label} · Generation en cours", origin_label=theme.origin_label)
            )
        self.apply_button.setEnabled(self.gowall_status.installed)
        self.save_button.setEnabled(self.gowall_status.installed)

    def _theme_for_item(self, item: QListWidgetItem | None) -> GowallTheme | None:
        if item is None:
            return None
        theme_id = item.data(self.THEME_ID_ROLE)
        if not isinstance(theme_id, str):
            return None
        for theme in self.themes:
            if theme.id == theme_id:
                return theme
        return None

    def _placeholder_icon(self) -> QIcon:
        pixmap = QPixmap(240, 136)
        pixmap.fill(Qt.GlobalColor.black)
        painter = QPainter(pixmap)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, tr("Preview"))
        painter.end()
        return QIcon(pixmap)
