# Jabil TradeAI Compliance Assistant (JTCA)

JTCA is an enterprise-grade AI-powered trade compliance desktop application designed to scrape, structure, and audit import tariff rates, ensuring trade rules adhere to Free Trade Agreements (FTAs) like ACFTA and USMCA.

---

## 🏗️ System Architecture

The application is built on a **layered, micro-services-supported desktop architecture** using PySide6 (PyQt), Google Gemini 1.5/2.0 API, MongoDB, PostgreSQL, and ChromaDB.

```mermaid
graph TD
    subgraph UI ["Desktop User Interface (PySide6)"]
        UI_Main[MainWindow]
        UI_Dash[DashboardPage]
        UI_Ship[ShipmentsListPage]
        UI_Crawl[CrawlerPage]
        UI_Audit[ShipmentView / Audit Page]
    end

    subgraph Crawler ["Data Ingestion Strategy"]
        Scraper[Crawl4AI Web Scraper]
        OCR[PDF Extractor / OCR Parser]
    end

    subgraph Storage ["Database Cluster (Docker)"]
        Mongo[(MongoDB Staging: Raw Crawls)]
        Postgres[(PostgreSQL: Clean Structured DB)]
        Chroma[(ChromaDB: Vector Search Store)]
    end

    subgraph AI ["AI & RAG Engine"]
        Gemini[Google Gemini API]
        RAG[RAG Semantic Matcher]
    end

    %% Data Flows
    Scraper -->|Raw HTML/JSON| Mongo
    OCR -->|Raw Text| Mongo
    
    Mongo -->|Raw Docs| ETL[ETL Pipeline]
    ETL -->|Extracts Text| Gemini
    Gemini -->|Structured Rules JSON| Postgres
    Postgres -->|Tariff Records| Embed[Chroma Embedder]
    Embed --> Chroma

    UI_Crawl -->|Controls| Scraper
    UI_Ship -->|Requests Audit| RAG
    RAG -->|Semantic Query| Chroma
    RAG -->|Enrichment Context| Gemini
    Gemini -->|Compliance Recs| UI_Audit
    UI_Audit -->|Approved Logs| Postgres
```

---

## 📁 Repository Structure

```text
Jabil-Hackathon/
│
├── JTCA/
│   ├── crawler/
│   │   └── crawl4ai_service.py     # Web crawler (WTO, MITI, custom portals)
│   │
│   ├── database/
│   │   ├── db.py                   # PostgreSQL queries & SQLite fallbacks
│   │   ├── etl_pipeline.py         # MongoDB -> Gemini extraction -> PostgreSQL
│   │   ├── mongo_db.py             # MongoDB connection & ingestion utilities
│   │   ├── postgres_db.py          # PostgreSQL schema initialization & connection
│   │   └── schema_postgres.sql     # PostgreSQL relational table definitions
│   │
│   ├── llm/
│   │   └── gemini_service.py       # Gemini API client & Pydantic structured output mapping
│   │
│   ├── ocr/
│   │   └── pdf_extractor.py        # PDF parser & OCR text extraction
│   │
│   ├── rag/
│   │   ├── embeddings.py           # Text embedding generator for ChromaDB
│   │   ├── retrieval.py            # RAG queries combining Semantic search + LLM
│   │   └── vector_store.py         # ChromaDB client & vector index refresh pipeline
│   │
│   ├── services/
│   │   ├── approval_engine.py      # Automated compliance validation algorithms
│   │   └── session.py              # User authentication state & role permission manager
│   │
│   ├── ui/
│   │   ├── main_window.py          # Application container, sidebar layout, themes
│   │   ├── dashboard.py            # KPI widgets, shipment stats, interactive charts
│   │   ├── crawler_page.py         # Crawler controls, log window, parsing rules grid
│   │   ├── shipments_list.py       # Grid of imported parts & audit queues
│   │   ├── shipment_view.py        # Compliance assessment panel & reasoning visualizer
│   │   ├── reports_page.py         # Audit export & dashboard report utilities
│   │   └── login_dialog.py         # Role-based user authentication modal
│   │
│   ├── main.py                     # Main application entry point & splash screen
│   ├── docker-compose.yml          # Container configuration (Postgres, Mongo, pgAdmin)
│   └── requirements.txt            # Python dependencies
│
└── READ.md                         # Architecture and documentation (this file)
```

---

## ⚙️ Core Architectural Layers

### 1. User Interface (PySide6)
Built with **PySide6 (Qt for Python)**, featuring a premium dark-themed layout, custom widgets, real-time logging, and role-based permissions:
* **Viewer**: Read-only access to shipments and rules.
* **Compliance Specialist**: Can run crawlers, initiate audits, and flag warnings.
* **Manager**: Full access, including final override approval and DB cleanup rights.

### 2. Database & Storage Layer (Dockerized)
* **MongoDB**: A schema-free landing zone for raw web crawl outputs. Storing raw pages here isolates crawling from AI extraction, preventing data loss in case of API limits or schema changes.
* **PostgreSQL**: The relational database containing cleaned and validated data. It holds table structures for `tariff_rules`, `shipments`, and `audit_log` with relational indexes.
* **ChromaDB**: An on-disk vector database storing embedding vectors of all known tariff rules. It serves as the knowledge base for semantic retrieval.

### 3. ETL Pipeline
* Located in `JTCA/database/etl_pipeline.py`.
* Iterates over raw crawl sessions saved in MongoDB.
* Sends raw document slices to Google Gemini.
* Gemini parses the text using structured Pydantic models to guarantee clean values for `hs_code`, `tariff_percent`, and `fta_name`.
* Inserts the structured records into PostgreSQL and indexes them in ChromaDB.

### 4. RAG & Compliance Audit Engine
* When a shipment is selected, the system triggers semantic matching on the shipment's product description.
* **ChromaDB** returns the top-matching tariff rules based on cosine similarity.
* The matching tariff rules, alongside shipment parameters (such as country of origin, destination, declared value, and material type), are fed into the **Gemini model**.
* Gemini validates whether the suggested HS Code is correct, calculates duties, flags compliance warning codes (e.g. anti-dumping risk), and outputs a transparent reasoning trace.

---

## 🚀 Getting Started

### 1. Start the Docker Services
Navigate to the `JTCA` directory and spin up the database cluster:
```bash
cd JTCA
docker-compose up -d
```
This launches:
* **MongoDB** at `localhost:27017`
* **PostgreSQL** at `localhost:5432`
* **Mongo Express** (Web UI) at `http://localhost:8081`
* **pgAdmin** (Web UI) at `http://localhost:5050`

### 2. Configure Environment Variables
Copy `.env.example` to `.env` inside the `JTCA` folder and add your Gemini API key:
```env
GEMINI_API_KEY=your_google_gemini_api_key_here
MONGO_URI=mongodb://jtca_user:jtca_pass@localhost:27017/
PG_URI=postgresql://jtca_user:jtca_pass@localhost:5432/jtca
```

### 3. Install Python Dependencies
Install the required packages:
```bash
pip install -r requirements.txt
```

### 4. Run the Application
Start the desktop application:
```bash
python main.py
```