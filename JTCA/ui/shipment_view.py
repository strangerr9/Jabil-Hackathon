"""
============================================================
JTCA - Shipment View Page
Invoice detail page matching wireframe layout
Shows HS Code result, Tariff %, calculation steps,
Approve / Disapprove action buttons
============================================================
"""

import logging
import json
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QTextEdit, QSizePolicy, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QSplitter,
    QGridLayout,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Sub-Widgets
# ─────────────────────────────────────────────
class InfoField(QWidget):
    """Label + value pair field widget."""

    def __init__(self, label: str, value: str = "", mono: bool = False):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(label.upper())
        lbl.setObjectName("label_field")
        lbl.setStyleSheet(
            "color: #90CAF9; font-size: 10px; font-weight: 700; letter-spacing: 1px;"
        )

        self.value_lbl = QLabel(value or "—")
        self.value_lbl.setObjectName("label_value")
        self.value_lbl.setStyleSheet(
            f"color: #E2E8F0; font-size: 13px; font-weight: 500;"
            + ("font-family: 'Consolas', monospace;" if mono else "")
        )
        self.value_lbl.setWordWrap(True)

        layout.addWidget(lbl)
        layout.addWidget(self.value_lbl)

    def set_value(self, val: str):
        self.value_lbl.setText(val or "—")


class ResultCard(QFrame):
    """Result card widget with confidence badge, source URL."""

    def __init__(self, title: str, icon: str = "📋"):
        super().__init__()
        self.setObjectName("card")
        self.setMinimumHeight(120)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 14, 16, 14)

        # Header
        header = QHBoxLayout()
        title_lbl = QLabel(f"{icon}  {title}")
        title_lbl.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
        )

        self.badge_lbl = QLabel("")
        self.badge_lbl.setStyleSheet(
            "background-color: #064E3B; color: #34D399; border: 1px solid #059669;"
            "border-radius: 10px; padding: 2px 10px; font-size: 12px; font-weight: 700;"
        )

        header.addWidget(title_lbl)
        header.addStretch()
        header.addWidget(self.badge_lbl)
        layout.addLayout(header)

        # Main value
        self.main_value = QLabel("—")
        self.main_value.setStyleSheet(
            "color: #42A5F5; font-size: 22px; font-weight: 800; font-family: 'Consolas';"
        )
        layout.addWidget(self.main_value)

        # Source line
        self.source_lbl = QLabel("")
        self.source_lbl.setStyleSheet("color: #4A6FA5; font-size: 10px;")
        self.source_lbl.setWordWrap(True)
        layout.addWidget(self.source_lbl)

        # Explanation label
        self.explanation_lbl = QLabel("")
        self.explanation_lbl.setStyleSheet("color: #90CAF9; font-size: 11px;")
        self.explanation_lbl.setWordWrap(True)
        layout.addWidget(self.explanation_lbl)

    def set_data(
        self,
        value: str,
        badge_text: str = "",
        badge_color: str = "#10B981",
        source: str = "",
        explanation: str = "",
    ):
        self.main_value.setText(value)
        if badge_text:
            self.badge_lbl.setText(badge_text)
            bg = self._badge_bg(badge_color)
            self.badge_lbl.setStyleSheet(
                f"background-color: {bg}; color: {badge_color}; "
                "border-radius: 10px; padding: 2px 10px; "
                "font-size: 12px; font-weight: 700;"
            )
        self.source_lbl.setText(f"🔗  {source}" if source else "")
        self.explanation_lbl.setText(explanation)

    @staticmethod
    def _badge_bg(color: str) -> str:
        mapping = {
            "#10B981": "#064E3B",
            "#F59E0B": "#451A03",
            "#EF4444": "#450A0A",
            "#42A5F5": "#0D2147",
        }
        return mapping.get(color, "#0D2147")


