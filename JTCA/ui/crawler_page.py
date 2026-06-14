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
    QAbstractItemView, QDialog, QListWidget, QListWidgetItem, QScrollArea,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)


class CustomCrawlerWorker(QThread):
    """Background thread for crawling a user-input custom URL."""

    log_message = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, url: str, fta_name: str):
        super().__init__()
        self.url = url
        self.fta_name = fta_name

    def run(self):
        try:
            from crawler.crawl4ai_service import crawl_custom_source_sync
            result = crawl_custom_source_sync(
                self.url,
                self.fta_name,
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


class FtaCard(QFrame):
    """Clickable visual card representing an FTA Agreement Category."""
    clicked = Signal(str)

    def __init__(self, title: str, description: str, theme_color: str, parent=None):
        super().__init__(parent)
        self.category_title = title
        self.theme_color = theme_color
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(140)
        self.setObjectName("fta_card")

        border_color = "#3B82F6" if theme_color == "blue" else "#10B981" if theme_color == "green" else "#F59E0B"
        bg_gradient = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {border_color}1a, stop:1 #0A1628)"

        self.setStyleSheet(f"""
            QFrame#fta_card {{
                background: {bg_gradient};
                border: 1px solid {border_color}aa;
                border-radius: 12px;
                padding: 16px;
            }}
            QFrame#fta_card:hover {{
                border: 2px solid {border_color};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {border_color}2b, stop:1 #0D1F3C);
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        # Title
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #FFFFFF;")
        layout.addWidget(self.title_lbl)

        # Description
        self.desc_lbl = QLabel(description)
        self.desc_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
        self.desc_lbl.setWordWrap(True)
        layout.addWidget(self.desc_lbl)

        layout.addStretch()

        # Action hint
        self.hint_lbl = QLabel("Click to explore rules 🔍")
        self.hint_lbl.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {border_color};")
        layout.addWidget(self.hint_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.category_title)
        super().mousePressEvent(event)


class TariffAgreementDialog(QDialog):
    """Popup Dialog to browse tariff rules by Free Trade Agreement."""

    def __init__(self, category_title: str, rules: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Tariff Knowledge Base - {category_title}")
        self.setMinimumSize(950, 600)
        self.resize(1000, 650)
        self.setModal(True)

        self.category_title = category_title
        self.all_rules = rules
        self.selected_agreement = None

        self.setStyleSheet("""
            QDialog {
                background-color: #0A1628;
            }
            QWidget {
                background-color: transparent;
                color: #E2E8F0;
            }
            QLineEdit {
                background-color: #0D2147;
                border: 1px solid #1565C0;
                border-radius: 6px;
                padding: 8px 12px;
                color: #E2E8F0;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 2px solid #42A5F5;
            }
            QListWidget {
                background-color: #0D1F3C;
                border: 1px solid #1565C0;
                border-radius: 8px;
                color: #E2E8F0;
                outline: none;
            }
            QListWidget::item {
                padding: 12px 16px;
                border-bottom: 1px solid #1A3A5C;
            }
            QListWidget::item:hover {
                background-color: #1A3A5C;
            }
            QListWidget::item:selected {
                background-color: #0057A8;
                color: #FFFFFF;
                font-weight: bold;
            }
        """)

        # Categorize rules
        self.grouped_rules = self._group_rules(category_title, rules)
        self._setup_ui()

    def _group_rules(self, category_title: str, rules: list[dict]) -> dict[str, list[dict]]:
        """Categorize and group rules by specific agreement name."""
        grouped: dict[str, list[dict]] = {}

        for r in rules:
            fta = r.get("fta_name") or "—"
            fta_lower = fta.lower()

            # Determine category of this rule
            # 1. Regional FTAs
            is_regional = (
                "usmca" in fta_lower or
                "acfta" in fta_lower or
                any(x in fta_lower for x in ["afta", "asean", "cptpp", "rcep", "regional", "eu", "nafta"])
            )
            # 2. Multilateral & Special
            is_multilateral = (
                "ita" in fta_lower or
                "mfn" in fta_lower or
                any(x in fta_lower for x in ["301", "232", "wto", "multilateral"])
            )
            # 3. Bilateral FTAs
            is_bilateral = not is_regional and not is_multilateral

            matches_category = False
            if category_title == "Regional FTAs" and is_regional:
                matches_category = True
            elif category_title == "Bilateral FTAs" and is_bilateral:
                matches_category = True
            elif category_title == "Multilateral & Special Tariffs" and is_multilateral:
                matches_category = True

            if matches_category:
                display_fta = fta
                if display_fta not in grouped:
                    grouped[display_fta] = []
                grouped[display_fta].append(r)

        return grouped

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # Header
        hdr_layout = QHBoxLayout()
        title_lbl = QLabel(f"📂  {self.category_title} Browser")
        title_lbl.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold;")
        hdr_layout.addWidget(title_lbl)
        hdr_layout.addStretch()

        # Search Box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search HS code or description...")
        self.search_input.setMinimumWidth(280)
        self.search_input.textChanged.connect(self._filter_rules)
        hdr_layout.addWidget(self.search_input)
        main_layout.addLayout(hdr_layout)

        # Content Split Layout
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Left Column: Agreement List
        left_panel = QVBoxLayout()
        left_panel.setSpacing(8)
        list_lbl = QLabel("SELECT AGREEMENT")
        list_lbl.setStyleSheet("color: #90CAF9; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        left_panel.addWidget(list_lbl)

        self.agreement_list = QListWidget()
        self.agreement_list.setMaximumWidth(280)
        self.agreement_list.currentTextChanged.connect(self._on_agreement_changed)

        sorted_agreements = sorted(self.grouped_rules.keys())
        for fta in sorted_agreements:
            count = len(self.grouped_rules[fta])
            item = QListWidgetItem(f"{fta} ({count} rules)")
            item.setData(Qt.UserRole, fta)
            self.agreement_list.addItem(item)

        left_panel.addWidget(self.agreement_list)
        content_layout.addLayout(left_panel)

        # Right Column: Rules Table
        right_panel = QVBoxLayout()
        right_panel.setSpacing(8)

        table_hdr_layout = QHBoxLayout()
        self.table_lbl = QLabel("TARIFF RULES")
        self.table_lbl.setStyleSheet("color: #90CAF9; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        table_hdr_layout.addWidget(self.table_lbl)
        table_hdr_layout.addStretch()

        self.count_lbl = QLabel("0 rules shown")
        self.count_lbl.setStyleSheet("color: #4A6FA5; font-size: 11px;")
        table_hdr_layout.addWidget(self.count_lbl)
        right_panel.addLayout(table_hdr_layout)

        self.tariff_table = QTableWidget()
        self.tariff_table.setColumnCount(6)
        self.tariff_table.setHorizontalHeaderLabels([
            "HS Code", "Description", "Origin", "Destination", "Tariff %", "Last Updated"
        ])
        hdr = self.tariff_table.horizontalHeader()
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.tariff_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tariff_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tariff_table.verticalHeader().setVisible(False)
        self.tariff_table.setStyleSheet(
            "QTableWidget { gridline-color: #1E3A5F; alternate-background-color: #071426; "
            "background-color: #030D1A; color: #E2E8F0; font-size: 12px; } "
            "QHeaderView::section { background-color: #0A1929; color: #90CAF9; "
            "font-weight: 700; font-size: 11px; padding: 6px; border: none; "
            "border-bottom: 2px solid #1E3A5F; } "
            "QTableWidget::item:selected { background-color: #0057A8; color: #FFFFFF; }"
        )
        right_panel.addWidget(self.tariff_table)
        content_layout.addLayout(right_panel, stretch=1)
        main_layout.addLayout(content_layout, stretch=1)

        # Footer Actions Row
        footer_layout = QHBoxLayout()

        self.export_btn = QPushButton("📥 Export Agreement CSV")
        self.export_btn.setObjectName("btn_secondary")
        self.export_btn.setStyleSheet(
            "QPushButton { background-color: #1B4332; color: #6EE7B7; font-weight: bold; "
            "padding: 8px 16px; border-radius: 4px; border: 1px solid #6EE7B7; font-size: 12px; }"
            "QPushButton:hover { background-color: #065F46; }"
        )
        self.export_btn.setCursor(Qt.PointingHandCursor)
        self.export_btn.clicked.connect(self._export_agreement_csv)
        footer_layout.addWidget(self.export_btn)

        self.export_all_btn = QPushButton("📥 Export All Category CSV")
        self.export_all_btn.setObjectName("btn_secondary")
        self.export_all_btn.setStyleSheet(
            "QPushButton { background-color: #1E3A5F; color: #90CAF9; font-weight: bold; "
            "padding: 8px 16px; border-radius: 4px; border: 1px solid #90CAF9; font-size: 12px; }"
            "QPushButton:hover { background-color: #1D4ED8; }"
        )
        self.export_all_btn.setCursor(Qt.PointingHandCursor)
        self.export_all_btn.clicked.connect(self._export_all_csv)
        footer_layout.addWidget(self.export_all_btn)

        footer_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setObjectName("btn_primary")
        close_btn.setStyleSheet(
            "QPushButton { background-color: #0057A8; color: #FFFFFF; font-weight: bold; "
            "padding: 8px 20px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #1976D2; }"
        )
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(close_btn)

        main_layout.addLayout(footer_layout)

        if self.agreement_list.count() > 0:
            self.agreement_list.setCurrentRow(0)

    def _on_agreement_changed(self):
        item = self.agreement_list.currentItem()
        if not item:
            self.selected_agreement = None
            self.tariff_table.setRowCount(0)
            self.count_lbl.setText("0 rules shown")
            return

        self.selected_agreement = item.data(Qt.UserRole)
        self.table_lbl.setText(f"TARIFF RULES FOR {self.selected_agreement.upper()}")
        self._filter_rules()

    def _filter_rules(self):
        if not self.selected_agreement:
            return

        query = self.search_input.text().strip().lower()
        rules = self.grouped_rules[self.selected_agreement]

        filtered = [
            r for r in rules
            if not query or
            query in r.get("hs_code", "").lower() or
            query in r.get("product_description", "").lower() or
            query in r.get("origin_country", "").lower() or
            query in r.get("destination_country", "").lower()
        ]

        self.count_lbl.setText(f"{len(filtered)} / {len(rules)} rules shown")
        self.tariff_table.setRowCount(0)

        for row_idx, rule in enumerate(filtered):
            self.tariff_table.insertRow(row_idx)
            tariff_pct = rule.get("tariff_percent", 0)
            row_data = [
                rule.get("hs_code", ""),
                rule.get("product_description", ""),
                rule.get("origin_country", ""),
                rule.get("destination_country", "USA"),
                f"{tariff_pct:.2f}%",
                rule.get("last_updated", "")[:10],
            ]
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                if col_idx == 4:
                    color = "#10B981" if tariff_pct == 0 else "#F59E0B" if tariff_pct <= 10 else "#EF4444"
                    item.setForeground(QColor(color))
                self.tariff_table.setItem(row_idx, col_idx, item)
            self.tariff_table.setRowHeight(row_idx, 32)

    def _export_agreement_csv(self):
        if not self.selected_agreement:
            return
        rules = self.grouped_rules[self.selected_agreement]
        self._export_rules_to_csv(rules, f"tariff_rules_{self.selected_agreement.replace(' ', '_')}.csv")

    def _export_all_csv(self):
        all_cat_rules = []
        for rules in self.grouped_rules.values():
            all_cat_rules.extend(rules)
        self._export_rules_to_csv(all_cat_rules, f"tariff_rules_{self.category_title.replace(' ', '_')}.csv")

    def _export_rules_to_csv(self, rules: list[dict], default_filename: str):
        if not rules:
            QMessageBox.information(self, "No Data", "No rules to export.")
            return

        import csv
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Tariff Rules", default_filename, "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            headers = ["HS Code", "Description", "Origin", "Destination", "Tariff %", "FTA / Agreement", "Last Updated"]
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for r in rules:
                    writer.writerow([
                        r.get("hs_code", ""),
                        r.get("product_description", ""),
                        r.get("origin_country", ""),
                        r.get("destination_country", "USA"),
                        f"{r.get('tariff_percent', 0.0):.2f}%",
                        r.get("fta_name") or "—",
                        r.get("last_updated", "")[:10]
                    ])
            QMessageBox.information(self, "Export Complete", f"Saved {len(rules)} rows to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))


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
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")

        scroll_content = QWidget()
        scroll_content.setObjectName("scroll_content")
        scroll_content.setStyleSheet("QWidget#scroll_content { background-color: transparent; }")

        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(20)
        layout.setContentsMargins(28, 24, 28, 24)

        # ── Header ─────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("🌐  Web Crawler & Knowledge Base")
        title.setStyleSheet("color: #FFFFFF; font-size: 20px; font-weight: 800;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # ── Warning Notice Banner (for Trade Analysts) ──
        self.notice_banner = QLabel("⚠️  Web Crawler management is restricted to Administrators. You have read-only access (Search & Export) to the Tariff Knowledge Base.")
        self.notice_banner.setStyleSheet("""
            QLabel {
                background-color: #1A2E40;
                color: #93C5FD;
                border: 1px solid #2563EB;
                border-radius: 8px;
                padding: 12px 16px;
                font-weight: 600;
                font-size: 13px;
            }
        """)
        self.notice_banner.setWordWrap(True)
        self.notice_banner.setVisible(False)
        layout.addWidget(self.notice_banner)

        # ── Crawler Control Card ────────────────────────
        self.ctrl_frame = QFrame()
        self.ctrl_frame.setObjectName("card")
        ctrl_layout = QVBoxLayout(self.ctrl_frame)
        ctrl_layout.setSpacing(12)
        ctrl_layout.setContentsMargins(20, 18, 20, 18)

        ctrl_title = QLabel("TARIFF DOCUMENT CRAWLER")
        ctrl_title.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        ctrl_layout.addWidget(ctrl_title)

        # Instructions tip
        self.tip_lbl = QLabel(
            "💡 <b>Instructions:</b> Enter the direct URL of an official trade agreement's website page "
            "or a Tariff Schedule PDF (e.g. from MITI Malaysia or USITC) along with the Agreement name (e.g. MJEPA). "
            "The system will crawl the source, extract all HS codes, descriptions, and tariff rates, and save them to the database."
        )
        self.tip_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; line-height: 1.4;")
        self.tip_lbl.setWordWrap(True)
        ctrl_layout.addWidget(self.tip_lbl)

        # Form Layout
        form_row = QHBoxLayout()
        form_row.setSpacing(12)

        self.custom_url_input = QLineEdit()
        self.custom_url_input.setPlaceholderText("Enter website URL or direct PDF link (e.g. https://fta.miti.gov.my/pdf/MJEPA_Tariff_Schedule.pdf)")
        self.custom_url_input.setStyleSheet(
            "QLineEdit { background-color: #030D1A; color: #FFFFFF; border: 1px solid #4A6FA5; "
            "padding: 10px; border-radius: 6px; font-size: 12px; }"
        )

        self.custom_fta_input = QLineEdit()
        self.custom_fta_input.setPlaceholderText("Agreement Name (e.g. MJEPA)")
        self.custom_fta_input.setMaximumWidth(220)
        self.custom_fta_input.setStyleSheet(
            "QLineEdit { background-color: #030D1A; color: #FFFFFF; border: 1px solid #4A6FA5; "
            "padding: 10px; border-radius: 6px; font-size: 12px; }"
        )

        form_row.addWidget(self.custom_url_input, stretch=3)
        form_row.addWidget(self.custom_fta_input, stretch=1)
        ctrl_layout.addLayout(form_row)

        # Status row (last run and progress bar)
        status_row = QHBoxLayout()
        
        self.last_run_label = QLabel(f"⏱️  Last Run: {self._last_run}")
        self.last_run_label.setStyleSheet("color: #4A6FA5; font-size: 11px;")
        status_row.addWidget(self.last_run_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(12)
        status_row.addWidget(self.progress_bar, stretch=1)
        
        ctrl_layout.addLayout(status_row)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.custom_crawl_btn = QPushButton("🔍  Start Crawler / Parser")
        self.custom_crawl_btn.setObjectName("btn_primary")
        self.custom_crawl_btn.setCursor(Qt.PointingHandCursor)
        self.custom_crawl_btn.setMinimumHeight(42)
        self.custom_crawl_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.custom_crawl_btn.clicked.connect(self._run_custom_crawler)

        # Map crawl_btn to custom_crawl_btn to maintain compatibility with existing worker callbacks
        self.crawl_btn = self.custom_crawl_btn

        self.index_btn = QPushButton("🔄  Re-Index Vector Store")
        self.index_btn.setObjectName("btn_secondary")
        self.index_btn.setCursor(Qt.PointingHandCursor)
        self.index_btn.setMinimumHeight(42)
        self.index_btn.clicked.connect(self._run_reindex)

        self.stop_btn = QPushButton("⏹  Stop")
        self.stop_btn.setObjectName("btn_danger")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setMinimumHeight(42)
        self.stop_btn.setMaximumWidth(100)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_crawler)

        btn_row.addWidget(self.custom_crawl_btn, stretch=2)
        btn_row.addWidget(self.index_btn, stretch=1)
        btn_row.addWidget(self.stop_btn)
        ctrl_layout.addLayout(btn_row)

        layout.addWidget(self.ctrl_frame)

        # ── Log Output ──────────────────────────────────
        self.log_label = QLabel("REAL-TIME LOG OUTPUT")
        self.log_label.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        layout.addWidget(self.log_label)

        self.log_frame = QFrame()
        self.log_frame.setObjectName("card")
        log_layout = QVBoxLayout(self.log_frame)
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
        layout.addWidget(self.log_frame)

        # ── FTA Agreements Classification ────────────────
        self.fta_label = QLabel("TRADE AGREEMENTS & FTAS CLASSIFICATION")
        self.fta_label.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 700; letter-spacing: 2px; margin-top: 10px;"
        )
        layout.addWidget(self.fta_label)

        self.fta_cards_frame = QFrame()
        self.fta_cards_frame.setObjectName("card")
        fta_cards_layout = QHBoxLayout(self.fta_cards_frame)
        fta_cards_layout.setContentsMargins(16, 16, 16, 16)
        fta_cards_layout.setSpacing(16)

        # Regional Card
        self.regional_card = FtaCard(
            "Regional FTAs",
            "Multi-nation trade agreements reducing tariffs and fostering integration within a geographical region (e.g. USMCA, ACFTA, RCEP).",
            "blue"
        )
        self.regional_card.clicked.connect(self._on_fta_card_clicked)

        # Bilateral Card
        self.bilateral_card = FtaCard(
            "Bilateral FTAs",
            "Custom trade partnerships negotiated between two individual sovereign nations (e.g. MITI FTA Test, MJEPA).",
            "green"
        )
        self.bilateral_card.clicked.connect(self._on_fta_card_clicked)

        # Multilateral & Special Card
        self.special_card = FtaCard(
            "Multilateral & Special Tariffs",
            "Global trade rules under WTO MFN, ITA Agreement, or unilateral actions (e.g. Section 301, Section 232).",
            "amber"
        )
        self.special_card.clicked.connect(self._on_fta_card_clicked)

        fta_cards_layout.addWidget(self.regional_card)
        fta_cards_layout.addWidget(self.bilateral_card)
        fta_cards_layout.addWidget(self.special_card)

        layout.addWidget(self.fta_cards_frame)

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

        self.delete_btn = QPushButton("🗑 Delete Selected")
        self.delete_btn.setObjectName("btn_danger")
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setStyleSheet(
            "QPushButton { background-color: #450A0A; color: #FCA5A5; font-weight: bold; "
            "padding: 6px 14px; border-radius: 4px; border: 1px solid #FCA5A5; font-size: 12px; }"
            "QPushButton:hover { background-color: #7F1D1D; }"
        )
        self.delete_btn.clicked.connect(self._delete_selected_rules)

        self.clear_crawled_btn = QPushButton("🗑 Clear Crawled Data")
        self.clear_crawled_btn.setObjectName("btn_danger")
        self.clear_crawled_btn.setCursor(Qt.PointingHandCursor)
        self.clear_crawled_btn.setStyleSheet(
            "QPushButton { background-color: #7A1C1C; color: #FCA5A5; font-weight: bold; "
            "padding: 6px 14px; border-radius: 4px; border: 1px solid #EF4444; font-size: 12px; }"
            "QPushButton:hover { background-color: #B91C1C; }"
        )
        self.clear_crawled_btn.clicked.connect(self._delete_all_crawled_rules)

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
        toolbar.addWidget(self.delete_btn)
        toolbar.addWidget(self.clear_crawled_btn)
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
        self.tariff_table.setMinimumHeight(450)

        self.scroll_area.setWidget(scroll_content)
        main_layout.addWidget(self.scroll_area)

    def _on_fta_card_clicked(self, category_title: str):
        rules = getattr(self, "_all_rules", [])
        if not rules:
            try:
                from database.db import get_all_tariff_rules
                rules = get_all_tariff_rules()
                self._all_rules = rules
            except Exception as e:
                self._append_log(f"[System] Could not load rules for dialog: {e}")
                QMessageBox.critical(self, "Database Error", f"Could not load rules: {e}")
                return

        dialog = TariffAgreementDialog(category_title, rules, self)
        dialog.exec()

    def apply_permissions(self):
        """Enforce role-based restrictions on crawler functions."""
        from services.session import SessionManager
        session = SessionManager()
        is_admin = session.is_admin()
        
        # Enable/disable crawler control inputs and buttons
        self.ctrl_frame.setVisible(is_admin)
        self.log_label.setVisible(is_admin)
        self.log_frame.setVisible(is_admin)
        
        # Show warning banner if not admin
        self.notice_banner.setVisible(not is_admin)
        
        # Hide delete/clear buttons in toolbar for non-admins
        self.delete_btn.setVisible(is_admin)
        self.clear_crawled_btn.setVisible(is_admin)

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
        if hasattr(self, "_custom_worker") and self._custom_worker and self._custom_worker.isRunning():
            self._custom_worker.terminate()
            self._append_log("[System] ⏹ Custom crawler stopped by user.")
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
        fta_name = self.custom_fta_input.text().strip()
        
        if not url:
            QMessageBox.warning(self, "Validation Error", "Please enter a valid website URL or PDF link to crawl.")
            return
            
        if not fta_name:
            QMessageBox.warning(self, "Validation Error", "Please enter the Agreement / FTA name for the crawled tariff rules.")
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

        self._custom_worker = CustomCrawlerWorker(url, fta_name)
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
            from database.db import delete_tariff_rules_by_ids
            deleted = delete_tariff_rules_by_ids(ids)
            self._append_log(f"[System] 🗑 Deleted {deleted} rule(s) from knowledge base.")
            self._load_tariff_table()
        except Exception as e:
            QMessageBox.critical(self, "Delete Error", str(e))

    def _delete_all_crawled_rules(self):
        """Delete all crawled tariff rules from PostgreSQL, MongoDB, and reset ChromaDB to seed rules."""
        confirm = QMessageBox.question(
            self, "Confirm Clear Crawled Data",
            "Are you sure you want to delete all crawled tariff rules from the database?\n"
            "Seed tariff rules will be preserved. This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        self._append_log("[System] Clearing crawled data from databases...")
        try:
            from database.db import clear_crawled_rules, clear_raw_crawls, get_all_tariff_rules
            from rag.vector_store import upsert_tariff_rules, reset_collection

            # 1. Clear PostgreSQL crawled rules (and restore seed rules)
            deleted_pg = clear_crawled_rules()
            self._append_log(f"[System] 🗑 Deleted {deleted_pg} crawled rule(s) from PostgreSQL database.")

            # 2. Clear MongoDB raw crawl history
            deleted_mongo = clear_raw_crawls()
            self._append_log(f"[System] 🗑 Cleared {deleted_mongo} raw crawls from MongoDB.")

            # 3. Re-index ChromaDB with only the remaining seed rules
            reset_collection()
            remaining_rules = get_all_tariff_rules()
            upsert_tariff_rules(remaining_rules)
            self._append_log(f"[System] ✅ Vector store re-indexed with {len(remaining_rules)} remaining seed rules.")

            QMessageBox.information(
                self, "Success",
                f"Successfully deleted crawled rules:\n"
                f"- PostgreSQL: {deleted_pg} rules cleared\n"
                f"- MongoDB: {deleted_mongo} raw records cleared\n\n"
                f"Vector store has been re-indexed with seed rules."
            )
            self._load_tariff_table()
        except Exception as e:
            self._append_log(f"[Error] ❌ Failed to clear crawled data: {e}")
            QMessageBox.critical(self, "Clear Error", f"Failed to clear crawled data: {e}")

