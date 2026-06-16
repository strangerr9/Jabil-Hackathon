"""
============================================================
JTCA - AI Compliance Assistant Page
Provides interactive natural language search for HS codes,
descriptions, and trade agreements using RAG and Gemini.
============================================================
"""

import logging
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QScrollArea, QSizePolicy, QSpacerItem,
    QProgressBar, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont, QTextDocument

from llm.gemini_service import ask_assistant_question

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Markdown to HTML converter helper
# ─────────────────────────────────────────────
def markdown_to_html(text: str) -> str:
    """Convert a subset of markdown syntax into clean HTML for QLabels."""
    # Escape HTML tags first to prevent syntax breakage
    html = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # Code blocks
    html = re.sub(
        r"```(?:[a-zA-Z0-9]+)?\n(.*?)\n```",
        r'<pre style="background-color: rgba(0,0,0,0.15); padding: 8px; border-radius: 4px; font-family: monospace;">\1</pre>',
        html,
        flags=re.DOTALL
    )
    
    # Inline code
    html = re.sub(
        r"`([^`]+)`",
        r'<code style="background-color: rgba(0,0,0,0.15); padding: 2px 4px; border-radius: 3px; font-family: monospace;">\1</code>',
        html
    )
    
    # Headers
    html = re.sub(r"^### (.*?)$", r"<h4><b>\1</b></h4>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.*?)$", r"<h3><b>\1</b></h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.*?)$", r"<h2><b>\1</b></h2>", html, flags=re.MULTILINE)
    
    # Bold / Strong
    html = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", html)
    
    # Bullet points
    html = re.sub(r"^\s*-\s+(.*?)$", r"&bull; \1", html, flags=re.MULTILINE)
    
    # Line breaks
    html = html.replace("\n", "<br>")
    
    return html


# ─────────────────────────────────────────────
# QThread Worker for Async Operations
# ─────────────────────────────────────────────
class AssistantQueryWorker(QThread):
    """Background worker that queries ChromaDB RAG and calls the Gemini Assistant service."""
    
    finished = Signal(str, list)  # (response_text, retrieved_rules)
    error = Signal(str)
    
    def __init__(self, query: str):
        super().__init__()
        self.query = query.strip()
        
    def run(self):
        try:
            if not self.query:
                self.finished.emit("Query is empty.", [])
                return
                
            from rag.retrieval import query_similar, format_context_for_llm
            # Step 1: Query ChromaDB vector store (RAG)
            # We fetch up to 5 matching rules to use as the context
            retrieved_rules = query_similar(product_description=self.query, top_k=5)
            
            # Step 2: Format context for the LLM
            rag_context = format_context_for_llm(retrieved_rules)
            
            # Step 3: Query Gemini assistant model
            response_text = ask_assistant_question(self.query, rag_context)
            
            self.finished.emit(response_text, retrieved_rules)
            
        except Exception as e:
            logger.error(f"Assistant background thread error: {e}", exc_info=True)
            self.error.emit(str(e))


