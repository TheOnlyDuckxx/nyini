from __future__ import annotations

from collections import Counter
from pathlib import Path
import subprocess

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QSize, QStringListModel, Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QUndoStack
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.application.commands import (
    MoveWallpaperCommand,
    RenameWallpaperCommand,
    ToggleFavoriteCommand,
    TrashWallpaperCommand,
    UpdateWallpaperDetailsCommand,
)
from src.application.services import WallManagerService
from src.config.app_info import APP_NAME
from src.domain.enums import MediaKind, Orientation, SmartCollection, SortField, WallpaperSourceKind
from src.domain.models import ScanSummary, Wallpaper
from src.infrastructure.filesystem.watcher import PollingLibraryWatcher
from src.i18n import set_language, smart_collection_label, tr, translate_qt_texts
from src.ui.dialogs.duplicate_review_dialog import DuplicateReviewDialog, DuplicateReviewGroup
from src.ui.dialogs.gowall_theme_dialog import GowallThemeDialog
from src.ui.dialogs.history_dialog import HistoryDialog
from src.ui.dialogs.onboarding_dialog import OnboardingDialog
from src.ui.dialogs.settings_dialog import SettingsDialog
from src.ui.dialogs.shortcuts_dialog import ShortcutsDialog
from src.ui.dialogs.wallhaven_dialog import WallhavenDialog
from src.ui.models.wallpaper_model import WallpaperFilterProxyModel, WallpaperListModel
from src.ui.shortcuts import ShortcutManager
from src.ui.theme import ThemeController
from src.ui.views.details_panel import DetailsPanel
from src.ui.views.grid_view import WallpaperGridView
from src.ui.views.sidebar import SidebarPanel
from src.ui.views.viewer import WallpaperViewer
from src.workers.index_worker import IndexWorker
from src.workers.job_queue import BackgroundJobQueue, JobInfo
from src.workers.preload_worker import PreloadWorker


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: WallManagerService,
        theme_controller: ThemeController,
        *,
        show_onboarding_on_startup: bool = False,
    ) -> None:
        super().__init__()
        self.service = service
        self.theme_controller = theme_controller
        self.show_onboarding_on_startup = show_onboarding_on_startup
        self.setWindowTitle(APP_NAME)
        self.resize(1680, 980)

        self.thread_pool = QThreadPool(self)
        self.job_queue = BackgroundJobQueue(self.thread_pool, self)
        self.undo_stack = QUndoStack(self)
        self.shortcut_manager = ShortcutManager(self)
        self.current_viewer_id: int | None = None
        self._preferred_refresh_id: int | None = None
        self.current_sidebar_selection: tuple[str, str | None] = ("all", None)
        self.scan_in_progress = False
        self._scan_worker: IndexWorker | None = None
        self._current_scan_job_id: str | None = None
        self._startup_completed = False

        self.model = WallpaperListModel()
        self.proxy = WallpaperFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)

        self.sidebar = SidebarPanel()
        self.grid_view = WallpaperGridView()
        self.grid_view.setModel(self.proxy)
        self.viewer = WallpaperViewer()
        self.details = DetailsPanel()
        self.stack = QStackedWidget()
        self.stack.addWidget(self.grid_view)
        self.stack.addWidget(self.viewer)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Recherche: nom, tags, notes, chemin")
        self.search_input.setClearButtonEnabled(True)
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Date", SortField.MTIME)
        self.sort_combo.addItem("Nom", SortField.NAME)
        self.sort_combo.addItem("Taille", SortField.SIZE)
        self.sort_combo.addItem("Orientation", SortField.ORIENTATION)
        self.sort_combo.addItem("Favoris", SortField.FAVORITE)
        self.sort_combo.addItem("Note", SortField.RATING)
        self.sort_combo.addItem("Vues", SortField.VIEWS)
        self.sort_combo.addItem("Luminosite", SortField.BRIGHTNESS)
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem("Toutes orientations", None)
        self.orientation_combo.addItem("Paysage", Orientation.LANDSCAPE)
        self.orientation_combo.addItem("Portrait", Orientation.PORTRAIT)
        self.orientation_combo.addItem("Carre", Orientation.SQUARE)
        self.source_combo = QComboBox()
        self.source_combo.addItem("Toutes sources", None)
        self.source_combo.addItem("Local", "local")
        self.source_combo.addItem("Wallhaven", "wallhaven")
        self.source_combo.addItem("Import manuel", "manual")
        self.source_combo.addItem("Gowall", "gowall")
        self.source_combo.addItem("Derive", "derived")
        self.favorites_only_checkbox = QCheckBox("Favoris")
        self.minimum_rating_spin = QSpinBox()
        self.minimum_rating_spin.setRange(0, 5)
        self.minimum_rating_spin.setPrefix("Note min ")
        self.scan_button = QPushButton("Scanner")
        self.filter_presets_combo = QComboBox()
        self.filter_presets_combo.setMinimumContentsLength(12)
        self.filter_presets_button = QToolButton()
        self.filter_presets_button.setText("Presets")
        self.filter_presets_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.filter_presets_menu = QMenu(self)
        self.filter_presets_menu.aboutToShow.connect(self._populate_filter_presets_menu)
        self.filter_presets_button.setMenu(self.filter_presets_menu)
        self.clear_filters_button = QPushButton("Effacer filtres")
        self.filter_chips_bar = QWidget()
        self.filter_chips_layout = QHBoxLayout(self.filter_chips_bar)
        self.filter_chips_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_chips_layout.setSpacing(8)
        self.filter_chips_bar.hide()
        self.workspace_header = QWidget()
        self.workspace_header.setObjectName("workspaceHeader")
        self.workspace_title_label = QLabel("Toute la bibliotheque")
        self.workspace_title_label.setObjectName("workspaceTitle")
        self.workspace_context_label = QLabel("Bibliotheque locale")
        self.workspace_context_label.setObjectName("workspaceContext")
        self.visible_metric_label = QLabel("0 visibles")
        self.selection_metric_label = QLabel("0 selection")
        self.mode_metric_label = QLabel("Mode Studio")
        self.last_action_metric_label = QLabel("Pret")
        for label in (
            self.visible_metric_label,
            self.selection_metric_label,
            self.mode_metric_label,
            self.last_action_metric_label,
        ):
            label.setObjectName("metricBadge")
        self.layout_studio_button = QPushButton("Studio")
        self.layout_browser_button = QPushButton("Browser")
        self.layout_focus_button = QPushButton("Focus")
        for button in (self.layout_studio_button, self.layout_browser_button, self.layout_focus_button):
            button.setCheckable(True)
            button.setObjectName("segmentedButton")
        self.toggle_sidebar_button = QPushButton("Sidebar")
        self.toggle_sidebar_button.setCheckable(True)
        self.toggle_sidebar_button.setObjectName("panelToggleButton")
        self.toggle_details_button = QPushButton("Inspecteur")
        self.toggle_details_button.setCheckable(True)
        self.toggle_details_button.setObjectName("panelToggleButton")
        self.thumbnail_slider = QSlider(Qt.Orientation.Horizontal)
        self.thumbnail_slider.setRange(160, 384)
        self.thumbnail_slider.setSingleStep(16)
        self.thumbnail_slider.setPageStep(32)
        self.thumbnail_slider.setValue(self.service.settings.thumbnail_size)
        self.thumbnail_slider.setFixedWidth(140)
        self.thumbnail_size_label = QLabel(f"{self.service.settings.thumbnail_size}px")
        self.thumbnail_size_label.setObjectName("metricBadge")
        self.selection_bar = QWidget()
        self.selection_bar.setObjectName("selectionBar")
        self.selection_bar_layout = QHBoxLayout(self.selection_bar)
        self.selection_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.selection_bar_layout.setSpacing(8)
        self.selection_count_label = QLabel("0 wallpapers selectionnes")
        self.selection_actions_button = QToolButton()
        self.selection_actions_button.setText("Actions selection")
        self.selection_actions_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.selection_actions_menu = QMenu(self)
        self.selection_actions_menu.aboutToShow.connect(self._populate_selection_actions_menu)
        self.selection_actions_button.setMenu(self.selection_actions_menu)
        self.selection_hint_label = QLabel("Clic droit pour plus d'actions")
        self.selection_hint_label.setObjectName("metricBadge")
        self.selection_bar.hide()
        self.tag_completion_model = QStringListModel(self)
        self.search_tag_completer = QCompleter(self.tag_completion_model, self)
        self.search_tag_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search_tag_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.search_tag_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.details_tag_completer = QCompleter(self.tag_completion_model, self)
        self.details_tag_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.details_tag_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.details_tag_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.search_input.setCompleter(self.search_tag_completer)
        self.details.tags_edit.setCompleter(self.details_tag_completer)
        self.status_summary_label = QLabel("0/0 visibles")
        self.status_selection_label = QLabel("0 selection")
        self.status_location_label = QLabel("Toute la bibliotheque")
        self.status_action_label = QLabel("Pret")

        self.slideshow_timer = QTimer(self)
        self.slideshow_timer.timeout.connect(self._advance_slideshow)
        self._update_slideshow_interval()

        self._setup_layout()
        self._setup_toolbar()
        self._retranslate_ui()
        self._apply_thumbnail_size()
        self.viewer.set_animated_video_previews_enabled(self.service.settings.animated_video_previews)
        self._connect_signals()
        self._setup_shortcuts()
        self._refresh_filter_presets_ui()
        self._apply_ui_preferences(persist=False)
        self._refresh_gowall_capabilities()

        default_sort_index = self.sort_combo.findData(self.service.settings.default_sort)
        self.sort_combo.setCurrentIndex(max(0, default_sort_index))

        self.watcher = PollingLibraryWatcher(
            self.service.settings.library_root,
            interval_ms=self.service.settings.polling_interval_ms,
        )
        self.watcher.library_changed.connect(self._debounced_rescan)
        self.rescan_timer = QTimer(self)
        self.rescan_timer.setSingleShot(True)
        self.rescan_timer.setInterval(1200)
        self.rescan_timer.timeout.connect(self.start_scan)

        self._show_status_message("Chargement de la bibliotheque...")
        self.statusBar().addPermanentWidget(self.status_summary_label)
        self.statusBar().addPermanentWidget(self.status_selection_label)
        self.statusBar().addPermanentWidget(self.status_location_label, 1)
        self.statusBar().addPermanentWidget(self.status_action_label, 1)
        if self.show_onboarding_on_startup and not self.service.settings.onboarding_completed:
            self._show_status_message("Configuration initiale requise")
            QTimer.singleShot(0, self._show_onboarding_if_needed)
        else:
            self._complete_startup()

    def closeEvent(self, event) -> None:
        self.watcher.stop()
        self.slideshow_timer.stop()
        self.thread_pool.waitForDone()
        self.service.settings.show_sidebar = not self.sidebar_dock.isHidden()
        self.service.settings.show_details = not self.details_dock.isHidden()
        self.service.settings.layout_preset = self._current_layout_mode()
        self.service.persist_settings()
        self.service.close()
        super().closeEvent(event)

    def _complete_startup(self) -> None:
        if self._startup_completed:
            return
        self.refresh_from_repository()
        self.watcher.start()
        self.start_scan()
        self._startup_completed = True

    def _show_onboarding_if_needed(self) -> None:
        if not self.show_onboarding_on_startup or self.service.settings.onboarding_completed:
            self._complete_startup()
            return
        dialog = OnboardingDialog(
            self.service.settings,
            wallpaper_backend_status=self.service.get_wallpaper_backend_status(),
            parent=self,
        )
        if dialog.exec() == dialog.DialogCode.Accepted:
            self._apply_new_settings(dialog.to_settings(), reset_sidebar=True)
        self._complete_startup()

    def _apply_new_settings(self, new_settings, *, reset_sidebar: bool) -> None:
        self.service.update_settings(new_settings)
        self.theme_controller.apply_theme(new_settings.theme_mode)
        set_language(new_settings.language)
        self.watcher.set_root_dir(new_settings.library_root)
        self.watcher.set_interval(new_settings.polling_interval_ms)
        self.thumbnail_slider.blockSignals(True)
        self.thumbnail_slider.setValue(new_settings.thumbnail_size)
        self.thumbnail_slider.blockSignals(False)
        self._apply_thumbnail_size()
        self.viewer.set_animated_video_previews_enabled(new_settings.animated_video_previews)
        self._update_slideshow_interval()
        self._setup_shortcuts()
        self._refresh_filter_presets_ui()
        self._retranslate_ui()
        self._apply_ui_preferences(persist=False)
        self._refresh_gowall_capabilities()
        self.sort_combo.setCurrentIndex(max(0, self.sort_combo.findData(new_settings.default_sort)))
        if reset_sidebar:
            self.current_sidebar_selection = ("all", None)
        self.refresh_from_repository()

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.search_input.setPlaceholderText(tr("Recherche: nom, tags, notes, chemin"))
        for index, label in enumerate(("Date", "Nom", "Taille", "Orientation", "Favoris", "Note", "Vues", "Luminosite")):
            self.sort_combo.setItemText(index, tr(label))
        for index, label in enumerate(("Toutes orientations", "Paysage", "Portrait", "Carre")):
            self.orientation_combo.setItemText(index, tr(label))
        for index, label in enumerate(("Toutes sources", "Local", "Wallhaven", "Import manuel", "Gowall", "Derive")):
            self.source_combo.setItemText(index, tr(label))
        self.favorites_only_checkbox.setText(tr("Favoris"))
        self.scan_button.setText(tr("Scanner"))
        self.filter_presets_button.setText(tr("Presets"))
        self.clear_filters_button.setText(tr("Effacer filtres"))
        self.layout_studio_button.setText(tr("Studio"))
        self.layout_browser_button.setText(tr("Browser"))
        self.layout_focus_button.setText(tr("Focus"))
        self.toggle_sidebar_button.setText(tr("Sidebar"))
        self.toggle_details_button.setText(tr("Inspecteur"))
        self.selection_actions_button.setText(tr("Actions selection"))
        self.selection_hint_label.setText(tr("Clic droit pour plus d'actions"))
        self.sidebar_dock.setWindowTitle(tr("Navigation"))
        self.details_dock.setWindowTitle(tr("Inspecteur"))
        self.scan_action.setText(tr("Scanner"))
        self.scan_inbox_action.setText(tr("Importer Inbox"))
        self.wallhaven_action.setText(tr("Wallhaven"))
        self.grid_action.setText(tr("Grille"))
        self.viewer_action.setText(tr("Visionneuse"))
        self.favorite_action.setText(tr("Favori"))
        self.move_action.setText(tr("Deplacer"))
        self.rename_action.setText(tr("Renommer"))
        self.delete_action.setText(tr("Corbeille"))
        self.gowall_action.setText(tr("Themes Gowall"))
        self.apply_action.setText(tr("Appliquer"))
        self.random_apply_action.setText(tr("Appliquer aleatoire"))
        self.review_inbox_action.setText(tr("Review Inbox"))
        self.review_duplicates_action.setText(tr("Review doublons"))
        self.duplicates_action.setText(tr("Rafraichir doublons"))
        self.slideshow_action.setText(tr("Slideshow"))
        self.history_action.setText(tr("Historique"))
        self.settings_action.setText(tr("Parametres"))
        self.shortcuts_help_action.setText(tr("Raccourcis"))
        self.undo_action.setText(tr("Annuler"))
        self.redo_action.setText(tr("Retablir"))
        self.edit_menu_button.setText(tr("Edition"))
        self.apply_menu_button.setText(tr("Appliquer"))
        self.review_menu_button.setText(tr("Review"))
        self.tools_menu_button.setText(tr("Outils"))
        self.filters_label.setText(tr("Filtres"))
        self.density_label.setText(tr("Densite"))
        self.toolbar.setWindowTitle(tr("Actions"))
        translate_qt_texts(self)
        self.minimum_rating_spin.setPrefix(tr("Note min "))
        self.sidebar.refresh_language()
        self.viewer.refresh_language()
        self.details.refresh_language()
        self._refresh_filter_presets_ui()
        self._update_filter_chip_bar()
        self._update_selection_bar()
        self._update_status_widgets()

    def _setup_layout(self) -> None:
        for button in (
            self.clear_filters_button,
            self.scan_button,
        ):
            button.setObjectName("secondaryButton")

        filter_bar = QWidget()
        filter_bar.setObjectName("filterBar")
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(16, 14, 16, 14)
        filter_layout.setSpacing(10)
        self.filters_label = QLabel("Filtres")
        self.filters_label.setObjectName("sectionLabel")
        filter_layout.addWidget(self.filters_label)
        filter_layout.addWidget(self.search_input, stretch=1)
        filter_layout.addWidget(self.filter_presets_combo)
        filter_layout.addWidget(self.filter_presets_button)
        filter_layout.addWidget(self.sort_combo)
        filter_layout.addWidget(self.orientation_combo)
        filter_layout.addWidget(self.source_combo)
        filter_layout.addWidget(self.favorites_only_checkbox)
        filter_layout.addWidget(self.minimum_rating_spin)
        filter_layout.addWidget(self.clear_filters_button)
        filter_layout.addWidget(self.scan_button)

        self.workspace_header.setObjectName("workspaceHeader")
        workspace_layout = QHBoxLayout(self.workspace_header)
        workspace_layout.setContentsMargins(18, 18, 18, 18)
        workspace_layout.setSpacing(14)
        workspace_text_column = QVBoxLayout()
        workspace_text_column.setSpacing(6)
        workspace_text_column.addWidget(self.workspace_title_label)
        workspace_text_column.addWidget(self.workspace_context_label)
        workspace_metrics_row = QHBoxLayout()
        workspace_metrics_row.setSpacing(8)
        workspace_metrics_row.addWidget(self.visible_metric_label)
        workspace_metrics_row.addWidget(self.selection_metric_label)
        workspace_metrics_row.addWidget(self.mode_metric_label)
        workspace_metrics_row.addWidget(self.last_action_metric_label)
        workspace_metrics_row.addStretch(1)
        workspace_text_column.addLayout(workspace_metrics_row)
        workspace_layout.addLayout(workspace_text_column, stretch=1)

        controls_column = QVBoxLayout()
        controls_column.setSpacing(8)
        layout_buttons_row = QHBoxLayout()
        layout_buttons_row.setSpacing(6)
        layout_buttons_row.addWidget(self.layout_studio_button)
        layout_buttons_row.addWidget(self.layout_browser_button)
        layout_buttons_row.addWidget(self.layout_focus_button)
        controls_column.addLayout(layout_buttons_row)
        density_row = QHBoxLayout()
        density_row.setSpacing(8)
        self.density_label = QLabel("Densite")
        density_row.addWidget(self.density_label)
        density_row.addWidget(self.thumbnail_slider)
        density_row.addWidget(self.thumbnail_size_label)
        density_row.addWidget(self.toggle_sidebar_button)
        density_row.addWidget(self.toggle_details_button)
        controls_column.addLayout(density_row)
        workspace_layout.addLayout(controls_column)

        center_widget = QWidget()
        center_widget.setObjectName("workspaceSurface")
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(14, 14, 14, 14)
        center_layout.setSpacing(12)
        center_layout.addWidget(self.workspace_header)
        center_layout.addWidget(filter_bar)
        self.selection_bar_layout.addWidget(self.selection_count_label)
        self.selection_bar_layout.addWidget(self.selection_hint_label)
        self.selection_bar_layout.addWidget(self.selection_actions_button)
        self.selection_bar_layout.addStretch(1)
        center_layout.addWidget(self.selection_bar)
        center_layout.addWidget(self.filter_chips_bar)
        center_layout.addWidget(self.stack, stretch=1)
        self.setCentralWidget(center_widget)

        self.sidebar_dock = QDockWidget("Navigation", self)
        self.sidebar_dock.setObjectName("sidebarDock")
        self.sidebar_dock.setWidget(self.sidebar)
        # Floating/movable docks are unstable on some Linux/Wayland stacks and
        # can trigger mouse-grab warnings followed by native crashes.
        self.sidebar_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sidebar_dock)

        self.details_dock = QDockWidget("Inspecteur", self)
        self.details_dock.setObjectName("detailsDock")
        self.details_dock.setWidget(self.details)
        self.details_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.details_dock)
        self.resizeDocks([self.sidebar_dock, self.details_dock], [300, 360], Qt.Orientation.Horizontal)

    def _setup_toolbar(self) -> None:
        self.toolbar = QToolBar("Actions", self)
        self.toolbar.setObjectName("primaryToolbar")
        self.toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

        self.scan_action = QAction("Scanner", self)
        self.scan_action.triggered.connect(self.start_scan)
        self.scan_inbox_action = QAction("Importer Inbox", self)
        self.scan_inbox_action.triggered.connect(self.import_inbox)
        self.wallhaven_action = QAction("Wallhaven", self)
        self.wallhaven_action.triggered.connect(self.show_wallhaven_gallery)
        self.grid_action = QAction("Grille", self)
        self.grid_action.triggered.connect(self.show_grid)
        self.viewer_action = QAction("Visionneuse", self)
        self.viewer_action.triggered.connect(self.open_current_in_viewer)
        self.favorite_action = QAction("Favori", self)
        self.favorite_action.triggered.connect(self.toggle_selected_favorite)
        self.move_action = QAction("Deplacer", self)
        self.move_action.triggered.connect(self.move_selected_wallpapers)
        self.rename_action = QAction("Renommer", self)
        self.rename_action.triggered.connect(self.rename_selected_wallpapers)
        self.delete_action = QAction("Corbeille", self)
        self.delete_action.triggered.connect(self.delete_selected_wallpapers)
        self.gowall_action = QAction("Themes Gowall", self)
        self.gowall_action.triggered.connect(self.show_gowall_themes)
        self.apply_action = QAction("Appliquer", self)
        self.apply_action.triggered.connect(self.apply_current_wallpaper)
        self.random_apply_action = QAction("Appliquer aleatoire", self)
        self.random_apply_action.triggered.connect(self.apply_random_filtered_wallpaper)
        self.review_inbox_action = QAction("Review Inbox", self)
        self.review_inbox_action.triggered.connect(self.show_inbox_review)
        self.review_duplicates_action = QAction("Review doublons", self)
        self.review_duplicates_action.triggered.connect(self.show_duplicate_review)
        self.duplicates_action = QAction("Rafraichir doublons", self)
        self.duplicates_action.triggered.connect(self.refresh_duplicate_filter)
        self.slideshow_action = QAction("Slideshow", self)
        self.slideshow_action.setCheckable(True)
        self.slideshow_action.triggered.connect(self.toggle_slideshow)
        self.history_action = QAction("Historique", self)
        self.history_action.triggered.connect(self.show_history)
        self.settings_action = QAction("Parametres", self)
        self.settings_action.triggered.connect(self.show_settings)
        self.shortcuts_help_action = QAction("Raccourcis", self)
        self.shortcuts_help_action.triggered.connect(self.show_shortcuts_help)
        self.undo_action = self.undo_stack.createUndoAction(self, "Annuler")
        self.redo_action = self.undo_stack.createRedoAction(self, "Retablir")
        self.toolbar.addAction(self.scan_action)
        self.toolbar.addAction(self.scan_inbox_action)
        self.toolbar.addAction(self.wallhaven_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.grid_action)
        self.toolbar.addAction(self.viewer_action)
        self.toolbar.addAction(self.slideshow_action)
        self.toolbar.addSeparator()
        self.edit_menu_button = self._create_toolbar_menu_button(
            "Edition",
            (
                self.favorite_action,
                self.move_action,
                self.rename_action,
                self.delete_action,
                self.gowall_action,
            ),
        )
        self.toolbar.addWidget(self.edit_menu_button)
        self.apply_menu_button = self._create_toolbar_menu_button(
            "Appliquer",
            (
                self.apply_action,
                self.random_apply_action,
            ),
        )
        self.toolbar.addWidget(self.apply_menu_button)
        self.review_menu_button = self._create_toolbar_menu_button(
            "Review",
            (
                self.review_inbox_action,
                self.review_duplicates_action,
                self.duplicates_action,
            ),
        )
        self.toolbar.addWidget(self.review_menu_button)
        self.toolbar.addAction(self.undo_action)
        self.toolbar.addAction(self.redo_action)
        self.tools_menu_button = self._create_toolbar_menu_button(
            "Outils",
            (
                self.history_action,
                self.settings_action,
                self.shortcuts_help_action,
            ),
        )
        self.toolbar.addWidget(self.tools_menu_button)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.sidebar_dock.toggleViewAction())
        self.toolbar.addAction(self.details_dock.toggleViewAction())

    def _connect_signals(self) -> None:
        self.search_input.textChanged.connect(self._schedule_search_update)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        self.orientation_combo.currentIndexChanged.connect(self._on_orientation_changed)
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.favorites_only_checkbox.toggled.connect(self.proxy.set_favorites_only)
        self.minimum_rating_spin.valueChanged.connect(self.proxy.set_minimum_rating)
        self.search_input.textChanged.connect(self._update_filter_chip_bar)
        self.orientation_combo.currentIndexChanged.connect(self._update_filter_chip_bar)
        self.source_combo.currentIndexChanged.connect(self._update_filter_chip_bar)
        self.favorites_only_checkbox.toggled.connect(self._update_filter_chip_bar)
        self.minimum_rating_spin.valueChanged.connect(self._update_filter_chip_bar)
        self.search_input.textChanged.connect(self._update_status_widgets)
        self.orientation_combo.currentIndexChanged.connect(self._update_status_widgets)
        self.source_combo.currentIndexChanged.connect(self._update_status_widgets)
        self.favorites_only_checkbox.toggled.connect(self._update_status_widgets)
        self.minimum_rating_spin.valueChanged.connect(self._update_status_widgets)
        self.search_timer.timeout.connect(self._apply_search_text)
        self.scan_button.clicked.connect(self.start_scan)
        self.clear_filters_button.clicked.connect(self.clear_filters)
        self.layout_studio_button.clicked.connect(lambda: self._apply_layout_preset("balanced"))
        self.layout_browser_button.clicked.connect(lambda: self._apply_layout_preset("browser"))
        self.layout_focus_button.clicked.connect(lambda: self._apply_layout_preset("focus"))
        self.toggle_sidebar_button.toggled.connect(self._set_sidebar_visible)
        self.toggle_details_button.toggled.connect(self._set_details_visible)
        self.thumbnail_slider.valueChanged.connect(self._on_thumbnail_slider_changed)
        self.sidebar.selection_changed.connect(self._on_sidebar_selection_changed)
        self.sidebar.context_menu_requested.connect(self._show_sidebar_context_menu)
        self.sidebar.wallpaper_drop_requested.connect(self._move_wallpaper_ids_to_directory)
        self.grid_view.open_requested.connect(self.open_current_in_viewer)
        self.grid_view.quick_preview_requested.connect(self.show_quick_preview)
        self.grid_view.current_proxy_index_changed.connect(self._on_current_proxy_index_changed)
        self.grid_view.context_menu_requested.connect(self._show_grid_context_menu)
        self.grid_view.thumbnail_zoom_requested.connect(self._change_thumbnail_density)
        self.viewer.navigate_requested.connect(self._navigate_viewer)
        self.viewer.exit_requested.connect(self.show_grid)
        self.viewer.gowall_requested.connect(self.show_gowall_themes)
        self.viewer.context_menu_requested.connect(self._show_viewer_context_menu)
        self.viewer.zoom_changed.connect(self._on_viewer_zoom_changed)
        self.details.favorite_changed.connect(self._set_current_favorite)
        self.details.save_requested.connect(self._save_current_details)
        self.details.hash_requested.connect(self._ensure_current_hash)
        self.details.open_folder_requested.connect(self._open_folder)
        self.details.open_source_requested.connect(self._open_external_target)
        self.job_queue.job_updated.connect(self._on_job_updated)
        self.sidebar_dock.visibilityChanged.connect(self._on_sidebar_dock_visibility_changed)
        self.details_dock.visibilityChanged.connect(self._on_details_dock_visibility_changed)
        if self.grid_view.selectionModel() is not None:
            self.grid_view.selectionModel().selectionChanged.connect(self._on_grid_selection_changed)

    def _setup_shortcuts(self) -> None:
        self.shortcut_manager.bind_shortcuts(
            self.service.settings.shortcuts,
            {
                "find": self.search_input.setFocus,
                "open_folder": self.open_current_folder,
                "quick_tag": self.quick_tag_current,
                "next_item": self.next_wallpaper,
                "previous_item": self.previous_wallpaper,
                "rating_1": lambda: self.set_current_rating(1),
                "rating_2": lambda: self.set_current_rating(2),
                "rating_3": lambda: self.set_current_rating(3),
                "rating_4": lambda: self.set_current_rating(4),
                "rating_5": lambda: self.set_current_rating(5),
            },
        )
        action_map = {
            "scan": self.scan_action,
            "scan_inbox": self.scan_inbox_action,
            "grid": self.grid_action,
            "viewer": self.viewer_action,
            "favorite": self.favorite_action,
            "move": self.move_action,
            "rename": self.rename_action,
            "delete": self.delete_action,
            "gowall": self.gowall_action,
            "apply": self.apply_action,
            "random_apply": self.random_apply_action,
            "review_inbox": self.review_inbox_action,
            "review_duplicates": self.review_duplicates_action,
            "duplicates": self.duplicates_action,
            "slideshow": self.slideshow_action,
            "history": self.history_action,
            "settings": self.settings_action,
            "shortcuts_help": self.shortcuts_help_action,
        }
        self.shortcut_manager.apply_action_shortcuts(self.service.settings.shortcuts, action_map)

    def _apply_ui_preferences(self, *, persist: bool) -> None:
        self.thumbnail_slider.blockSignals(True)
        self.thumbnail_slider.setValue(self.service.settings.thumbnail_size)
        self.thumbnail_slider.blockSignals(False)
        self.thumbnail_size_label.setText(f"{self.service.settings.thumbnail_size}px")
        self._set_dock_visibility(self.sidebar_dock, self.service.settings.show_sidebar)
        self._set_dock_visibility(self.details_dock, self.service.settings.show_details)
        self._sync_panel_toggle_buttons()
        self._sync_layout_buttons()
        self._update_workspace_header()
        if persist:
            self.service.persist_settings()

    def _refresh_gowall_capabilities(self) -> None:
        status = self.service.get_gowall_status()
        self.gowall_action.setEnabled(status.installed)
        self.gowall_action.setStatusTip(status.message)
        self.gowall_action.setToolTip(status.message)
        self.viewer.set_gowall_enabled(status.installed, status.message)
        wallhaven_status = self.service.get_wallhaven_status()
        self.wallhaven_action.setEnabled(wallhaven_status.available)
        self.wallhaven_action.setStatusTip(wallhaven_status.message)
        self.wallhaven_action.setToolTip(wallhaven_status.message)
        self.selection_actions_button.setToolTip(tr("Actions de groupe"))
        self.filter_presets_button.setToolTip(tr("Presets de filtres"))

    def _create_toolbar_menu_button(self, label: str, actions: tuple[QAction, ...]) -> QToolButton:
        button = QToolButton(self)
        button.setText(label)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(button)
        for action in actions:
            menu.addAction(action)
        button.setMenu(menu)
        return button

    def _set_dock_visibility(self, dock: QDockWidget, visible: bool) -> None:
        dock.blockSignals(True)
        dock.setVisible(visible)
        dock.blockSignals(False)

    def _sync_panel_toggle_buttons(self) -> None:
        self.toggle_sidebar_button.blockSignals(True)
        self.toggle_sidebar_button.setChecked(not self.sidebar_dock.isHidden())
        self.toggle_sidebar_button.blockSignals(False)
        self.toggle_details_button.blockSignals(True)
        self.toggle_details_button.setChecked(not self.details_dock.isHidden())
        self.toggle_details_button.blockSignals(False)

    def _sync_layout_buttons(self) -> None:
        preset = self._current_layout_mode()
        button_map = {
            "balanced": self.layout_studio_button,
            "browser": self.layout_browser_button,
            "focus": self.layout_focus_button,
        }
        for name, button in button_map.items():
            button.blockSignals(True)
            button.setChecked(name == preset)
            button.blockSignals(False)

    def _current_layout_mode(self) -> str:
        show_sidebar = not self.sidebar_dock.isHidden()
        show_details = not self.details_dock.isHidden()
        if show_sidebar and show_details:
            return "balanced"
        if show_sidebar and not show_details:
            return "browser"
        if not show_sidebar and not show_details:
            return "focus"
        return "custom"

    def _apply_layout_preset(self, preset: str) -> None:
        if preset == "browser":
            self.service.settings.show_sidebar = True
            self.service.settings.show_details = False
        elif preset == "focus":
            self.service.settings.show_sidebar = False
            self.service.settings.show_details = False
        else:
            preset = "balanced"
            self.service.settings.show_sidebar = True
            self.service.settings.show_details = True
        self.service.settings.layout_preset = preset
        self._apply_ui_preferences(persist=True)
        self.last_action_metric_label.setText(
            {
                "balanced": tr("Mode Studio"),
                "browser": tr("Mode Browser"),
                "focus": tr("Mode Focus"),
            }[preset]
        )
        self._show_status_message(tr("Layout {preset}", preset=preset), 2000)

    def _set_sidebar_visible(self, visible: bool) -> None:
        self.service.settings.show_sidebar = visible
        self._set_dock_visibility(self.sidebar_dock, visible)
        self.service.settings.layout_preset = self._current_layout_mode()
        self._sync_panel_toggle_buttons()
        self._sync_layout_buttons()
        self._update_workspace_header()
        self.service.persist_settings()

    def _set_details_visible(self, visible: bool) -> None:
        self.service.settings.show_details = visible
        self._set_dock_visibility(self.details_dock, visible)
        self.service.settings.layout_preset = self._current_layout_mode()
        self._sync_panel_toggle_buttons()
        self._sync_layout_buttons()
        self._update_workspace_header()
        self.service.persist_settings()

    def _on_sidebar_dock_visibility_changed(self, visible: bool) -> None:
        self.service.settings.show_sidebar = visible
        self.service.settings.layout_preset = self._current_layout_mode()
        self._sync_panel_toggle_buttons()
        self._sync_layout_buttons()
        self._update_workspace_header()
        self.service.persist_settings()

    def _on_details_dock_visibility_changed(self, visible: bool) -> None:
        self.service.settings.show_details = visible
        self.service.settings.layout_preset = self._current_layout_mode()
        self._sync_panel_toggle_buttons()
        self._sync_layout_buttons()
        self._update_workspace_header()
        self.service.persist_settings()

    def _schedule_search_update(self, _value: str) -> None:
        self.search_timer.start()

    def _apply_search_text(self) -> None:
        self.proxy.set_search_text(self.search_input.text())
        self._update_status_widgets()

    def _on_thumbnail_slider_changed(self, value: int) -> None:
        snapped = max(160, min(384, int(round(value / 16) * 16)))
        if snapped != value:
            self.thumbnail_slider.blockSignals(True)
            self.thumbnail_slider.setValue(snapped)
            self.thumbnail_slider.blockSignals(False)
        if snapped == self.service.settings.thumbnail_size:
            self.thumbnail_size_label.setText(f"{snapped}px")
            return
        self.service.settings.thumbnail_size = snapped
        self.thumbnail_size_label.setText(f"{snapped}px")
        self._apply_thumbnail_size()
        self.service.persist_settings()

    def _change_thumbnail_density(self, direction: int) -> None:
        self.thumbnail_slider.setValue(self.thumbnail_slider.value() + (16 if direction > 0 else -16))

    def _apply_thumbnail_size(self) -> None:
        thumb_size = self.service.settings.thumbnail_size
        self.grid_view.setIconSize(QSize(thumb_size, thumb_size))
        self.grid_view.setGridSize(QSize(thumb_size + 54, thumb_size + 72))
        self.thumbnail_size_label.setText(f"{thumb_size}px")

    def _update_slideshow_interval(self) -> None:
        self.slideshow_timer.setInterval(self.service.settings.slideshow_interval_seconds * 1000)

    def refresh_from_repository(self, preserve_id: int | None = None) -> None:
        scroll_position = self._capture_grid_scroll_position()
        viewer_was_active = self.stack.currentWidget() is self.viewer
        viewer_was_quick_preview = self.viewer.quick_preview_mode if viewer_was_active else False
        if viewer_was_active:
            self.viewer.clearFocus()
            self.stack.setCurrentWidget(self.grid_view)
        wallpapers = self.service.list_wallpapers()
        duplicate_ids = self.service.duplicate_wallpaper_ids()
        self.model.set_wallpapers(wallpapers)
        self.proxy.set_duplicate_ids(duplicate_ids)
        self._refresh_tag_completions()
        folders = self.service.list_folders()
        stats = self.service.library_stats()
        self.sidebar.populate(
            self.service.settings.library_root,
            folders,
            selected_key=self.current_sidebar_selection,
        )
        self.sidebar.update_stats(stats.total, stats.favorites, stats.unviewed, stats.duplicates)
        self._on_sort_changed()
        selection_restored = False

        if preserve_id is not None:
            proxy_index = self._proxy_index_for_id(preserve_id)
            if proxy_index.isValid():
                self.grid_view.setCurrentIndex(proxy_index)
                self.grid_view.selectionModel().select(
                    proxy_index,
                    QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
                )
                self._on_current_proxy_index_changed(proxy_index)
                selection_restored = True

        if not selection_restored and self.proxy.rowCount() > 0:
            first = self.proxy.index(0, 0)
            self.grid_view.setCurrentIndex(first)
            self.grid_view.selectionModel().select(
                first,
                QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
            )
            self._on_current_proxy_index_changed(first)
        elif not selection_restored:
            self.details.set_wallpaper(None)
            self.viewer.set_wallpaper(None)
        self._update_filter_chip_bar()
        self._update_selection_bar()
        self._update_status_widgets()
        self._restore_grid_scroll_position(scroll_position)
        if viewer_was_active:
            self._restore_viewer_after_refresh(quick_preview=viewer_was_quick_preview)

    def _capture_grid_scroll_position(self) -> tuple[int, int]:
        return (
            self.grid_view.horizontalScrollBar().value(),
            self.grid_view.verticalScrollBar().value(),
        )

    def _restore_grid_scroll_position(self, scroll_position: tuple[int, int]) -> None:
        horizontal, vertical = scroll_position

        def restore() -> None:
            self.grid_view.horizontalScrollBar().setValue(horizontal)
            self.grid_view.verticalScrollBar().setValue(vertical)

        QTimer.singleShot(0, restore)

    def _restore_viewer_after_refresh(self, *, quick_preview: bool) -> None:
        wallpaper = self.current_wallpaper()
        if wallpaper is None or wallpaper.id is None:
            self.current_viewer_id = None
            self.viewer.set_quick_preview_mode(False)
            self.viewer.set_wallpaper(None)
            self.grid_view.setFocus()
            return
        self.current_viewer_id = wallpaper.id
        self.viewer.set_quick_preview_mode(quick_preview)
        self.viewer.set_wallpaper(wallpaper)
        self.details.set_wallpaper(wallpaper)
        self.stack.setCurrentWidget(self.viewer)
        self.viewer.setFocus()
        self._update_selection_bar()
        self._update_status_widgets()

    def _on_sort_changed(self) -> None:
        value = self.sort_combo.currentData()
        if not value:
            value = self.service.settings.default_sort
        self.proxy.set_sort_field(value)
        order = Qt.SortOrder.AscendingOrder if value in {SortField.NAME, SortField.ORIENTATION, SortField.BRIGHTNESS} else Qt.SortOrder.DescendingOrder
        self.proxy.sort(0, order)

    def _on_orientation_changed(self) -> None:
        self.proxy.set_orientation_filter(self.orientation_combo.currentData())

    def _on_source_changed(self) -> None:
        value = self.source_combo.currentData()
        self.proxy.set_source_filter(None if value in (None, "") else str(value))

    def _on_sidebar_selection_changed(self, selection: tuple[str, str | None]) -> None:
        self.current_sidebar_selection = selection
        kind, value = selection
        self.proxy.set_folder_filter(None)
        self.proxy.set_collection_filter(None)
        if kind == "folder" and value:
            self.proxy.set_folder_filter(Path(value))
        elif kind == "collection" and value:
            collection = SmartCollection(value)
            if collection == SmartCollection.DUPLICATES:
                self.refresh_duplicate_filter()
            self.proxy.set_collection_filter(collection)
        self._focus_first_visible_wallpaper()
        self._update_filter_chip_bar()
        self._update_status_widgets()

    def _focus_first_visible_wallpaper(self) -> None:
        if self.proxy.rowCount() <= 0:
            self.details.set_wallpaper(None)
            self.viewer.set_wallpaper(None)
            return
        first = self.proxy.index(0, 0)
        self.grid_view.setCurrentIndex(first)
        self._on_current_proxy_index_changed(first)

    def _on_current_proxy_index_changed(self, proxy_index: QModelIndex) -> None:
        wallpaper = self._wallpaper_from_proxy(proxy_index)
        self.details.set_wallpaper(wallpaper)
        if self.stack.currentWidget() is self.viewer and wallpaper is not None:
            self.current_viewer_id = wallpaper.id
        self._update_workspace_header()

    def _wallpaper_from_proxy(self, proxy_index: QModelIndex) -> Wallpaper | None:
        if not proxy_index.isValid():
            return None
        source_index = self.proxy.mapToSource(proxy_index)
        return self.model.wallpaper_from_index(source_index)

    def _proxy_index_for_id(self, wallpaper_id: int) -> QModelIndex:
        source_index = self.model.source_index_for_id(wallpaper_id)
        if not source_index.isValid():
            return QModelIndex()
        return self.proxy.mapFromSource(source_index)

    def current_wallpaper(self) -> Wallpaper | None:
        if self.stack.currentWidget() is self.viewer and self.current_viewer_id is not None:
            return self.model.wallpaper_by_id(self.current_viewer_id)
        return self._wallpaper_from_proxy(self.grid_view.currentIndex())

    def selected_wallpaper_ids(self) -> list[int]:
        if self.stack.currentWidget() is self.viewer:
            wallpaper = self.current_wallpaper()
            return [wallpaper.id] if wallpaper and wallpaper.id is not None else []
        ids: list[int] = []
        for proxy_index in self.grid_view.selectionModel().selectedIndexes():
            wallpaper = self._wallpaper_from_proxy(proxy_index)
            if wallpaper and wallpaper.id is not None:
                ids.append(wallpaper.id)
        return list(dict.fromkeys(ids))

    def visible_wallpaper_ids(self) -> list[int]:
        ids: list[int] = []
        for row in range(self.proxy.rowCount()):
            wallpaper = self._wallpaper_from_proxy(self.proxy.index(row, 0))
            if wallpaper and wallpaper.id is not None:
                ids.append(wallpaper.id)
        return ids

    def _on_grid_selection_changed(self, *_args) -> None:
        self._update_selection_bar()
        self._update_status_widgets()

    def _update_selection_bar(self) -> None:
        count = len(self.selected_wallpaper_ids()) if self.stack.currentWidget() is self.grid_view else 0
        self.selection_count_label.setText(tr("{count} wallpapers selectionnes", count=count))
        self.selection_bar.setVisible(count > 1)
        self.selection_actions_button.setEnabled(count > 0)
        self.selection_metric_label.setText(tr("{count} selection", count=count))

    def _update_filter_chip_bar(self, *_args) -> None:
        while self.filter_chips_layout.count():
            item = self.filter_chips_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        chips: list[tuple[str, object]] = []
        if self.current_sidebar_selection != ("all", None):
            chips.append((self._selection_label(self.current_sidebar_selection), self._clear_sidebar_filter))
        if self.search_input.text().strip():
            chips.append((tr("Recherche: {query}", query=self.search_input.text().strip()), self.search_input.clear))
        if self.orientation_combo.currentIndex() > 0:
            chips.append((tr("Orientation: {orientation}", orientation=self.orientation_combo.currentText()), lambda: self.orientation_combo.setCurrentIndex(0)))
        if self.source_combo.currentIndex() > 0:
            chips.append((tr("Source: {source}", source=self.source_combo.currentText()), lambda: self.source_combo.setCurrentIndex(0)))
        if self.favorites_only_checkbox.isChecked():
            chips.append((tr("Favoris seulement"), lambda: self.favorites_only_checkbox.setChecked(False)))
        if self.minimum_rating_spin.value() > 0:
            chips.append((tr("Note min {rating}", rating=self.minimum_rating_spin.value()), lambda: self.minimum_rating_spin.setValue(0)))

        for label, callback in chips:
            button = QPushButton(tr("{label} x", label=label))
            button.setObjectName("filterChip")
            button.clicked.connect(callback)
            self.filter_chips_layout.addWidget(button)

        self.filter_chips_layout.addStretch(1)
        self.filter_chips_bar.setVisible(bool(chips))

    def _selection_label(self, selection: tuple[str, str | None]) -> str:
        kind, value = selection
        if kind == "collection" and value:
            try:
                return tr("Collection: {label}", label=smart_collection_label(SmartCollection(value)))
            except ValueError:
                return tr("Collection: {label}", label=value)
        if kind == "folder" and value:
            return tr("Dossier: {folder}", folder=Path(value).name or value)
        return tr("Toute la bibliotheque")

    def _update_status_widgets(self, *_args) -> None:
        self.status_summary_label.setText(tr("{visible}/{total} visibles", visible=self.proxy.rowCount(), total=self.model.rowCount()))
        self.status_selection_label.setText(tr("{count} selection", count=len(self.selected_wallpaper_ids())))
        self.status_location_label.setText(self._selection_label(self.current_sidebar_selection))
        self._update_workspace_header()

    def _show_status_message(self, message: str, timeout_ms: int = 0) -> None:
        self.status_action_label.setText(message)
        self.last_action_metric_label.setText(message)
        self.statusBar().showMessage(message, timeout_ms)

    def _update_workspace_header(self) -> None:
        current = self.current_wallpaper()
        location_label = self._selection_label(self.current_sidebar_selection)
        self.workspace_title_label.setText(location_label)
        if current is None:
            current_label = tr("Aucun wallpaper selectionne")
        else:
            current_label = current.filename
        mode_labels = {
            "balanced": tr("Mode Studio"),
            "browser": tr("Mode Browser"),
            "focus": tr("Mode Focus"),
            "custom": tr("Mode Custom"),
        }
        self.workspace_context_label.setText(tr("{current_label} · Densite {size}px · {count} resultat(s)", current_label=current_label, size=self.service.settings.thumbnail_size, count=self.proxy.rowCount()))
        self.visible_metric_label.setText(tr("{visible}/{total} visibles", visible=self.proxy.rowCount(), total=self.model.rowCount()))
        self.selection_metric_label.setText(tr("{count} selection", count=len(self.selected_wallpaper_ids())))
        self.mode_metric_label.setText(mode_labels.get(self._current_layout_mode(), tr("Mode Custom")))

    def _refresh_tag_completions(self) -> None:
        self.tag_completion_model.setStringList(self.service.list_tags())

    def _refresh_filter_presets_ui(self) -> None:
        current_text = self.filter_presets_combo.currentText()
        self.filter_presets_combo.blockSignals(True)
        self.filter_presets_combo.clear()
        self.filter_presets_combo.addItem("")
        for preset_name in sorted(self.service.settings.filter_presets):
            self.filter_presets_combo.addItem(preset_name)
        index = self.filter_presets_combo.findText(current_text)
        self.filter_presets_combo.setCurrentIndex(max(0, index))
        self.filter_presets_combo.blockSignals(False)
        self.filter_presets_button.setEnabled(True)

    def _populate_filter_presets_menu(self) -> None:
        self.filter_presets_menu.clear()
        apply_action = self.filter_presets_menu.addAction(tr("Appliquer le preset"))
        apply_action.triggered.connect(self.apply_selected_filter_preset)
        apply_action.setEnabled(bool(self.filter_presets_combo.currentText().strip()))
        self.filter_presets_menu.addSeparator()
        save_action = self.filter_presets_menu.addAction(tr("Sauver le filtre courant"))
        save_action.triggered.connect(self.save_current_filter_preset)
        delete_action = self.filter_presets_menu.addAction(tr("Supprimer le preset"))
        delete_action.triggered.connect(self.delete_selected_filter_preset)
        delete_action.setEnabled(bool(self.filter_presets_combo.currentText().strip()))

    def _populate_selection_actions_menu(self) -> None:
        self.selection_actions_menu.clear()
        count = len(self.selected_wallpaper_ids())
        favorite_action = self.selection_actions_menu.addAction(tr("Favori"))
        favorite_action.triggered.connect(self.toggle_selected_favorite)
        favorite_action.setEnabled(count > 0)
        move_action = self.selection_actions_menu.addAction(tr("Deplacer"))
        move_action.triggered.connect(self.move_selected_wallpapers)
        move_action.setEnabled(count > 0)
        rename_action = self.selection_actions_menu.addAction(tr("Renommer"))
        rename_action.triggered.connect(self.rename_selected_wallpapers)
        rename_action.setEnabled(count > 0)
        delete_action = self.selection_actions_menu.addAction(tr("Corbeille"))
        delete_action.triggered.connect(self.delete_selected_wallpapers)
        delete_action.setEnabled(count > 0)

    def _current_filter_preset_payload(self) -> dict[str, str | int | bool | None]:
        sort_value = self.sort_combo.currentData()
        orientation_value = self.orientation_combo.currentData()
        return {
            "search_text": self.search_input.text().strip(),
            "sort": None if sort_value is None else str(sort_value.value if isinstance(sort_value, SortField) else sort_value),
            "orientation": None if orientation_value is None else str(orientation_value.value if isinstance(orientation_value, Orientation) else orientation_value),
            "source": None if self.source_combo.currentData() is None else str(self.source_combo.currentData()),
            "favorites_only": self.favorites_only_checkbox.isChecked(),
            "minimum_rating": self.minimum_rating_spin.value(),
            "sidebar_kind": self.current_sidebar_selection[0],
            "sidebar_value": self.current_sidebar_selection[1],
        }

    def save_current_filter_preset(self) -> None:
        preset_name, ok = QInputDialog.getText(self, tr("Sauver preset"), tr("Nom du preset"))
        preset_name = preset_name.strip()
        if not ok or not preset_name:
            return
        self.service.settings.filter_presets[preset_name] = self._current_filter_preset_payload()
        self.service.persist_settings()
        self._refresh_filter_presets_ui()
        self.filter_presets_combo.setCurrentText(preset_name)
        self._show_status_message(tr("Preset enregistre: {preset_name}", preset_name=preset_name), 3000)

    def apply_selected_filter_preset(self) -> None:
        preset_name = self.filter_presets_combo.currentText().strip()
        if not preset_name:
            return
        preset = self.service.settings.filter_presets.get(preset_name)
        if not preset:
            return
        self.search_input.setText(str(preset.get("search_text", "")))
        sort_value = preset.get("sort")
        if sort_value is not None:
            self.sort_combo.setCurrentIndex(max(0, self.sort_combo.findData(SortField(str(sort_value)))))
        orientation_value = preset.get("orientation")
        if orientation_value is None:
            self.orientation_combo.setCurrentIndex(0)
        else:
            self.orientation_combo.setCurrentIndex(max(0, self.orientation_combo.findData(Orientation(str(orientation_value)))))
        source_value = preset.get("source")
        if source_value is None:
            self.source_combo.setCurrentIndex(0)
        else:
            self.source_combo.setCurrentIndex(max(0, self.source_combo.findData(str(source_value))))
        self.favorites_only_checkbox.setChecked(bool(preset.get("favorites_only", False)))
        self.minimum_rating_spin.setValue(int(preset.get("minimum_rating", 0) or 0))
        sidebar_kind = str(preset.get("sidebar_kind", "all"))
        sidebar_value = preset.get("sidebar_value")
        self.sidebar.select_key((sidebar_kind, None if sidebar_value in ("", None) else str(sidebar_value)))
        self.search_timer.stop()
        self._apply_search_text()
        self._show_status_message(tr("Preset applique: {preset_name}", preset_name=preset_name), 3000)

    def delete_selected_filter_preset(self) -> None:
        preset_name = self.filter_presets_combo.currentText().strip()
        if not preset_name or preset_name not in self.service.settings.filter_presets:
            return
        del self.service.settings.filter_presets[preset_name]
        self.service.persist_settings()
        self._refresh_filter_presets_ui()
        self._show_status_message(tr("Preset supprime: {preset_name}", preset_name=preset_name), 3000)

    def _clear_sidebar_filter(self) -> None:
        self.sidebar.select_key(("all", None))

    def clear_filters(self) -> None:
        self.search_input.clear()
        self.orientation_combo.setCurrentIndex(0)
        self.source_combo.setCurrentIndex(0)
        self.favorites_only_checkbox.setChecked(False)
        self.minimum_rating_spin.setValue(0)
        self._clear_sidebar_filter()
        self.search_timer.stop()
        self._apply_search_text()
        self._show_status_message(tr("Filtres effaces"), 3000)

    def set_current_rating(self, rating: int) -> None:
        wallpaper = self.current_wallpaper()
        if wallpaper is None or wallpaper.id is None or wallpaper.rating == rating:
            return
        self.undo_stack.push(
            UpdateWallpaperDetailsCommand(
                self.service,
                wallpaper.id,
                tags=list(wallpaper.tags),
                notes=wallpaper.notes,
                rating=rating,
                refresh_callback=self._refresh_after_command,
            )
        )
        self._show_status_message(tr("Note {rating} appliquee", rating=rating), 2500)

    def quick_tag_current(self) -> None:
        wallpaper = self.current_wallpaper()
        if wallpaper is None or wallpaper.id is None:
            return
        text, ok = QInputDialog.getText(
            self,
            tr("Tags rapides"),
            tr("Tags (separes par des virgules)"),
            text=", ".join(wallpaper.tags),
        )
        if not ok:
            return
        tags = [tag.strip() for tag in text.split(",") if tag.strip()]
        if tags == list(wallpaper.tags):
            return
        self.undo_stack.push(
            UpdateWallpaperDetailsCommand(
                self.service,
                wallpaper.id,
                tags=tags,
                notes=wallpaper.notes,
                rating=wallpaper.rating,
                refresh_callback=self._refresh_after_command,
            )
        )
        self._show_status_message(tr("Tags mis a jour"), 2500)

    def open_current_folder(self) -> None:
        wallpaper = self.current_wallpaper()
        if wallpaper is None:
            return
        self._open_folder(wallpaper.path.parent)

    def show_inbox_review(self) -> None:
        self.sidebar.select_key(("collection", SmartCollection.INBOX.value))
        if self.proxy.rowCount() <= 0:
            self._show_status_message(tr("Inbox vide"), 3000)
            return
        self.open_current_in_viewer()
        self._show_status_message(tr("Review Inbox actif"), 3000)

    def show_wallhaven_gallery(self) -> None:
        dialog = WallhavenDialog(self.service, self.job_queue, self)
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.imported_count <= 0:
            return
        preserve_id = self.current_wallpaper().id if self.current_wallpaper() else None
        self.refresh_from_repository(preserve_id=preserve_id)
        self.sidebar.select_key(("collection", SmartCollection.INBOX.value))
        self._show_status_message(
            tr("{count} wallpaper(s) importes depuis Wallhaven", count=dialog.imported_count),
            5000,
        )

    def _show_grid_context_menu(self, point) -> None:
        index = self.grid_view.indexAt(point)
        if not index.isValid():
            return
        if self.grid_view.selectionModel() is not None and not self.grid_view.selectionModel().isSelected(index):
            self.grid_view.setCurrentIndex(index)
            self.grid_view.selectionModel().select(
                index,
                QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
            )
        menu = QMenu(self)
        wallpaper = self.current_wallpaper()
        menu.addAction(tr("Ouvrir"), self.open_current_in_viewer)
        menu.addAction(tr("Favori"), self.toggle_selected_favorite)
        menu.addAction(tr("Appliquer"), self.apply_current_wallpaper)
        gowall_action = menu.addAction(tr("Themes Gowall"), self.show_gowall_themes)
        gowall_action.setEnabled(self.gowall_action.isEnabled() and wallpaper is not None and wallpaper.media_kind is MediaKind.IMAGE)
        menu.addAction(tr("Ouvrir dossier"), self.open_current_folder)
        menu.addSeparator()
        menu.addAction(tr("Deplacer"), self.move_selected_wallpapers)
        menu.addAction(tr("Renommer"), self.rename_selected_wallpapers)
        menu.addAction(tr("Corbeille"), self.delete_selected_wallpapers)
        menu.exec(self.grid_view.viewport().mapToGlobal(point))

    def _show_viewer_context_menu(self, point) -> None:
        wallpaper = self.current_wallpaper()
        if wallpaper is None:
            return
        menu = QMenu(self)
        menu.addAction(tr("Favori"), self.toggle_selected_favorite)
        menu.addAction(tr("Appliquer"), self.apply_current_wallpaper)
        gowall_action = menu.addAction(tr("Themes Gowall"), self.show_gowall_themes)
        gowall_action.setEnabled(self.gowall_action.isEnabled() and wallpaper.media_kind is MediaKind.IMAGE)
        menu.addAction(tr("Ouvrir dossier"), self.open_current_folder)
        menu.addSeparator()
        menu.addAction(tr("Tags rapides"), self.quick_tag_current)
        menu.addAction(tr("Deplacer"), self.move_selected_wallpapers)
        menu.addAction(tr("Renommer"), self.rename_selected_wallpapers)
        menu.addAction(tr("Corbeille"), self.delete_selected_wallpapers)
        menu.exec(self.viewer.context_global_pos(point))

    def _show_sidebar_context_menu(self, point) -> None:
        selection = self.sidebar.selection_at(point)
        if selection is None:
            return
        self.sidebar.select_key(selection)
        kind, value = selection
        menu = QMenu(self)
        if kind == "folder" and value:
            menu.addAction(tr("Afficher ce dossier"), lambda: self.sidebar.select_key(selection))
            menu.addAction(tr("Ouvrir le dossier"), lambda: self._open_folder(Path(value)))
        elif kind == "collection" and value:
            if value == SmartCollection.DUPLICATES.value:
                menu.addAction(tr("Rafraichir doublons"), self.refresh_duplicate_filter)
                menu.addAction(tr("Review doublons"), self.show_duplicate_review)
            if value == SmartCollection.INBOX.value:
                menu.addAction(tr("Review Inbox"), self.show_inbox_review)
        if menu.actions():
            menu.exec(self.sidebar.tree.viewport().mapToGlobal(point))

    def show_quick_preview(self, index: QModelIndex | None = None) -> None:
        self.open_current_in_viewer(index, quick_preview=True)
        self._show_status_message(tr("Quick preview"), 2000)

    def show_gowall_themes(self) -> None:
        self._refresh_gowall_capabilities()
        wallpaper = self.current_wallpaper()
        if wallpaper is None or wallpaper.id is None:
            return
        if wallpaper.media_kind is not MediaKind.IMAGE:
            QMessageBox.information(
                self,
                tr("Gowall"),
                tr("Les themes Gowall ne s'appliquent qu'aux wallpapers image."),
            )
            return
        status = self.service.get_gowall_status()
        if not status.installed:
            QMessageBox.information(self, tr("Gowall absent"), status.message)
            return
        dialog = GowallThemeDialog(self.service, self.job_queue, wallpaper, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if dialog.saved_wallpaper is not None:
            self.refresh_from_repository(preserve_id=dialog.saved_wallpaper.id if dialog.saved_wallpaper.id is not None else None)
            self._show_status_message(
                tr("Rendu Gowall sauvegarde: {filename}", filename=dialog.saved_wallpaper.filename),
                5000,
            )
            return
        if dialog.applied_output_path is None:
            return
        self._show_status_message(
            tr(
                "Theme Gowall applique sur {filename}: {output_name}",
                filename=wallpaper.filename,
                output_name=dialog.applied_output_path.name,
            ),
            5000,
        )

    def open_current_in_viewer(self, index: QModelIndex | None = None, *, quick_preview: bool = False) -> None:
        wallpaper = self.current_wallpaper() if index is None or not isinstance(index, QModelIndex) else self._wallpaper_from_proxy(index)
        if wallpaper is None or wallpaper.id is None:
            return
        refreshed = self.service.mark_viewed(wallpaper.id)
        self.model.update_wallpaper(refreshed)
        self.current_viewer_id = refreshed.id
        self.viewer.set_quick_preview_mode(quick_preview)
        self.viewer.set_wallpaper(refreshed)
        self.details.set_wallpaper(refreshed)
        self.stack.setCurrentWidget(self.viewer)
        self.viewer.setFocus()
        self._schedule_adjacent_preload(refreshed.id or 0)
        self._update_selection_bar()
        self._update_status_widgets()

    def show_grid(self) -> None:
        self.slideshow_timer.stop()
        self.slideshow_action.setChecked(False)
        self.viewer.set_quick_preview_mode(False)
        self.stack.setCurrentWidget(self.grid_view)
        self.grid_view.setFocus()
        current = self.grid_view.currentIndex()
        if current.isValid():
            self._on_current_proxy_index_changed(current)
        self._update_selection_bar()
        self._update_status_widgets()

    def _navigate_viewer(self, step: int) -> None:
        self._move_viewer(step, wrap=False)

    def next_wallpaper(self) -> None:
        self._move_current_selection(1)

    def previous_wallpaper(self) -> None:
        self._move_current_selection(-1)

    def _move_current_selection(self, step: int) -> None:
        if self.stack.currentWidget() is self.viewer:
            self._move_viewer(step, wrap=False)
            return
        current = self.grid_view.currentIndex()
        if not current.isValid() or self.proxy.rowCount() <= 0:
            return
        target_row = max(0, min(self.proxy.rowCount() - 1, current.row() + step))
        target = self.proxy.index(target_row, 0)
        self.grid_view.setCurrentIndex(target)
        self.grid_view.selectionModel().select(
            target,
            QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
        )
        self.grid_view.scrollTo(target)
        self._on_current_proxy_index_changed(target)

    def _move_viewer(self, step: int, *, wrap: bool) -> None:
        if self.current_viewer_id is None:
            return
        current_proxy = self._proxy_index_for_id(self.current_viewer_id)
        if not current_proxy.isValid():
            return
        next_row = current_proxy.row() + step
        if wrap and self.proxy.rowCount() > 0:
            next_row %= self.proxy.rowCount()
        if next_row < 0 or next_row >= self.proxy.rowCount():
            return
        next_proxy = self.proxy.index(next_row, 0)
        self.grid_view.setCurrentIndex(next_proxy)
        self.open_current_in_viewer(next_proxy)

    def _adjacent_wallpaper_id(
        self,
        wallpaper_id: int,
        *,
        excluded_ids: set[int] | None = None,
    ) -> int | None:
        current_proxy = self._proxy_index_for_id(wallpaper_id)
        if not current_proxy.isValid():
            return None
        blocked = excluded_ids or set()
        for row in range(current_proxy.row() + 1, self.proxy.rowCount()):
            wallpaper = self._wallpaper_from_proxy(self.proxy.index(row, 0))
            if wallpaper is not None and wallpaper.id is not None and wallpaper.id not in blocked:
                return wallpaper.id
        for row in range(current_proxy.row() - 1, -1, -1):
            wallpaper = self._wallpaper_from_proxy(self.proxy.index(row, 0))
            if wallpaper is not None and wallpaper.id is not None and wallpaper.id not in blocked:
                return wallpaper.id
        return None

    def _schedule_adjacent_preload(self, wallpaper_id: int) -> None:
        current_proxy = self._proxy_index_for_id(wallpaper_id)
        if not current_proxy.isValid():
            return
        preload_paths: list[Path] = []
        for delta in (-1, 1):
            row = current_proxy.row() + delta
            if row < 0 or row >= self.proxy.rowCount():
                continue
            wallpaper = self._wallpaper_from_proxy(self.proxy.index(row, 0))
            if wallpaper is not None:
                preload_paths.append(wallpaper.path)
        if not preload_paths:
            return
        worker = PreloadWorker(preload_paths)
        self.job_queue.submit("preload", worker, description=tr("Prechargement viewer"))

    def _on_viewer_zoom_changed(self, scale: float) -> None:
        if self.stack.currentWidget() is self.viewer:
            self.status_action_label.setText(tr("Zoom {percent}%", percent=int(scale * 100)))

    def _on_job_updated(self, info: JobInfo) -> None:
        if info.name == "preload" and info.status == "done":
            return
        if info.status in {"pending", "running"} and info.message:
            self.last_action_metric_label.setText(info.message)
            return
        if info.status == "done" and info.message:
            self.last_action_metric_label.setText(info.message)
            return
        if info.status == "failed":
            self.status_action_label.setText(
                tr("{job_name}: {message}", job_name=tr(info.name), message=info.message)
            )

    def start_scan(self) -> None:
        if self.scan_in_progress:
            return
        self.scan_in_progress = True
        self._show_status_message(tr("Scan en cours..."))
        worker = IndexWorker(self.service.settings.library_root)
        self._scan_worker = worker
        worker.signals.progress.connect(self._on_scan_progress)
        worker.signals.finished.connect(self._on_scan_finished)
        worker.signals.failed.connect(self._on_scan_failed)
        self._current_scan_job_id = self.job_queue.submit("scan", worker, description=tr("Scan bibliotheque"))

    def _on_scan_progress(self, current: int, total: int, path: str) -> None:
        filename = Path(path).name
        if self._current_scan_job_id is not None:
            self.job_queue.update_message(
                self._current_scan_job_id,
                tr("Scan {current}/{total}: {filename}", current=current, total=max(total, 1), filename=filename),
            )
        self._show_status_message(tr("Scan {current}/{total}: {filename}", current=current, total=max(total, 1), filename=filename))

    def _on_scan_finished(self, summary: ScanSummary) -> None:
        self.scan_in_progress = False
        self._scan_worker = None
        self._current_scan_job_id = None
        preserve_id = self.current_wallpaper().id if self.current_wallpaper() else None
        self.refresh_from_repository(preserve_id=preserve_id)
        message = tr(
            "Scan termine: {scanned} indexes, {imported} ajoutes, {updated} mis a jour, {removed} retires",
            scanned=summary.scanned_count,
            imported=summary.imported_count,
            updated=summary.updated_count,
            removed=summary.removed_count,
        )
        if summary.inbox_imported_count:
            message += tr(", {count} importes depuis Inbox", count=summary.inbox_imported_count)
        if summary.errors:
            message += tr(", {count} erreurs", count=len(summary.errors))
        self._show_status_message(message, 8000)

    def _on_scan_failed(self, error_message: str) -> None:
        self.scan_in_progress = False
        self._scan_worker = None
        self._current_scan_job_id = None
        self._show_status_message(tr("Echec du scan"), 8000)
        QMessageBox.critical(self, tr("Scan impossible"), error_message)

    def _debounced_rescan(self) -> None:
        self.rescan_timer.start()

    def toggle_selected_favorite(self) -> None:
        ids = self.selected_wallpaper_ids()
        if not ids:
            return
        self.undo_stack.beginMacro(tr("Favoris"))
        try:
            for wallpaper_id in ids:
                self.undo_stack.push(
                    ToggleFavoriteCommand(
                        self.service,
                        wallpaper_id,
                        refresh_callback=self._refresh_after_command,
                    )
                )
        finally:
            self.undo_stack.endMacro()

    def _set_current_favorite(self, value: bool) -> None:
        wallpaper = self.current_wallpaper()
        if wallpaper is None or wallpaper.id is None or wallpaper.is_favorite == value:
            return
        self.undo_stack.push(
            ToggleFavoriteCommand(
                self.service,
                wallpaper.id,
                refresh_callback=self._refresh_after_command,
                value=value,
            )
        )

    def move_selected_wallpapers(self) -> None:
        ids = self.selected_wallpaper_ids()
        if not ids:
            return
        target_dir = QFileDialog.getExistingDirectory(
            self,
            tr("Choisir le dossier cible"),
            str(self.service.settings.library_root),
        )
        if not target_dir:
            return
        planned_targets = [Path(target_dir) / self.service.get_wallpaper(wallpaper_id).filename for wallpaper_id in ids]
        conflict_strategy = self._choose_conflict_strategy(planned_targets, title=tr("Conflit de deplacement"))
        if conflict_strategy is None:
            return
        self._move_wallpaper_ids_to_directory(ids, Path(target_dir), conflict_strategy=conflict_strategy)

    def _move_wallpaper_ids_to_directory(
        self,
        ids: list[int],
        target_dir: Path,
        *,
        conflict_strategy: str = "unique",
    ) -> None:
        if not ids:
            return
        self.undo_stack.beginMacro(tr("Deplacement"))
        try:
            for wallpaper_id in list(dict.fromkeys(ids)):
                self.undo_stack.push(
                    MoveWallpaperCommand(
                        self.service,
                        wallpaper_id,
                        target_dir,
                        refresh_callback=self._refresh_after_command,
                        conflict_strategy=conflict_strategy,
                    )
                )
        finally:
            self.undo_stack.endMacro()
        self._show_status_message(
            tr("Deplacement vers {target}", target=target_dir.name or str(target_dir)),
            3000,
        )

    def rename_selected_wallpapers(self) -> None:
        ids = self.selected_wallpaper_ids()
        if not ids:
            return
        template, ok = QInputDialog.getText(
            self,
            tr("Renommage"),
            tr("Template de renommage"),
            text=self.service.settings.rename_template,
        )
        if not ok or not template.strip():
            return
        conflict_strategy = self._choose_conflict_strategy(
            [
                self.service.get_wallpaper(wallpaper_id).path.with_name(
                    f"{self.service.render_rename_template(self.service.get_wallpaper(wallpaper_id), template.strip(), index=index if len(ids) > 1 else None)}{self.service.get_wallpaper(wallpaper_id).extension}"
                )
                for index, wallpaper_id in enumerate(ids, start=1)
            ],
            title=tr("Conflit de renommage"),
        )
        if conflict_strategy is None:
            return
        self.undo_stack.beginMacro(tr("Renommage"))
        try:
            for index, wallpaper_id in enumerate(ids, start=1):
                self.undo_stack.push(
                    RenameWallpaperCommand(
                        self.service,
                        wallpaper_id,
                        template.strip(),
                        refresh_callback=self._refresh_after_command,
                        index=index if len(ids) > 1 else None,
                        conflict_strategy=conflict_strategy,
                    )
                )
        finally:
            self.undo_stack.endMacro()
        self._show_status_message(tr("Renommage termine"), 3000)

    def _choose_conflict_strategy(self, planned_targets: list[Path], *, title: str) -> str | None:
        conflicting_targets = [target for target in planned_targets if target.exists()]
        target_counts = Counter(planned_targets)
        conflicting_targets.extend(target for target, count in target_counts.items() if count > 1 and target not in conflicting_targets)
        if not conflicting_targets:
            return "unique"
        message = tr(
            "{count} destination(s) existent deja.\nExemple: {example}\n\nChoisis la strategie a appliquer.",
            count=len(conflicting_targets),
            example=conflicting_targets[0].name,
        )
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        keep_both_button = dialog.addButton(tr("Garder les deux"), QMessageBox.ButtonRole.AcceptRole)
        replace_button = dialog.addButton(tr("Remplacer"), QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = dialog.addButton(tr("Annuler"), QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked == cancel_button:
            return None
        if clicked == replace_button:
            return "overwrite"
        if clicked == keep_both_button:
            return "unique"
        return None

    def delete_selected_wallpapers(self) -> None:
        ids = self.selected_wallpaper_ids()
        if not ids:
            return
        self._trash_wallpaper_ids(ids)

    def _trash_wallpaper_ids(self, ids: list[int], *, confirm: bool = True) -> None:
        if not ids:
            return
        deleting_ids = set(ids)
        if self.stack.currentWidget() is self.viewer and self.current_viewer_id in deleting_ids:
            self._preferred_refresh_id = self._adjacent_wallpaper_id(
                self.current_viewer_id,
                excluded_ids=deleting_ids,
            )
        if len(ids) > 1:
            if confirm:
                result = QMessageBox.question(
                    self,
                    tr("Supprimer vers la corbeille"),
                    tr("Envoyer {count} wallpapers vers la corbeille ?", count=len(ids)),
                )
                if result != QMessageBox.StandardButton.Yes:
                    return
        self.undo_stack.beginMacro(tr("Suppression"))
        try:
            for wallpaper_id in ids:
                self.undo_stack.push(
                    TrashWallpaperCommand(
                        self.service,
                        wallpaper_id,
                        refresh_callback=self._refresh_after_command,
                    )
                )
        finally:
            self.undo_stack.endMacro()

    def show_duplicate_review(self) -> None:
        self.refresh_duplicate_filter()
        groups = [
            DuplicateReviewGroup(
                sha256=group.sha256,
                wallpapers=[self.service.get_wallpaper(wallpaper_id) for wallpaper_id in group.wallpaper_ids],
            )
            for group in self.service.list_duplicate_groups()
        ]
        if not groups:
            self._show_status_message(tr("Aucun doublon a revoir"), 3000)
            return
        dialog = DuplicateReviewDialog(groups, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if not dialog.selected_ids_to_delete:
            self._show_status_message(tr("Aucun doublon selectionne pour suppression"), 3000)
            return
        self._trash_wallpaper_ids(dialog.selected_ids_to_delete, confirm=True)
        self._show_status_message(
            tr("{count} doublon(s) envoyes vers la corbeille", count=len(dialog.selected_ids_to_delete)),
            4000,
        )

    def _save_current_details(self, tags: list[str], notes: str, rating: int) -> None:
        wallpaper = self.current_wallpaper()
        if wallpaper is None or wallpaper.id is None:
            return
        if list(wallpaper.tags) == tags and wallpaper.notes == notes and wallpaper.rating == rating:
            return
        self.undo_stack.push(
            UpdateWallpaperDetailsCommand(
                self.service,
                wallpaper.id,
                tags=tags,
                notes=notes,
                rating=rating,
                refresh_callback=self._refresh_after_command,
            )
        )

    def _ensure_current_hash(self) -> None:
        wallpaper = self.current_wallpaper()
        if wallpaper is None or wallpaper.id is None:
            return
        refreshed = self.service.ensure_hash(wallpaper.id)
        self.model.update_wallpaper(refreshed)
        self.details.set_wallpaper(refreshed)
        if self.current_viewer_id == refreshed.id:
            self.viewer.set_wallpaper(refreshed)
        self.proxy.set_duplicate_ids(self.service.duplicate_wallpaper_ids())
        self._show_status_message(tr("Hash calcule"), 3000)

    def refresh_duplicate_filter(self) -> None:
        updated = self.service.ensure_hashes_for_library()
        self.proxy.set_duplicate_ids(self.service.duplicate_wallpaper_ids())
        if updated:
            preserve_id = self.current_wallpaper().id if self.current_wallpaper() else None
            self.refresh_from_repository(preserve_id=preserve_id)
        self._show_status_message(tr("Doublons actualises"), 4000)

    def import_inbox(self) -> None:
        imported = self.service.import_inbox(rescan=False)
        if imported <= 0:
            self._show_status_message(tr("Inbox vide ou inexistante"), 3000)
            return
        self._show_status_message(tr("{count} fichier(s) importes depuis Inbox", count=imported), 4000)
        self.start_scan()

    def apply_current_wallpaper(self) -> None:
        wallpaper = self.current_wallpaper()
        if wallpaper is None or wallpaper.id is None:
            return
        try:
            self.service.apply_wallpaper(wallpaper.id)
        except Exception as exc:
            QMessageBox.critical(self, tr("Application impossible"), str(exc))
            return
        if wallpaper.media_kind is MediaKind.VIDEO:
            self._show_status_message(
                tr(
                    "Video wallpaper applique: {filename} ({preset})",
                    filename=wallpaper.filename,
                    preset=self.service.settings.mpvpaper_preset,
                ),
                4000,
            )
            return
        self._show_status_message(tr("Wallpaper applique: {filename}", filename=wallpaper.filename), 4000)

    def apply_random_filtered_wallpaper(self) -> None:
        try:
            wallpaper = self.service.apply_random_wallpaper(self.visible_wallpaper_ids())
        except Exception as exc:
            QMessageBox.critical(self, tr("Application aleatoire impossible"), str(exc))
            return
        self._show_status_message(tr("Wallpaper aleatoire applique: {filename}", filename=wallpaper.filename), 4000)

    def toggle_slideshow(self) -> None:
        if self.slideshow_timer.isActive():
            self.slideshow_timer.stop()
            self.slideshow_action.setChecked(False)
            self._show_status_message(tr("Slideshow arrete"), 3000)
            return
        if self.proxy.rowCount() <= 1:
            self._show_status_message(tr("Pas assez d'images pour un slideshow"), 3000)
            self.slideshow_action.setChecked(False)
            return
        if self.stack.currentWidget() is not self.viewer:
            self.open_current_in_viewer()
        self._update_slideshow_interval()
        self.slideshow_timer.start()
        self.slideshow_action.setChecked(True)
        self._show_status_message(tr("Slideshow actif"), 3000)

    def _advance_slideshow(self) -> None:
        self._move_viewer(1, wrap=True)

    def show_history(self) -> None:
        dialog = HistoryDialog(self.service.list_operations(), self)
        dialog.exec()

    def show_shortcuts_help(self) -> None:
        dialog = ShortcutsDialog(self.service.settings.shortcuts, self)
        dialog.exec()

    def show_settings(self) -> None:
        dialog = SettingsDialog(
            self.service.settings,
            gowall_status=self.service.get_gowall_status(),
            gowall_themes_dir=self.service.paths.gowall_themes_dir,
            wallpaper_backend_status=self.service.get_wallpaper_backend_status(),
            video_wallpaper_backend_status=self.service.get_video_wallpaper_backend_status(),
            wallhaven_status=self.service.get_wallhaven_status(),
            parent=self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self._apply_new_settings(dialog.to_settings(), reset_sidebar=True)
        self._refresh_gowall_capabilities()
        if self._startup_completed:
            self.start_scan()

    def _open_folder(self, path: Path) -> None:
        subprocess.run(["xdg-open", str(path)], check=False)

    def _open_external_target(self, target: object) -> None:
        subprocess.run(["xdg-open", str(target)], check=False)

    def _refresh_after_command(self) -> None:
        preserve_id = self._preferred_refresh_id
        self._preferred_refresh_id = None
        if preserve_id is None:
            preserve_id = self.current_viewer_id or (self.current_wallpaper().id if self.current_wallpaper() else None)
        self.refresh_from_repository(preserve_id=preserve_id)
        wallpaper = self.current_wallpaper()
        if self.stack.currentWidget() is self.viewer:
            self.viewer.set_wallpaper(wallpaper)
        self.details.set_wallpaper(wallpaper)
