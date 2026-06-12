-- ============================================================
-- JTCA Database Schema
-- Jabil TradeAI Compliance Assistant
-- ============================================================

-- Table 1: Tariff Rules Knowledge Base
CREATE TABLE IF NOT EXISTS tariff_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hs_code TEXT NOT NULL,
    product_description TEXT NOT NULL,
    origin_country TEXT NOT NULL,
    destination_country TEXT NOT NULL DEFAULT 'USA',
    tariff_percent REAL NOT NULL DEFAULT 0.0,
    fta_name TEXT,
    regulation_source TEXT,
    last_updated TEXT NOT NULL
);

-- Table 2: Shipments (Main Processing Table)
CREATE TABLE IF NOT EXISTS shipments (
    shipment_id TEXT PRIMARY KEY,
    part_number TEXT,
    product_description TEXT NOT NULL,
    country_of_origin TEXT NOT NULL,
    declared_value REAL NOT NULL DEFAULT 0.0,
    suggested_hs_code TEXT,
    tariff_percent REAL DEFAULT 0.0,
    estimated_duty REAL DEFAULT 0.0,
    confidence_score REAL DEFAULT 0.0,
    reasoning_trace TEXT,
    status TEXT NOT NULL DEFAULT 'Pending Review',
    reviewer_name TEXT,
    review_notes TEXT,
    source_pdf TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

-- Table 3: Audit Log
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id TEXT NOT NULL,
    action TEXT NOT NULL,
    ai_recommendation TEXT,
    human_decision TEXT,
    reviewer_name TEXT,
    notes TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_shipments_status ON shipments(status);
CREATE INDEX IF NOT EXISTS idx_shipments_created ON shipments(created_at);
CREATE INDEX IF NOT EXISTS idx_tariff_origin ON tariff_rules(origin_country);
CREATE INDEX IF NOT EXISTS idx_tariff_hscode ON tariff_rules(hs_code);
CREATE INDEX IF NOT EXISTS idx_audit_shipment ON audit_log(shipment_id);
