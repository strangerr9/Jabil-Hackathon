"""
============================================================
JTCA - Crawler Control Page
Web crawler management panel with real-time log output
============================================================
"""

import logging
from datetime import datetime

import csv
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QProgressBar, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QComboBox, QFileDialog,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)


class CustomCrawlerWorker(QThread):
    """Background thread for crawling a user-input custom URL."""

    log_message = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, url: str, origin: str):
        super().__init__()
        self.url = url
        self.origin = origin

    def run(self):
        try:
            from crawler.crawl4ai_service import crawl_custom_source_sync
            result = crawl_custom_source_sync(
                self.url,
                self.origin,
                log_callback=lambda msg: self.log_message.emit(msg)
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class CrawlerWorker(QThread):
    """Background thread for web crawling."""

    log_message = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def run(self):
        try:
            from crawler.crawl4ai_service import run_crawler_sync
            result = run_crawler_sync(log_callback=lambda msg: self.log_message.emit(msg))
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class IndexWorker(QThread):
    """Background thread for re-indexing vector store."""

    log_message = Signal(str)
    finished = Signal(int)
    error = Signal(str)

    def run(self):
        try:
            from database.db import get_all_tariff_rules
            from rag.vector_store import upsert_tariff_rules, reset_collection

            self.log_message.emit("[Index] Loading tariff rules from database...")
            rules = get_all_tariff_rules()
            self.log_message.emit(f"[Index] Found {len(rules)} rules. Resetting collection...")
            reset_collection()
            upsert_tariff_rules(rules)
            self.log_message.emit(f"[Index] ✅ Vector store indexed with {len(rules)} rules.")
            self.finished.emit(len(rules))
        except Exception as e:
            self.error.emit(str(e))


class CrawlerPage(QWidget):
    """Web crawler management and RAG index control page."""

    def __init__(self):
        super().__init__()
        self._crawler_worker: CrawlerWorker | None = None
        self._index_worker: IndexWorker | None = None
        self._last_run: str = "Never"
        self._setup_ui()
        self._load_tariff_table()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(28, 24, 28, 24)

        # ── Header ─────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("🌐  Web Crawler & Knowledge Base")
        title.setStyleSheet("color: #FFFFFF; font-size: 20px; font-weight: 800;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # ── Crawler Control Card ────────────────────────
        ctrl_frame = QFrame()
        ctrl_frame.setObjectName("card")
        ctrl_layout = QVBoxLayout(ctrl_frame)
        ctrl_layout.setSpacing(12)
        ctrl_layout.setContentsMargins(20, 16, 20, 16)

        ctrl_title = QLabel("CRAWLER CONTROL")
        ctrl_title.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        ctrl_layout.addWidget(ctrl_title)

        # Sources info
        sources_info = QLabel(
            "🎯  Targets: MITI FTA Portal (Malaysia)  |  WTO Tariff Database  |  ASEAN Trade Repository"
        )
        sources_info.setStyleSheet("color: #CBD5E1; font-size: 12px;")
        ctrl_layout.addWidget(sources_info)

        # Last run info
        self.last_run_label = QLabel(f"⏱️  Last Run: {self._last_run}")
        self.last_run_label.setStyleSheet("color: #4A6FA5; font-size: 11px;")
        ctrl_layout.addWidget(self.last_run_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(16)
        ctrl_layout.addWidget(self.progress_bar)

        # Custom Crawl Input Layout
        custom_crawl_lbl = QLabel("CRAWL CUSTOM TARIFF SOURCE (MITI / USITC / ETC.)")
        custom_crawl_lbl.setStyleSheet(
            "color: #90CAF9; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; margin-top: 10px;"
        )
        ctrl_layout.addWidget(custom_crawl_lbl)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(10)

        self.custom_url_input = QLineEdit()
        self.custom_url_input.setPlaceholderText("Enter custom URL (e.g. https://fta.miti.gov.my/index.php/pages/view/asean-china or https://hts.usitc.gov)")
        self.custom_url_input.setStyleSheet(
            "QLineEdit { background-color: #030D1A; color: #FFFFFF; border: 1px solid #4A6FA5; "
            "padding: 8px; border-radius: 4px; }"
        )

        self.custom_origin_input = QLineEdit()
        self.custom_origin_input.setPlaceholderText("Origin (e.g. China)")
        self.custom_origin_input.setMaximumWidth(150)
        self.custom_origin_input.setStyleSheet(
            "QLineEdit { background-color: #030D1A; color: #FFFFFF; border: 1px solid #4A6FA5; "
            "padding: 8px; border-radius: 4px; }"
        )

        self.custom_crawl_btn = QPushButton("🔍 Crawl Custom Link")
        self.custom_crawl_btn.setObjectName("btn_secondary")
        self.custom_crawl_btn.setStyleSheet(
            "QPushButton { background-color: #0057A8; color: #FFFFFF; font-weight: bold; padding: 8px 15px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #42A5F5; }"
        )
        self.custom_crawl_btn.setCursor(Qt.PointingHandCursor)
        self.custom_crawl_btn.clicked.connect(self._run_custom_crawler)

        custom_row.addWidget(self.custom_url_input)
        custom_row.addWidget(self.custom_origin_input)
        custom_row.addWidget(self.custom_crawl_btn)
        ctrl_layout.addLayout(custom_row)

        # Buttons row
        btn_row = QHBoxLayout()

        self.crawl_btn = QPushButton("🌐  Run Web Crawler")
        self.crawl_btn.setObjectName("btn_primary")
        self.crawl_btn.setCursor(Qt.PointingHandCursor)
        self.crawl_btn.setMinimumHeight(42)
        self.crawl_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.crawl_btn.clicked.connect(self._run_crawler)

        self.index_btn = QPushButton("🔄  Re-Index Vector Store")
        self.index_btn.setObjectName("btn_secondary")
        self.index_btn.setCursor(Qt.PointingHandCursor)
        self.index_btn.setMinimumHeight(42)
        self.index_btn.clicked.connect(self._run_reindex)

        self.stop_btn = QPushButton("⏹  Stop")
        self.stop_btn.setObjectName("btn_danger")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setMinimumHeight(42)
        self.stop_btn.setMaximumWidth(90)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_crawler)

        btn_row.addWidget(self.crawl_btn)
        btn_row.addWidget(self.index_btn)
        btn_row.addWidget(self.stop_btn)
        ctrl_layout.addLayout(btn_row)

        layout.addWidget(ctrl_frame)

        # ── Log Output ──────────────────────────────────
        log_label = QLabel("REAL-TIME LOG OUTPUT")
        log_label.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        layout.addWidget(log_label)

        log_frame = QFrame()
        log_frame.setObjectName("card")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(4, 4, 4, 4)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(200)
        self.log_output.setStyleSheet(
            "QTextEdit { background-color: #030D1A; color: #22D3EE; "
            "font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; "
            "border: none; padding: 10px; }"
        )
        self.log_output.setPlaceholderText("Crawler log output will appear here...")

        clear_btn = QPushButton("🗑 Clear Log")
        clear_btn.setObjectName("btn_secondary")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setMaximumWidth(110)
        clear_btn.setMaximumHeight(30)
        clear_btn.clicked.connect(self.log_output.clear)

        log_layout.addWidget(self.log_output)
        log_layout.addWidget(clear_btn, alignment=Qt.AlignRight)
        layout.addWidget(log_frame)

        # ── Knowledge Base Table ────────────────────────
        kb_header = QHBoxLayout()
        kb_label = QLabel("TARIFF KNOWLEDGE BASE")
        kb_label.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        self.kb_count_label = QLabel("0 rules")
        self.kb_count_label.setStyleSheet("color: #4A6FA5; font-size: 11px;")
        kb_header.addWidget(kb_label)
        kb_header.addStretch()
        kb_header.addWidget(self.kb_count_label)
        layout.addLayout(kb_header)

        # ── Search + Filter + Actions row ───────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search HS code, description, FTA...")
        self.search_input.setStyleSheet(
            "QLineEdit { background-color: #030D1A; color: #FFFFFF; border: 1px solid #4A6FA5; "
            "padding: 6px 10px; border-radius: 4px; font-size: 12px; }"
        )
        self.search_input.textChanged.connect(self._filter_tariff_table)

        self.origin_filter = QComboBox()
        self.origin_filter.setMinimumWidth(140)
        self.origin_filter.setStyleSheet(
            "QComboBox { background-color: #030D1A; color: #FFFFFF; border: 1px solid #4A6FA5; "
            "padding: 5px 8px; border-radius: 4px; font-size: 12px; }"
            "QComboBox QAbstractItemView { background-color: #0A1929; color: #FFFFFF; "
            "selection-background-color: #0057A8; }"
        )
        self.origin_filter.addItem("All Origins")
        self.origin_filter.currentIndexChanged.connect(self._filter_tariff_table)

        export_btn = QPushButton("📥 Export CSV")
        export_btn.setObjectName("btn_secondary")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setStyleSheet(
            "QPushButton { background-color: #1B4332; color: #6EE7B7; font-weight: bold; "
            "padding: 6px 14px; border-radius: 4px; border: 1px solid #6EE7B7; font-size: 12px; }"
            "QPushButton:hover { background-color: #065F46; }"
        )
        export_btn.clicked.connect(self._export_csv)

        delete_btn = QPushButton("🗑 Delete Selected")
        delete_btn.setObjectName("btn_danger")
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.setStyleSheet(
            "QPushButton { background-color: #450A0A; color: #FCA5A5; font-weight: bold; "
            "padding: 6px 14px; border-radius: 4px; border: 1px solid #FCA5A5; font-size: 12px; }"
            "QPushButton:hover { background-color: #7F1D1D; }"
        )
        delete_btn.clicked.connect(self._delete_selected_rules)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setObjectName("btn_secondary")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(
            "QPushButton { background-color: #1E3A5F; color: #90CAF9; font-weight: bold; "
            "padding: 6px 14px; border-radius: 4px; border: 1px solid #90CAF9; font-size: 12px; }"
            "QPushButton:hover { background-color: #1D4ED8; }"
        )
        refresh_btn.clicked.connect(self._load_tariff_table)

        toolbar.addWidget(self.search_input, stretch=3)
        toolbar.addWidget(self.origin_filter, stretch=1)
        toolbar.addWidget(refresh_btn)
        toolbar.addWidget(export_btn)
        toolbar.addWidget(delete_btn)
        layout.addLayout(toolbar)

        # ── Table ───────────────────────────────────────
        self.tariff_table = QTableWidget()
        self.tariff_table.setColumnCount(7)
        self.tariff_table.setHorizontalHeaderLabels([
            "ID", "HS Code", "Description", "Origin", "Tariff %", "FTA / Agreement", "Last Updated"
        ])
        hdr = self.tariff_table.horizontalHeader()
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)   # Description stretches
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # HS Code
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Origin
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Tariff %
        hdr.setSectionResizeMode(5, QHeaderView.Interactive)       # FTA
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Updated
        self.tariff_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tariff_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tariff_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tariff_table.verticalHeader().setVisible(False)
        self.tariff_table.setShowGrid(True)
        self.tariff_table.setAlternatingRowColors(True)
        self.tariff_table.setSortingEnabled(True)
        self.tariff_table.setStyleSheet(
            "QTableWidget { gridline-color: #1E3A5F; alternate-background-color: #071426; "
            "background-color: #030D1A; color: #E2E8F0; font-size: 12px; } "
            "QHeaderView::section { background-color: #0A1929; color: #90CAF9; "
            "font-weight: 700; font-size: 11px; padding: 6px; border: none; "
            "border-bottom: 2px solid #1E3A5F; letter-spacing: 1px; } "
            "QTableWidget::item:selected { background-color: #0057A8; color: #FFFFFF; }"
        )
        layout.addWidget(self.tariff_table)

    def _run_crawler(self):
        if self._crawler_worker and self._crawler_worker.isRunning():
            return

        from crawler.crawl4ai_service import HAS_CRAWL4AI
        if not HAS_CRAWL4AI:
            self._append_log("[System] ⚠️ crawl4ai is not installed.")
            self._append_log("[System] Falling back to pre-loaded seed data (25 rules).")
            QMessageBox.information(
                self,
                "Crawler Offline",
                "crawl4ai is not installed.\n\n"
                "The system is running in offline demo mode using the pre-loaded 25 seed tariff rules."
            )
            return

        self._append_log("[System] Starting web crawler...")
        self.crawl_btn.setEnabled(False)
        self.index_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)

        self._crawler_worker = CrawlerWorker()
        self._crawler_worker.log_message.connect(self._append_log)
        self._crawler_worker.finished.connect(self._on_crawler_done)
        self._crawler_worker.error.connect(self._on_crawler_error)
        self._crawler_worker.start()

    def _run_reindex(self):
        if self._index_worker and self._index_worker.isRunning():
            return

        self._append_log("[System] Starting RAG vector store re-indexing...")
        self.crawl_btn.setEnabled(False)
        self.index_btn.setEnabled(False)
        self.progress_bar.setVisible(True)

        self._index_worker = IndexWorker()
        self._index_worker.log_message.connect(self._append_log)
        self._index_worker.finished.connect(self._on_index_done)
        self._index_worker.error.connect(self._on_crawler_error)
        self._index_worker.start()

    def _stop_crawler(self):
        if self._crawler_worker and self._crawler_worker.isRunning():
            self._crawler_worker.terminate()
            self._append_log("[System] ⏹ Crawler stopped by user.")
        self._reset_ui()

    def _on_crawler_done(self, result: dict):
        self._reset_ui()
        self._last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_run_label.setText(f"⏱️  Last Run: {self._last_run}")
        self._append_log(
            f"[System] ✅ Crawl complete — "
            f"Found: {result['rules_found']} | "
            f"Saved: {result['rules_saved']} | "
            f"Sources: {result['sources_crawled']}"
        )
        if result["errors"]:
            for err in result["errors"]:
                self._append_log(f"[Error] {err}")
        self._load_tariff_table()

    def _on_index_done(self, count: int):
        self._reset_ui()
        self._append_log(f"[System] ✅ Vector store indexed: {count} rules.")
        self._load_tariff_table()

    def _on_crawler_error(self, error: str):
        self._reset_ui()
        self._append_log(f"[Error] ❌ {error}")
        QMessageBox.critical(self, "Crawler Error", error)

    def _run_custom_crawler(self):
        url = self.custom_url_input.text().strip()
        origin = self.custom_origin_input.text().strip()
        
        if not url:
            QMessageBox.warning(self, "Validation Error", "Please enter a valid website URL or PDF link to crawl.")
            return
            
        if not origin:
            QMessageBox.warning(self, "Validation Error", "Please enter the Country of Origin for the crawled tariff rules.")
            return

        from crawler.crawl4ai_service import HAS_CRAWL4AI
        if not HAS_CRAWL4AI:
            self._append_log(f"[System] ⚠️ crawl4ai not installed. Simulating custom crawl fallback for: {url}")
            QMessageBox.warning(
                self,
                "Crawler Offline",
                "crawl4ai is not installed.\n\n"
                "The custom crawl cannot execute. Please install crawl4ai and Playwright."
            )
            return

        self._append_log(f"[System] Starting custom crawler on: {url}...")
        self.crawl_btn.setEnabled(False)
        self.custom_crawl_btn.setEnabled(False)
        self.index_btn.setEnabled(False)
        self.progress_bar.setVisible(True)

        self._custom_worker = CustomCrawlerWorker(url, origin)
        self._custom_worker.log_message.connect(self._append_log)
        self._custom_worker.finished.connect(self._on_custom_crawler_done)
        self._custom_worker.error.connect(self._on_crawler_error)
        self._custom_worker.start()

    def _on_custom_crawler_done(self, result: dict):
        self._reset_ui()
        self._append_log(
            f"[System] ✅ Custom crawl complete — "
            f"Found: {result['rules_found']} | "
            f"Saved: {result['rules_saved']}"
        )
        if result["errors"]:
            for err in result["errors"]:
                self._append_log(f"[Error] {err}")
        self._load_tariff_table()

    def _reset_ui(self):
        self.crawl_btn.setEnabled(True)
        if hasattr(self, "custom_crawl_btn"):
            self.custom_crawl_btn.setEnabled(True)
        self.index_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)

    def _append_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{ts}] {msg}")
        self.log_output.ensureCursorVisible()

    def _load_tariff_table(self):
        """Load ALL tariff rules from DB and refresh origin filter."""
        try:
            from database.db import get_all_tariff_rules
            self._all_rules = get_all_tariff_rules()
            total = len(self._all_rules)
            self.kb_count_label.setText(f"{total} rules in knowledge base")

            # Refresh origin dropdown
            origins = sorted({r.get("origin_country", "") for r in self._all_rules if r.get("origin_country")})
            current_origin = self.origin_filter.currentText()
            self.origin_filter.blockSignals(True)
            self.origin_filter.clear()
            self.origin_filter.addItem("All Origins")
            for o in origins:
                self.origin_filter.addItem(o)
            # Restore previous selection if still valid
            idx = self.origin_filter.findText(current_origin)
            self.origin_filter.setCurrentIndex(idx if idx >= 0 else 0)
            self.origin_filter.blockSignals(False)

            self._filter_tariff_table()
        except Exception as e:
            self._append_log(f"[System] Could not load tariff table: {e}")

    def _filter_tariff_table(self):
        """Apply search text and origin filter to the displayed table rows."""
        if not hasattr(self, "_all_rules"):
            return

        query = self.search_input.text().strip().lower()
        origin_sel = self.origin_filter.currentText()

        filtered = [
            r for r in self._all_rules
            if (origin_sel == "All Origins" or r.get("origin_country", "") == origin_sel)
            and (
                not query
                or query in r.get("hs_code", "").lower()
                or query in r.get("product_description", "").lower()
                or query in (r.get("fta_name") or "").lower()
                or query in r.get("origin_country", "").lower()
            )
        ]

        self.kb_count_label.setText(f"{len(filtered)} / {len(self._all_rules)} rules shown")
        self.tariff_table.setSortingEnabled(False)
        self.tariff_table.setRowCount(0)

        for row_idx, rule in enumerate(filtered):
            self.tariff_table.insertRow(row_idx)
            tariff_pct = rule.get("tariff_percent", 0)
            row_data = [
                str(rule.get("id", "")),
                rule.get("hs_code", ""),
                rule.get("product_description", ""),
                rule.get("origin_country", ""),
                f"{tariff_pct:.2f}%",
                rule.get("fta_name") or "—",
                rule.get("last_updated", "")[:10],
            ]
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                if col_idx == 4:  # Tariff %
                    color = "#10B981" if tariff_pct == 0 else "#F59E0B" if tariff_pct <= 10 else "#EF4444"
                    item.setForeground(QColor(color))
                self.tariff_table.setItem(row_idx, col_idx, item)
            self.tariff_table.setRowHeight(row_idx, 36)

        self.tariff_table.setSortingEnabled(True)

    def _export_csv(self):
        """Export visible (filtered) table rows to a CSV file."""
        if not hasattr(self, "_all_rules") or self.tariff_table.rowCount() == 0:
            QMessageBox.information(self, "No Data", "No data to export. Run the crawler first.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Tariff Rules", "tariff_rules.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            headers = ["ID", "HS Code", "Description", "Origin", "Tariff %", "FTA / Agreement", "Last Updated"]
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for row in range(self.tariff_table.rowCount()):
                    writer.writerow([
                        self.tariff_table.item(row, col).text() if self.tariff_table.item(row, col) else ""
                        for col in range(self.tariff_table.columnCount())
                    ])
            self._append_log(f"[System] ✅ Exported {self.tariff_table.rowCount()} rules to: {path}")
            QMessageBox.information(self, "Export Complete", f"Saved {self.tariff_table.rowCount()} rows to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _delete_selected_rules(self):
        """Delete selected rows from the database and refresh."""
        selected_rows = self.tariff_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Select one or more rows to delete.")
            return

        ids = []
        for index in selected_rows:
            id_item = self.tariff_table.item(index.row(), 0)
            if id_item and id_item.text().isdigit():
                ids.append(int(id_item.text()))

        if not ids:
            return

        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete {len(ids)} selected rule(s) from the knowledge base?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            from database.db import get_connection
            conn = get_connection()
            conn.executemany("DELETE FROM tariff_rules WHERE id = ?", [(i,) for i in ids])
            conn.commit()
            conn.close()
            self._append_log(f"[System] 🗑 Deleted {len(ids)} rule(s) from knowledge base.")
            self._load_tariff_table()
        except Exception as e:
            QMessageBox.critical(self, "Delete Error", str(e))
