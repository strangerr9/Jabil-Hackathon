"""
============================================================
JTCA - Reports & Analytics Page
Statistics, charts summary, and audit log viewer
============================================================
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QGridLayout, QMessageBox, QFileDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

logger = logging.getLogger(__name__)


class ReportsPage(QWidget):
    """Analytics and audit log viewer."""

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(28, 24, 28, 24)

        # Header
        header = QHBoxLayout()
        title = QLabel("📊  Reports & Analytics")
        title.setStyleSheet("color: #FFFFFF; font-size: 20px; font-weight: 800;")

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setObjectName("btn_secondary")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setMaximumWidth(110)
        refresh_btn.clicked.connect(self.refresh_data)

        export_btn = QPushButton("📊 Export Report")
        export_btn.setObjectName("btn_primary")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setMaximumWidth(140)
        export_btn.clicked.connect(self._export_report)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(refresh_btn)
        header.addWidget(export_btn)
        layout.addLayout(header)

        # Stats grid
        stats_frame = QFrame()
        stats_frame.setObjectName("card")
        stats_layout = QGridLayout(stats_frame)
        stats_layout.setSpacing(20)
        stats_layout.setContentsMargins(20, 16, 20, 16)

        stats_title = QLabel("SUMMARY STATISTICS")
        stats_title.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        stats_layout.addWidget(stats_title, 0, 0, 1, 4)

        self._stat_labels = {}
        stat_defs = [
            ("total", "Total Shipments", "📦", "#42A5F5"),
            ("approved", "Approved", "✅", "#10B981"),
            ("pending", "Pending Review", "⏳", "#F59E0B"),
            ("rejected", "Rejected", "❌", "#EF4444"),
            ("avg_confidence", "Avg Confidence", "🎯", "#A78BFA"),
            ("total_duties", "Total Duties", "💵", "#FB7185"),
        ]

        for col_idx, (key, label, icon, color) in enumerate(stat_defs):
            col_frame = QFrame()
            col_layout = QVBoxLayout(col_frame)
            col_layout.setSpacing(4)
            col_layout.setContentsMargins(8, 8, 8, 8)

            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(f"font-size: 20px; color: {color};")
            icon_lbl.setAlignment(Qt.AlignCenter)

            value_lbl = QLabel("—")
            value_lbl.setStyleSheet(
                f"color: {color}; font-size: 22px; font-weight: 800;"
            )
            value_lbl.setAlignment(Qt.AlignCenter)
            self._stat_labels[key] = value_lbl

            name_lbl = QLabel(label)
            name_lbl.setStyleSheet("color: #90CAF9; font-size: 10px; font-weight: 600;")
            name_lbl.setAlignment(Qt.AlignCenter)

            col_layout.addWidget(icon_lbl)
            col_layout.addWidget(value_lbl)
            col_layout.addWidget(name_lbl)
            stats_layout.addWidget(col_frame, 1, col_idx)

        layout.addWidget(stats_frame)

        # Audit log
        audit_header = QHBoxLayout()
        audit_lbl = QLabel("AUDIT TRAIL LOG")
        audit_lbl.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        audit_header.addWidget(audit_lbl)
        audit_header.addStretch()
        layout.addLayout(audit_header)

        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(7)
        self.audit_table.setHorizontalHeaderLabels([
            "Time", "Shipment ID", "Action", "AI Recommendation",
            "Human Decision", "Reviewer", "Notes"
        ])
        self.audit_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.audit_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.audit_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.audit_table.verticalHeader().setVisible(False)
        self.audit_table.setShowGrid(False)
        layout.addWidget(self.audit_table)

    def refresh_data(self):
        try:
            from database.db import get_dashboard_stats, get_recent_audit_log

            stats = get_dashboard_stats()
            self._stat_labels["total"].setText(str(stats.get("total", 0)))
            self._stat_labels["approved"].setText(str(stats.get("approved", 0)))
            self._stat_labels["pending"].setText(str(stats.get("pending", 0)))
            self._stat_labels["rejected"].setText(str(stats.get("rejected", 0)))
            self._stat_labels["avg_confidence"].setText(
                f"{stats.get('avg_confidence', 0):.1f}%"
            )
            self._stat_labels["total_duties"].setText(
                f"${stats.get('total_duties', 0):,.2f}"
            )

            # Load audit log using PostgreSQL-safe API
            rows = get_recent_audit_log(limit=200)

            self.audit_table.setRowCount(0)
            for row_idx, row in enumerate(rows):
                self.audit_table.insertRow(row_idx)
                action_colors = {
                    "AI_PROCESSED": "#42A5F5",
                    "HUMAN_APPROVED": "#10B981",
                    "HUMAN_REJECTED_OVERRIDE": "#EF4444",
                }
                for col_idx, value in enumerate(row):
                    val_str = str(value or "")
                    if col_idx == 0:
                        val_str = val_str[:19].replace("T", " ")
                    if col_idx == 1:
                        val_str = val_str[-14:]
                    item = QTableWidgetItem(val_str)
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                    if col_idx == 2:
                        color = action_colors.get(val_str, "#90CAF9")
                        item.setForeground(QColor(color))
                        item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                    self.audit_table.setItem(row_idx, col_idx, item)
                self.audit_table.setRowHeight(row_idx, 40)

        except Exception as e:
            logger.error(f"Reports refresh error: {e}")

    def _export_report(self):
        try:
            from database.db import get_all_shipments
            from services.export_excel import export_to_excel
            shipments = get_all_shipments()
            if not shipments:
                QMessageBox.information(self, "No Data", "No shipments to export.")
                return
            path, _ = QFileDialog.getSaveFileName(
                self, "Export Report", "JTCA_Report.xlsx", "Excel Files (*.xlsx)"
            )
            if path:
                result = export_to_excel(shipments, path)
                QMessageBox.information(self, "Done", f"✅ Report exported:\n{result}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
