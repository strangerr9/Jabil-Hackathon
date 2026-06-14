"""
============================================================
JTCA - Main Window
PySide6 root window with sidebar navigation
Dual theme system (Compliance White / Deep Compliance)
============================================================
"""

import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout,
    QVBoxLayout, QPushButton, QLabel, QStackedWidget,
    QFrame, QSizePolicy, QSpacerItem, QMenu, QMessageBox,
)
from PySide6.QtCore import Qt, QSize, Signal, QTimer
from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor, QAction

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Theme Style Sheet Generator
# ─────────────────────────────────────────────
def get_theme_stylesheet(theme_name: str) -> str:
    """
    Generate stylesheet for a specific theme.
    Ensures high contrast, premium aesthetics, and compliance with specifications.
    """
    if theme_name == "light":
        colors = {
            "bg_primary": "#F7F9FC",     # Compliance White background primary
            "bg_surface": "#FFFFFF",     # Background Surface
            "bg_panel": "#EEF2F8",       # Background Panel
            "bg_card": "#FFFFFF",        # White card for light mode
            "accent_primary": "#0A3D91",  # Jabil deep navy primary actions/headers
            "accent_secondary": "#1565C0",# Medium blue hover states/badges
            "accent_highlight": "#2196F3",# Bright blue active states
            "border": "#D0D9E8",         # Border color
            "text_primary": "#0D1B2A",   # Text Primary
            "text_secondary": "#4A5568", # Text Secondary
            "text_muted": "#8A9BB0",     # Text Muted
            "status_approved": "#1B8A4E",# Deep green status approved
            "status_pending": "#C07A00", # Amber status pending
            "status_rejected": "#C0392B", # Status rejected
            "status_escalated": "#6D28D9",# Violet status escalated
            "nav_hover": "#EEF2F8",
            "nav_active_bg": "#EEF2F8",
            "input_bg": "#FFFFFF",
            "progress_chunk": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0A3D91, stop:1 #2196F3)",
        }
    else:
        colors = {
            "bg_primary": "#080E1A",     # Near-black navy background primary
            "bg_surface": "#0F1C2E",     # Background Surface
            "bg_panel": "#162236",       # Background Panel
            "bg_card": "#1A2A40",        # Background Card
            "accent_primary": "#2D78D6",  # Electric blue primary actions
            "accent_secondary": "#1E5FAA",# Accent Secondary
            "accent_highlight": "#56B4FF",# Sky blue active indicators
            "border": "#1E3150",         # Border color
            "text_primary": "#E8F0FE",   # Text Primary
            "text_secondary": "#94A8C4", # Text Secondary
            "text_muted": "#4E6480",     # Text Muted
            "status_approved": "#22C55E",# Status approved
            "status_pending": "#F59E0B", # Status pending
            "status_rejected": "#EF4444", # Status rejected
            "status_escalated": "#A78BFA",# Status escalated
            "nav_hover": "#162236",
            "nav_active_bg": "#1A2A40",
            "input_bg": "#0F1C2E",
            "progress_chunk": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2D78D6, stop:1 #56B4FF)",
        }

    return f"""
    /* ─── Global Reset ─────────────────────────── */
    * {{
        font-family: 'Inter', 'Segoe UI', 'Arial', sans-serif;
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }}

    QMainWindow, QDialog {{
        background-color: {colors["bg_primary"]};
    }}

    QWidget {{
        background-color: transparent;
        color: {colors["text_primary"]};
    }}

    QLabel {{
        color: {colors["text_primary"]};
    }}

    /* ─── Top Bar ───────────────────────────────── */
    #top_bar {{
        background-color: {colors["bg_surface"]};
        border-bottom: 1px solid {colors["border"]};
    }}

    #top_logo_mark {{
        background-color: #0A3D91; /* Jabil navy square logo mark */
        color: #FFFFFF;
        font-size: 15px;
        font-weight: bold;
        border-radius: 4px;
        padding: 4px;
        min-width: 24px;
        max-width: 24px;
        min-height: 24px;
        max-height: 24px;
    }}

    #top_wordmark {{
        color: {colors["text_primary"]};
        font-size: 16px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }}

    #top_version_chip {{
        background-color: {colors["bg_panel"]};
        color: {colors["text_muted"]};
        font-size: 10px;
        font-weight: 600;
        border-radius: 8px;
        padding: 2px 8px;
    }}

    #top_breadcrumb {{
        color: {colors["text_secondary"]};
        font-size: 13px;
        font-weight: 500;
    }}

    #top_status_pill {{
        background-color: {colors["bg_panel"]};
        color: {colors["status_approved"]};
        font-size: 11px;
        font-weight: bold;
        border: 1px solid {colors["border"]};
        border-radius: 12px;
        padding: 4px 10px;
    }}

    /* ─── Sidebar ───────────────────────────────── */
    #sidebar {{
        background-color: {colors["bg_surface"]};
        border-right: 1px solid {colors["border"]};
    }}

    #nav_section_label {{
        color: {colors["text_muted"]};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 2px;
    }}

    /* ─── Sidebar Nav Buttons ───────────────────── */
    #nav_btn {{
        background-color: transparent;
        color: {colors["text_secondary"]};
        border: none;
        border-radius: 8px;
        text-align: left;
        padding: 12px 16px;
        font-size: 13px;
        font-weight: 500;
        margin: 2px 8px;
    }}

    #nav_btn:hover {{
        background-color: {colors["nav_hover"]};
        color: {colors["text_primary"]};
    }}

    #nav_btn[active="true"] {{
        background-color: {colors["nav_active_bg"]};
        color: {colors["accent_primary"]};
        font-weight: 700;
        border-left: 3px solid {colors["accent_primary"]};
        border-top-left-radius: 0px;
        border-bottom-left-radius: 0px;
    }}

    /* ─── Content Area ──────────────────────────── */
    #content_area {{
        background-color: {colors["bg_primary"]};
    }}

    /* ─── Cards & Panels ────────────────────────── */
    #card {{
        background-color: {colors["bg_card"]};
        border: 1px solid {colors["border"]};
        border-radius: 12px;
        padding: 16px;
    }}

    #stat_card {{
        background-color: {colors["bg_card"]};
        border: 1px solid {colors["border"]};
        border-radius: 12px;
        padding: 20px;
        min-width: 160px;
    }}

    #stat_value {{
        font-size: 28px;
        font-weight: 800;
        color: {colors["accent_highlight"]};
    }}

    #stat_label {{
        font-size: 11px;
        color: {colors["text_secondary"]};
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}

    /* ─── Buttons ───────────────────────────────── */
    #btn_primary {{
        background-color: {colors["accent_primary"]};
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }}

    #btn_primary:hover {{
        background-color: {colors["accent_secondary"]};
    }}

    #btn_success {{
        background-color: {colors["status_approved"]};
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-size: 13px;
        font-weight: 600;
    }}

    #btn_danger {{
        background-color: {colors["status_rejected"]};
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-size: 13px;
        font-weight: 600;
    }}

    #btn_secondary {{
        background-color: {colors["bg_panel"]};
        color: {colors["text_secondary"]};
        border: 1px solid {colors["border"]};
        border-radius: 8px;
        padding: 10px 20px;
        font-size: 13px;
        font-weight: 500;
    }}

    #btn_secondary:hover {{
        background-color: {colors["border"]};
        color: {colors["text_primary"]};
    }}

    #btn_outlined {{
        background-color: transparent;
        color: {colors["text_secondary"]};
        border: 1px solid {colors["border"]};
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 500;
    }}

    #btn_outlined:hover {{
        background-color: {colors["bg_panel"]};
        color: {colors["text_primary"]};
    }}

    /* ─── Table / List ──────────────────────────── */
    QTableWidget {{
        background-color: {colors["bg_card"]};
        border: 1px solid {colors["border"]};
        border-radius: 8px;
        gridline-color: {colors["border"]};
        selection-background-color: {colors["accent_secondary"]};
        outline: none;
        color: {colors["text_primary"]};
        font-size: 13px;
    }}

    QTableWidget::item {{
        padding: 10px 12px;
        border-bottom: 1px solid {colors["border"]};
    }}

    QTableWidget::item:selected {{
        background-color: {colors["accent_secondary"]};
        color: #FFFFFF;
    }}

    QHeaderView::section {{
        background-color: {colors["bg_panel"]};
        color: {colors["text_primary"]};
        font-weight: 600;
        font-size: 13px;
        padding: 10px 12px;
        border: none;
        border-bottom: 1px solid {colors["border"]};
        border-right: 1px solid {colors["border"]};
    }}

    QScrollBar:vertical {{
        background-color: {colors["bg_panel"]};
        width: 8px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical {{
        background-color: {colors["border"]};
        border-radius: 4px;
        min-height: 30px;
    }}

    /* ─── Input Fields ──────────────────────────── */
    QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
        background-color: {colors["input_bg"]};
        border: 1px solid {colors["border"]};
        border-radius: 6px;
        padding: 8px 12px;
        color: {colors["text_primary"]};
        font-size: 13px;
    }}

    QLineEdit:focus, QTextEdit:focus {{
        border: 2px solid {colors["accent_highlight"]};
    }}

    /* ─── Labels ────────────────────────────────── */
    #section_title {{
        font-size: 14px;
        font-weight: 600;
        color: {colors["text_primary"]};
    }}

    #page_title {{
        font-size: 20px;
        font-weight: 700;
        color: {colors["text_primary"]};
    }}

    #label_field {{
        font-size: 11px;
        font-weight: 600;
        color: {colors["text_muted"]};
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }}

    #label_value {{
        font-size: 13px;
        color: {colors["text_primary"]};
        font-weight: 500;
    }}

    /* ─── Badge / Status ────────────────────────── */
    #badge_approved {{
        background-color: {colors["bg_panel"]};
        color: {colors["status_approved"]};
        border: 1px solid {colors["status_approved"]};
        border-radius: 12px;
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 700;
    }}

    #badge_pending {{
        background-color: {colors["bg_panel"]};
        color: {colors["status_pending"]};
        border: 1px solid {colors["status_pending"]};
        border-radius: 12px;
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 700;
    }}

    #badge_rejected {{
        background-color: {colors["bg_panel"]};
        color: {colors["status_rejected"]};
        border: 1px solid {colors["status_rejected"]};
        border-radius: 12px;
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 700;
    }}

    #badge_escalated {{
        background-color: {colors["bg_panel"]};
        color: {colors["status_escalated"]};
        border: 1px solid {colors["status_escalated"]};
        border-radius: 12px;
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 700;
    }}

    /* ─── Drop Zone ─────────────────────────────── */
    #drop_zone {{
        background-color: {colors["bg_panel"]};
        border: 2px dashed {colors["border"]};
        border-radius: 12px;
        min-height: 110px;
    }}

    #drop_zone:hover {{
        border-color: {colors["accent_highlight"]};
        background-color: {colors["bg_surface"]};
    }}

    /* ─── Progress / Log ────────────────────────── */
    QProgressBar {{
        background-color: {colors["bg_panel"]};
        border: 1px solid {colors["border"]};
        border-radius: 6px;
        text-align: center;
        color: {colors["text_primary"]};
        font-size: 12px;
        font-weight: 600;
        height: 22px;
    }}

    QProgressBar::chunk {{
        background: {colors["progress_chunk"]};
        border-radius: 6px;
    }}

    /* ─── ComboBox ──────────────────────────────── */
    QComboBox {{
        background-color: {colors["input_bg"]};
        border: 1px solid {colors["border"]};
        border-radius: 6px;
        padding: 8px 12px;
        color: {colors["text_primary"]};
        font-size: 13px;
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {colors["bg_surface"]};
        border: 1px solid {colors["border"]};
        selection-background-color: {colors["accent_secondary"]};
        color: {colors["text_primary"]};
    }}

    /* ─── Tooltip ───────────────────────────────── */
    QToolTip {{
        background-color: {colors["bg_surface"]};
        color: {colors["text_primary"]};
        border: 1px solid {colors["border"]};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
    }}

    /* ─── Menu / Context Menu ───────────────────── */
    QMenu {{
        background-color: {colors["bg_surface"]};
        border: 1px solid {colors["border"]};
        border-radius: 6px;
        padding: 4px;
    }}
    QMenu::item {{
        color: {colors["text_primary"]};
        padding: 8px 20px;
        font-size: 12px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: {colors["accent_secondary"]};
        color: #FFFFFF;
    }}

    /* ─── List Widget ───────────────────────────── */
    QListWidget {{
        background-color: {colors["bg_card"]};
        border: 1px solid {colors["border"]};
        border-radius: 8px;
        color: {colors["text_primary"]};
        outline: none;
    }}
    QListWidget::item {{
        padding: 12px 16px;
        border-bottom: 1px solid {colors["border"]};
    }}
    QListWidget::item:hover {{
        background-color: {colors["nav_hover"]};
    }}
    QListWidget::item:selected {{
        background-color: {colors["accent_secondary"]};
        color: #FFFFFF;
        font-weight: bold;
    }}

    /* ─── Result Card Badges ──────────────────────── */
    #result_badge {{
        border-radius: 10px;
        padding: 2px 10px;
        font-size: 12px;
        font-weight: 700;
        background-color: {colors["bg_panel"]};
    }}
    #result_badge[status="approved"] {{
        color: {colors["status_approved"]};
        border: 1px solid {colors["status_approved"]};
    }}
    #result_badge[status="pending"] {{
        color: {colors["status_pending"]};
        border: 1px solid {colors["status_pending"]};
    }}
    #result_badge[status="rejected"] {{
        color: {colors["status_rejected"]};
        border: 1px solid {colors["status_rejected"]};
    }}
    #result_badge[status="highlight"] {{
        color: {colors["accent_highlight"]};
        border: 1px solid {colors["accent_highlight"]};
    }}

    /* ─── Reasoning Step ─────────────────────────── */
    #reasoning_step {{
        background-color: {colors["bg_panel"]};
        border-radius: 6px;
        border-left: 3px solid {colors["accent_primary"]};
        padding: 2px;
    }}

    /* ─── Notice Banner ─────────────────────────── */
    #notice_banner {{
        background-color: {colors["bg_panel"]};
        color: {colors["text_secondary"]};
        border: 1px solid {colors["border"]};
        border-radius: 8px;
        padding: 12px 16px;
        font-weight: 600;
        font-size: 13px;
    }}

    /* ─── User Profile & Status Panel ───────────── */
    #profile_frame {{
        background-color: {colors["bg_panel"]};
        border: 1px solid {colors["border"]};
        border-radius: 8px;
        margin: 8px;
    }}

    #avatar_circle {{
        background-color: {colors["accent_primary"]};
        color: #FFFFFF;
        font-size: 12px;
        font-weight: bold;
        border-radius: 18px;
        min-width: 36px;
        max-width: 36px;
        min-height: 36px;
        max-height: 36px;
        qproperty-alignment: 'AlignCenter';
    }}

    #tech_badge {{
        background-color: {colors["bg_panel"]};
        border: 1px solid {colors["border"]};
        color: {colors["text_muted"]};
        font-family: 'JetBrains Mono', 'Consolas', monospace;
        font-size: 10px;
        border-radius: 6px;
        padding: 2px 6px;
    }}
    """;

