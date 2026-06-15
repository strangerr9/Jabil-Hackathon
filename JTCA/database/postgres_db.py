"""
============================================================
JTCA - PostgreSQL Module
Replaces SQLite (database/db.py) for production.
Exposes the SAME public API as db.py so all existing
UI code continues to work without modification.

Key functions (drop-in replacements):
  initialize_db()
  get_connection()          ← returns psycopg2 connection
  insert_shipment(data)
  get_all_shipments()
  get_shipment(id)
  delete_shipment(id)
  update_shipment_status(...)
  get_dashboard_stats()
  get_all_tariff_rules()
  insert_tariff_rule(rule)
  insert_audit_log(...)
  get_audit_log(id)
============================================================
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Schema path ──────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent.parent
SCHEMA_PATH = _BASE_DIR / "database" / "schema_postgres.sql"
SEED_PATH = _BASE_DIR / "data" / "seed_tariffs.json"

# ── Lazy import ──────────────────────────────────────────────
try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    logger.warning("[PostgreSQL] psycopg2 not installed. Run: pip install psycopg2-binary")


# ─────────────────────────────────────────────
# Connection
# ─────────────────────────────────────────────
def get_connection():
    """
    Return a psycopg2 connection using POSTGRES_URI from env.
    Row factory: psycopg2.extras.RealDictCursor (dict-like rows).
    """
    if not HAS_PSYCOPG2:
        raise ImportError("psycopg2 not installed. Run: pip install psycopg2-binary")

    uri = os.getenv(
        "POSTGRES_URI",
        "postgresql://jtca_user:jtca_pass@localhost:5432/jtca"
    )
    conn = psycopg2.connect(uri, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


# ─────────────────────────────────────────────
# Schema Initialization
# ─────────────────────────────────────────────
def initialize_db():
    """Create all PostgreSQL tables (idempotent) and seed tariff data."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            with open(SCHEMA_PATH, "r") as f:
                cur.execute(f.read())
        conn.commit()
        logger.info("[PostgreSQL] Schema initialized.")
        _seed_tariff_data(conn)
    except Exception as e:
        conn.rollback()
        logger.error(f"[PostgreSQL] DB initialization error: {e}")
        raise
    finally:
        conn.close()


