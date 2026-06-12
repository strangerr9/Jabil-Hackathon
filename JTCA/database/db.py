"""
============================================================
JTCA - Database Module
Handles SQLite connection, schema creation, and all CRUD ops
============================================================
"""

import sqlite3
import json
import os
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Resolve paths relative to project root
_BASE_DIR = Path(__file__).parent.parent
DB_PATH = _BASE_DIR / os.getenv("DB_PATH", "data/jtca.db")
SCHEMA_PATH = _BASE_DIR / "database" / "schema.sql"
SEED_PATH = _BASE_DIR / "data" / "seed_tariffs.json"


def get_connection() -> sqlite3.Connection:
    """Return a thread-safe SQLite connection with row_factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ─────────────────────────────────────────────
# Schema Initialization
# ─────────────────────────────────────────────
def _migrate_db(conn: sqlite3.Connection):
    """Run migrations to add new columns to shipments table if missing."""
    new_cols = [
        ("material_type", "TEXT DEFAULT 'ZROH'"),
        ("plant_code", "TEXT DEFAULT 'US02'"),
        ("supplier_name", "TEXT DEFAULT 'EMERSON'"),
        ("shipping_country", "TEXT DEFAULT 'Malaysia'"),
        ("wto_member_status", "TEXT DEFAULT 'Yes'"),
        ("fta_applicable", "TEXT DEFAULT 'No'"),
        ("target_sap_system", "TEXT DEFAULT 'Condition_Type_ZDUT'")
    ]
    
    # Get existing columns in shipments table
    cursor = conn.execute("PRAGMA table_info(shipments)")
    existing_cols = {row["name"] for row in cursor.fetchall()}
    
    for col_name, col_type in new_cols:
        if col_name not in existing_cols:
            try:
                conn.execute(f"ALTER TABLE shipments ADD COLUMN {col_name} {col_type}")
                logger.info(f"Database migrated: Added column '{col_name}' to shipments table.")
            except Exception as e:
                logger.error(f"Failed to add column '{col_name}': {e}")


def initialize_db():
    """Create tables and seed initial tariff data if empty."""
    conn = get_connection()
    try:
        with open(SCHEMA_PATH, "r") as f:
            conn.executescript(f.read())
        conn.commit()
        logger.info("Database schema initialized.")
        _migrate_db(conn)
        conn.commit()
        _seed_tariff_data(conn)
    except Exception as e:
        logger.error(f"DB initialization error: {e}")
        raise
    finally:
        conn.close()


def _seed_tariff_data(conn: sqlite3.Connection):
    """Load seed tariff rules from JSON if tariff_rules table is empty or out of date."""
    cur = conn.execute("SELECT COUNT(*) FROM tariff_rules")
    count = cur.fetchone()[0]

    if not SEED_PATH.exists():
        logger.warning("Seed data file not found. Skipping seed.")
        return

    with open(SEED_PATH, "r") as f:
        rules = json.load(f)

    if count >= len(rules):
        logger.info(f"Tariff rules already seeded ({count} records). Skipping.")
        return

    if count > 0:
        logger.info(f"Current database rules ({count}) is less than seed count ({len(rules)}). Re-seeding...")
        conn.execute("DELETE FROM tariff_rules")

    now = datetime.now().isoformat()
    for rule in rules:
        conn.execute(
            """
            INSERT OR REPLACE INTO tariff_rules
              (hs_code, product_description, origin_country, destination_country,
               tariff_percent, fta_name, regulation_source, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule.get("hs_code"),
                rule.get("product_description"),
                rule.get("origin_country"),
                rule.get("destination_country", "USA"),
                rule.get("tariff_percent", 0.0),
                rule.get("fta_name"),
                rule.get("regulation_source"),
                rule.get("last_updated", now),
            ),
        )
    conn.commit()
    logger.info(f"Seeded {len(rules)} tariff rules.")


# ─────────────────────────────────────────────
# Shipment CRUD
# ─────────────────────────────────────────────
def insert_shipment(data: dict) -> bool:
    """Insert a new shipment record. Returns True on success."""
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        conn.execute(
            """
            INSERT OR REPLACE INTO shipments
              (shipment_id, part_number, product_description, country_of_origin,
               declared_value, suggested_hs_code, tariff_percent, estimated_duty,
               confidence_score, reasoning_trace, status, source_pdf, created_at, updated_at,
               material_type, plant_code, supplier_name, shipping_country,
               wto_member_status, fta_applicable, target_sap_system)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["shipment_id"],
                data.get("part_number", ""),
                data["product_description"],
                data["country_of_origin"],
                data.get("declared_value", 0.0),
                data.get("suggested_hs_code", ""),
                data.get("tariff_percent", 0.0),
                data.get("estimated_duty", 0.0),
                data.get("confidence_score", 0.0),
                json.dumps(data.get("reasoning_trace", [])),
                data.get("status", "Pending Review"),
                data.get("source_pdf", ""),
                now,
                now,
                data.get("material_type", "ZROH"),
                data.get("plant_code", "US02"),
                data.get("supplier_name", "EMERSON"),
                data.get("shipping_country", "Malaysia"),
                data.get("wto_member_status", "Yes"),
                data.get("fta_applicable", "No"),
                data.get("target_sap_system", "Condition_Type_ZDUT"),
            ),
        )
        conn.commit()
        logger.info(f"Shipment inserted: {data['shipment_id']}")
        return True
    except Exception as e:
        logger.error(f"Failed to insert shipment: {e}")
        return False
    finally:
        conn.close()


def get_all_shipments() -> list[dict]:
    """Retrieve all shipments ordered by creation date descending."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT * FROM shipments ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            # Parse JSON reasoning trace
            try:
                d["reasoning_trace"] = json.loads(d.get("reasoning_trace") or "[]")
            except Exception:
                d["reasoning_trace"] = []
            result.append(d)
        return result
    finally:
        conn.close()


def get_shipment(shipment_id: str) -> dict | None:
    """Get a single shipment by ID."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT * FROM shipments WHERE shipment_id = ?", (shipment_id,)
        )
        row = cur.fetchone()
        if row:
            d = dict(row)
            try:
                d["reasoning_trace"] = json.loads(d.get("reasoning_trace") or "[]")
            except Exception:
                d["reasoning_trace"] = []
            return d
        return None
    finally:
        conn.close()


def delete_shipment(shipment_id: str) -> bool:
    """Permanently delete a shipment and its audit log entries."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM audit_log WHERE shipment_id = ?", (shipment_id,))
        conn.execute("DELETE FROM shipments WHERE shipment_id = ?", (shipment_id,))
        conn.commit()
        logger.info(f"Shipment deleted: {shipment_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete shipment {shipment_id}: {e}")
        return False
    finally:
        conn.close()


