"""
============================================================
JTCA - Crawler Control Page
Web crawler management panel with real-time log output
============================================================
"""

import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QProgressBar, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)


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

        self.tariff_table = QTableWidget()
        self.tariff_table.setColumnCount(6)
        self.tariff_table.setHorizontalHeaderLabels([
            "HS Code", "Description", "Origin", "Tariff %", "FTA", "Updated"
        ])
        self.tariff_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tariff_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tariff_table.verticalHeader().setVisible(False)
        self.tariff_table.setShowGrid(False)
        self.tariff_table.setMaximumHeight(280)
        layout.addWidget(self.tariff_table)

    # ── Crawler Controls ───────────────────────────────────
    def _run_crawler(self):
        if self._crawler_worker and self._crawler_worker.isRunning():
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

    def _reset_ui(self):
        self.crawl_btn.setEnabled(True)
        self.index_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)

    def _append_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{ts}] {msg}")
        self.log_output.ensureCursorVisible()

    def _load_tariff_table(self):
        """Load tariff rules from DB into the table."""
        try:
            from database.db import get_all_tariff_rules
            rules = get_all_tariff_rules()
            self.kb_count_label.setText(f"{len(rules)} rules in knowledge base")
            self.tariff_table.setRowCount(0)

            for row_idx, rule in enumerate(rules[:100]):  # Show max 100
                self.tariff_table.insertRow(row_idx)
                tariff_pct = rule.get("tariff_percent", 0)
                row_data = [
                    rule.get("hs_code", ""),
                    rule.get("product_description", "")[:60],
                    rule.get("origin_country", ""),
                    f"{tariff_pct:.2f}%",
                    rule.get("fta_name", ""),
                    rule.get("last_updated", "")[:10],
                ]
                for col_idx, value in enumerate(row_data):
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                    if col_idx == 3:  # Tariff %
                        color = "#10B981" if tariff_pct == 0 else "#F59E0B" if tariff_pct <= 10 else "#EF4444"
                        item.setForeground(QColor(color))
                    self.tariff_table.setItem(row_idx, col_idx, item)
                self.tariff_table.setRowHeight(row_idx, 38)
        except Exception as e:
            self._append_log(f"[System] Could not load tariff table: {e}")
