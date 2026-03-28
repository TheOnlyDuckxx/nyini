from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.application.services import WallManagerService
from src.config.app_info import APP_DESKTOP_FILE, APP_NAME, APP_ORGANIZATION, app_icon_path
from src.ui.theme import ThemeController
from src.ui.main_window import MainWindow


def create_application(library_root: Path | None = None) -> tuple[QApplication, MainWindow]:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setDesktopFileName(APP_DESKTOP_FILE)
    app_icon = QIcon(app_icon_path())
    app.setWindowIcon(app_icon)
    app.setStyle("Fusion")
    service = WallManagerService.create(library_root=library_root)
    theme_controller = ThemeController(app)
    theme_controller.apply_theme(service.settings.theme_mode)
    window = MainWindow(
        service,
        theme_controller,
        show_onboarding_on_startup=library_root is None,
    )
    window.setWindowIcon(app_icon)
    return app, window