def update_shipment_status(
    shipment_id: str,
    status: str,
    reviewer_name: str = "",
    review_notes: str = "",
    hs_code: str | None = None,
    tariff_percent: float | None = None,
):
    """Update shipment status and optional human corrections."""
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        updates = ["status = ?", "reviewer_name = ?", "review_notes = ?", "updated_at = ?"]
        values = [status, reviewer_name, review_notes, now]

        if hs_code is not None:
            updates.append("suggested_hs_code = ?")
            values.append(hs_code)
        if tariff_percent is not None:
            updates.append("tariff_percent = ?")
            values.append(tariff_percent)

        values.append(shipment_id)
        sql = f"UPDATE shipments SET {', '.join(updates)} WHERE shipment_id = ?"
        conn.execute(sql, values)
        conn.commit()
        logger.info(f"Shipment {shipment_id} updated to status: {status}")
    except Exception as e:
        logger.error(f"Failed to update shipment: {e}")
    finally:
        conn.close()


def get_dashboard_stats() -> dict:
    """Compute aggregate statistics for the dashboard."""
    conn = get_connection()
    try:
        stats = {}
        stats["total"] = conn.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
        stats["approved"] = conn.execute(
            "SELECT COUNT(*) FROM shipments WHERE status = 'Approved'"
        ).fetchone()[0]
        stats["pending"] = conn.execute(
            "SELECT COUNT(*) FROM shipments WHERE status = 'Pending Review'"
        ).fetchone()[0]
        stats["rejected"] = conn.execute(
            "SELECT COUNT(*) FROM shipments WHERE status = 'Rejected'"
        ).fetchone()[0]
        avg = conn.execute(
            "SELECT AVG(confidence_score) FROM shipments"
        ).fetchone()[0]
        stats["avg_confidence"] = round(avg or 0.0, 1)
        total_duty = conn.execute(
            "SELECT SUM(estimated_duty) FROM shipments"
        ).fetchone()[0]
        stats["total_duties"] = round(total_duty or 0.0, 2)
        return stats
    finally:
        conn.close()


# ─────────────────────────────────────────────
# Tariff Rules
# ─────────────────────────────────────────────
def get_all_tariff_rules() -> list[dict]:
    """Retrieve all tariff rules."""
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM tariff_rules ORDER BY origin_country, hs_code")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def insert_tariff_rule(rule: dict) -> bool:
    """Insert a single tariff rule (used by crawler)."""
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        conn.execute(
            """
            INSERT OR REPLACE INTO tariff_rules
              (hs_code, product_description, origin_country, destination_country,
               tariff_percent, fta_name, regulation_source, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule.get("hs_code"),
                rule.get("product_description"),
                rule.get("origin_country"),
                rule.get("destination_country", "USA"),
                rule.get("tariff_percent", 0.0),
                rule.get("fta_name"),
                rule.get("regulation_source"),
                now,
            ),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to insert tariff rule: {e}")
        return False
    finally:
        conn.close()


# ─────────────────────────────────────────────
# Audit Log
# ─────────────────────────────────────────────
def insert_audit_log(
    shipment_id: str,
    action: str,
    ai_recommendation: str = "",
    human_decision: str = "",
    reviewer_name: str = "",
    notes: str = "",
):
    """Record an audit trail entry."""
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        conn.execute(
            """
            INSERT INTO audit_log
              (shipment_id, action, ai_recommendation, human_decision,
               reviewer_name, notes, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (shipment_id, action, ai_recommendation, human_decision,
             reviewer_name, notes, now),
        )
        conn.commit()
        logger.info(f"Audit log: {action} for {shipment_id}")
    except Exception as e:
        logger.error(f"Audit log insert failed: {e}")
    finally:
        conn.close()


def get_audit_log(shipment_id: str) -> list[dict]:
    """Get audit log entries for a specific shipment."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT * FROM audit_log WHERE shipment_id = ? ORDER BY timestamp",
            (shipment_id,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