def _seed_tariff_data(conn):
    """Load seed tariff rules from JSON if tariff_rules table is empty or outdated."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM tariff_rules")
        count = cur.fetchone()["count"]

    if not SEED_PATH.exists():
        logger.warning("[PostgreSQL] Seed file not found. Skipping seed.")
        return

    with open(SEED_PATH, "r") as f:
        rules = json.load(f)

    if count >= len(rules):
        logger.info(f"[PostgreSQL] Tariff rules already seeded ({count} records). Skipping.")
        return

    if count > 0:
        logger.info(f"[PostgreSQL] Re-seeding ({count} < {len(rules)} rules)...")
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tariff_rules")

    now = datetime.now().isoformat()
    with conn.cursor() as cur:
        for rule in rules:
            cur.execute(
                """
                INSERT INTO tariff_rules
                  (hs_code, product_description, origin_country, destination_country,
                   tariff_percent, fta_name, regulation_source, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
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
    logger.info(f"[PostgreSQL] Seeded {len(rules)} tariff rules.")


# ─────────────────────────────────────────────
# Shipment CRUD
# ─────────────────────────────────────────────
def insert_shipment(data: dict) -> bool:
    """Insert or replace a shipment record. Returns True on success."""
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO shipments
                  (shipment_id, part_number, product_description, country_of_origin,
                   declared_value, suggested_hs_code, tariff_percent, estimated_duty,
                   confidence_score, reasoning_trace, status, source_pdf, created_at, updated_at,
                   material_type, plant_code, supplier_name, shipping_country,
                   wto_member_status, fta_applicable, target_sap_system)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (shipment_id) DO UPDATE SET
                  part_number = EXCLUDED.part_number,
                  product_description = EXCLUDED.product_description,
                  country_of_origin = EXCLUDED.country_of_origin,
                  declared_value = EXCLUDED.declared_value,
                  suggested_hs_code = EXCLUDED.suggested_hs_code,
                  tariff_percent = EXCLUDED.tariff_percent,
                  estimated_duty = EXCLUDED.estimated_duty,
                  confidence_score = EXCLUDED.confidence_score,
                  reasoning_trace = EXCLUDED.reasoning_trace,
                  status = EXCLUDED.status,
                  source_pdf = EXCLUDED.source_pdf,
                  updated_at = EXCLUDED.updated_at,
                  material_type = EXCLUDED.material_type,
                  plant_code = EXCLUDED.plant_code,
                  supplier_name = EXCLUDED.supplier_name,
                  shipping_country = EXCLUDED.shipping_country,
                  wto_member_status = EXCLUDED.wto_member_status,
                  fta_applicable = EXCLUDED.fta_applicable,
                  target_sap_system = EXCLUDED.target_sap_system
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
        logger.info(f"[PostgreSQL] Shipment inserted: {data['shipment_id']}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"[PostgreSQL] Failed to insert shipment: {e}")
        return False
    finally:
        conn.close()


def get_all_shipments() -> list[dict]:
    """Retrieve all shipments ordered by creation date descending."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shipments ORDER BY created_at DESC")
            rows = cur.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d["reasoning_trace"] = json.loads(d.get("reasoning_trace") or "[]")
            except Exception:
                d["reasoning_trace"] = []
            result.append(d)
        return result
    finally:
        conn.close()


def get_shipment(shipment_id: str) -> Optional[dict]:
    """Get a single shipment by ID."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shipments WHERE shipment_id = %s", (shipment_id,))
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
        with conn.cursor() as cur:
            cur.execute("DELETE FROM audit_log WHERE shipment_id = %s", (shipment_id,))
            cur.execute("DELETE FROM shipments WHERE shipment_id = %s", (shipment_id,))
        conn.commit()
        logger.info(f"[PostgreSQL] Shipment deleted: {shipment_id}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"[PostgreSQL] Failed to delete shipment {shipment_id}: {e}")
        return False
    finally:
        conn.close()


def update_shipment_status(
    shipment_id: str,
    status: str,
    reviewer_name: str = "",
    review_notes: str = "",
    hs_code: Optional[str] = None,
    tariff_percent: Optional[float] = None,
):
    """Update shipment status and optional human corrections."""
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        updates = ["status = %s", "reviewer_name = %s", "review_notes = %s", "updated_at = %s"]
        values = [status, reviewer_name, review_notes, now]

        if hs_code is not None:
            updates.append("suggested_hs_code = %s")
            values.append(hs_code)
        if tariff_percent is not None:
            updates.append("tariff_percent = %s")
            values.append(tariff_percent)

        values.append(shipment_id)
        sql = f"UPDATE shipments SET {', '.join(updates)} WHERE shipment_id = %s"
        with conn.cursor() as cur:
            cur.execute(sql, values)
        conn.commit()
        logger.info(f"[PostgreSQL] Shipment {shipment_id} updated to status: {status}")
    except Exception as e:
        conn.rollback()
        logger.error(f"[PostgreSQL] Failed to update shipment: {e}")
    finally:
        conn.close()


def get_dashboard_stats() -> dict:
    """Compute aggregate statistics for the dashboard."""
    conn = get_connection()
    try:
        stats = {}
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM shipments")
            stats["total"] = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) FROM shipments WHERE status = 'Approved'")
            stats["approved"] = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) FROM shipments WHERE status = 'Pending Review'")
            stats["pending"] = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) FROM shipments WHERE status = 'Rejected'")
            stats["rejected"] = cur.fetchone()["count"]

            cur.execute("SELECT AVG(confidence_score) FROM shipments")
            avg = cur.fetchone()["avg"]
            stats["avg_confidence"] = round(avg or 0.0, 1)

            cur.execute("SELECT SUM(estimated_duty) FROM shipments")
            total_duty = cur.fetchone()["sum"]
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
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM tariff_rules ORDER BY origin_country, hs_code")
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def insert_tariff_rule(rule: dict) -> bool:
    """
    Insert a single tariff rule.
    Deduplicates on (hs_code, origin_country, destination_country).
    """
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tariff_rules
                  (hs_code, product_description, origin_country, destination_country,
                   tariff_percent, fta_name, regulation_source, last_updated, mongo_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (mongo_id) DO UPDATE SET
                  tariff_percent = EXCLUDED.tariff_percent,
                  product_description = EXCLUDED.product_description,
                  last_updated = EXCLUDED.last_updated
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
                    rule.get("mongo_id"),   # None for seed data; set by ETL pipeline
                ),
            )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"[PostgreSQL] Failed to insert tariff rule: {e}")
        return False
    finally:
        conn.close()


