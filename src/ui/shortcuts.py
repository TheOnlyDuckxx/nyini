from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget

from src.config.shortcuts import SHORTCUT_DEFINITIONS, ShortcutDefinition, default_shortcut_map


class ShortcutManager:
    def __init__(self, parent: QWidget) -> None:
        self.parent = parent
        self._shortcuts: list[QShortcut] = []

    def clear(self) -> None:
        for shortcut in self._shortcuts:
            shortcut.setParent(None)
            shortcut.deleteLater()
        self._shortcuts.clear()

    def bind_shortcuts(self, shortcuts: dict[str, str], handlers: dict[str, Callable[[], None]]) -> None:
        self.clear()
        merged = default_shortcut_map()
        merged.update(shortcuts)
        for definition in SHORTCUT_DEFINITIONS:
            sequence = merged.get(definition.action_id, "").strip()
            if not sequence or definition.action_id not in handlers:
                continue
            shortcut = QShortcut(QKeySequence(sequence), self.parent)
            shortcut.activated.connect(handlers[definition.action_id])
            self._shortcuts.append(shortcut)

    def apply_action_shortcuts(self, shortcuts: dict[str, str], action_map: dict[str, QAction]) -> None:
        merged = default_shortcut_map()
        merged.update(shortcuts)
        for action_id, action in action_map.items():
            action.setShortcut(QKeySequence(merged.get(action_id, "")))


def shortcut_rows(shortcuts: dict[str, str]) -> list[tuple[ShortcutDefinition, str]]:
    merged = default_shortcut_map()
    merged.update(shortcuts)
    return [(definition, merged.get(definition.action_id, "")) for definition in SHORTCUT_DEFINITIONS]
