# JTCA — Jabil TradeAI Compliance Assistant

> **Proof-of-Concept** for Jabil IT ECP Bootcamp 3.0 | Use Case 2: Tariff Calculation Automation

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd JTCA
pip install -r requirements.txt
```

For full RAG + OCR support (optional but recommended):
```bash
pip install sentence-transformers chromadb pytesseract Pillow crawl4ai
playwright install chromium
```

### 2. Set Up Environment

```bash
# Copy template and add your Gemini API key
copy .env.example .env
# Edit .env and set: GEMINI_API_KEY=your_key_here
```

Get a free Gemini API key at: https://aistudio.google.com/app/apikey

### 3. Run the Application

```bash
python main.py
```

---

## 📁 Project Structure

```
JTCA/
├── main.py                    # Application entry point
├── .env                       # Your environment config (create from .env.example)
├── requirements.txt
├── ui/
│   ├── main_window.py         # Root PySide6 window + global theme
│   ├── dashboard.py           # KPI cards + drag-drop PDF upload
│   ├── shipment_view.py       # Invoice detail + AI results
│   ├── review_dialog.py       # Human override dialog
│   ├── shipments_list.py      # Full searchable shipment list
│   ├── crawler_page.py        # Web crawler control panel
│   └── reports_page.py        # Analytics + audit log
├── database/
│   ├── db.py                  # SQLite CRUD helpers
│   └── schema.sql             # Table definitions
├── crawler/
│   └── crawl4ai_service.py    # Async web crawler
├── ocr/
│   └── pdf_extractor.py       # PDF text extraction
├── rag/
│   ├── embeddings.py          # SentenceTransformer wrapper
│   ├── vector_store.py        # ChromaDB integration
│   └── retrieval.py           # Vector similarity search
├── llm/
│   └── gemini_service.py      # Gemini API + prompt builder
├── services/
│   ├── duty_calculator.py     # Duty = Value × Tariff%
│   ├── approval_engine.py     # Confidence-based routing
│   └── export_excel.py        # SAP_Export.xlsx generator
├── data/
│   ├── seed_tariffs.json      # 25 pre-loaded HS code rules
│   └── exports/               # Generated Excel files
└── logs/
    └── app.log                # Application log
```

---

## 🎯 Features

| Feature | Description |
|---|---|
| 📄 PDF OCR | Extract Part Number, Description, COO, Value |
| 🤖 Gemini AI | Structured HS Code + tariff recommendation |
| 🔍 RAG | SentenceTransformers + ChromaDB similarity search |
| 🌐 Web Crawler | Crawl4AI targeting MITI, WTO, ASEAN |
| 💰 Duty Calculator | `Value × Tariff%` with breakdown steps |
| ✅ Auto-Approval | Confidence ≥ 90% → Approved Queue |
| 👤 Human Review | Edit HS Code, Tariff, add notes |
| 📊 Excel Export | SAP-compatible XLSX with styling |
| 📋 Audit Trail | Full log of all AI + human actions |

---

## 🎨 UI Pages

1. **Dashboard** — KPIs, drag-drop PDF upload, shipment list
2. **Shipments** — Full list with search and filter
3. **Web Crawler** — Crawl trade portal sites, re-index RAG
4. **Reports** — Analytics + full audit trail log
5. **Invoice Detail** — AI results, reasoning trace, approve/disapprove

---

## 🔑 Configuration (`.env`)

```env
GEMINI_API_KEY=your_key_here        # Required for AI features
CONFIDENCE_THRESHOLD=90             # Auto-approve threshold %
DB_PATH=data/jtca.db               # SQLite database path
CHROMA_PATH=data/chroma_store       # ChromaDB storage
LOG_LEVEL=INFO                      # DEBUG | INFO | WARNING
```

---

## ⚠️ Notes

- The app **works without Gemini API key** using a built-in demo mode
- The app **works without Tesseract** using pdfplumber for text PDFs
- The app **works without crawl4ai** — seed data is pre-loaded
- All RAG dependencies are **optional** — falls back gracefully

---

## 📜 License

Internal use — Jabil IT ECP Bootcamp 3.0 POC
