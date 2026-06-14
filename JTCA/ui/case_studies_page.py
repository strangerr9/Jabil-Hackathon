"""
============================================================
JTCA - Case Studies Page
Interactive database of compliance case studies (Classification, FTA, AD-CVD)
============================================================
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QGridLayout, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)

# Mock Case Studies Data
CASE_STUDIES_DATA = [
    {
        "id": "CS-101",
        "title": "Semiconductor Classification Dispute",
        "category": "Classification",
        "summary": "Dispute with US Customs regarding active semiconductor components classified under a high-tariff category. Successfully argued for classification under Duty-Free subheading.",
        "hs_code": "8542.31.0000",
        "impact": "Saved $340,000 in retrofitted duties. Avoided future 2.5% duties.",
        "status": "Resolved",
        "status_color": "#1B8A4E"
    },
    {
        "id": "CS-102",
        "title": "USMCA Automotive Electronic Assemblies",
        "category": "FTA Verification",
        "summary": "Origin verification audit for trans-border shipments of automotive electronic control units. Demonstrated compliance with Regional Value Content (RVC) thresholds.",
        "hs_code": "8708.29.9000",
        "impact": "Duties waived. $125,000 in duty-free savings certified.",
        "status": "Approved",
        "status_color": "#1B8A4E"
    },
    {
        "id": "CS-103",
        "title": "Anti-Dumping Audit: Aluminium Heat Sinks",
        "category": "AD-CVD",
        "summary": "Customs audit on imported heat sinks from Southeast Asia suspected of circumvention. Verified material trace to show exemption from 48% AD-CVD penalty.",
        "hs_code": "7616.99.5090",
        "impact": "Prevented $80,000 penalty. Certified supply chain trace compliance.",
        "status": "Resolved",
        "status_color": "#1B8A4E"
    },
    {
        "id": "CS-104",
        "title": "EU RoHS Assemblies Cadmium Traces",
        "category": "Environmental",
        "summary": "Incoming audit flagged minor parts with cadmium traces near EU RoHS thresholds. Traced supply chain and validated compliance certificates to avert import bans.",
        "hs_code": "8504.40.9500",
        "impact": "Escalation resolved. No material impounded.",
        "status": "Escalated",
        "status_color": "#6D28D9"
    },
    {
        "id": "CS-105",
        "title": "Medical Device Display Classification",
        "category": "Classification",
        "summary": "Ongoing classification alignment for touch-screen LCD modules used in hospital equipment. Assessing dual-use vs. medical-specific subheadings.",
        "hs_code": "9018.90.7500",
        "impact": "Pending determination. Potential duty difference: 4.2% ($60,000).",
        "status": "Pending",
        "status_color": "#C07A00"
    }
]

class CaseStudiesPage(QWidget):
    """Compliance Case Studies reference catalog."""

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._populate_cases(CASE_STUDIES_DATA)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(28, 24, 28, 24)

        # Header Section
        header_layout = QHBoxLayout()
        title = QLabel("📚  Compliance Case Studies")
        title.setObjectName("page_title")
        title.setFont(QFont("Inter", 20, QFont.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # Search and Filter Panel
        filter_frame = QFrame()
        filter_frame.setObjectName("card")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(16, 12, 16, 12)
        filter_layout.setSpacing(12)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size: 16px;")
        filter_layout.addWidget(search_icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search cases by title, category, summary, HS Code...")
        self.search_input.setMinimumHeight(38)
        self.search_input.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.search_input, stretch=2)

        filter_layout.addWidget(QLabel("Category:"))
        self.cat_all_btn = QPushButton("All")
        self.cat_all_btn.setObjectName("btn_secondary")
        self.cat_all_btn.setCheckable(True)
        self.cat_all_btn.setChecked(True)
        self.cat_all_btn.clicked.connect(lambda: self._select_category("All"))

        self.cat_class_btn = QPushButton("Classification")
        self.cat_class_btn.setObjectName("btn_secondary")
        self.cat_class_btn.setCheckable(True)
        self.cat_class_btn.clicked.connect(lambda: self._select_category("Classification"))

        self.cat_fta_btn = QPushButton("FTA")
        self.cat_fta_btn.setObjectName("btn_secondary")
        self.cat_fta_btn.setCheckable(True)
        self.cat_fta_btn.clicked.connect(lambda: self._select_category("FTA Verification"))

        self.cat_ad_btn = QPushButton("AD-CVD")
        self.cat_ad_btn.setObjectName("btn_secondary")
        self.cat_ad_btn.setCheckable(True)
        self.cat_ad_btn.clicked.connect(lambda: self._select_category("AD-CVD"))

        self.cat_buttons = [self.cat_all_btn, self.cat_class_btn, self.cat_fta_btn, self.cat_ad_btn]
        for btn in self.cat_buttons:
            btn.setMinimumHeight(36)
            btn.setCursor(Qt.PointingHandCursor)
            filter_layout.addWidget(btn)

        main_layout.addWidget(filter_frame)

        # Scrollable Area for Case Study Cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("scroll_area")
        self.scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        self.scroll_widget = QWidget()
        self.scroll_widget.setObjectName("scroll_content")
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setSpacing(16)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_widget)
        main_layout.addWidget(self.scroll_area, stretch=1)

        self._active_category = "All"

    def _select_category(self, category: str):
        self._active_category = category
        for btn in self.cat_buttons:
            if btn.text() == category or (category == "FTA Verification" and btn.text() == "FTA") or (category == "All" and btn.text() == "All"):
                btn.setChecked(True)
            else:
                btn.setChecked(False)
        self._apply_filters()

    def _apply_filters(self):
        search_text = self.search_input.text().lower().strip()
        filtered = []
        for case in CASE_STUDIES_DATA:
            # Category filter
            if self._active_category != "All":
                if case["category"] != self._active_category:
                    continue
            
            # Search filter
            if search_text:
                combined_text = " ".join([
                    case["title"],
                    case["category"],
                    case["summary"],
                    case["hs_code"],
                    case["impact"]
                ]).lower()
                if search_text not in combined_text:
                    continue
            
            filtered.append(case)
        
        self._populate_cases(filtered)

    def _populate_cases(self, cases):
        # Clear existing items except the spacer
        while self.scroll_layout.count() > 1:
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add cards
        for case in cases:
            card = QFrame()
            card.setObjectName("card")
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(10)
            card_layout.setContentsMargins(20, 16, 20, 16)

            # Title Row
            title_row = QHBoxLayout()
            case_title = QLabel(case["title"])
            case_title.setObjectName("section_title")
            case_title.setFont(QFont("Inter", 14, QFont.Medium))
            
            cat_badge = QLabel(case["category"].upper())
            cat_badge.setObjectName("badge_secondary")
            cat_badge.setStyleSheet("""
                QLabel#badge_secondary {
                    background-color: #1E3A5F;
                    color: #90CAF9;
                    font-size: 10px;
                    font-weight: 700;
                    padding: 4px 8px;
                    border-radius: 4px;
                }
            """)

            status_badge = QLabel(case["status"].upper())
            # Map statuses to specified colors in dynamic styling, or apply badge names
            status_map = {
                "Approved": "approved",
                "Resolved": "approved",
                "Pending": "pending",
                "Escalated": "escalated"
            }
            status_badge.setObjectName(f"badge_{status_map.get(case['status'], 'pending')}")
            status_badge.setFont(QFont("Inter", 10, QFont.Bold))
            status_badge.setAlignment(Qt.AlignCenter)
            status_badge.setMinimumWidth(80)

            title_row.addWidget(case_title)
            title_row.addStretch()
            title_row.addWidget(cat_badge)
            title_row.addWidget(status_badge)
            card_layout.addLayout(title_row)

            # Details
            summary_lbl = QLabel(case["summary"])
            summary_lbl.setFont(QFont("Inter", 13))
            summary_lbl.setWordWrap(True)
            summary_lbl.setObjectName("body_text")
            card_layout.addWidget(summary_lbl)

            # Grid for specs
            grid = QGridLayout()
            grid.setSpacing(12)

            hs_label = QLabel("HS CODE")
            hs_label.setObjectName("label_field")
            hs_label.setFont(QFont("Inter", 11, QFont.Bold))
            hs_val = QLabel(case["hs_code"])
            hs_val.setObjectName("label_value")
            hs_val.setFont(QFont("JetBrains Mono", 12))

            impact_label = QLabel("COMPLIANCE IMPACT")
            impact_label.setObjectName("label_field")
            impact_label.setFont(QFont("Inter", 11, QFont.Bold))
            impact_val = QLabel(case["impact"])
            impact_val.setObjectName("label_value")
            impact_val.setFont(QFont("Inter", 13))

            grid.addWidget(hs_label, 0, 0)
            grid.addWidget(hs_val, 0, 1)
            grid.addWidget(impact_label, 1, 0)
            grid.addWidget(impact_val, 1, 1)
            
            card_layout.addLayout(grid)

            self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, card)

        if not cases:
            no_results = QLabel("No case studies match your search filter.")
            no_results.setStyleSheet("color: #8A9BB0; font-size: 14px; font-style: italic; padding: 20px;")
            no_results.setAlignment(Qt.AlignCenter)
            self.scroll_layout.insertWidget(0, no_results)
