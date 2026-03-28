from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.config.app_info import APP_NAME
from src.config.settings import AppSettings
from src.domain.models import WallpaperBackendStatus
from src.i18n import tr


class OnboardingDialog(QDialog):
    def __init__(
        self,
        settings: AppSettings,
        *,
        wallpaper_backend_status: WallpaperBackendStatus | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Bienvenue dans {app_name}", app_name=APP_NAME))
        self.resize(640, 260)
        self.settings = settings
        self.wallpaper_backend_status = wallpaper_backend_status

        intro = QLabel(
            tr(
                "Choisis les emplacements de base avant le premier scan. Tu pourras tout modifier plus tard dans les parametres."
            )
        )
        intro.setWordWrap(True)

        self.library_root_edit = QLineEdit(str(settings.library_root))
        self.inbox_root_edit = QLineEdit(str(settings.inbox_root))
        self.wallpaper_backend_combo = QComboBox()
        self._populate_wallpaper_backend_combo()
        self.wallpaper_backend_help_label = QLabel(self._wallpaper_backend_help_text())
        self.wallpaper_backend_help_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow(tr("Bibliotheque"), self._path_row(self.library_root_edit))
        form.addRow(tr("Inbox"), self._path_row(self.inbox_root_edit))
        form.addRow(tr("Backend wallpaper"), self.wallpaper_backend_combo)
        form.addRow("", self.wallpaper_backend_help_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _path_row(self, line_edit: QLineEdit) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton(tr("Parcourir"))
        button.clicked.connect(lambda: self._choose_directory(line_edit))
        layout.addWidget(line_edit, stretch=1)
        layout.addWidget(button)
        return widget

    def _choose_directory(self, line_edit: QLineEdit) -> None:
        directory = QFileDialog.getExistingDirectory(self, tr("Choisir un dossier"), line_edit.text() or str(Path.home()))
        if directory:
            line_edit.setText(directory)

    def _populate_wallpaper_backend_combo(self) -> None:
        status = self.wallpaper_backend_status
        self.wallpaper_backend_combo.clear()
        auto_label = "Auto"
        if status is not None and status.available:
            auto_label = f"Auto ({status.active_display_name})"
        self.wallpaper_backend_combo.addItem(auto_label, "auto")
        seen = {"auto"}
        if status is not None:
            for option in status.options:
                if option.backend_id in seen:
                    continue
                label = option.display_name
                if not option.available:
                    label += f" ({tr('indisponible')})"
                self.wallpaper_backend_combo.addItem(label, option.backend_id)
                seen.add(option.backend_id)
        if self.settings.wallpaper_backend not in seen:
            self.wallpaper_backend_combo.addItem(self.settings.wallpaper_backend, self.settings.wallpaper_backend)
        current_index = self.wallpaper_backend_combo.findData(self.settings.wallpaper_backend)
        self.wallpaper_backend_combo.setCurrentIndex(max(0, current_index))

    def _wallpaper_backend_help_text(self) -> str:
        if self.wallpaper_backend_status is None:
            return tr("Le mode `Auto` detecte le backend wallpaper compatible avec ta session Linux.")
        return self.wallpaper_backend_status.message

    def _current_wallpaper_backend(self) -> str:
        value = self.wallpaper_backend_combo.currentData()
        return str(value or "auto")

    def to_settings(self) -> AppSettings:
        return replace(
            self.settings,
            library_root=Path(self.library_root_edit.text()).expanduser(),
            inbox_root=Path(self.inbox_root_edit.text()).expanduser(),
            wallpaper_backend=self._current_wallpaper_backend(),
            onboarding_completed=True,
        )
