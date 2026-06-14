"""
============================================================
JTCA - Main Window
PySide6 root window with sidebar navigation
Jabil Blue & White theme
============================================================
"""

import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout,
    QVBoxLayout, QPushButton, QLabel, QStackedWidget,
    QFrame, QSizePolicy, QSpacerItem,
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Global Stylesheet — Jabil Blue Theme
# ─────────────────────────────────────────────
GLOBAL_STYLE = """
/* ─── Global Reset ─────────────────────────── */
* {
    font-family: 'Segoe UI', 'Arial', sans-serif;
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

QMainWindow, QDialog {
    background-color: #0A1628;
}

QWidget {
    background-color: transparent;
    color: #E2E8F0;
}

/* ─── Sidebar ───────────────────────────────── */
#sidebar {
    background-color: #0D1F3C;
    border-right: 2px solid #1565C0;
    min-width: 220px;
    max-width: 220px;
}

#logo_frame {
    background-color: #0057A8;
    padding: 16px;
    border-bottom: 2px solid #1976D2;
}

#app_title {
    color: #FFFFFF;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 1px;
}

#app_subtitle {
    color: #90CAF9;
    font-size: 10px;
    font-weight: 400;
}

/* ─── Sidebar Nav Buttons ───────────────────── */
#nav_btn {
    background-color: transparent;
    color: #B0C4DE;
    border: none;
    border-radius: 8px;
    text-align: left;
    padding: 12px 16px;
    font-size: 13px;
    font-weight: 500;
    margin: 2px 8px;
}

#nav_btn:hover {
    background-color: #1A3A5C;
    color: #FFFFFF;
}

#nav_btn[active="true"] {
    background-color: #0057A8;
    color: #FFFFFF;
    font-weight: 700;
    border-left: 3px solid #42A5F5;
}

/* ─── Content Area ──────────────────────────── */
#content_area {
    background-color: #0A1628;
}

/* ─── Cards ─────────────────────────────────── */
#card {
    background-color: #0D1F3C;
    border: 1px solid #1565C0;
    border-radius: 12px;
    padding: 16px;
}

#stat_card {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #0D2147, stop:1 #0A1A38
    );
    border: 1px solid #1565C0;
    border-radius: 12px;
    padding: 20px;
    min-width: 160px;
}

#stat_value {
    font-size: 32px;
    font-weight: 800;
    color: #42A5F5;
}

#stat_label {
    font-size: 12px;
    color: #90CAF9;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ─── Buttons ───────────────────────────────── */
#btn_primary {
    background-color: #0057A8;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.5px;
}

#btn_primary:hover {
    background-color: #1976D2;
}

#btn_primary:pressed {
    background-color: #003D7A;
}

#btn_success {
    background-color: #059669;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 13px;
    font-weight: 600;
}

#btn_success:hover {
    background-color: #10B981;
}

#btn_danger {
    background-color: #DC2626;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 13px;
    font-weight: 600;
}

#btn_danger:hover {
    background-color: #EF4444;
}

#btn_secondary {
    background-color: #1E3A5F;
    color: #90CAF9;
    border: 1px solid #1565C0;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 500;
}

#btn_secondary:hover {
    background-color: #243E6A;
    color: #FFFFFF;
}

/* ─── Table / List ──────────────────────────── */
QTableWidget {
    background-color: #0D1F3C;
    border: 1px solid #1565C0;
    border-radius: 8px;
    gridline-color: #1A3A5C;
    selection-background-color: #1565C0;
    outline: none;
    color: #E2E8F0;
    font-size: 12px;
}

QTableWidget::item {
    padding: 10px 12px;
    border-bottom: 1px solid #1A3A5C;
}

QTableWidget::item:selected {
    background-color: #1565C0;
    color: #FFFFFF;
}

QHeaderView::section {
    background-color: #0057A8;
    color: #FFFFFF;
    font-weight: 700;
    font-size: 12px;
    padding: 10px 12px;
    border: none;
    border-right: 1px solid #1976D2;
}

QScrollBar:vertical {
    background-color: #0D1F3C;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background-color: #1565C0;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    background: none;
    height: 0px;
}

/* ─── Input Fields ──────────────────────────── */
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
    background-color: #0D2147;
    border: 1px solid #1565C0;
    border-radius: 6px;
    padding: 8px 12px;
    color: #E2E8F0;
    font-size: 13px;
    selection-background-color: #1976D2;
}

QLineEdit:focus, QTextEdit:focus {
    border: 2px solid #42A5F5;
}

QLineEdit::placeholder {
    color: #4A6FA5;
}

/* ─── Labels ────────────────────────────────── */
#section_title {
    font-size: 18px;
    font-weight: 700;
    color: #FFFFFF;
    letter-spacing: 0.5px;
}

#page_title {
    font-size: 22px;
    font-weight: 800;
    color: #FFFFFF;
}

#label_field {
    font-size: 11px;
    font-weight: 600;
    color: #90CAF9;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}

#label_value {
    font-size: 14px;
    color: #E2E8F0;
    font-weight: 500;
}

/* ─── Badge / Status ────────────────────────── */
#badge_approved {
    background-color: #064E3B;
    color: #34D399;
    border: 1px solid #059669;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}

#badge_pending {
    background-color: #451A03;
    color: #FCD34D;
    border: 1px solid #D97706;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}

#badge_rejected {
    background-color: #450A0A;
    color: #F87171;
    border: 1px solid #DC2626;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}

/* ─── Drop Zone ─────────────────────────────── */
#drop_zone {
    background-color: #091628;
    border: 2px dashed #1565C0;
    border-radius: 12px;
    min-height: 100px;
}

#drop_zone:hover {
    border-color: #42A5F5;
    background-color: #0D1F3C;
}

/* ─── Progress / Log ────────────────────────── */
QProgressBar {
    background-color: #0D1F3C;
    border: 1px solid #1565C0;
    border-radius: 6px;
    text-align: center;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 600;
    height: 22px;
}

QProgressBar::chunk {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #0057A8, stop:1 #42A5F5
    );
    border-radius: 6px;
}

/* ─── Separator ─────────────────────────────── */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {
    color: #1565C0;
}

/* ─── Tooltip ───────────────────────────────── */
QToolTip {
    background-color: #0D2147;
    color: #E2E8F0;
    border: 1px solid #1565C0;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}

/* ─── ComboBox ──────────────────────────────── */
QComboBox {
    background-color: #0D2147;
    border: 1px solid #1565C0;
    border-radius: 6px;
    padding: 8px 12px;
    color: #E2E8F0;
    font-size: 13px;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #0D2147;
    border: 1px solid #1565C0;
    selection-background-color: #1565C0;
    color: #E2E8F0;
}

/* ─── Message Box ───────────────────────────── */
QMessageBox {
    background-color: #0D1F3C;
}

QMessageBox QLabel {
    color: #E2E8F0;
    font-size: 13px;
}

QMessageBox QPushButton {
    background-color: #0057A8;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 12px;
    min-width: 80px;
}

QMessageBox QPushButton:hover {
    background-color: #1976D2;
}
"""