# ─────────────────────────────────────────────
# Shipment View Page
# ─────────────────────────────────────────────
class ShipmentViewPage(QWidget):
    """Full invoice detail page."""

    navigate_back = Signal()
    shipment_updated = Signal()

    def __init__(self):
        super().__init__()
        self._current_shipment: dict | None = None
        self._setup_ui()

    def _setup_ui(self):
        # Outer scroll area
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: #0A1628; border: none; }")

        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #0A1628;")
        self._content_layout = QVBoxLayout(content_widget)
        self._content_layout.setSpacing(20)
        self._content_layout.setContentsMargins(28, 24, 28, 24)

        scroll.setWidget(content_widget)
        outer.addWidget(scroll)

        self._build_content()

    def _build_content(self):
        layout = self._content_layout

        # ── Header Bar ─────────────────────────────────
        header = QHBoxLayout()

        back_btn = QPushButton("← Back")
        back_btn.setObjectName("btn_secondary")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setMaximumWidth(100)
        back_btn.clicked.connect(self.navigate_back.emit)

        self.page_title = QLabel("📋  Invoice Analysis")
        self.page_title.setObjectName("page_title")
        self.page_title.setStyleSheet("color: #FFFFFF; font-size: 20px; font-weight: 800;")

        self.status_badge = QLabel("Pending Review")
        self.status_badge.setObjectName("badge_pending")
        self.status_badge.setMaximumWidth(140)
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setMinimumHeight(28)

        header.addWidget(back_btn)
        header.addSpacing(16)
        header.addWidget(self.page_title)
        header.addStretch()
        header.addWidget(self.status_badge)
        layout.addLayout(header)

        # ── Shipment Info Grid ─────────────────────────
        info_card = QFrame()
        info_card.setObjectName("card")
        info_grid = QGridLayout(info_card)
        info_grid.setSpacing(20)
        info_grid.setContentsMargins(20, 16, 20, 16)

        self.f_part_number = InfoField("Part Number")
        self.f_description = InfoField("Product Description")
        self.f_origin = InfoField("Country of Origin")
        self.f_declared_value = InfoField("Declared Value")
        self.f_shipment_id = InfoField("Shipment ID", mono=True)
        self.f_created = InfoField("Created At")

        info_grid.addWidget(self.f_shipment_id, 0, 0)
        info_grid.addWidget(self.f_part_number, 0, 1)
        info_grid.addWidget(self.f_created, 0, 2)
        info_grid.addWidget(self.f_description, 1, 0, 1, 2)
        info_grid.addWidget(self.f_origin, 1, 2)
        info_grid.addWidget(self.f_declared_value, 2, 0)

        layout.addWidget(info_card)

        # ── AI Results Section ─────────────────────────
        results_label = QLabel("AI CLASSIFICATION RESULTS")
        results_label.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        layout.addWidget(results_label)

        results_row = QHBoxLayout()
        results_row.setSpacing(16)

        self.hs_card = ResultCard("HS CODE CLASSIFICATION", "🏷️")
        self.tariff_card = ResultCard("TARIFF RATE", "📊")
        self.confidence_card = ResultCard("AI CONFIDENCE SCORE", "🎯")

        results_row.addWidget(self.hs_card)
        results_row.addWidget(self.tariff_card)
        results_row.addWidget(self.confidence_card)
        layout.addLayout(results_row)

        # ── Reasoning Trace ────────────────────────────
        reasoning_label = QLabel("AI REASONING TRACE (EXPLAINABLE AI)")
        reasoning_label.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        layout.addWidget(reasoning_label)

        self.reasoning_frame = QFrame()
        self.reasoning_frame.setObjectName("card")
        self._reasoning_layout = QVBoxLayout(self.reasoning_frame)
        self._reasoning_layout.setSpacing(8)
        self._reasoning_layout.setContentsMargins(16, 14, 16, 14)
        layout.addWidget(self.reasoning_frame)

        # ── Calculation Steps ──────────────────────────
        calc_label = QLabel("DUTY CALCULATION STEPS")
        calc_label.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        layout.addWidget(calc_label)

        self.calc_card = QFrame()
        self.calc_card.setObjectName("card")
        calc_card_layout = QVBoxLayout(self.calc_card)
        calc_card_layout.setContentsMargins(16, 14, 16, 14)

        self.calc_text = QTextEdit()
        self.calc_text.setReadOnly(True)
        self.calc_text.setMaximumHeight(180)
        self.calc_text.setStyleSheet(
            "QTextEdit { background-color: #071020; color: #A5F3FC; "
            "font-family: 'Consolas', 'Courier New', monospace; font-size: 13px; "
            "border: 1px solid #1565C0; border-radius: 6px; padding: 10px; }"
        )
        calc_card_layout.addWidget(self.calc_text)

        # Final Value
        self.final_value_label = QLabel("Final Landed Cost: —")
        self.final_value_label.setStyleSheet(
            "color: #42A5F5; font-size: 18px; font-weight: 800; "
            "padding: 10px 0; letter-spacing: 0.5px;"
        )
        calc_card_layout.addWidget(self.final_value_label)
        layout.addWidget(self.calc_card)

        # ── Action Buttons ─────────────────────────────
        action_label = QLabel("HUMAN REVIEW ACTIONS")
        action_label.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        layout.addWidget(action_label)

        actions_frame = QFrame()
        actions_frame.setObjectName("card")
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(20, 16, 20, 16)
        actions_layout.setSpacing(16)

        self.approve_btn = QPushButton("✅  APPROVE")
        self.approve_btn.setObjectName("btn_success")
        self.approve_btn.setCursor(Qt.PointingHandCursor)
        self.approve_btn.setMinimumHeight(44)
        self.approve_btn.setMinimumWidth(160)
        self.approve_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.approve_btn.clicked.connect(self._approve)

        self.disapprove_btn = QPushButton("❌  DISAPPROVE")
        self.disapprove_btn.setObjectName("btn_danger")
        self.disapprove_btn.setCursor(Qt.PointingHandCursor)
        self.disapprove_btn.setMinimumHeight(44)
        self.disapprove_btn.setMinimumWidth(160)
        self.disapprove_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.disapprove_btn.clicked.connect(self._disapprove)

        export_btn = QPushButton("📄  Export This Record")
        export_btn.setObjectName("btn_secondary")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setMinimumHeight(44)
        export_btn.clicked.connect(self._export_single)

        actions_layout.addWidget(self.approve_btn)
        actions_layout.addWidget(self.disapprove_btn)
        actions_layout.addStretch()
        actions_layout.addWidget(export_btn)
        layout.addWidget(actions_frame)

        layout.addStretch()

    # ── Data Loading ──────────────────────────────────────
    def load_shipment(self, shipment: dict):
        """Populate page with shipment data."""
        self._current_shipment = shipment

        # Info fields
        self.f_shipment_id.set_value(shipment.get("shipment_id", ""))
        self.f_part_number.set_value(shipment.get("part_number", "") or "N/A")
        self.f_description.set_value(shipment.get("product_description", ""))
        self.f_origin.set_value(shipment.get("country_of_origin", ""))
        self.f_declared_value.set_value(
            f"USD {shipment.get('declared_value', 0):,.2f}"
        )
        self.f_created.set_value(
            shipment.get("created_at", "")[:19].replace("T", " ")
        )

        # Status badge
        status = shipment.get("status", "Pending Review")
        self._set_status_badge(status)

        # HS Code card
        confidence = shipment.get("confidence_score", 0)
        badge_text, badge_color = self._confidence_badge(confidence)
        self.hs_card.set_data(
            value=shipment.get("suggested_hs_code", "—"),
            badge_text=badge_text,
            badge_color=badge_color,
            source=f"hts.usitc.gov",
            explanation="RAG retrieval + Gemini AI classification",
        )

        # Tariff card
        tariff = shipment.get("tariff_percent", 0)
        self.tariff_card.set_data(
            value=f"{tariff:.2f}%",
            badge_text="MFN / FTA" if tariff == 0 else f"{tariff}%",
            badge_color="#10B981" if tariff == 0 else "#F59E0B",
            source="ustr.gov / hts.usitc.gov",
            explanation="Retrieved from tariff knowledge base",
        )

        # Confidence card
        self.confidence_card.set_data(
            value=f"{confidence:.0f}%",
            badge_text="HIGH" if confidence >= 90 else ("MED" if confidence >= 70 else "LOW"),
            badge_color="#10B981" if confidence >= 90 else (
                "#F59E0B" if confidence >= 70 else "#EF4444"
            ),
            explanation=(
                "Auto-routed to Approved Queue"
                if confidence >= 90
                else "Requires human review"
            ),
        )

        # Reasoning trace
        self._populate_reasoning(shipment.get("reasoning_trace", []))

        # Calculation steps
        from services.duty_calculator import format_duty_breakdown, calculate_landed_cost
        duty = shipment.get("estimated_duty", 0)
        value = shipment.get("declared_value", 0)
        steps = format_duty_breakdown(value, tariff, duty)
        self.calc_text.setText("\n".join(steps))

        landed = calculate_landed_cost(value, duty)
        self.final_value_label.setText(
            f"💰  Total Landed Cost: USD {landed:,.2f}  "
            f"(Duty: USD {duty:,.2f})"
        )

        # Disable buttons based on current status
        already_reviewed = status in ("Approved", "Rejected")
        self.approve_btn.setEnabled(not (status == "Approved"))
        self.disapprove_btn.setEnabled(not (status == "Rejected"))

    def _populate_reasoning(self, trace: list):
        """Build reasoning trace step items."""
        # Clear existing
        while self._reasoning_layout.count():
            item = self._reasoning_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not trace:
            lbl = QLabel("No reasoning trace available.")
            lbl.setStyleSheet("color: #4A6FA5; font-size: 12px;")
            self._reasoning_layout.addWidget(lbl)
            return

        icons = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        for i, step in enumerate(trace):
            step_frame = QFrame()
            step_frame.setStyleSheet(
                "QFrame { background-color: #0A1A35; border-radius: 6px; "
                "border-left: 3px solid #1565C0; padding: 2px; }"
            )
            step_layout = QHBoxLayout(step_frame)
            step_layout.setContentsMargins(12, 8, 12, 8)

            icon_lbl = QLabel(icons[i] if i < len(icons) else "▶")
            icon_lbl.setStyleSheet("font-size: 14px; min-width: 26px;")

            step_lbl = QLabel(str(step))
            step_lbl.setStyleSheet("color: #CBD5E1; font-size: 12px; line-height: 1.5;")
            step_lbl.setWordWrap(True)

            step_layout.addWidget(icon_lbl)
            step_layout.addWidget(step_lbl, stretch=1)
            self._reasoning_layout.addWidget(step_frame)

    def _set_status_badge(self, status: str):
        colors = {
            "Approved": ("badge_approved", "#10B981"),
            "Pending Review": ("badge_pending", "#F59E0B"),
            "Rejected": ("badge_rejected", "#EF4444"),
        }
        obj_name, color = colors.get(status, ("badge_pending", "#F59E0B"))
        self.status_badge.setObjectName(obj_name)
        self.status_badge.setText(status)
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    @staticmethod
    def _confidence_badge(confidence: float) -> tuple[str, str]:
        if confidence >= 90:
            return f"{confidence:.0f}% HIGH", "#10B981"
        elif confidence >= 75:
            return f"{confidence:.0f}% MED", "#F59E0B"
        else:
            return f"{confidence:.0f}% LOW", "#EF4444"

    # ── Actions ───────────────────────────────────────────
    def _approve(self):
        if not self._current_shipment:
            return
        from database.db import update_shipment_status, insert_audit_log

        sid = self._current_shipment["shipment_id"]
        update_shipment_status(sid, "Approved", reviewer_name="Human Reviewer")
        insert_audit_log(
            shipment_id=sid,
            action="HUMAN_APPROVED",
            ai_recommendation=f"HS:{self._current_shipment.get('suggested_hs_code')}",
            human_decision="Approved",
            reviewer_name="Human Reviewer",
        )
        self._current_shipment["status"] = "Approved"
        self._set_status_badge("Approved")
        self.approve_btn.setEnabled(False)
        self.shipment_updated.emit()
        QMessageBox.information(self, "Approved", "✅ Shipment has been APPROVED.")

    def _disapprove(self):
        if not self._current_shipment:
            return
        from ui.review_dialog import ReviewDialog
        dialog = ReviewDialog(self._current_shipment, self)
        if dialog.exec():
            self._current_shipment["status"] = "Rejected"
            self._set_status_badge("Rejected")
            self.disapprove_btn.setEnabled(False)
            self.shipment_updated.emit()

    def _export_single(self):
        if not self._current_shipment:
            return
        try:
            from services.export_excel import export_to_excel
            from PySide6.QtWidgets import QFileDialog
            save_path, _ = QFileDialog.getSaveFileName(
                self, "Export Shipment", f"Shipment_{self._current_shipment['shipment_id']}.xlsx",
                "Excel Files (*.xlsx)"
            )
            if save_path:
                path = export_to_excel([self._current_shipment], save_path)
                QMessageBox.information(self, "Exported", f"✅ Exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
