from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout

from src.i18n import tr
from src.ui.shortcuts import shortcut_rows


class ShortcutsDialog(QDialog):
    def __init__(self, shortcuts: dict[str, str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Raccourcis clavier"))
        self.resize(720, 460)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([tr("Action"), tr("Raccourci"), tr("Description")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        self.set_shortcuts(shortcuts)

    def set_shortcuts(self, shortcuts: dict[str, str]) -> None:
        rows = shortcut_rows(shortcuts)
        self.table.setRowCount(len(rows))
        for row, (definition, sequence) in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(tr(definition.label)))
            self.table.setItem(row, 1, QTableWidgetItem(sequence))
            self.table.setItem(row, 2, QTableWidgetItem(tr(definition.description)))