class SidebarButton(QPushButton):
    """Custom sidebar navigation button."""

    def __init__(self, icon_text: str, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("nav_btn")
        self.setText(f"  {icon_text}  {label}")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(44)
        self.setFont(QFont("Segoe UI", 12))

    def set_active(self, active: bool):
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QMainWindow):
    """Root application window with sidebar and stacked content area."""

    page_changed = Signal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("JTCA — Jabil TradeAI Compliance Assistant")
        self.setMinimumSize(1280, 780)
        self.resize(1400, 860)
        self._nav_buttons: list[SidebarButton] = []
        self._pages: list[QWidget] = []
        self._current_page = 0
        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setSpacing(0)
        root_layout.setContentsMargins(0, 0, 0, 0)

        # ── Sidebar ──────────────────────────────────
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFrameShape(QFrame.NoFrame)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(0)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        # Logo block
        logo_frame = QFrame()
        logo_frame.setObjectName("logo_frame")
        logo_layout = QVBoxLayout(logo_frame)
        logo_layout.setContentsMargins(16, 16, 16, 16)
        logo_layout.setSpacing(4)

        title_label = QLabel("JABIL")
        title_label.setObjectName("app_title")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title_label.setStyleSheet("color: #FFFFFF; letter-spacing: 3px;")

        subtitle_label = QLabel("TradeAI Compliance Assistant")
        subtitle_label.setObjectName("app_subtitle")
        subtitle_label.setStyleSheet("color: #90CAF9; font-size: 10px;")
        subtitle_label.setWordWrap(True)

        version_label = QLabel("v1.0.0 POC")
        version_label.setStyleSheet("color: #4A6FA5; font-size: 9px;")

        logo_layout.addWidget(title_label)
        logo_layout.addWidget(subtitle_label)
        logo_layout.addWidget(version_label)
        sidebar_layout.addWidget(logo_frame)

        # Nav separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #1565C0; max-height: 1px;")
        sidebar_layout.addWidget(sep)
        sidebar_layout.addSpacing(12)

        # Nav menu label
        menu_label = QLabel("  NAVIGATION")
        menu_label.setStyleSheet(
            "color: #4A6FA5; font-size: 10px; font-weight: 700; "
            "letter-spacing: 2px; padding: 0 8px;"
        )
        sidebar_layout.addWidget(menu_label)
        sidebar_layout.addSpacing(4)

        # Nav buttons
        nav_items = [
            ("🏠", "Dashboard"),
            ("📋", "Shipments"),
            ("🌐", "Web Crawler"),
            ("📊", "Reports"),
        ]
        for icon, label in nav_items:
            btn = SidebarButton(icon, label)
            btn.clicked.connect(lambda checked, b=btn: self._on_nav_clicked(b))
            sidebar_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        sidebar_layout.addStretch()

        # ── User Profile Panel ─────────────────────────
        self.profile_frame = QFrame()
        self.profile_frame.setStyleSheet("""
            QFrame {
                background-color: #0A1A35;
                border: 1px solid #1565C0;
                border-radius: 8px;
                margin: 8px;
            }
        """)
        profile_layout = QVBoxLayout(self.profile_frame)
        profile_layout.setContentsMargins(12, 10, 12, 10)
        profile_layout.setSpacing(6)

        self.profile_user_lbl = QLabel("👤 Guest User")
        self.profile_user_lbl.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 12px;")
        
        self.profile_role_lbl = QLabel("Guest")
        self.profile_role_lbl.setAlignment(Qt.AlignCenter)
        
        profile_layout.addWidget(self.profile_user_lbl)
        profile_layout.addWidget(self.profile_role_lbl)
        sidebar_layout.addWidget(self.profile_frame)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("background-color: #1565C0; max-height: 1px; margin: 8px;")
        sidebar_layout.addWidget(sep2)

        # System info
        info_label = QLabel("  📡 SQLite + ChromaDB\n  🤖 Gemini 2.0 Flash\n  🔍 SentenceTransformers")
        info_label.setStyleSheet("color: #4A6FA5; font-size: 10px; padding: 8px 12px; line-height: 1.6;")
        sidebar_layout.addWidget(info_label)
        sidebar_layout.addSpacing(8)

        # Sign Out button
        self.logout_btn = QPushButton("  🚪  Sign Out")
        self.logout_btn.setObjectName("nav_btn")
        self.logout_btn.setCursor(Qt.PointingHandCursor)
        self.logout_btn.setMinimumHeight(40)
        self.logout_btn.clicked.connect(self._on_logout)
        sidebar_layout.addWidget(self.logout_btn)
        sidebar_layout.addSpacing(8)

        root_layout.addWidget(sidebar)

        # ── Content Stack ─────────────────────────────
        self.stack = QStackedWidget()
        self.stack.setObjectName("content_area")
        root_layout.addWidget(self.stack, stretch=1)

        # Set first nav button active
        if self._nav_buttons:
            self._nav_buttons[0].set_active(True)

    def add_page(self, widget: QWidget):
        """Add a page to the stacked widget and track it."""
        self.stack.addWidget(widget)
        self._pages.append(widget)

    def navigate_to(self, index: int):
        """Switch to a page by index."""
        self.stack.setCurrentIndex(index)
        self._current_page = index
        for i, btn in enumerate(self._nav_buttons):
            btn.set_active(i == index)
        self.page_changed.emit(index)

    def _on_nav_clicked(self, button: SidebarButton):
        if button in self._nav_buttons:
            index = self._nav_buttons.index(button)
            self.navigate_to(index)

    def apply_permissions(self):
        """Apply active user role permissions to the sidebar and all sub-pages."""
        from services.session import SessionManager
        session = SessionManager()
        username = session.get_username()
        role = session.get_role()
        
        # Update profile sidebar display
        self.profile_user_lbl.setText(f"👤 {username}")
        self.profile_role_lbl.setText(role.upper())
        
        if role == "Admin":
            self.profile_role_lbl.setStyleSheet("""
                background-color: #1E3A8A;
                color: #93C5FD;
                font-size: 10px;
                font-weight: bold;
                border-radius: 4px;
                padding: 3px 6px;
                border: 1px solid #3B82F6;
            """)
        else:  # Trade Analyst
            self.profile_role_lbl.setStyleSheet("""
                background-color: #064E3B;
                color: #6EE7B7;
                font-size: 10px;
                font-weight: bold;
                border-radius: 4px;
                padding: 3px 6px;
                border: 1px solid #059669;
            """)

        # Call apply_permissions on any page that has it
        for page in self._pages:
            if hasattr(page, "apply_permissions"):
                try:
                    page.apply_permissions()
                except Exception as e:
                    logger.error(f"Error applying permissions to page {page}: {e}")

    def _on_logout(self):
        from PySide6.QtWidgets import QMessageBox
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
                # Navigate to dashboard (index 0) upon relogin
                self.navigate_to(0)
                self.show()
            else:
                QApplication.quit()