# ─────────────────────────────────────────────
# Sidebar navigation button
# ─────────────────────────────────────────────
class SidebarButton(QPushButton):
    """Custom sidebar navigation button."""

    def __init__(self, icon_text: str, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("nav_btn")
        self.setText(f"  {icon_text}  {label}")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(44)

    def set_active(self, active: bool):
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)


# ─────────────────────────────────────────────
# Pulsing Dot Indicator Widget
# ─────────────────────────────────────────────
class PulsingDot(QLabel):
    """Circular, pulsing status indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self._state = "amber"  # default loading state
        self._alpha = 1.0
        self._decreasing = True
        
        # Smooth pulse timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_pulse)
        self._timer.start(100)
        self._update_style()

    def set_state(self, state: str):
        self._state = state
        self._update_style()

    def _update_pulse(self):
        if self._state == "red":
            # Offline stays solid red
            self._alpha = 1.0
        else:
            # Pulse intensity oscillation
            if self._decreasing:
                self._alpha -= 0.08
                if self._alpha <= 0.3:
                    self._alpha = 0.3
                    self._decreasing = False
            else:
                self._alpha += 0.08
                if self._alpha >= 1.0:
                    self._alpha = 1.0
                    self._decreasing = True
        self._update_style()

    def _update_style(self):
        colors = {
            "green": "34, 197, 94",   # Ready (deep green)
            "amber": "245, 158, 11",  # Loading (amber)
            "red": "239, 68, 68"      # Offline (red)
        }
        rgb = colors.get(self._state, "245, 158, 11")
        self.setStyleSheet(f"""
            background-color: rgba({rgb}, {self._alpha:.2f});
            border-radius: 5px;
            border: 1px solid rgb({rgb});
        """)


# ─────────────────────────────────────────────
# Main Window Class
# ─────────────────────────────────────────────
class MainWindow(QMainWindow):
    """Root application window with Top Bar, Sidebar, and QStackedWidget."""

    page_changed = Signal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("JTCA — Jabil TradeAI Compliance Assistant")
        self.setMinimumSize(1280, 780)
        self.resize(1400, 860)
        
        self._current_theme = "dark"  # default
        self._nav_buttons: list[SidebarButton] = []
        self._pages: list[QWidget] = []
        self._current_page = 0
        
        self._setup_ui()
        self.set_theme("dark")  # Initialize stylesheet

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        # Parent vertical layout
        parent_layout = QVBoxLayout(central)
        parent_layout.setSpacing(0)
        parent_layout.setContentsMargins(0, 0, 0, 0)

        # ─────────────────────────────────────────────
        # 1. TOP BAR (Height: 52px)
        # ─────────────────────────────────────────────
        top_bar = QFrame()
        top_bar.setObjectName("top_bar")
        top_bar.setFixedHeight(52)
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(16, 0, 16, 0)
        top_bar_layout.setSpacing(16)

        # Left Part: Brand & Logo
        logo_mark = QLabel("J")
        logo_mark.setObjectName("top_logo_mark")
        logo_mark.setAlignment(Qt.AlignCenter)

        wordmark = QLabel("JTCA")
        wordmark.setObjectName("top_wordmark")

        version_chip = QLabel("v1.0.0 POC")
        version_chip.setObjectName("top_version_chip")

        top_bar_layout.addWidget(logo_mark)
        top_bar_layout.addWidget(wordmark)
        top_bar_layout.addWidget(version_chip)

        # Separator
        v_line = QFrame()
        v_line.setFrameShape(QFrame.VLine)
        v_line.setStyleSheet("color: #D0D9E8; max-width: 1px; min-height: 20px;")
        top_bar_layout.addWidget(v_line)

        # Center Part: Breadcrumbs
        self.breadcrumb_lbl = QLabel("Dashboard / Overview")
        self.breadcrumb_lbl.setObjectName("top_breadcrumb")
        top_bar_layout.addWidget(self.breadcrumb_lbl)

        top_bar_layout.addStretch()

        # Right Part: Controls & Profile
        # System status pill
        self.top_status_pill = QLabel("System Ready")
        self.top_status_pill.setObjectName("top_status_pill")
        top_bar_layout.addWidget(self.top_status_pill)

        # Refresh
        self.top_refresh_btn = QPushButton("🔄 Refresh")
        self.top_refresh_btn.setObjectName("btn_outlined")
        self.top_refresh_btn.setCursor(Qt.PointingHandCursor)
        self.top_refresh_btn.clicked.connect(self._on_refresh_clicked)
        top_bar_layout.addWidget(self.top_refresh_btn)

        # Export dropdown button
        self.top_export_btn = QPushButton("Export ▾")
        self.top_export_btn.setObjectName("btn_outlined")
        self.top_export_btn.setCursor(Qt.PointingHandCursor)
        
        # Export dropdown Menu
        export_menu = QMenu(self)
        excel_action = QAction("Export Excel", self)
        excel_action.triggered.connect(self._on_export_excel)
        pdf_action = QAction("Export PDF", self)
        pdf_action.triggered.connect(self._on_export_pdf)
        json_action = QAction("Export JSON", self)
        json_action.triggered.connect(self._on_export_json)

        export_menu.addAction(excel_action)
        export_menu.addAction(pdf_action)
        export_menu.addAction(json_action)
        self.top_export_btn.setMenu(export_menu)
        top_bar_layout.addWidget(self.top_export_btn)

        # Theme Toggle Button
        self.theme_btn = QPushButton("☀")
        self.theme_btn.setObjectName("btn_outlined")
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setFixedWidth(36)
        self.theme_btn.clicked.connect(self.toggle_theme)
        top_bar_layout.addWidget(self.theme_btn)

        # User Avatar Circle
        self.top_avatar = QLabel("CHAI")
        self.top_avatar.setObjectName("top_user_avatar")
        self.top_avatar.setAlignment(Qt.AlignCenter)
        self.top_avatar.setStyleSheet("""
            min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px;
            background-color: #0A3D91; color: #FFFFFF; border-radius: 14px; font-weight: bold; font-size: 10px;
        """)
        top_bar_layout.addWidget(self.top_avatar)

        parent_layout.addWidget(top_bar)

        # ─────────────────────────────────────────────
        # 2. BODY LAYOUT (Sidebar + Content Stack)
        # ─────────────────────────────────────────────
        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setSpacing(0)
        body_layout.setContentsMargins(0, 0, 0, 0)

        # ── Sidebar ──
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFrameShape(QFrame.NoFrame)
        sidebar.setFixedWidth(220)
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(0)
        sidebar_layout.setContentsMargins(0, 16, 0, 16)

        # Nav label
        menu_label = QLabel("  NAVIGATION")
        menu_label.setObjectName("nav_section_label")
        sidebar_layout.addWidget(menu_label)
        sidebar_layout.addSpacing(8)

        # Nav buttons
        nav_items = [
            ("🏠", "Dashboard"),
            ("📋", "Shipments"),
            ("📚", "Case Studies"),
            ("🌐", "Web Crawler"),
            ("📊", "Reports"),
        ]
        for icon, label in nav_items:
            btn = SidebarButton(icon, label)
            btn.clicked.connect(lambda checked, b=btn: self._on_nav_clicked(b))
            sidebar_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        sidebar_layout.addStretch()

        # ── User Profile Panel ──
        self.profile_frame = QFrame()
        self.profile_frame.setObjectName("profile_frame")
        profile_layout = QVBoxLayout(self.profile_frame)
        profile_layout.setContentsMargins(12, 12, 12, 12)
        profile_layout.setSpacing(8)

        # Top section of profile: Circle avatar + Username/Role
        user_row = QHBoxLayout()
        self.sidebar_avatar = QLabel("CH")
        self.sidebar_avatar.setObjectName("avatar_circle")
        self.sidebar_avatar.setAlignment(Qt.AlignCenter)
        
        user_info = QVBoxLayout()
        user_info.setSpacing(2)
        self.profile_user_lbl = QLabel("Guest User")
        self.profile_user_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.profile_role_lbl = QLabel("Guest")
        self.profile_role_lbl.setAlignment(Qt.AlignCenter)
        self.profile_role_lbl.setMinimumWidth(80)
        
        user_info.addWidget(self.profile_user_lbl)
        user_info.addWidget(self.profile_role_lbl)
        user_row.addWidget(self.sidebar_avatar)
        user_row.addLayout(user_info)
        profile_layout.addLayout(user_row)

        sidebar_layout.addWidget(self.profile_frame)

        # ── AI Status Panel ──
        self.ai_status_frame = QFrame()
        self.ai_status_frame.setObjectName("profile_frame")
        self.ai_status_frame.setStyleSheet("margin-top: 0px;")
        ai_layout = QVBoxLayout(self.ai_status_frame)
        ai_layout.setContentsMargins(12, 12, 12, 12)
        ai_layout.setSpacing(8)

        # Pulse indicator row
        pulse_row = QHBoxLayout()
        ai_title = QLabel("AI STATUS")
        ai_title.setStyleSheet("font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        self.pulse_dot = PulsingDot()
        pulse_row.addWidget(ai_title)
        pulse_row.addStretch()
        pulse_row.addWidget(self.pulse_dot)
        ai_layout.addLayout(pulse_row)

        # Tech pills
        self.pills = [
            QLabel("SQLite+ChromaDB"),
            QLabel("Gemini 2.0 Flash"),
            QLabel("SentenceTransformers")
        ]
        for pill in self.pills:
            pill.setObjectName("tech_badge")
            pill.setAlignment(Qt.AlignCenter)
            ai_layout.addWidget(pill)

        sidebar_layout.addWidget(self.ai_status_frame)

        # Sign Out button
        self.logout_btn = QPushButton("  🚪  Sign Out")
        self.logout_btn.setObjectName("nav_btn")
        self.logout_btn.setCursor(Qt.PointingHandCursor)
        self.logout_btn.setMinimumHeight(40)
        self.logout_btn.clicked.connect(self._on_logout)
        sidebar_layout.addWidget(self.logout_btn)

        body_layout.addWidget(sidebar)

        # ── Content Stack ──
        self.stack = QStackedWidget()
        self.stack.setObjectName("content_area")
        body_layout.addWidget(self.stack, stretch=1)

        parent_layout.addWidget(body_widget, stretch=1)

        # Set first nav button active
        if self._nav_buttons:
            self._nav_buttons[0].set_active(True)

    def add_page(self, widget: QWidget):
        """Add a page to the stacked widget."""
        self.stack.addWidget(widget)
        self._pages.append(widget)

    def navigate_to(self, index: int):
        """Switch to a page by index."""
        self.stack.setCurrentIndex(index)
        self._current_page = index
        for i, btn in enumerate(self._nav_buttons):
            btn.set_active(i == index)
            
        # Update breadcrumbs dynamically
        breadcrumbs = {
            0: "Dashboard / Overview",
            1: "Shipments / All Shipments",
            2: "Case Studies / Catalog",
            3: "Web Crawler / Tariff Knowledge",
            4: "Reports / Analytics & Logs",
            5: "Shipments / Shipment Details"
        }
        self.breadcrumb_lbl.setText(breadcrumbs.get(index, "JTCA"))
        self.page_changed.emit(index)

    def _on_nav_clicked(self, button: SidebarButton):
        if button in self._nav_buttons:
            index = self._nav_buttons.index(button)
            self.navigate_to(index)

    def set_theme(self, theme_name: str):
        """Switch global theme colors."""
        self._current_theme = theme_name
        qss = get_theme_stylesheet(theme_name)
        QApplication.instance().setStyleSheet(qss)
        
        # Toggle icon
        if theme_name == "light":
            self.theme_btn.setText("🌙")
            self.theme_btn.setToolTip("Switch to Dark Mode")
        else:
            self.theme_btn.setText("☀")
            self.theme_btn.setToolTip("Switch to Light Mode")
            
        self.apply_permissions()

    def toggle_theme(self):
        """Toggle between light and dark themes."""
        if self._current_theme == "dark":
            self.set_theme("light")
        else:
            self.set_theme("dark")

    def set_ai_status(self, state: str, status_text: str = None):
        """Set the state of the pulsing dot and the top bar status text."""
        self.pulse_dot.set_state(state)
        
        # Update status pill in top bar
        if status_text:
            self.top_status_pill.setText(status_text)
        else:
            state_labels = {
                "green": "System Ready",
                "amber": "AI Loading...",
                "red": "System Offline"
            }
            self.top_status_pill.setText(state_labels.get(state, "System Ready"))

        # Style top status pill based on state
        styles = {
            "green": "color: #1B8A4E; background-color: #EEF2F8; border: 1px solid #D0D9E8;",
            "amber": "color: #C07A00; background-color: #EEF2F8; border: 1px solid #D0D9E8;",
            "red": "color: #C0392B; background-color: #EEF2F8; border: 1px solid #D0D9E8;"
        }
        if self._current_theme == "dark":
            styles = {
                "green": "color: #22C55E; background-color: #162236; border: 1px solid #1E3150;",
                "amber": "color: #F59E0B; background-color: #162236; border: 1px solid #1E3150;",
                "red": "color: #EF4444; background-color: #162236; border: 1px solid #1E3150;"
            }
        self.top_status_pill.setStyleSheet(styles.get(state, ""))

    def apply_permissions(self):
        """Apply active user role permissions to the sidebar and all sub-pages."""
        from services.session import SessionManager
        session = SessionManager()
        username = session.get_username()
        role = session.get_role()
        
        # Update user section
        self.profile_user_lbl.setText(username)
        
        # Initials for avatar
        initials = "".join([part[0] for part in username.split() if part])[:2].upper()
        self.sidebar_avatar.setText(initials if initials else "US")
        self.top_avatar.setText("CHAI") # Always show CHAI for the top avatar circle as requested, or initials
        
        self.profile_role_lbl.setText(role.upper())
        
        # Role badge styling depending on theme
        if role == "Admin":
            if self._current_theme == "light":
                self.profile_role_lbl.setStyleSheet("""
                    background-color: #EEF2F8;
                    color: #0A3D91;
                    font-size: 10px;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 3px 6px;
                    border: 1px solid #D0D9E8;
                """)
            else:
                self.profile_role_lbl.setStyleSheet("""
                    background-color: #162236;
                    color: #56B4FF;
                    font-size: 10px;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 3px 6px;
                    border: 1px solid #1E3150;
                """)
        else:  # Trade Analyst
            if self._current_theme == "light":
                self.profile_role_lbl.setStyleSheet("""
                    background-color: #EEF2F8;
                    color: #1B8A4E;
                    font-size: 10px;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 3px 6px;
                    border: 1px solid #D0D9E8;
                """)
            else:
                self.profile_role_lbl.setStyleSheet("""
                    background-color: #162236;
                    color: #22C55E;
                    font-size: 10px;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 3px 6px;
                    border: 1px solid #1E3150;
                """)

        # Call apply_permissions on any page that has it
        for page in self._pages:
            if hasattr(page, "apply_permissions"):
                try:
                    page.apply_permissions()
                except Exception as e:
                    logger.error(f"Error applying permissions to page {page}: {e}")

    def _on_refresh_clicked(self):
        """Trigger refresh on active stacked page."""
        curr_widget = self.stack.currentWidget()
        if hasattr(curr_widget, "refresh_data"):
            try:
                curr_widget.refresh_data()
                logger.info(f"Refreshed page {curr_widget.__class__.__name__}")
            except Exception as e:
                logger.error(f"Error refreshing page: {e}")

    def _on_export_excel(self):
        """Trigger Excel export on current page or general exports."""
        curr_widget = self.stack.currentWidget()
        if hasattr(curr_widget, "_export_report"):
            curr_widget._export_report()
        elif hasattr(curr_widget, "_export_all"):
            curr_widget._export_all()
        else:
            QMessageBox.information(self, "Export", "Excel export is not supported for the current page.")

    def _on_export_pdf(self):
        """Trigger PDF export if page supports it."""
        curr_widget = self.stack.currentWidget()
        if hasattr(curr_widget, "_export_pdf"):
            curr_widget._export_pdf()
        else:
            QMessageBox.information(self, "Export", "PDF export is not supported for the current page.")

    def _on_export_json(self):
        """Trigger JSON export if page supports it."""
        curr_widget = self.stack.currentWidget()
        if hasattr(curr_widget, "_export_json"):
            curr_widget._export_json()
        else:
            QMessageBox.information(self, "Export", "JSON export is not supported for the current page.")

    def _on_logout(self):
        reply = QMessageBox.question(
            self,
            "Sign Out",
            "Are you sure you want to sign out of JTCA?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            from services.session import SessionManager
            from ui.login_dialog import LoginDialog
            
            SessionManager().logout()
            self.hide()
            
            login_dlg = LoginDialog()
            if login_dlg.exec() == LoginDialog.Accepted:
                self.apply_permissions()
                self.navigate_to(0)
                self.show()
            else:
                QApplication.quit()
