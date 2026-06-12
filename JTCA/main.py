"""
============================================================
JTCA - Jabil TradeAI Compliance Assistant
Main Application Entry Point

Usage:
    python main.py

Environment:
    Copy .env.example to .env and set your GEMINI_API_KEY

Requirements:
    pip install -r requirements.txt
============================================================
"""

import sys
import os
import logging
from pathlib import Path

# ─────────────────────────────────────────────
# Setup: ensure JTCA root is on sys.path
# ─────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

# ─────────────────────────────────────────────
# Load Environment Variables (.env file)
# ─────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

# ─────────────────────────────────────────────
# Configure Logging
# ─────────────────────────────────────────────
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("JTCA")

# ─────────────────────────────────────────────
# PySide6 DPI and platform settings
# ─────────────────────────────────────────────
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

# ─────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────
from PySide6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PySide6.QtCore import Qt, QTimer, QThread, Signal as QtSignal
from PySide6.QtGui import QFont, QPixmap, QColor, QPainter

from ui.main_window import MainWindow, GLOBAL_STYLE
from ui.dashboard import DashboardPage
from ui.shipments_list import ShipmentsListPage
from ui.crawler_page import CrawlerPage
from ui.reports_page import ReportsPage
from ui.shipment_view import ShipmentViewPage


# ─────────────────────────────────────────────
# Splash Screen
# ─────────────────────────────────────────────
def create_splash_screen() -> QSplashScreen:
    """Create a branded splash screen."""
    pixmap = QPixmap(580, 320)
    pixmap.fill(QColor("#0A1628"))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Background gradient bar
    from PySide6.QtGui import QLinearGradient
    grad = QLinearGradient(0, 0, 580, 0)
    grad.setColorAt(0.0, QColor("#0057A8"))
    grad.setColorAt(1.0, QColor("#003580"))
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QBrush
    painter.fillRect(0, 0, 580, 8, QBrush(grad))

    # JABIL title
    painter.setPen(QColor("#FFFFFF"))
    font = QFont("Segoe UI", 42, QFont.Bold)
    font.setLetterSpacing(QFont.AbsoluteSpacing, 8)
    painter.setFont(font)
    painter.drawText(QRectF(0, 50, 580, 80), Qt.AlignHCenter, "JABIL")

    # Subtitle
    painter.setPen(QColor("#42A5F5"))
    font2 = QFont("Segoe UI", 14, QFont.Normal)
    painter.setFont(font2)
    painter.drawText(QRectF(0, 115, 580, 40), Qt.AlignHCenter, "TradeAI Compliance Assistant")

    # Version
    painter.setPen(QColor("#4A6FA5"))
    font3 = QFont("Segoe UI", 10)
    painter.setFont(font3)
    painter.drawText(QRectF(0, 160, 580, 30), Qt.AlignHCenter, "Version 1.0.0  |  POC — Jabil IT ECP Bootcamp 3.0")

    # Loading text
    painter.setPen(QColor("#90CAF9"))
    font4 = QFont("Segoe UI", 11)
    painter.setFont(font4)
    painter.drawText(QRectF(0, 230, 580, 30), Qt.AlignHCenter, "Initializing AI systems...")

    # Bottom bar
    painter.fillRect(0, 312, 580, 8, QBrush(grad))

    painter.end()

    splash = QSplashScreen(pixmap)
    splash.setWindowFlags(Qt.SplashScreen | Qt.WindowStaysOnTopHint)
    return splash


# ─────────────────────────────────────────────
# Background RAG Indexing Worker
# ─────────────────────────────────────────────

class RagIndexWorker(QThread):
    """Downloads SentenceTransformer model and indexes ChromaDB in background."""

    status_update = QtSignal(str)
    finished = QtSignal(bool, str)  # (success, message)

    def run(self):
        try:
            from rag.embeddings import HAS_SENTENCE_TRANSFORMERS
            from rag.vector_store import HAS_CHROMADB, get_vector_count, upsert_tariff_rules
            from database.db import get_all_tariff_rules

            if not HAS_SENTENCE_TRANSFORMERS or not HAS_CHROMADB:
                missing = []
                if not HAS_SENTENCE_TRANSFORMERS:
                    missing.append("sentence-transformers")
                if not HAS_CHROMADB:
                    missing.append("chromadb")
                msg = f"RAG offline (missing: {', '.join(missing)})"
                self.status_update.emit(msg)
                self.finished.emit(False, msg)
                return

            self.status_update.emit("Connecting to vector store...")
            count = get_vector_count()

            if count == 0:
                self.status_update.emit("Downloading AI embedding model (first run)...")
                rules = get_all_tariff_rules()
                if rules:
                    self.status_update.emit(f"Indexing {len(rules)} tariff rules...")
                    upsert_tariff_rules(rules)
                    self.finished.emit(True, f"RAG ready: {len(rules)} rules indexed.")
                else:
                    self.finished.emit(True, "RAG ready (no rules to index).")
            else:
                self.finished.emit(True, f"RAG ready: {count} rules in vector store.")
        except Exception as e:
            logger.warning(f"RAG background init failed: {e}")
            self.finished.emit(False, f"RAG unavailable: {e}")


