"""
============================================================
JTCA - Login & Role Selection Dialog
Select between Admin and Trade Analyst roles
============================================================
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

class RoleCard(QFrame):
    """Clickable, visual card representing a user role."""
    clicked = Signal(str)

    def __init__(self, role_id: str, icon: str, title: str, description: str, theme_color: str, parent=None):
        super().__init__(parent)
        self.role_id = role_id
        self.theme_color = theme_color
        self.selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(220, 160)
        self.setObjectName("role_card")

        self.setStyleSheet(f"""
            QFrame#role_card {{
                background-color: #0D1F3C;
                border: 2px solid #1565C0;
                border-radius: 12px;
                padding: 16px;
            }}
            QFrame#role_card:hover {{
                border-color: {theme_color};
                background-color: #1A3A5C;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_lbl = QLabel(icon)
        self.icon_lbl.setStyleSheet("font-size: 36px;")
        self.icon_lbl.setAlignment(Qt.AlignCenter)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: #FFFFFF;")
        self.title_lbl.setAlignment(Qt.AlignCenter)

        self.desc_lbl = QLabel(description)
        self.desc_lbl.setStyleSheet("font-size: 11px; color: #90CAF9;")
        self.desc_lbl.setAlignment(Qt.AlignCenter)
        self.desc_lbl.setWordWrap(True)

        layout.addWidget(self.icon_lbl)
        layout.addWidget(self.title_lbl)
        layout.addWidget(self.desc_lbl)

    def set_selected(self, selected: bool):
        self.selected = selected
        if selected:
            self.setStyleSheet(f"""
                QFrame#role_card {{
                    background-color: #1A3A5C;
                    border: 3px solid {self.theme_color};
                    border-radius: 12px;
                    padding: 15px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#role_card {{
                    background-color: #0D1F3C;
                    border: 2px solid #1565C0;
                    border-radius: 12px;
                    padding: 16px;
                }}
                QFrame#role_card:hover {{
                    border-color: {self.theme_color};
                    background-color: #1A3A5C;
                }}
            """)

    def mousePressEvent(self, event):
        self.clicked.emit(self.role_id)
        super().mousePressEvent(event)


class LoginDialog(QDialog):
    """Beautiful custom role selection & login modal dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sign In — JTCA Compliance Assistant")
        self.setMinimumSize(560, 480)
        self.setModal(True)
        self.selected_role = None

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
                padding: 10px 14px;
                color: #E2E8F0;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 2px solid #42A5F5;
            }
            #sign_in_btn {
                background-color: #0057A8;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            #sign_in_btn:hover {
                background-color: #1976D2;
            }
            #sign_in_btn:pressed {
                background-color: #003D7A;
            }
            #sign_in_btn:disabled {
                background-color: #102A45;
                color: #4A6FA5;
                border: 1px solid #1565C0;
            }
        """)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(36, 30, 36, 30)

        # ── Header ──────────────────────────────────────
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        header_layout.setAlignment(Qt.AlignCenter)

        jabil_lbl = QLabel("JABIL")
        jabil_lbl.setStyleSheet("color: #FFFFFF; font-size: 26px; font-weight: 800; letter-spacing: 4px;")
        jabil_lbl.setAlignment(Qt.AlignCenter)

        subtitle_lbl = QLabel("TradeAI Compliance Assistant")
        subtitle_lbl.setStyleSheet("color: #42A5F5; font-size: 13px; font-weight: 600; letter-spacing: 0.5px;")
        subtitle_lbl.setAlignment(Qt.AlignCenter)

        header_layout.addWidget(jabil_lbl)
        header_layout.addWidget(subtitle_lbl)
        layout.addLayout(header_layout)

        # Prompt text
        prompt_lbl = QLabel("SELECT YOUR SYSTEM ROLE")
        prompt_lbl.setStyleSheet("color: #90CAF9; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        prompt_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(prompt_lbl)

        # ── Cards Row ───────────────────────────────────
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self.admin_card = RoleCard(
            role_id="Admin",
            icon="🛡️",
            title="Administrator",
            description="Manage knowledge base, configure crawler, view reports and full logs.",
            theme_color="#42A5F5"
        )
        self.analyst_card = RoleCard(
            role_id="Trade Analyst",
            icon="📋",
            title="Trade Analyst",
            description="Upload incoming supplier invoices, review HS codes, and approve/reject shipments.",
            theme_color="#059669"
        )

        cards_layout.addWidget(self.admin_card)
        cards_layout.addWidget(self.analyst_card)
        layout.addLayout(cards_layout)

        # Connect signals
        self.admin_card.clicked.connect(self._select_role)
        self.analyst_card.clicked.connect(self._select_role)

        # ── Name Input ──────────────────────────────────
        name_lbl = QLabel("ENTER YOUR NAME")
        name_lbl.setStyleSheet("color: #90CAF9; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        layout.addWidget(name_lbl)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter your full name (e.g. Sarah Connor)")
        self.name_input.textChanged.connect(self._validate)
        layout.addWidget(self.name_input)

        layout.addSpacing(4)

        # ── Sign In / Close Buttons ────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.close_btn = QPushButton("Exit")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #B0C4DE;
                border: 1px solid #1E3A5F;
                border-radius: 8px;
                padding: 11px 20px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #450A0A;
                color: #F87171;
                border-color: #EF4444;
            }
        """)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.reject)

        self.sign_in_btn = QPushButton("Sign In")
        self.sign_in_btn.setObjectName("sign_in_btn")
        self.sign_in_btn.setCursor(Qt.PointingHandCursor)
        self.sign_in_btn.setEnabled(False)
        self.sign_in_btn.clicked.connect(self._on_sign_in)

        btn_layout.addWidget(self.close_btn)
        btn_layout.addWidget(self.sign_in_btn, stretch=1)
        layout.addLayout(btn_layout)

    def _select_role(self, role_id: str):
        self.selected_role = role_id
        self.admin_card.set_selected(role_id == "Admin")
        self.analyst_card.set_selected(role_id == "Trade Analyst")
        self._validate()

    def _validate(self):
        name = self.name_input.text().strip()
        has_role = self.selected_role is not None
        has_name = len(name) > 0
        self.sign_in_btn.setEnabled(has_role and has_name)

    def _on_sign_in(self):
        name = self.name_input.text().strip()
        if not self.selected_role:
            QMessageBox.warning(self, "Sign In", "Please select a system role.")
            return
        if not name:
            QMessageBox.warning(self, "Sign In", "Please enter your name.")
            return

        from services.session import SessionManager
        SessionManager().login(name, self.selected_role)
        self.accept()
