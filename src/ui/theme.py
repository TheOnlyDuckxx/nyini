from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication

from src.config.app_info import stylesheet_text
from src.domain.enums import ThemeMode


class ThemeController(QObject):
    theme_changed = Signal(str)

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.current_mode = ThemeMode.AUTO
        self.app.styleHints().colorSchemeChanged.connect(self._on_system_scheme_changed)

    def apply_theme(self, mode: ThemeMode) -> None:
        self.current_mode = mode
        effective_mode = self.effective_mode(mode)
        suffix = "dark" if effective_mode == ThemeMode.DARK else "light"
        stylesheet = stylesheet_text(suffix)
        self.app.setStyleSheet(stylesheet)
        self.theme_changed.emit(effective_mode.value)

    def effective_mode(self, mode: ThemeMode | None = None) -> ThemeMode:
        requested_mode = mode or self.current_mode
        if requested_mode != ThemeMode.AUTO:
            return requested_mode
        color_scheme = self.app.styleHints().colorScheme()
        if color_scheme == Qt.ColorScheme.Light:
            return ThemeMode.LIGHT
        if color_scheme == Qt.ColorScheme.Dark:
            return ThemeMode.DARK
        lightness = self.app.palette().window().color().lightness()
        return ThemeMode.DARK if lightness < 128 else ThemeMode.LIGHT

    def _on_system_scheme_changed(self, _scheme) -> None:
        if self.current_mode == ThemeMode.AUTO:
            self.apply_theme(self.current_mode)
