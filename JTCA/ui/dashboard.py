"""
============================================================
JTCA - Dashboard Page
KPI cards, drag-and-drop PDF upload, shipment list table
============================================================
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QFileDialog, QMessageBox, QProgressDialog, QSizePolicy,
    QSpacerItem, QGridLayout,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QMimeData
from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent, QColor

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Stat Card Widget
# ─────────────────────────────────────────────
class StatCard(QFrame):
    """KPI statistics card."""

    def __init__(self, label: str, value: str, icon: str, color: str = "#42A5F5"):
        super().__init__()
        self.setObjectName("stat_card")
        self._color = color
        self.setMinimumWidth(160)
        self.setMinimumHeight(110)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(20, 16, 20, 16)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: 24px; color: {color};")
        icon_label.setAlignment(Qt.AlignLeft)

        self.value_label = QLabel(str(value))
        self.value_label.setObjectName("stat_value")
        self.value_label.setFont(QFont("Segoe UI", 28, QFont.Bold))
        self.value_label.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: 800;")

        self.label_lbl = QLabel(label)
        self.label_lbl.setObjectName("stat_label")
        self.label_lbl.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 600; text-transform: uppercase;"
        )

        layout.addWidget(icon_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.label_lbl)

    def update_value(self, new_val: str):
        self.value_label.setText(str(new_val))


# ─────────────────────────────────────────────
# PDF Drop Zone
# ─────────────────────────────────────────────
class DropZone(QFrame):
    """Drag-and-drop PDF upload zone."""

    file_dropped = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("drop_zone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(110)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)

        icon = QLabel("📄")
        icon.setStyleSheet("font-size: 28px;")
        icon.setAlignment(Qt.AlignCenter)

        self.text_label = QLabel("Drag & Drop Supplier PDF here")
        self.text_label.setStyleSheet(
            "color: #90CAF9; font-size: 13px; font-weight: 600;"
        )
        self.text_label.setAlignment(Qt.AlignCenter)

        hint = QLabel("or click to browse — PDF format only")
        hint.setStyleSheet("color: #4A6FA5; font-size: 11px;")
        hint.setAlignment(Qt.AlignCenter)

        layout.addWidget(icon)
        layout.addWidget(self.text_label)
        layout.addWidget(hint)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith(".pdf") for u in urls):
                event.acceptProposedAction()
                self.setStyleSheet(
                    "QFrame#drop_zone { border: 2px dashed #42A5F5; "
                    "background-color: #112244; border-radius: 12px; }"
                )
                self.text_label.setText("✅ Release to process PDF")
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._reset_style()

    def dropEvent(self, event: QDropEvent):
        self._reset_style()
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                self.file_dropped.emit(path)
                break

    def mousePressEvent(self, event):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Supplier PDF", "", "PDF Files (*.pdf)"
        )
        if path:
            self.file_dropped.emit(path)

    def _reset_style(self):
        self.setStyleSheet("")
        self.text_label.setText("Drag & Drop Supplier PDF here")


# ─────────────────────────────────────────────
# Processing Worker Thread
# ─────────────────────────────────────────────
class ProcessingWorker(QThread):
    """Background thread for PDF → OCR → RAG → Gemini pipeline."""

    progress = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, pdf_path: str):
        super().__init__()
        self.pdf_path = pdf_path

    def run(self):
        try:
            from ocr.pdf_extractor import extract_from_pdf
            from rag.retrieval import query_similar, format_context_for_llm
            from llm.gemini_service import get_tariff_recommendation
            from services.duty_calculator import calculate_duty
            from services.approval_engine import route_shipment
            from database.db import insert_shipment, insert_audit_log

            # Step 1: OCR
            self.progress.emit("📄 Extracting text from PDF...")
            ocr_data = extract_from_pdf(self.pdf_path)
            logger.info(f"OCR complete: {ocr_data}")

            if not ocr_data.get("product_description"):
                # Use filename as fallback description
                ocr_data["product_description"] = Path(self.pdf_path).stem.replace("_", " ")

            # Step 2: RAG
            self.progress.emit("🔍 Searching tariff knowledge base (RAG)...")
            try:
                retrieved = query_similar(
                    ocr_data["product_description"],
                    ocr_data.get("country_of_origin", ""),
                    top_k=5,
                )
                rag_context = format_context_for_llm(retrieved)
            except Exception as e:
                logger.warning(f"RAG unavailable: {e}")
                rag_context = "Vector store not initialized. Using Gemini knowledge only."

            # Step 3: Gemini
            self.progress.emit("🤖 Generating AI recommendation (Gemini)...")
            ai_result = get_tariff_recommendation(
                product_description=ocr_data["product_description"],
                part_number=ocr_data.get("part_number", ""),
                country_of_origin=ocr_data.get("country_of_origin", ""),
                declared_value=ocr_data.get("declared_value", 0.0),
                rag_context=rag_context,
            )

            # Step 4: Calculate Duty
            self.progress.emit("💰 Calculating estimated duty...")
            duty = calculate_duty(
                ocr_data.get("declared_value", 0.0),
                ai_result.get("suggested_tariff_percent", 0.0),
            )

            # Step 5: Route
            status = route_shipment(ai_result.get("confidence_score", 0))

            # Step 6: Persist
            self.progress.emit("💾 Saving to database...")
            import re
            
            # Determine shipment ID: check OCR or AI extraction first, fallback to generated
            shipment_id = ocr_data.get("shipment_id", "").strip() or ai_result.get("shipment_id", "").strip()
            if not shipment_id or not re.match(r"^[A-Z0-9\-_]+$", shipment_id):
                shipment_id = f"SHIP-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

            # Dynamically determine Target SAP System / Table based on HTS Code prefix (9025 Temperature sensors map to Table_ZLANDED_COST, others to Condition_Type_ZDUT)
            suggested_hs = ai_result.get("suggested_hs_code", "")
            target_sap = "Table_ZLANDED_COST" if suggested_hs.startswith("9025") else "Condition_Type_ZDUT"

            shipment_data = {
                "shipment_id": shipment_id,
                "part_number": ocr_data.get("part_number", "") or ai_result.get("manufacturing_part_number", ""),
                "product_description": ocr_data["product_description"],
                "country_of_origin": ocr_data.get("country_of_origin", "") or ai_result.get("country_of_origin", "Unknown"),
                "declared_value": ocr_data.get("declared_value", 0.0),
                "suggested_hs_code": suggested_hs,
                "tariff_percent": ai_result.get("suggested_tariff_percent", 0.0),
                "estimated_duty": duty,
                "confidence_score": ai_result.get("confidence_score", 0),
                "reasoning_trace": ai_result.get("reasoning_trace", []),
                "status": status,
                "source_pdf": str(self.pdf_path),
                "material_type": ocr_data.get("material_type", "") or ai_result.get("material_type", "ZROH"),
                "plant_code": ocr_data.get("plant_code", "") or ai_result.get("plant_code", "US02"),
                "supplier_name": ocr_data.get("supplier_name", "") or ai_result.get("supplier_name", "EMERSON"),
                "shipping_country": ocr_data.get("shipping_country", "") or ai_result.get("shipping_country", "Malaysia"),
                "wto_member_status": ocr_data.get("wto_member_status", "") or ai_result.get("wto_member_status", "Yes"),
                "fta_applicable": ai_result.get("fta_applicable", "") or ocr_data.get("fta_applicable", "No"),
                "target_sap_system": target_sap,
            }
            insert_shipment(shipment_data)

            # Audit log
            insert_audit_log(
                shipment_id=shipment_id,
                action="AI_PROCESSED",
                ai_recommendation=f"HS:{ai_result.get('suggested_hs_code')} Tariff:{ai_result.get('suggested_tariff_percent')}%",
                human_decision="",
                reviewer_name="System",
            )

            self.progress.emit(f"✅ Complete! Status: {status}")
            self.finished.emit(shipment_data)

        except Exception as e:
            logger.error(f"Processing error: {e}", exc_info=True)
            self.error.emit(str(e))


# ─────────────────────────────────────────────
# Dashboard Page
# ─────────────────────────────────────────────
class DashboardPage(QWidget):
    """Main dashboard with KPIs, drop zone, and shipment list."""

    shipment_selected = Signal(dict)
    navigate_to = Signal(int)

    def __init__(self):
        super().__init__()
        self._worker: ProcessingWorker | None = None
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(28, 24, 28, 24)

        # ── Header ─────────────────────────────────────
        header = QHBoxLayout()
        page_title = QLabel("🏠  Dashboard")
        page_title.setObjectName("page_title")
        page_title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        page_title.setStyleSheet("color: #FFFFFF; font-size: 20px; font-weight: 800;")

        refresh_btn = QPushButton("🔄  Refresh")
        refresh_btn.setObjectName("btn_secondary")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setMaximumWidth(120)
        refresh_btn.clicked.connect(self.refresh_data)

        export_btn = QPushButton("📊  Export Excel")
        export_btn.setObjectName("btn_primary")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setMaximumWidth(140)
        export_btn.clicked.connect(self._export_excel)

        header.addWidget(page_title)
        header.addStretch()
        header.addWidget(refresh_btn)
        header.addWidget(export_btn)
        layout.addLayout(header)

        # ── KPI Cards ──────────────────────────────────
        self.card_total = StatCard("Total Shipments", "0", "📦", "#42A5F5")
        self.card_approved = StatCard("Approved", "0", "✅", "#10B981")
        self.card_pending = StatCard("Pending Review", "0", "⏳", "#F59E0B")
        self.card_confidence = StatCard("Avg Confidence", "0%", "🎯", "#A78BFA")
        self.card_duties = StatCard("Total Duties (USD)", "$0", "💵", "#FB7185")

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)
        for card in [
            self.card_total, self.card_approved, self.card_pending,
            self.card_confidence, self.card_duties,
        ]:
            cards_layout.addWidget(card)
        layout.addLayout(cards_layout)

        # ── Drop Zone ──────────────────────────────────
        drop_section_label = QLabel("UPLOAD SUPPLIER INVOICE PDF")
        drop_section_label.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        layout.addWidget(drop_section_label)

        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self._process_pdf)
        layout.addWidget(self.drop_zone)

        # ── Processing Status Label ────────────────────
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            "color: #42A5F5; font-size: 12px; font-style: italic; padding: 4px;"
        )
        layout.addWidget(self.status_label)

        # ── Shipment List ──────────────────────────────
        list_header = QHBoxLayout()
        list_label = QLabel("RECENT SHIPMENTS")
        list_label.setStyleSheet(
            "color: #90CAF9; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        list_header.addWidget(list_label)
        list_header.addStretch()
        layout.addLayout(list_header)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "#", "Shipment ID", "Description", "Origin",
            "HS Code", "Confidence", "Status",
        ])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        self.table.setMinimumHeight(240)
        layout.addWidget(self.table)

        hint = QLabel("💡 Double-click a row to view shipment details and AI recommendations")
        hint.setStyleSheet("color: #4A6FA5; font-size: 11px; font-style: italic;")
        layout.addWidget(hint)

    # ── Data Methods ───────────────────────────────────────
    def refresh_data(self):
        """Reload stats and shipment list from DB."""
        try:
            from database.db import get_dashboard_stats, get_all_shipments
            stats = get_dashboard_stats()
            self.card_total.update_value(str(stats.get("total", 0)))
            self.card_approved.update_value(str(stats.get("approved", 0)))
            self.card_pending.update_value(str(stats.get("pending", 0)))
            self.card_confidence.update_value(f"{stats.get('avg_confidence', 0):.1f}%")
            self.card_duties.update_value(f"${stats.get('total_duties', 0):,.2f}")

            shipments = get_all_shipments()
            self._populate_table(shipments)
        except Exception as e:
            logger.error(f"Dashboard refresh error: {e}")

    def _populate_table(self, shipments: list[dict]):
        """Fill the table with shipment rows."""
        self.table.setRowCount(0)
        self._shipments = shipments

        for row_idx, s in enumerate(shipments):
            self.table.insertRow(row_idx)

            row_data = [
                str(row_idx + 1),
                s.get("shipment_id", "")[-12:],
                s.get("product_description", "")[:50],
                s.get("country_of_origin", ""),
                s.get("suggested_hs_code", ""),
                f"{s.get('confidence_score', 0):.0f}%",
                s.get("status", ""),
            ]

            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)

                # Color confidence column
                if col_idx == 5:
                    conf = s.get("confidence_score", 0)
                    if conf >= 90:
                        item.setForeground(QColor("#10B981"))
                    elif conf >= 75:
                        item.setForeground(QColor("#F59E0B"))
                    else:
                        item.setForeground(QColor("#EF4444"))

                # Color status column
                if col_idx == 6:
                    status = s.get("status", "")
                    color_map = {
                        "Approved": "#10B981",
                        "Pending Review": "#F59E0B",
                        "Rejected": "#EF4444",
                    }
                    item.setForeground(QColor(color_map.get(status, "#6B7280")))
                    font = QFont("Segoe UI", 10, QFont.Bold)
                    item.setFont(font)

                self.table.setItem(row_idx, col_idx, item)

            self.table.setRowHeight(row_idx, 44)

    def _on_row_double_clicked(self, index):
        row = index.row()
        if hasattr(self, "_shipments") and row < len(self._shipments):
            self.shipment_selected.emit(self._shipments[row])

    # ── PDF Processing ─────────────────────────────────────
    def _process_pdf(self, pdf_path: str):
        """Start the AI processing pipeline for a dropped PDF."""
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Busy", "A PDF is already being processed.")
            return

        self.status_label.setText(f"🔄 Processing: {Path(pdf_path).name}")
        self.drop_zone.setEnabled(False)

        self._worker = ProcessingWorker(pdf_path)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_processing_done)
        self._worker.error.connect(self._on_processing_error)
        self._worker.start()

    def _on_progress(self, msg: str):
        self.status_label.setText(msg)

    def _on_processing_done(self, shipment: dict):
        self.drop_zone.setEnabled(True)
        self.status_label.setStyleSheet("color: #10B981; font-size: 12px; padding: 4px;")
        self.status_label.setText(
            f"✅ Processed! Shipment ID: {shipment['shipment_id']} — "
            f"Status: {shipment['status']}"
        )
        self.refresh_data()
        QTimer.singleShot(5000, lambda: self.status_label.setText(""))

    def _on_processing_error(self, error: str):
        self.drop_zone.setEnabled(True)
        self.status_label.setStyleSheet("color: #EF4444; font-size: 12px; padding: 4px;")
        self.status_label.setText(f"❌ Error: {error}")
        QMessageBox.critical(self, "Processing Error", f"Failed to process PDF:\n\n{error}")

    def _export_excel(self):
        """Export all shipments to Excel."""
        try:
            from database.db import get_all_shipments
            from services.export_excel import export_to_excel

            shipments = get_all_shipments()
            if not shipments:
                QMessageBox.information(self, "No Data", "No shipments to export yet.")
                return

            save_path, _ = QFileDialog.getSaveFileName(
                self, "Save Excel Export", "SAP_Export.xlsx",
                "Excel Files (*.xlsx)"
            )
            if not save_path:
                return

            path = export_to_excel(shipments, save_path)
            QMessageBox.information(
                self, "Export Complete",
                f"✅ Excel file saved successfully!\n\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{e}")