def delete_tariff_rules_by_fta(fta_pattern: str) -> int:
    """Delete tariff rules where fta_name matches a LIKE pattern. Returns count deleted."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tariff_rules WHERE fta_name LIKE %s", (fta_pattern,))
            deleted = cur.rowcount
        conn.commit()
        return deleted
    except Exception as e:
        conn.rollback()
        logger.error(f"[PostgreSQL] Failed to delete tariff rules: {e}")
        return 0
    finally:
        conn.close()


def delete_tariff_rules_by_ids(ids: list[int]) -> int:
    """Delete tariff rules by primary key list. Returns count deleted."""
    if not ids:
        return 0
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM tariff_rules WHERE id = ANY(%s)",
                (ids,)
            )
            deleted = cur.rowcount
        conn.commit()
        return deleted
    except Exception as e:
        conn.rollback()
        logger.error(f"[PostgreSQL] Failed to delete tariff rules by ids: {e}")
        return 0
    finally:
        conn.close()


def clear_crawled_rules() -> int:
    """Delete all crawled tariff rules and restore seed tariff rules. Returns count deleted."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM tariff_rules")
            initial_count = cur.fetchone()["count"]
            cur.execute("DELETE FROM tariff_rules")
            
        conn.commit()
        
        # Seed tariff data again
        _seed_tariff_data(conn)
        
        # Calculate deleted crawled count
        if SEED_PATH.exists():
            with open(SEED_PATH, "r") as f:
                seed_rules = json.load(f)
                seed_count = len(seed_rules)
        else:
            seed_count = 0
            
        crawled_deleted = max(0, initial_count - seed_count)
        logger.info(f"[PostgreSQL] Cleared {crawled_deleted} crawled rules and restored seed.")
        return crawled_deleted
    except Exception as e:
        conn.rollback()
        logger.error(f"[PostgreSQL] Failed to clear crawled rules: {e}")
        return 0
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
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_log
                  (shipment_id, action, ai_recommendation, human_decision,
                   reviewer_name, notes, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (shipment_id, action, ai_recommendation, human_decision,
                 reviewer_name, notes, now),
            )
        conn.commit()
        logger.info(f"[PostgreSQL] Audit log: {action} for {shipment_id}")
    except Exception as e:
        conn.rollback()
        logger.error(f"[PostgreSQL] Audit log insert failed: {e}")
    finally:
        conn.close()


def get_audit_log(shipment_id: str) -> list[dict]:
    """Get audit log entries for a specific shipment."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM audit_log WHERE shipment_id = %s ORDER BY timestamp",
                (shipment_id,),
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_recent_audit_log(limit: int = 200) -> list[tuple]:
    """Get recent audit log entries across all shipments (for Reports page)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT timestamp, shipment_id, action, ai_recommendation,
                       human_decision, reviewer_name, notes
                FROM audit_log
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [
                (
                    row.get("timestamp"),
                    row.get("shipment_id"),
                    row.get("action"),
                    row.get("ai_recommendation"),
                    row.get("human_decision"),
                    row.get("reviewer_name"),
                    row.get("notes")
                )
                for row in cur.fetchall()
            ]
    finally:
        conn.close()


# ─────────────────────────────────────────────
# Self-test (python -m database.postgres_db)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from dotenv import load_dotenv
    load_dotenv()

    print("Testing PostgreSQL connection...")
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            ver = cur.fetchone()
        conn.close()
        print("[OK] Connected to PostgreSQL!")
        print(f"   Version: {ver['version'][:60]}...")
    except Exception as e:
        print(f"[FAIL] Connection failed: {e}")
        print("   Make sure Docker is running: docker compose up -d")
        sys.exit(1)

    print("\nInitializing schema (creating tables if not exist)...")
    try:
        initialize_db()
        print("[OK] Schema ready! Tables created/verified.")
        rules = get_all_tariff_rules()
        print(f"   tariff_rules: {len(rules)} rows")
        shipments = get_all_shipments()
        print(f"   shipments:    {len(shipments)} rows")
    except Exception as e:
        print(f"[FAIL] Schema init failed: {e}")
