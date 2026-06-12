"""
============================================================
JTCA - Shipments List Page
Full paginated list of all shipments with filter/search
============================================================
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QComboBox, QFrame, QMessageBox, QMenu,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QAction

logger = logging.getLogger(__name__)


class ShipmentsListPage(QWidget):
    """Full shipment list with search and filter capabilities."""

    shipment_selected = Signal(dict)

    def __init__(self):
        super().__init__()
        self._all_shipments = []
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 24)

        # Header
        header = QHBoxLayout()
        title = QLabel("📋  All Shipments")
        title.setStyleSheet("color: #FFFFFF; font-size: 20px; font-weight: 800;")

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setObjectName("btn_secondary")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setMaximumWidth(110)
        refresh_btn.clicked.connect(self.refresh_data)

        export_btn = QPushButton("📊 Export All")
        export_btn.setObjectName("btn_primary")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setMaximumWidth(120)
        export_btn.clicked.connect(self._export_all)

        self.delete_btn = QPushButton("🗑  Delete Selected")
        self.delete_btn.setObjectName("btn_danger")
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setMaximumWidth(150)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_selected)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(refresh_btn)
        header.addWidget(self.delete_btn)
        header.addWidget(export_btn)
        layout.addLayout(header)

        # Filter row
        filter_frame = QFrame()
        filter_frame.setObjectName("card")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(16, 12, 16, 12)
        filter_layout.setSpacing(12)

        search_label = QLabel("🔍")
        search_label.setStyleSheet("font-size: 16px;")
        filter_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by description, HS code, part number...")
        self.search_input.setMinimumHeight(36)
        self.search_input.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.search_input, stretch=2)

        status_lbl = QLabel("Status:")
        status_lbl.setStyleSheet("color: #90CAF9; font-size: 12px;")
        filter_layout.addWidget(status_lbl)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Approved", "Pending Review", "Rejected"])
        self.status_filter.setMinimumHeight(36)
        self.status_filter.currentTextChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.status_filter)

        layout.addWidget(filter_frame)

        # Count label
        self.count_label = QLabel("0 shipments")
        self.count_label.setStyleSheet("color: #4A6FA5; font-size: 11px; font-style: italic;")
        layout.addWidget(self.count_label)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "No.", "Shipment ID", "Part No.", "Description",
            "Origin", "HS Code", "Confidence", "Status",
        ])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.table)

        hint = QLabel("💡 Double-click to open details  |  Right-click or select row then click Delete to remove")
        hint.setStyleSheet("color: #4A6FA5; font-size: 11px; font-style: italic;")
        layout.addWidget(hint)

    def refresh_data(self):
        from database.db import get_all_shipments
        self._all_shipments = get_all_shipments()
        self._apply_filter()

    def _apply_filter(self):
        search = self.search_input.text().lower()
        status_filter = self.status_filter.currentText()

        filtered = []
        for s in self._all_shipments:
            if status_filter != "All" and s.get("status") != status_filter:
                continue
            if search:
                combined = " ".join([
                    s.get("product_description", ""),
                    s.get("suggested_hs_code", ""),
                    s.get("part_number", ""),
                    s.get("country_of_origin", ""),
                ]).lower()
                if search not in combined:
                    continue
            filtered.append(s)

        self._populate_table(filtered)
        self.count_label.setText(
            f"{len(filtered)} of {len(self._all_shipments)} shipments"
        )

    def _populate_table(self, shipments: list[dict]):
        self.table.setRowCount(0)
        self._displayed = shipments

        for row_idx, s in enumerate(shipments):
            self.table.insertRow(row_idx)
            status = s.get("status", "")
            confidence = s.get("confidence_score", 0)

            row_data = [
                str(row_idx + 1),
                s.get("shipment_id", "")[-14:],
                s.get("part_number", "") or "—",
                s.get("product_description", "")[:55],
                s.get("country_of_origin", ""),
                s.get("suggested_hs_code", ""),
                f"{confidence:.0f}%",
                status,
            ]

            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)

                if col_idx == 6:
                    color = (
                        "#10B981" if confidence >= 90 else
                        "#F59E0B" if confidence >= 70 else
                        "#EF4444"
                    )
                    item.setForeground(QColor(color))

                if col_idx == 7:
                    color_map = {
                        "Approved": "#10B981",
                        "Pending Review": "#F59E0B",
                        "Rejected": "#EF4444",
                    }
                    item.setForeground(QColor(color_map.get(status, "#6B7280")))
                    item.setFont(QFont("Segoe UI", 10, QFont.Bold))

                self.table.setItem(row_idx, col_idx, item)
            self.table.setRowHeight(row_idx, 42)

    def _on_row_double_clicked(self, index):
        row = index.row()
        if hasattr(self, "_displayed") and row < len(self._displayed):
            self.shipment_selected.emit(self._displayed[row])

    def _on_selection_changed(self):
        """Enable Delete button when a row is selected."""
        has_selection = len(self.table.selectedItems()) > 0
        self.delete_btn.setEnabled(has_selection)

    def _show_context_menu(self, position):
        """Right-click context menu on table rows."""
        row = self.table.rowAt(position.y())
        if row < 0 or not hasattr(self, "_displayed") or row >= len(self._displayed):
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0D1F3C;
                border: 1px solid #1565C0;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                color: #E2E8F0;
                padding: 8px 20px;
                font-size: 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1565C0;
            }
        """)

        open_action = QAction("📋  Open Details", self)
        open_action.triggered.connect(
            lambda: self.shipment_selected.emit(self._displayed[row])
        )

        delete_action = QAction("🗑  Delete Shipment", self)
        delete_action.triggered.connect(lambda: self._delete_single(self._displayed[row]))

        menu.addAction(open_action)
        menu.addSeparator()
        menu.addAction(delete_action)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def _delete_single(self, shipment: dict):
        """Delete a single shipment with confirmation."""
        sid = shipment.get("shipment_id", "")
        desc = shipment.get("product_description", "")[:50]

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to permanently delete this shipment?\n\n"
            f"ID: {sid}\n"
            f"Description: {desc}\n\n"
            f"This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            from database.db import delete_shipment
            if delete_shipment(sid):
                QMessageBox.information(self, "Deleted", f"Shipment {sid[-12:]} deleted successfully.")
                self.refresh_data()
            else:
                QMessageBox.critical(self, "Error", "Failed to delete shipment.")

    def _delete_selected(self):
        """Delete all currently selected rows."""
        selected_rows = sorted(
            set(item.row() for item in self.table.selectedItems()),
            reverse=True,
        )
        if not selected_rows or not hasattr(self, "_displayed"):
            return

        to_delete = [self._displayed[r] for r in selected_rows if r < len(self._displayed)]
        if not to_delete:
            return

        if len(to_delete) == 1:
            self._delete_single(to_delete[0])
            return

        # Multiple selected
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to permanently delete {len(to_delete)} shipments?\n\n"
            f"This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            from database.db import delete_shipment
            deleted = sum(1 for s in to_delete if delete_shipment(s["shipment_id"]))
            QMessageBox.information(self, "Done", f"Deleted {deleted} of {len(to_delete)} shipments.")
            self.refresh_data()

    def _export_all(self):
        try:
            from database.db import get_all_shipments
            from services.export_excel import export_to_excel
            from PySide6.QtWidgets import QFileDialog
            shipments = get_all_shipments()
            if not shipments:
                QMessageBox.information(self, "No Data", "No shipments to export.")
                return
            path, _ = QFileDialog.getSaveFileName(
                self, "Export to Excel", "SAP_Export.xlsx", "Excel Files (*.xlsx)"
            )
            if path:
                result = export_to_excel(shipments, path)
                QMessageBox.information(self, "Done", f"✅ Exported to:\n{result}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
