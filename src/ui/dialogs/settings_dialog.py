from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QKeySequenceEdit,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.config.shortcuts import SHORTCUT_DEFINITIONS
from src.config.settings import AppSettings
from src.domain.enums import AppLanguage, SortField, ThemeMode
from src.domain.models import GowallStatus, VideoWallpaperBackendStatus, WallpaperBackendStatus, WallhavenStatus
from src.i18n import language_label, sort_field_label, theme_mode_label, tr, yes_no


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: AppSettings,
        *,
        gowall_status: GowallStatus | None = None,
        gowall_themes_dir: Path | None = None,
        wallpaper_backend_status: WallpaperBackendStatus | None = None,
        video_wallpaper_backend_status: VideoWallpaperBackendStatus | None = None,
        wallhaven_status: WallhavenStatus | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Parametres"))
        self.resize(720, 640)
        self.settings = settings
        self.gowall_status = gowall_status
        self.gowall_themes_dir = gowall_themes_dir
        self.wallpaper_backend_status = wallpaper_backend_status
        self.video_wallpaper_backend_status = video_wallpaper_backend_status
        self.wallhaven_status = wallhaven_status
        self.shortcut_edits: dict[str, QKeySequenceEdit] = {}

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(), tr("General"))
        self.tabs.addTab(self._build_appearance_tab(), tr("Apparence"))
        self.tabs.addTab(self._build_integrations_tab(), tr("Integrations"))
        self.tabs.addTab(self._build_shortcuts_tab(), tr("Raccourcis"))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)

    def _build_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)

        self.library_root_edit = QLineEdit(str(self.settings.library_root))
        self.inbox_root_edit = QLineEdit(str(self.settings.inbox_root))
        self.thumbnail_size_spin = QSpinBox()
        self.thumbnail_size_spin.setRange(96, 768)
        self.thumbnail_size_spin.setValue(self.settings.thumbnail_size)
        self.polling_interval_spin = QSpinBox()
        self.polling_interval_spin.setRange(1000, 60000)
        self.polling_interval_spin.setSingleStep(500)
        self.polling_interval_spin.setValue(self.settings.polling_interval_ms)
        self.slideshow_interval_spin = QSpinBox()
        self.slideshow_interval_spin.setRange(1, 60)
        self.slideshow_interval_spin.setValue(self.settings.slideshow_interval_seconds)
        self.default_sort_combo = QComboBox()
        for value in (
            SortField.MTIME,
            SortField.NAME,
            SortField.SIZE,
            SortField.ORIENTATION,
            SortField.FAVORITE,
            SortField.RATING,
            SortField.VIEWS,
            SortField.BRIGHTNESS,
        ):
            self.default_sort_combo.addItem(sort_field_label(value), value)
        self.default_sort_combo.setCurrentIndex(max(0, self.default_sort_combo.findData(self.settings.default_sort)))
        self.compute_hashes_checkbox = QCheckBox(tr("Calculer les hash pendant le scan"))
        self.compute_hashes_checkbox.setChecked(self.settings.compute_hashes_on_scan)
        self.auto_import_checkbox = QCheckBox(tr("Importer automatiquement le dossier Inbox avant scan"))
        self.auto_import_checkbox.setChecked(self.settings.auto_import_inbox)
        self.rename_template_edit = QLineEdit(self.settings.rename_template)
        self.wallpaper_backend_combo = QComboBox()
        self._populate_wallpaper_backend_combo()
        self.wallpaper_backend_help_label = QLabel(self._wallpaper_backend_help_text())
        self.wallpaper_backend_help_label.setWordWrap(True)
        self.animated_video_previews_checkbox = QCheckBox(tr("Lire les previews video dans la visionneuse"))
        self.animated_video_previews_checkbox.setChecked(self.settings.animated_video_previews)
        self.mpvpaper_preset_combo = QComboBox()
        self.mpvpaper_preset_combo.addItem(tr("Video"), "video")
        self.mpvpaper_preset_combo.addItem(tr("Silencieux"), "silent")
        self.mpvpaper_preset_combo.addItem(tr("Pause"), "pause")
        self.mpvpaper_preset_combo.setCurrentIndex(max(0, self.mpvpaper_preset_combo.findData(self.settings.mpvpaper_preset)))

        layout.addRow(tr("Bibliotheque"), self._path_row(self.library_root_edit))
        layout.addRow(tr("Inbox"), self._path_row(self.inbox_root_edit))
        layout.addRow(tr("Miniatures"), self.thumbnail_size_spin)
        layout.addRow(tr("Polling (ms)"), self.polling_interval_spin)
        layout.addRow(tr("Slideshow (s)"), self.slideshow_interval_spin)
        layout.addRow(tr("Backend wallpaper"), self.wallpaper_backend_combo)
        layout.addRow("", self.wallpaper_backend_help_label)
        layout.addRow(tr("Preset mpvpaper"), self.mpvpaper_preset_combo)
        layout.addRow("", self.animated_video_previews_checkbox)
        layout.addRow(tr("Tri par defaut"), self.default_sort_combo)
        layout.addRow("", self.compute_hashes_checkbox)
        layout.addRow("", self.auto_import_checkbox)
        layout.addRow(tr("Template renommage"), self.rename_template_edit)
        return widget

    def _build_appearance_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        self.language_combo = QComboBox()
        self.language_combo.addItem(language_label(AppLanguage.FR), AppLanguage.FR)
        self.language_combo.addItem(language_label(AppLanguage.EN), AppLanguage.EN)
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(self.settings.language)))
        self.theme_mode_combo = QComboBox()
        for value in (ThemeMode.AUTO, ThemeMode.LIGHT, ThemeMode.DARK):
            self.theme_mode_combo.addItem(theme_mode_label(value), value)
        self.theme_mode_combo.setCurrentIndex(max(0, self.theme_mode_combo.findData(self.settings.theme_mode)))
        info = QLabel(tr("Le mode auto suit `QStyleHints.colorScheme()` quand le systeme l'expose."))
        info.setWordWrap(True)
        layout.addRow(tr("Langue"), self.language_combo)
        layout.addRow(tr("Theme"), self.theme_mode_combo)
        layout.addRow("", info)
        return widget

    def _build_shortcuts_tab(self) -> QWidget:
        container = QWidget()
        layout = QFormLayout(container)
        for definition in SHORTCUT_DEFINITIONS:
            editor = QKeySequenceEdit()
            editor.setKeySequence(self.settings.shortcuts.get(definition.action_id, definition.default_sequence))
            self.shortcut_edits[definition.action_id] = editor
            layout.addRow(tr(definition.label), editor)
            help_label = QLabel(tr(definition.description))
            help_label.setWordWrap(True)
            layout.addRow("", help_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.addWidget(scroll)
        return wrapper

    def _build_integrations_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        status = self.gowall_status
        wallpaper_status = self.wallpaper_backend_status
        video_wallpaper_status = self.video_wallpaper_backend_status
        wallhaven_status = self.wallhaven_status
        status_text = status.message if status is not None else tr("Statut inconnu")
        version_text = status.version if status is not None and status.version else "-"
        executable_text = str(status.executable_path) if status is not None and status.executable_path else "-"
        wallpaper_backend_text = wallpaper_status.message if wallpaper_status is not None else tr("Statut inconnu")
        wallpaper_active_text = (
            wallpaper_status.active_display_name if wallpaper_status is not None and wallpaper_status.available else "-"
        )
        wallpaper_session_text = wallpaper_status.session_type if wallpaper_status is not None else "-"
        wallpaper_desktop_text = wallpaper_status.desktop_environment if wallpaper_status is not None else "-"
        video_backend_text = video_wallpaper_status.message if video_wallpaper_status is not None else tr("Statut inconnu")
        video_backend_active_text = (
            video_wallpaper_status.active_display_name if video_wallpaper_status is not None and video_wallpaper_status.available else "-"
        )
        wallhaven_text = wallhaven_status.message if wallhaven_status is not None else tr("Statut inconnu")
        wallhaven_key_text = yes_no(wallhaven_status is not None and wallhaven_status.api_key_configured)
        wallhaven_rate_text = f"{wallhaven_status.rate_limit_per_minute} req/min" if wallhaven_status is not None else "-"

        self.gowall_status_label = QLabel(status_text)
        self.gowall_status_label.setWordWrap(True)
        self.gowall_version_label = QLabel(version_text)
        self.gowall_path_label = QLabel(executable_text)
        self.gowall_path_label.setWordWrap(True)
        self.gowall_themes_dir_label = QLabel(str(self.gowall_themes_dir) if self.gowall_themes_dir else "-")
        self.gowall_themes_dir_label.setWordWrap(True)
        self.wallpaper_backend_status_label = QLabel(wallpaper_backend_text)
        self.wallpaper_backend_status_label.setWordWrap(True)
        self.wallpaper_backend_active_label = QLabel(wallpaper_active_text)
        self.wallpaper_backend_session_label = QLabel(wallpaper_session_text)
        self.wallpaper_backend_desktop_label = QLabel(wallpaper_desktop_text)
        self.video_wallpaper_backend_status_label = QLabel(video_backend_text)
        self.video_wallpaper_backend_status_label.setWordWrap(True)
        self.video_wallpaper_backend_active_label = QLabel(video_backend_active_text)
        self.wallhaven_status_label = QLabel(wallhaven_text)
        self.wallhaven_status_label.setWordWrap(True)
        self.wallhaven_key_label = QLabel(wallhaven_key_text)
        self.wallhaven_rate_label = QLabel(wallhaven_rate_text)
        self.wallhaven_api_key_edit = QLineEdit(self.settings.wallhaven_api_key)
        self.wallhaven_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.wallhaven_purity_combo = QComboBox()
        self.wallhaven_purity_combo.addItem("SFW", "100")
        self.wallhaven_purity_combo.addItem("SFW + Sketchy", "110")
        self.wallhaven_purity_combo.addItem(tr("Tout"), "111")
        self.wallhaven_purity_combo.setCurrentIndex(
            max(0, self.wallhaven_purity_combo.findData(self.settings.wallhaven_default_purity))
        )
        self.wallhaven_ratios_edit = QLineEdit(self.settings.wallhaven_default_ratios)
        self.wallhaven_atleast_edit = QLineEdit(self.settings.wallhaven_default_atleast)
        self.wallhaven_blacklist_edit = QLineEdit(self.settings.wallhaven_default_blacklist)

        layout.addRow(tr("Backend wallpaper"), self.wallpaper_backend_status_label)
        layout.addRow(tr("Backend actif"), self.wallpaper_backend_active_label)
        layout.addRow(tr("Session"), self.wallpaper_backend_session_label)
        layout.addRow(tr("Desktop"), self.wallpaper_backend_desktop_label)
        layout.addRow(tr("Backend video"), self.video_wallpaper_backend_status_label)
        layout.addRow(tr("Backend video actif"), self.video_wallpaper_backend_active_label)
        layout.addRow(tr("Wallhaven"), self.wallhaven_status_label)
        layout.addRow(tr("Cle API configuree"), self.wallhaven_key_label)
        layout.addRow(tr("Rate limit"), self.wallhaven_rate_label)
        layout.addRow(tr("Cle API"), self.wallhaven_api_key_edit)
        layout.addRow(tr("Purete par defaut"), self.wallhaven_purity_combo)
        layout.addRow(tr("Ratios par defaut"), self.wallhaven_ratios_edit)
        layout.addRow(tr("Resolution min"), self.wallhaven_atleast_edit)
        layout.addRow(tr("Blacklist"), self.wallhaven_blacklist_edit)
        layout.addRow(tr("Gowall"), self.gowall_status_label)
        layout.addRow(tr("Version"), self.gowall_version_label)
        layout.addRow(tr("Executable"), self.gowall_path_label)
        layout.addRow(tr("Themes importes"), self.gowall_themes_dir_label)
        return widget

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
        status = self.wallpaper_backend_status
        if status is None:
            return tr("Choisis `Auto` pour laisser l'application detecter le backend Linux le plus adapte.")
        return status.message

    def _current_wallpaper_backend(self) -> str:
        value = self.wallpaper_backend_combo.currentData()
        return str(value or "auto")

    def _current_wallhaven_purity(self) -> str:
        value = self.wallhaven_purity_combo.currentData()
        return str(value or "100")

    def _current_mpvpaper_preset(self) -> str:
        value = self.mpvpaper_preset_combo.currentData()
        return str(value or "video")

    def _path_row(self, line_edit: QLineEdit) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        browse_button = QPushButton(tr("Parcourir"))
        browse_button.clicked.connect(lambda: self._choose_directory(line_edit))
        layout.addWidget(line_edit, stretch=1)
        layout.addWidget(browse_button)
        return widget

    def _choose_directory(self, line_edit: QLineEdit) -> None:
        directory = QFileDialog.getExistingDirectory(self, tr("Choisir un dossier"), line_edit.text() or str(Path.home()))
        if directory:
            line_edit.setText(directory)

    def _current_sort_field(self) -> SortField:
        value = self.default_sort_combo.currentData()
        return value if isinstance(value, SortField) else SortField(str(value))

    def _current_theme_mode(self) -> ThemeMode:
        value = self.theme_mode_combo.currentData()
        return value if isinstance(value, ThemeMode) else ThemeMode(str(value))

    def _current_language(self) -> AppLanguage:
        value = self.language_combo.currentData()
        return value if isinstance(value, AppLanguage) else AppLanguage(str(value))

    def to_settings(self) -> AppSettings:
        shortcuts = {
            action_id: editor.keySequence().toString()
            for action_id, editor in self.shortcut_edits.items()
        }
        return replace(
            self.settings,
            library_root=Path(self.library_root_edit.text()).expanduser(),
            inbox_root=Path(self.inbox_root_edit.text()).expanduser(),
            language=self._current_language(),
            thumbnail_size=self.thumbnail_size_spin.value(),
            polling_interval_ms=self.polling_interval_spin.value(),
            default_sort=self._current_sort_field(),
            compute_hashes_on_scan=self.compute_hashes_checkbox.isChecked(),
            auto_import_inbox=self.auto_import_checkbox.isChecked(),
            rename_template=self.rename_template_edit.text().strip() or "{stem}",
            slideshow_interval_seconds=self.slideshow_interval_spin.value(),
            theme_mode=self._current_theme_mode(),
            wallpaper_backend=self._current_wallpaper_backend(),
            animated_video_previews=self.animated_video_previews_checkbox.isChecked(),
            mpvpaper_preset=self._current_mpvpaper_preset(),
            wallhaven_api_key=self.wallhaven_api_key_edit.text().strip(),
            wallhaven_default_purity=self._current_wallhaven_purity(),
            wallhaven_default_ratios=self.wallhaven_ratios_edit.text().strip(),
            wallhaven_default_atleast=self.wallhaven_atleast_edit.text().strip(),
            wallhaven_default_blacklist=self.wallhaven_blacklist_edit.text().strip(),
            shortcuts=shortcuts,
        )
