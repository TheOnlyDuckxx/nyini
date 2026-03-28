from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.application.services import WallManagerService
from src.domain.models import WallhavenSearchPage, WallhavenSearchRequest, WallhavenSearchResult
from src.i18n import tr
from src.workers.job_queue import BackgroundJobQueue
from src.workers.wallhaven_search_worker import WallhavenSearchWorker


class WallhavenDialog(QDialog):
    RESULT_ROLE = Qt.ItemDataRole.UserRole
    PREVIEW_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(
        self,
        service: WallManagerService,
        job_queue: BackgroundJobQueue,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Wallhaven"))
        self.resize(1380, 900)
        self.service = service
        self.job_queue = job_queue
        self.status = self.service.get_wallhaven_status()
        self.current_page: WallhavenSearchPage | None = None
        self.detail_cache: dict[str, WallhavenSearchResult] = {}
        self.imported_wallpapers = []
        self.imported_count = 0
        self._current_job_id: str | None = None

        self.status_label = QLabel(self.status.message)
        self.status_label.setWordWrap(True)
        self.progress_label = QLabel(tr("Pret"))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr("Recherche Wallhaven"))
        self.search_edit.returnPressed.connect(self.start_search)
        self.purity_combo = QComboBox()
        self.purity_combo.addItem("SFW", "100")
        self.purity_combo.addItem("SFW + Sketchy", "110")
        self.purity_combo.addItem(tr("Tout"), "111")
        self.purity_combo.setCurrentIndex(max(0, self.purity_combo.findData(self.service.settings.wallhaven_default_purity)))
        self.ratios_edit = QLineEdit(self.service.settings.wallhaven_default_ratios)
        self.ratios_edit.setPlaceholderText("16x9,21x9")
        self.atleast_edit = QLineEdit(self.service.settings.wallhaven_default_atleast)
        self.atleast_edit.setPlaceholderText("1920x1080")
        self.blacklist_edit = QLineEdit(self.service.settings.wallhaven_default_blacklist)
        self.blacklist_edit.setPlaceholderText("tag1, tag2")
        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, 9999)
        self.page_spin.setValue(1)
        self.search_button = QPushButton(tr("Rechercher"))
        self.search_button.clicked.connect(self.start_search)
        self.prev_button = QPushButton(tr("Page -"))
        self.prev_button.clicked.connect(self.previous_page)
        self.next_button = QPushButton(tr("Page +"))
        self.next_button.clicked.connect(self.next_page)

        self.result_list = QListWidget()
        self.result_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.result_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.result_list.setMovement(QListWidget.Movement.Static)
        self.result_list.setWrapping(True)
        self.result_list.setWordWrap(True)
        self.result_list.setSpacing(12)
        self.result_list.setIconSize(QSize(240, 136))
        self.result_list.setGridSize(QSize(270, 220))
        self.result_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.result_list.currentItemChanged.connect(self._on_current_item_changed)
        self.result_list.itemSelectionChanged.connect(self._update_import_button)

        self.preview_label = QLabel(tr("Aucun resultat"))
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(420, 240)
        self.preview_label.setObjectName("viewerCanvas")
        self.title_label = QLabel(tr("Selectionne un wallpaper"))
        self.title_label.setObjectName("detailsTitle")
        self.meta_label = QLabel("")
        self.meta_label.setWordWrap(True)
        self.tags_edit = QTextEdit()
        self.tags_edit.setReadOnly(True)
        self.tags_edit.setPlaceholderText(tr("Tags Wallhaven"))
        self.import_button = QPushButton(tr("Importer vers Inbox"))
        self.import_button.clicked.connect(self.import_selected)
        self.import_button.setEnabled(False)
        self.close_button = QPushButton(tr("Fermer"))
        self.close_button.clicked.connect(self.reject)

        controls = QHBoxLayout()
        controls.addWidget(self.search_edit, stretch=1)
        controls.addWidget(self.purity_combo)
        controls.addWidget(self.ratios_edit)
        controls.addWidget(self.atleast_edit)
        controls.addWidget(self.blacklist_edit)
        controls.addWidget(self.page_spin)
        controls.addWidget(self.prev_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.search_button)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(self.status_label)
        left_layout.addWidget(self.progress_label)
        left_layout.addLayout(controls)
        left_layout.addWidget(self.result_list, stretch=1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(self.preview_label)
        right_layout.addWidget(self.title_label)
        right_layout.addWidget(self.meta_label)
        right_layout.addWidget(self.tags_edit, stretch=1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self.import_button)
        actions.addWidget(self.close_button)
        right_layout.addLayout(actions)

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([860, 440])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        self.start_search()

    def _build_request(self) -> WallhavenSearchRequest:
        return WallhavenSearchRequest(
            query=self.search_edit.text().strip(),
            page=self.page_spin.value(),
            purity=str(self.purity_combo.currentData() or "100"),
            ratios=self.ratios_edit.text().strip(),
            atleast=self.atleast_edit.text().strip(),
            blacklist=self.blacklist_edit.text().strip(),
        )

    def start_search(self) -> None:
        request = self._build_request()
        self.result_list.clear()
        self.detail_cache.clear()
        self.current_page = None
        self.preview_label.setText(tr("Chargement..."))
        self.title_label.setText(tr("Recherche en cours"))
        self.meta_label.clear()
        self.tags_edit.clear()
        self.progress_label.setText(tr("Recherche Wallhaven..."))
        worker = WallhavenSearchWorker(
            self.service.wallhaven_client,
            request,
            api_key=self.service.settings.wallhaven_api_key,
        )
        worker.signals.preview_ready.connect(self._on_preview_ready)
        worker.signals.progress.connect(self._on_search_progress)
        worker.signals.finished.connect(self._on_search_finished)
        worker.signals.failed.connect(self._on_search_failed)
        self._current_job_id = self.job_queue.submit(
            "wallhaven-search",
            worker,
            description=f"Wallhaven: {request.query or 'browse'}",
        )

    def previous_page(self) -> None:
        self.page_spin.setValue(max(1, self.page_spin.value() - 1))
        self.start_search()

    def next_page(self) -> None:
        self.page_spin.setValue(self.page_spin.value() + 1)
        self.start_search()

    def _on_preview_ready(self, result: WallhavenSearchResult, preview_path: str) -> None:
        item = QListWidgetItem(f"{result.wallhaven_id}\n{result.resolution} · {result.purity}")
        item.setData(self.RESULT_ROLE, result)
        item.setData(self.PREVIEW_ROLE, preview_path)
        if preview_path:
            item.setIcon(QIcon(preview_path))
        item.setToolTip(result.wallhaven_url)
        self.result_list.addItem(item)
        self.detail_cache[result.wallhaven_id] = result
        if self.result_list.count() == 1:
            self.result_list.setCurrentRow(0)

    def _on_search_progress(self, current: int, total: int, wallhaven_id: str) -> None:
        self.progress_label.setText(tr("Resultat {current}/{total}: {wallhaven_id}", current=current, total=max(total, 1), wallhaven_id=wallhaven_id))
        if self._current_job_id is not None:
            self.job_queue.update_message(self._current_job_id, self.progress_label.text())

    def _on_search_finished(self, page: WallhavenSearchPage) -> None:
        self.current_page = page
        self.progress_label.setText(
            tr(
                "{count} resultat(s) · page {page}/{last_page} · total {total}",
                count=len(page.results),
                page=page.current_page,
                last_page=page.last_page,
                total=page.total,
            )
        )
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(page.current_page)
        self.page_spin.blockSignals(False)
        self.prev_button.setEnabled(page.current_page > 1)
        self.next_button.setEnabled(page.current_page < page.last_page)
        if self.result_list.count() == 0:
            self.preview_label.setText(tr("Aucun resultat"))
            self.title_label.setText(tr("Aucun resultat"))
            self.meta_label.setText(tr("Ajuste les filtres ou la recherche."))
        self._current_job_id = None

    def _on_search_failed(self, message: str) -> None:
        self.progress_label.setText(message)
        QMessageBox.critical(self, tr("Recherche Wallhaven impossible"), message)
        self._current_job_id = None

    def _on_current_item_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self.preview_label.setText(tr("Selectionne un resultat"))
            self.title_label.setText(tr("Selectionne un wallpaper"))
            self.meta_label.clear()
            self.tags_edit.clear()
            return
        result = current.data(self.RESULT_ROLE)
        if not isinstance(result, WallhavenSearchResult):
            return
        detailed = self.detail_cache.get(result.wallhaven_id, result)
        if not detailed.tags or detailed.uploader is None:
            try:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                detailed = self.service.wallhaven_client.fetch_wallpaper(
                    result.wallhaven_id,
                    api_key=self.service.settings.wallhaven_api_key,
                )
                self.detail_cache[result.wallhaven_id] = detailed
                current.setData(self.RESULT_ROLE, detailed)
            except Exception:
                detailed = result
            finally:
                QApplication.restoreOverrideCursor()
        preview_path = current.data(self.PREVIEW_ROLE)
        self._set_detail_state(detailed, Path(preview_path) if isinstance(preview_path, str) and preview_path else None)

    def _set_detail_state(self, result: WallhavenSearchResult, preview_path: Path | None) -> None:
        if preview_path is not None and preview_path.exists():
            pixmap = QPixmap(str(preview_path))
            self.preview_label.setPixmap(
                pixmap.scaled(
                    self.preview_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(tr("Preview indisponible"))
        self.title_label.setText(result.wallhaven_id)
        parts = [result.resolution, result.purity, result.category, result.uploader or tr("auteur inconnu")]
        if result.source_url:
            parts.append(result.source_url)
        self.meta_label.setText(" · ".join(part for part in parts if part))
        self.tags_edit.setPlainText(", ".join(result.tags))

    def _update_import_button(self) -> None:
        self.import_button.setEnabled(bool(self.result_list.selectedItems()))

    def import_selected(self) -> None:
        selected_ids: list[str] = []
        for item in self.result_list.selectedItems():
            result = item.data(self.RESULT_ROLE)
            if isinstance(result, WallhavenSearchResult):
                selected_ids.append(result.wallhaven_id)
        if not selected_ids:
            return
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            imported = self.service.download_wallhaven_results(selected_ids)
        except Exception as exc:
            QMessageBox.critical(self, tr("Import Wallhaven impossible"), str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.imported_wallpapers = imported
        self.imported_count = len(imported)
        self.accept()
