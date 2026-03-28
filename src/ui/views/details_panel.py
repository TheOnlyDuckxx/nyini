from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.domain.models import Wallpaper
from src.i18n import media_kind_label, orientation_label, source_kind_label, tr


def human_size(size_bytes: int) -> str:
    value = float(size_bytes)
    units = ["B", "KB", "MB", "GB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def human_datetime(timestamp: float | None) -> str:
    if not timestamp:
        return "-"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def human_duration(duration_seconds: float | None) -> str:
    if duration_seconds is None:
        return "-"
    total_seconds = max(0, int(duration_seconds))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"


class DetailsPanel(QWidget):
    favorite_changed = Signal(bool)
    save_requested = Signal(list, str, int)
    hash_requested = Signal()
    open_folder_requested = Signal(object)
    open_source_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._wallpaper: Wallpaper | None = None
        self._updating = False

        self.title_label = QLabel()
        self.title_label.setObjectName("detailsTitle")
        self.summary_label = QLabel()
        self.summary_label.setObjectName("detailsSubtitle")
        self.filename_label = QLabel("-")
        self.path_label = QLabel("-")
        self.path_label.setWordWrap(True)
        self.media_kind_label = QLabel("-")
        self.dimensions_label = QLabel("-")
        self.duration_label = QLabel("-")
        self.orientation_value_label = QLabel("-")
        self.orientation_label = self.orientation_value_label
        self.size_label = QLabel("-")
        self.modified_label = QLabel("-")
        self.viewed_label = QLabel("-")
        self.hash_label = QLabel("-")
        self.hash_label.setWordWrap(True)
        self.color_label = QLabel("-")
        self.brightness_label = QLabel("-")
        self.source_kind_value_label = QLabel("-")
        self.source_kind_label = self.source_kind_value_label
        self.source_provider_label = QLabel("-")
        self.source_url_label = QLabel("-")
        self.source_url_label.setWordWrap(True)
        self.author_label = QLabel("-")
        self.license_label = QLabel("-")
        self.imported_at_label = QLabel("-")
        self.generator_tool_label = QLabel("-")
        self.favorite_pill = QLabel()
        self.views_pill = QLabel()
        self.rating_pill = QLabel()
        for label in (self.favorite_pill, self.views_pill, self.rating_pill):
            label.setObjectName("metricBadge")
        self.color_swatch = QFrame()
        self.color_swatch.setObjectName("colorSwatch")
        self.color_swatch.setFixedSize(40, 40)
        self.favorite_checkbox = QCheckBox()
        self.favorite_checkbox.toggled.connect(self._on_favorite_toggled)
        self.rating_spin = QSpinBox()
        self.rating_spin.setRange(0, 5)
        self.tags_edit = QLineEdit()
        self.notes_edit = QPlainTextEdit()
        self.save_button = QPushButton()
        self.save_button.clicked.connect(self._emit_save)
        self.hash_button = QPushButton()
        self.hash_button.clicked.connect(self.hash_requested.emit)
        self.open_folder_button = QPushButton()
        self.open_folder_button.clicked.connect(self._emit_open_folder)
        self.open_source_button = QPushButton()
        self.open_source_button.clicked.connect(self._emit_open_source)

        header_card = QWidget()
        header_card.setObjectName("detailsHeaderCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_top_layout = QHBoxLayout()
        header_text_layout = QVBoxLayout()
        header_text_layout.addWidget(self.title_label)
        header_text_layout.addWidget(self.summary_label)
        header_top_layout.addLayout(header_text_layout, stretch=1)
        header_top_layout.addWidget(self.color_swatch, alignment=Qt.AlignmentFlag.AlignTop)
        header_layout.addLayout(header_top_layout)
        header_layout.addWidget(self.path_label)
        badge_layout = QHBoxLayout()
        badge_layout.addWidget(self.favorite_pill)
        badge_layout.addWidget(self.views_pill)
        badge_layout.addWidget(self.rating_pill)
        badge_layout.addStretch(1)
        header_layout.addLayout(badge_layout)

        self.info_group = QGroupBox()
        info_layout = QFormLayout(self.info_group)
        self.info_layout = info_layout
        info_layout.addRow("", self.filename_label)
        info_layout.addRow("", self.media_kind_label)
        info_layout.addRow("", self.dimensions_label)
        info_layout.addRow("", self.duration_label)
        info_layout.addRow("", self.orientation_value_label)
        info_layout.addRow("", self.size_label)
        info_layout.addRow("", self.modified_label)
        info_layout.addRow("", self.viewed_label)
        info_layout.addRow("", self.hash_label)
        info_layout.addRow("", self.color_label)
        info_layout.addRow("", self.brightness_label)

        self.provenance_group = QGroupBox()
        provenance_layout = QFormLayout(self.provenance_group)
        self.provenance_layout = provenance_layout
        provenance_layout.addRow("", self.source_kind_value_label)
        provenance_layout.addRow("", self.source_provider_label)
        provenance_layout.addRow("", self.source_url_label)
        provenance_layout.addRow("", self.author_label)
        provenance_layout.addRow("", self.license_label)
        provenance_layout.addRow("", self.imported_at_label)
        provenance_layout.addRow("", self.generator_tool_label)

        self.edit_group = QGroupBox()
        edit_layout = QFormLayout(self.edit_group)
        self.edit_layout = edit_layout
        edit_layout.addRow("", self.favorite_checkbox)
        edit_layout.addRow("", self.rating_spin)
        edit_layout.addRow("", self.tags_edit)
        edit_layout.addRow("", self.notes_edit)

        actions = QHBoxLayout()
        actions.addWidget(self.save_button)
        actions.addWidget(self.hash_button)
        actions.addWidget(self.open_folder_button)
        actions.addWidget(self.open_source_button)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.addWidget(header_card)
        content_layout.addWidget(self.info_group)
        content_layout.addWidget(self.provenance_group)
        content_layout.addWidget(self.edit_group)
        content_layout.addLayout(actions)
        content_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)

        self.refresh_language()

    @property
    def wallpaper(self) -> Wallpaper | None:
        return self._wallpaper

    def refresh_language(self) -> None:
        self.info_group.setTitle(tr("Metadonnees"))
        self.provenance_group.setTitle(tr("Provenance"))
        self.edit_group.setTitle(tr("Edition"))
        self.info_layout.setWidget(0, QFormLayout.ItemRole.LabelRole, QLabel(tr("Nom")))
        self.info_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, QLabel(tr("Media")))
        self.info_layout.setWidget(2, QFormLayout.ItemRole.LabelRole, QLabel(tr("Dimensions")))
        self.info_layout.setWidget(3, QFormLayout.ItemRole.LabelRole, QLabel(tr("Duree")))
        self.info_layout.setWidget(4, QFormLayout.ItemRole.LabelRole, QLabel(tr("Orientation")))
        self.info_layout.setWidget(5, QFormLayout.ItemRole.LabelRole, QLabel(tr("Taille")))
        self.info_layout.setWidget(6, QFormLayout.ItemRole.LabelRole, QLabel(tr("Modifie")))
        self.info_layout.setWidget(7, QFormLayout.ItemRole.LabelRole, QLabel(tr("Vues")))
        self.info_layout.setWidget(8, QFormLayout.ItemRole.LabelRole, QLabel("SHA256"))
        self.info_layout.setWidget(9, QFormLayout.ItemRole.LabelRole, QLabel(tr("Couleur moyenne")))
        self.info_layout.setWidget(10, QFormLayout.ItemRole.LabelRole, QLabel(tr("Luminosite")))
        self.provenance_layout.setWidget(0, QFormLayout.ItemRole.LabelRole, QLabel(tr("Type")))
        self.provenance_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, QLabel(tr("Provider")))
        self.provenance_layout.setWidget(2, QFormLayout.ItemRole.LabelRole, QLabel(tr("Source URL")))
        self.provenance_layout.setWidget(3, QFormLayout.ItemRole.LabelRole, QLabel(tr("Auteur")))
        self.provenance_layout.setWidget(4, QFormLayout.ItemRole.LabelRole, QLabel(tr("Licence")))
        self.provenance_layout.setWidget(5, QFormLayout.ItemRole.LabelRole, QLabel(tr("Importe")))
        self.provenance_layout.setWidget(6, QFormLayout.ItemRole.LabelRole, QLabel(tr("Generateur")))
        self.edit_layout.setWidget(0, QFormLayout.ItemRole.LabelRole, QLabel(""))
        self.edit_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, QLabel(tr("Note")))
        self.edit_layout.setWidget(2, QFormLayout.ItemRole.LabelRole, QLabel(tr("Tags")))
        self.edit_layout.setWidget(3, QFormLayout.ItemRole.LabelRole, QLabel(tr("Notes")))
        self.favorite_checkbox.setText(tr("Favori"))
        self.notes_edit.setPlaceholderText(tr("Notes locales"))
        self.save_button.setText(tr("Enregistrer"))
        self.hash_button.setText(tr("Calculer hash"))
        self.open_folder_button.setText(tr("Ouvrir dossier"))
        self.open_source_button.setText(tr("Ouvrir source"))
        self.set_wallpaper(self._wallpaper)

    def set_wallpaper(self, wallpaper: Wallpaper | None) -> None:
        self._updating = True
        self._wallpaper = wallpaper
        if wallpaper is None:
            self.title_label.setText(tr("Aucun wallpaper"))
            self.summary_label.setText(tr("Selectionnez un wallpaper pour inspecter ses metadonnees"))
            self.filename_label.setText("-")
            self.path_label.setText("-")
            self.media_kind_label.setText("-")
            self.dimensions_label.setText("-")
            self.duration_label.setText("-")
            self.orientation_value_label.setText("-")
            self.size_label.setText("-")
            self.modified_label.setText("-")
            self.viewed_label.setText("-")
            self.hash_label.setText("-")
            self.color_label.setText("-")
            self.brightness_label.setText("-")
            self.source_kind_value_label.setText("-")
            self.source_provider_label.setText("-")
            self.source_url_label.setText("-")
            self.author_label.setText("-")
            self.license_label.setText("-")
            self.imported_at_label.setText("-")
            self.generator_tool_label.setText("-")
            self.favorite_pill.setText(tr("Normal"))
            self.views_pill.setText(tr("0 vues"))
            self.rating_pill.setText(tr("Note 0"))
            self.color_swatch.setStyleSheet("")
            self.favorite_checkbox.setChecked(False)
            self.rating_spin.setValue(0)
            self.tags_edit.clear()
            self.notes_edit.clear()
            self.open_source_button.setEnabled(False)
            self._updating = False
            return
        summary_parts = [
            tr("Video") if wallpaper.media_kind.value == "video" else tr("Image"),
        ]
        if wallpaper.width and wallpaper.height:
            summary_parts.append(f"{wallpaper.width} x {wallpaper.height}")
        if wallpaper.duration_seconds is not None:
            summary_parts.append(human_duration(wallpaper.duration_seconds))
        summary_parts.append(human_size(wallpaper.size_bytes))
        summary_parts.append(orientation_label(wallpaper.orientation))
        self.title_label.setText(wallpaper.filename)
        self.summary_label.setText(" · ".join(summary_parts))
        self.filename_label.setText(wallpaper.filename)
        self.path_label.setText(str(wallpaper.path))
        self.media_kind_label.setText(media_kind_label(wallpaper.media_kind))
        dimensions = f"{wallpaper.width} x {wallpaper.height}" if wallpaper.width and wallpaper.height else "-"
        self.dimensions_label.setText(dimensions)
        self.duration_label.setText(human_duration(wallpaper.duration_seconds))
        self.orientation_value_label.setText(orientation_label(wallpaper.orientation))
        self.size_label.setText(human_size(wallpaper.size_bytes))
        self.modified_label.setText(human_datetime(wallpaper.mtime))
        last_viewed = wallpaper.last_viewed_at or "-"
        self.viewed_label.setText(f"{wallpaper.times_viewed} ({last_viewed})")
        self.hash_label.setText(wallpaper.sha256 or "-")
        self.color_label.setText(wallpaper.avg_color or "-")
        self.brightness_label.setText("-" if wallpaper.brightness is None else f"{wallpaper.brightness:.1f}")
        provenance = wallpaper.provenance
        self.source_kind_value_label.setText(
            source_kind_label(provenance.source_kind if provenance is not None else "local")
        )
        self.source_provider_label.setText(provenance.source_provider or "-" if provenance is not None else tr("filesystem"))
        self.source_url_label.setText(provenance.source_url or "-" if provenance is not None else "-")
        self.author_label.setText(provenance.author_name or "-" if provenance is not None else "-")
        self.license_label.setText(provenance.license_name or "-" if provenance is not None else "-")
        self.imported_at_label.setText(provenance.imported_at or "-" if provenance is not None else "-")
        self.generator_tool_label.setText(provenance.generator_tool or "-" if provenance is not None else "-")
        self.favorite_pill.setText(tr("Favori") if wallpaper.is_favorite else tr("Normal"))
        self.views_pill.setText(tr("{count} vues", count=wallpaper.times_viewed))
        self.rating_pill.setText(tr("Note {rating}", rating=wallpaper.rating))
        if wallpaper.avg_color:
            self.color_swatch.setStyleSheet(
                f"background-color: {wallpaper.avg_color}; border: 1px solid rgba(255, 255, 255, 0.18); border-radius: 12px;"
            )
        else:
            self.color_swatch.setStyleSheet("")
        self.favorite_checkbox.setChecked(wallpaper.is_favorite)
        self.rating_spin.setValue(wallpaper.rating)
        self.tags_edit.setText(", ".join(wallpaper.tags))
        self.notes_edit.setPlainText(wallpaper.notes)
        self.open_source_button.setEnabled(bool(provenance and provenance.source_url))
        self._updating = False

    def _on_favorite_toggled(self, checked: bool) -> None:
        if self._updating or self._wallpaper is None:
            return
        self.favorite_changed.emit(checked)

    def _emit_save(self) -> None:
        if self._wallpaper is None:
            return
        tags = [tag.strip() for tag in self.tags_edit.text().split(",") if tag.strip()]
        self.save_requested.emit(tags, self.notes_edit.toPlainText(), self.rating_spin.value())

    def _emit_open_folder(self) -> None:
        if self._wallpaper is None:
            return
        self.open_folder_requested.emit(self._wallpaper.path.parent)

    def _emit_open_source(self) -> None:
        if self._wallpaper is None or self._wallpaper.provenance is None or not self._wallpaper.provenance.source_url:
            return
        self.open_source_requested.emit(self._wallpaper.provenance.source_url)
