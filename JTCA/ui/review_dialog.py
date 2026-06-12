"""
============================================================
JTCA - Review Dialog (Disapprove/Edit)
Human override: edit HS Code, Tariff %, Tax
Add reviewer notes, confirm or back
============================================================
"""

import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QFrame, QFormLayout, QMessageBox,
    QDoubleSpinBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)


class ReviewDialog(QDialog):
    """
    Disapprove / Edit dialog for human review.
    Allows reviewer to modify HS Code, Tariff %, add notes,
    then confirm or go back. Saves to audit_log on confirm.
    """

    def __init__(self, shipment: dict, parent=None):
        super().__init__(parent)
        self._shipment = shipment
        self.setWindowTitle("Human Review — Override Classification")
        self.setMinimumWidth(540)
        self.setMinimumHeight(560)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background-color: #0D1F3C;
            }
            QWidget {
                background-color: transparent;
                color: #E2E8F0;
            }
            QLabel {
                color: #E2E8F0;
            }
        """)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(28, 24, 28, 24)

        # ── Header ─────────────────────────────────────
        header_frame = QFrame()
        header_frame.setStyleSheet(
            "QFrame { background-color: #0057A8; border-radius: 10px; padding: 12px; }"
        )
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 12, 16, 12)

        title = QLabel("🔍  HUMAN REVIEW — OVERRIDE")
        title.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: 800; letter-spacing: 1px;")

        subtitle = QLabel(
            f"Shipment: {self._shipment.get('shipment_id', '')[-16:]}\n"
            f"Product: {self._shipment.get('product_description', '')[:60]}"
        )
        subtitle.setStyleSheet("color: #90CAF9; font-size: 11px;")
        subtitle.setWordWrap(True)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header_frame)

        # ── Current AI Values (read-only) ───────────────
        current_frame = QFrame()
        current_frame.setObjectName("card")
        current_layout = QVBoxLayout(current_frame)
        current_layout.setContentsMargins(16, 12, 16, 12)
        current_layout.setSpacing(6)

        curr_title = QLabel("CURRENT AI RECOMMENDATION")
        curr_title.setStyleSheet(
            "color: #90CAF9; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;"
        )
        current_layout.addWidget(curr_title)

        curr_row = QHBoxLayout()
        for label, key, fmt in [
            ("HS Code", "suggested_hs_code", "{}"),
            ("Tariff", "tariff_percent", "{:.2f}%"),
            ("Duty Est.", "estimated_duty", "USD {:.2f}"),
        ]:
            col = QVBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #4A6FA5; font-size: 10px;")
            val = QLabel(fmt.format(self._shipment.get(key, 0)))
            val.setStyleSheet("color: #42A5F5; font-size: 14px; font-weight: 700;")
            col.addWidget(lbl)
            col.addWidget(val)
            curr_row.addLayout(col)

        current_layout.addLayout(curr_row)
        layout.addWidget(current_frame)

        # ── Override Fields ─────────────────────────────
        override_frame = QFrame()
        override_frame.setObjectName("card")
        override_layout = QVBoxLayout(override_frame)
        override_layout.setContentsMargins(16, 12, 16, 12)
        override_layout.setSpacing(12)

        override_title = QLabel("OVERRIDE VALUES")
        override_title.setStyleSheet(
            "color: #90CAF9; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;"
        )
        override_layout.addWidget(override_title)

        # HS Code
        hs_lbl = QLabel("HS CODE")
        hs_lbl.setStyleSheet(
            "color: #90CAF9; font-size: 10px; font-weight: 700; letter-spacing: 1px;"
        )
        self.hs_input = QLineEdit()
        self.hs_input.setText(self._shipment.get("suggested_hs_code", ""))
        self.hs_input.setPlaceholderText("e.g. 847130")
        self.hs_input.setMinimumHeight(38)
        override_layout.addWidget(hs_lbl)
        override_layout.addWidget(self.hs_input)

        # Tariff %
        tariff_lbl = QLabel("TARIFF RATE (%)")
        tariff_lbl.setStyleSheet(
            "color: #90CAF9; font-size: 10px; font-weight: 700; letter-spacing: 1px;"
        )
        self.tariff_input = QDoubleSpinBox()
        self.tariff_input.setRange(0.0, 100.0)
        self.tariff_input.setDecimals(2)
        self.tariff_input.setSuffix("  %")
        self.tariff_input.setValue(self._shipment.get("tariff_percent", 0.0))
        self.tariff_input.setMinimumHeight(38)
        self.tariff_input.setStyleSheet(
            "QDoubleSpinBox { background-color: #0D2147; border: 1px solid #1565C0; "
            "border-radius: 6px; padding: 6px 12px; color: #E2E8F0; font-size: 13px; }"
        )
        override_layout.addWidget(tariff_lbl)
        override_layout.addWidget(self.tariff_input)

        # Tax override field (additional)
        tax_lbl = QLabel("ADDITIONAL TAX / CUSTOMS CODE")
        tax_lbl.setStyleSheet(
            "color: #90CAF9; font-size: 10px; font-weight: 700; letter-spacing: 1px;"
        )
        self.tax_input = QLineEdit()
        self.tax_input.setPlaceholderText("e.g. ZDUT / VAT / AD-CVD")
        self.tax_input.setMinimumHeight(38)
        override_layout.addWidget(tax_lbl)
        override_layout.addWidget(self.tax_input)

        layout.addWidget(override_frame)

        # ── Reviewer Name ───────────────────────────────
        reviewer_lbl = QLabel("REVIEWER NAME")
        reviewer_lbl.setStyleSheet(
            "color: #90CAF9; font-size: 10px; font-weight: 700; letter-spacing: 1px;"
        )
        self.reviewer_input = QLineEdit()
        self.reviewer_input.setPlaceholderText("Enter your name")
        self.reviewer_input.setMinimumHeight(38)
        layout.addWidget(reviewer_lbl)
        layout.addWidget(self.reviewer_input)

        # ── Feedback / Notes ────────────────────────────
        feedback_lbl = QLabel("FEEDBACK / REVIEW NOTES")
        feedback_lbl.setStyleSheet(
            "color: #90CAF9; font-size: 10px; font-weight: 700; letter-spacing: 1px;"
        )
        self.feedback_input = QTextEdit()
        self.feedback_input.setPlaceholderText(
            "Enter reason for disapproval or override notes...\n"
            "e.g. HS Code corrected based on product spec sheet. "
            "Tariff rate updated per 2024 US HTS Schedule."
        )
        self.feedback_input.setMinimumHeight(90)
        self.feedback_input.setMaximumHeight(120)
        layout.addWidget(feedback_lbl)
        layout.addWidget(self.feedback_input)

        # ── Action Buttons ──────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.confirm_btn = QPushButton("✅  CONFIRM OVERRIDE")
        self.confirm_btn.setObjectName("btn_primary")
        self.confirm_btn.setCursor(Qt.PointingHandCursor)
        self.confirm_btn.setMinimumHeight(44)
        self.confirm_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.confirm_btn.clicked.connect(self._confirm)

        back_btn = QPushButton("← BACK")
        back_btn.setObjectName("btn_secondary")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setMinimumHeight(44)
        back_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.confirm_btn)
        btn_layout.addWidget(back_btn)
        layout.addLayout(btn_layout)

    def _confirm(self):
        """Save override data to DB and close dialog."""
        new_hs = self.hs_input.text().strip()
        new_tariff = self.tariff_input.value()
        reviewer = self.reviewer_input.text().strip() or "Anonymous"
        notes = self.feedback_input.toPlainText().strip()
        tax_code = self.tax_input.text().strip()

        if not new_hs:
            QMessageBox.warning(self, "Validation", "Please enter a corrected HS Code.")
            return

        try:
            from database.db import update_shipment_status, insert_audit_log
            from services.duty_calculator import calculate_duty

            sid = self._shipment["shipment_id"]
            declared_value = self._shipment.get("declared_value", 0.0)
            new_duty = calculate_duty(declared_value, new_tariff)

            # Combine notes with tax code
            full_notes = notes
            if tax_code:
                full_notes = f"Tax Code: {tax_code}\n{notes}"

            update_shipment_status(
                shipment_id=sid,
                status="Rejected",
                reviewer_name=reviewer,
                review_notes=full_notes,
                hs_code=new_hs,
                tariff_percent=new_tariff,
            )

            insert_audit_log(
                shipment_id=sid,
                action="HUMAN_REJECTED_OVERRIDE",
                ai_recommendation=(
                    f"HS:{self._shipment.get('suggested_hs_code')} "
                    f"Tariff:{self._shipment.get('tariff_percent')}%"
                ),
                human_decision=(
                    f"HS:{new_hs} Tariff:{new_tariff}% "
                    f"TaxCode:{tax_code}"
                ),
                reviewer_name=reviewer,
                notes=full_notes,
            )

            logger.info(f"Shipment {sid} rejected and overridden by {reviewer}")
            QMessageBox.information(
                self, "Override Saved",
                f"✅ Override confirmed!\n\n"
                f"HS Code: {new_hs}\n"
                f"Tariff: {new_tariff:.2f}%\n"
                f"Estimated Duty: USD {new_duty:,.2f}\n"
                f"Reviewer: {reviewer}"
            )
            self.accept()

        except Exception as e:
            logger.error(f"Override save error: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save override:\n{e}")
