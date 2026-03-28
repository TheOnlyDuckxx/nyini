from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout

from src.domain.models import OperationLogEntry
from src.i18n import operation_label, tr


class HistoryDialog(QDialog):
    def __init__(self, operations: list[OperationLogEntry], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Historique"))
        self.resize(900, 500)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([tr("Date"), tr("Action"), tr("Wallpaper ID"), tr("Payload")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        self.set_operations(operations)

    def set_operations(self, operations: list[OperationLogEntry]) -> None:
        self.table.setRowCount(len(operations))
        for row, operation in enumerate(operations):
            self.table.setItem(row, 0, QTableWidgetItem(operation.created_at))
            self.table.setItem(row, 1, QTableWidgetItem(operation_label(operation.action)))
            self.table.setItem(row, 2, QTableWidgetItem("" if operation.wallpaper_id is None else str(operation.wallpaper_id)))
            self.table.setItem(row, 3, QTableWidgetItem(operation.payload_json))