# ─────────────────────────────────────────────
# Database Initialization (fast — no model download)
# ─────────────────────────────────────────────
def initialize_db_only(splash: QSplashScreen | None = None):
    """Initialize only the SQLite database (fast, no ML models)."""

    def update(msg: str):
        logger.info(msg)
        if splash:
            splash.showMessage(
                f"  {msg}",
                Qt.AlignBottom | Qt.AlignLeft,
                QColor("#42A5F5"),
            )
            QApplication.processEvents()

    update("Initializing database...")
    from database.db import initialize_db
    initialize_db()
    update("Database ready. Loading UI...")


# ─────────────────────────────────────────────
# Main Application
# ─────────────────────────────────────────────
def main():
    logger.info("=" * 60)
    logger.info("JTCA - Jabil TradeAI Compliance Assistant")
    logger.info("Starting application...")
    logger.info("=" * 60)

    app = QApplication(sys.argv)
    app.setApplicationName("JTCA")
    app.setApplicationDisplayName("Jabil TradeAI Compliance Assistant")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Jabil")

    # Apply global stylesheet
    app.setStyleSheet(GLOBAL_STYLE)

    # Default font
    default_font = QFont("Segoe UI", 10)
    app.setFont(default_font)

    # Splash screen
    splash = create_splash_screen()
    splash.show()
    QApplication.processEvents()

    # Initialize DB only (fast — no ML model download)
    try:
        initialize_db_only(splash)
    except Exception as e:
        logger.error(f"Initialization error: {e}", exc_info=True)
        splash.hide()
        QMessageBox.critical(
            None, "Initialization Error",
            f"JTCA failed to start:\n\n{e}\n\n"
            "Please check your requirements are installed:\n"
            "  pip install -r requirements.txt"
        )
        sys.exit(1)

    # ── Build Main Window ──────────────────────
    window = MainWindow()

    # ── Pages ──────────────────────────────────
    dashboard = DashboardPage()
    shipments_list = ShipmentsListPage()
    crawler = CrawlerPage()
    reports = ReportsPage()
    shipment_view = ShipmentViewPage()

    # Add pages to stack (matches sidebar nav order)
    window.add_page(dashboard)       # Index 0: Dashboard
    window.add_page(shipments_list)  # Index 1: Shipments
    window.add_page(crawler)         # Index 2: Crawler
    window.add_page(reports)         # Index 3: Reports
    window.add_page(shipment_view)   # Index 4: Shipment Detail (hidden from nav)

    # ── Navigation Wiring ──────────────────────
    def open_shipment(shipment_data: dict):
        """Navigate to shipment detail view."""
        shipment_view.load_shipment(shipment_data)
        window.navigate_to(4)

    def back_from_shipment():
        """Return to previous page (shipments list or dashboard)."""
        window.navigate_to(1)
        shipments_list.refresh_data()
        dashboard.refresh_data()

    def on_shipment_updated():
        """Refresh lists after review action."""
        shipments_list.refresh_data()
        dashboard.refresh_data()

    # Connect signals
    dashboard.shipment_selected.connect(open_shipment)
    shipments_list.shipment_selected.connect(open_shipment)
    shipment_view.navigate_back.connect(back_from_shipment)
    shipment_view.shipment_updated.connect(on_shipment_updated)

    # ── Background RAG Initialization ──────────
    # Runs after window is visible so UI is never blocked
    _rag_worker = RagIndexWorker()

    def _on_rag_status(msg: str):
        logger.info(f"[RAG] {msg}")

    def _on_rag_done(success: bool, msg: str):
        logger.info(f"[RAG] {msg}")
        # Refresh crawler page count
        try:
            crawler._load_tariff_table()
        except Exception:
            pass

    _rag_worker.status_update.connect(_on_rag_status)
    _rag_worker.finished.connect(_on_rag_done)

    # ── Show Window ─────────────────────────────
    def _show_and_start_rag():
        splash.close()
        window.show()
        logger.info("Application UI launched.")
        # Start RAG in background AFTER window is visible
        _rag_worker.start()

    QTimer.singleShot(2000, _show_and_start_rag)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