# ─────────────────────────────────────────────
# Custom Chat Bubble Widget
# ─────────────────────────────────────────────
class ChatBubble(QFrame):
    """Custom speech bubble for user and assistant messages."""
    
    def __init__(self, text: str, is_user: bool, theme: str = "dark", parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.theme = theme
        
        self.init_ui(text)
        self.apply_theme_styling()
        
    def init_ui(self, text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        
        # Sender Header
        sender_lbl = QLabel("👤 You" if self.is_user else "🤖 JTCA Compliance Assistant")
        sender_lbl.setStyleSheet("font-weight: bold; font-size: 11px; color: #42A5F5;")
        layout.addWidget(sender_lbl)
        
        # Message Content
        self.content_lbl = QLabel()
        self.content_lbl.setWordWrap(True)
        self.content_lbl.setTextFormat(Qt.RichText)
        self.content_lbl.setText(markdown_to_html(text))
        self.content_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.content_lbl)
        
    def apply_theme_styling(self):
        # Set border radius and background colors
        if self.is_user:
            if self.theme == "light":
                # User bubble in Light Mode
                bg = "#EEF2F8"
                border = "1px solid #D0D9E8"
                color = "#0D1B2A"
            else:
                # User bubble in Dark Mode
                bg = "#1A2A40"
                border = "1px solid #1E3150"
                color = "#E8F0FE"
        else:
            if self.theme == "light":
                # Assistant bubble in Light Mode
                bg = "#FFFFFF"
                border = "1px solid #D0D9E8"
                color = "#0D1B2A"
            else:
                # Assistant bubble in Dark Mode
                bg = "#162236"
                border = "1px solid #1E3150"
                color = "#E8F0FE"
                
        self.setStyleSheet(f"""
            ChatBubble {{
                background-color: {bg};
                border: {border};
                border-radius: 8px;
            }}
            QLabel {{
                color: {color};
                border: none;
                background-color: transparent;
            }}
        """)


# ─────────────────────────────────────────────
# Custom RAG Reference Card Widget
# ─────────────────────────────────────────────
class ReferenceCard(QFrame):
    """Custom card displaying a single retrieved tariff rule."""
    
    def __init__(self, rule: dict, theme: str = "dark", parent=None):
        super().__init__(parent)
        self.theme = theme
        self.init_ui(rule)
        
    def init_ui(self, rule: dict):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        
        # Title Row: HS Code + Similarity
        title_layout = QHBoxLayout()
        
        hs_lbl = QLabel(f"HS Code: {rule.get('hs_code', '000000')}")
        hs_lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #42A5F5;")
        
        score = rule.get("similarity_score", 0.0)
        score_lbl = QLabel(f"Match: {score}%")
        score_lbl.setObjectName("result_badge")
        score_lbl.setProperty("status", "approved" if score >= 85 else ("pending" if score >= 60 else "rejected"))
        score_lbl.setToolTip("RAG Vector Space Similarity Match Score")
        
        title_layout.addWidget(hs_lbl)
        title_layout.addStretch()
        title_layout.addWidget(score_lbl)
        layout.addLayout(title_layout)
        
        # Description
        desc_lbl = QLabel(rule.get("product_description", "No description provided"))
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 12px; font-weight: 500;")
        layout.addWidget(desc_lbl)
        
        # Details Row: Origin -> Dest | FTA Rate
        details_layout = QHBoxLayout()
        origin = rule.get("origin_country", "Any")
        dest = rule.get("destination_country", "Malaysia")
        route_lbl = QLabel(f"📍 {origin} ➔ {dest}")
        route_lbl.setStyleSheet("font-size: 11px; color: #94A8C4;")
        
        fta_name = rule.get("fta_name", "None")
        tariff_pct = rule.get("tariff_percent", 0.0)
        tariff_lbl = QLabel(f"Rate: <b>{tariff_pct}%</b> ({fta_name})")
        tariff_lbl.setStyleSheet("font-size: 11px; color: #94A8C4;")
        
        details_layout.addWidget(route_lbl)
        details_layout.addStretch()
        details_layout.addWidget(tariff_lbl)
        layout.addLayout(details_layout)
        
        # Source link
        source = rule.get("regulation_source", "")
        if source:
            source_lbl = QLabel(f"Source: <a href='{source}' style='color: #42A5F5;'>{source.split('//')[-1].split('/')[0]}</a>")
            source_lbl.setOpenExternalLinks(True)
            source_lbl.setStyleSheet("font-size: 10px; color: #4E6480;")
            layout.addWidget(source_lbl)
            
        self.apply_theme_styling()
        
    def apply_theme_styling(self):
        if self.theme == "light":
            bg = "#FFFFFF"
            border = "1px solid #D0D9E8"
            text_color = "#0D1B2A"
        else:
            bg = "#1A2A40"
            border = "1px solid #1E3150"
            text_color = "#E8F0FE"
            
        self.setStyleSheet(f"""
            ReferenceCard {{
                background-color: {bg};
                border: {border};
                border-radius: 8px;
            }}
            QLabel {{
                color: {text_color};
                background-color: transparent;
            }}
        """)


# ─────────────────────────────────────────────
# Main Page Class
# ─────────────────────────────────────────────
class AiAssistantPage(QWidget):
    """Interactive AI Compliance Assistant view."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ai_assistant_page")
        self._current_theme = "dark"  # Default
        self._active_worker = None
        
        self.init_ui()
        
    def init_ui(self):
        # Master Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        
        # ─── HEADER ───
        header_frame = QFrame()
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        
        title_lbl = QLabel("🤖 AI Compliance Assistant")
        title_lbl.setObjectName("page_title")
        
        sub_lbl = QLabel("Search the knowledge base, verify HS codes, and determine applicable trade agreements (FTAs) using RAG and Gemini AI.")
        sub_lbl.setStyleSheet("font-size: 13px; color: #94A8C4;")
        
        header_layout.addWidget(title_lbl)
        header_layout.addWidget(sub_lbl)
        main_layout.addWidget(header_frame)
        
        # ─── SPLIT VIEW (Chat left, RAG context right) ───
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: rgba(255, 255, 255, 0.05);
                width: 4px;
            }
        """)
        
        # Left Panel (Chat Frame)
        chat_panel = QFrame()
        chat_layout = QVBoxLayout(chat_panel)
        chat_layout.setContentsMargins(0, 0, 8, 0)
        chat_layout.setSpacing(10)
        
        # 1. Quick suggestion chips row
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(8)
        chips_lbl = QLabel("Quick Queries:")
        chips_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #4E6480;")
        chips_layout.addWidget(chips_lbl)
        
        suggestions = [
            "PCB from China under Section 301",
            "Laptop computers under WTO ITA",
            "Processors imported from Malaysia",
            "Active FTAs for batteries",
        ]
        
        for text in suggestions:
            chip_btn = QPushButton(text)
            chip_btn.setObjectName("btn_outlined")
            chip_btn.setStyleSheet("""
                QPushButton {
                    font-size: 11px;
                    padding: 4px 10px;
                    border-radius: 10px;
                }
            """)
            chip_btn.setCursor(Qt.PointingHandCursor)
            chip_btn.clicked.connect(lambda checked, t=text: self._on_chip_clicked(t))
            chips_layout.addWidget(chip_btn)
        chips_layout.addStretch()
        chat_layout.addLayout(chips_layout)
        
        # 2. Chat history scroll area
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.chat_container = QWidget()
        self.chat_container_layout = QVBoxLayout(self.chat_container)
        self.chat_container_layout.setSpacing(12)
        self.chat_container_layout.setContentsMargins(4, 4, 4, 4)
        self.chat_container_layout.addStretch()
        self.chat_scroll.setWidget(self.chat_container)
        
        chat_layout.addWidget(self.chat_scroll, stretch=1)
        
        # 3. Processing / Loading Indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Infinite pulsing loading bar
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.hide()
        chat_layout.addWidget(self.progress_bar)
        
        # 4. Input Row
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)
        
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Ask the compliance assistant (e.g. 'What is the tariff on PCB from China to US?')")
        self.query_input.setMinimumHeight(42)
        self.query_input.returnPressed.connect(self._on_send_clicked)
        
        self.send_btn = QPushButton("🚀 Ask AI")
        self.send_btn.setObjectName("btn_primary")
        self.send_btn.setMinimumHeight(42)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self._on_send_clicked)
        
        self.clear_btn = QPushButton("🗑️ Clear")
        self.clear_btn.setObjectName("btn_secondary")
        self.clear_btn.setMinimumHeight(42)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_chat)
        
        input_layout.addWidget(self.query_input, stretch=1)
        input_layout.addWidget(self.send_btn)
        input_layout.addWidget(self.clear_btn)
        chat_layout.addLayout(input_layout)
        
        # Right Panel (RAG Reference Frame)
        ref_panel = QFrame()
        ref_panel.setObjectName("card")
        ref_panel.setMinimumWidth(320)
        ref_layout = QVBoxLayout(ref_panel)
        ref_layout.setContentsMargins(12, 12, 12, 12)
        ref_layout.setSpacing(10)
        
        ref_title = QLabel("🔍 Retrieved RAG References")
        ref_title.setObjectName("section_title")
        ref_layout.addWidget(ref_title)
        
        ref_desc = QLabel("The database records matching the semantics of your query will appear below for audits and source cross-checking.")
        ref_desc.setStyleSheet("font-size: 11px; color: #94A8C4;")
        ref_desc.setWordWrap(True)
        ref_layout.addWidget(ref_desc)
        
        self.ref_scroll = QScrollArea()
        self.ref_scroll.setWidgetResizable(True)
        self.ref_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ref_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.ref_container = QWidget()
        self.ref_container_layout = QVBoxLayout(self.ref_container)
        self.ref_container_layout.setSpacing(8)
        self.ref_container_layout.setContentsMargins(0, 0, 0, 0)
        self.ref_container_layout.addStretch()
        self.ref_scroll.setWidget(self.ref_container)
        
        ref_layout.addWidget(self.ref_scroll, stretch=1)
        
        # Add panes to splitter
        splitter.addWidget(chat_panel)
        splitter.addWidget(ref_panel)
        splitter.setSizes([750, 350])
        main_layout.addWidget(splitter, stretch=1)
        
        # Prepopulate with a friendly welcome message
        self.add_assistant_message(
            "Hello! I am your **AI Compliance Assistant**.\n\n"
            "I can help you search for **HS Codes**, verify **product descriptions**, and determine "
            "what **trade agreements (FTAs)** are active between regions.\n\n"
            "Ask me a question or choose one of the quick suggestions above to begin!"
        )
        
    # ─────────────────────────────────────────────
    # Business Logic / Handlers
    # ─────────────────────────────────────────────
    def _on_chip_clicked(self, text: str):
        self.query_input.setText(text)
        self._on_send_clicked()
        
    def _on_send_clicked(self):
        query = self.query_input.text().strip()
        if not query:
            return
            
        # Clear input line
        self.query_input.clear()
        
        # Disable controls during query execution
        self.query_input.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.progress_bar.show()
        
        # Add User message to chat list
        self.add_user_message(query)
        
        # Start background task thread
        self._active_worker = AssistantQueryWorker(query)
        self._active_worker.finished.connect(self._on_query_success)
        self._active_worker.error.connect(self._on_query_error)
        self._active_worker.start()
        
    def _on_query_success(self, response_text: str, retrieved_rules: list):
        # Enable controls
        self.query_input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.progress_bar.hide()
        self.query_input.setFocus()
        
        # Add Assistant response to chat
        self.add_assistant_message(response_text)
        
        # Load and render reference cards on right side
        self.update_reference_cards(retrieved_rules)
        
    def _on_query_error(self, error_message: str):
        # Enable controls
        self.query_input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.progress_bar.hide()
        
        # Add system warning response
        self.add_assistant_message(
            f"⚠️ **Error executing compliance query**:\n\n"
            f"*{error_message}*\n\n"
            f"Please verify your database connection or network settings."
        )
        
    def add_user_message(self, text: str):
        bubble = ChatBubble(text, is_user=True, theme=self._current_theme)
        # Add bubble before the spacer item (which is at count-1)
        count = self.chat_container_layout.count()
        self.chat_container_layout.insertWidget(count - 1, bubble)
        self.scroll_to_bottom()
        
    def add_assistant_message(self, text: str):
        bubble = ChatBubble(text, is_user=False, theme=self._current_theme)
        # Add bubble before the spacer
        count = self.chat_container_layout.count()
        self.chat_container_layout.insertWidget(count - 1, bubble)
        self.scroll_to_bottom()
        
    def update_reference_cards(self, rules: list):
        # Clear old reference cards
        while self.ref_container_layout.count() > 1:
            child = self.ref_container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        # Load rules
        if not rules:
            no_ref_lbl = QLabel("No matching regulations found in the knowledge base.")
            no_ref_lbl.setStyleSheet("font-size: 12px; color: #4E6480; font-style: italic;")
            self.ref_container_layout.insertWidget(0, no_ref_lbl)
            return
            
        for idx, rule in enumerate(rules):
            card = ReferenceCard(rule, theme=self._current_theme)
            self.ref_container_layout.insertWidget(idx, card)
            
    def clear_chat(self):
        # Remove all bubbles except first welcome message
        while self.chat_container_layout.count() > 2:
            child = self.chat_container_layout.takeAt(1)
            if child.widget():
                child.widget().deleteLater()
                
        # Clear reference cards
        while self.ref_container_layout.count() > 1:
            child = self.ref_container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
    def scroll_to_bottom(self):
        # Tiny delay to ensure layout updates first
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))
        
    def apply_permissions(self):
        """Standard permission update hook required by MainWindow."""
        pass
        
    def refresh_data(self):
        """Called when user clicks the refresh breadcrumb button."""
        self.clear_chat()
        
    def _export_json(self):
        """Optional JSON export of the active session conversation."""
        import json
        from PySide6.QtWidgets import QFileDialog
        
        path, _ = QFileDialog.getSaveFileName(self, "Export Conversation", "Compliance_Chat.json", "JSON Files (*.json)")
        if not path:
            return
            
        chat_log = []
        for i in range(self.chat_container_layout.count() - 1):
            w = self.chat_container_layout.itemAt(i).widget()
            if isinstance(w, ChatBubble):
                chat_log.append({
                    "sender": "User" if w.is_user else "Assistant",
                    "text": w.content_lbl.text()
                })
                
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(chat_log, f, indent=2)
            logger.info(f"Conversation exported to {path}")
        except Exception as e:
            logger.error(f"Failed to export chat: {e}")

    def set_theme(self, theme_name: str):
        """Update current theme and refresh styles of child widgets."""
        self._current_theme = theme_name
        
        # Update styling of all ChatBubbles
        for i in range(self.chat_container_layout.count()):
            item = self.chat_container_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ChatBubble):
                item.widget().theme = theme_name
                item.widget().apply_theme_styling()
                
        # Update styling of all ReferenceCards
        for i in range(self.ref_container_layout.count()):
            item = self.ref_container_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ReferenceCard):
                item.widget().theme = theme_name
                item.widget().apply_theme_styling()
