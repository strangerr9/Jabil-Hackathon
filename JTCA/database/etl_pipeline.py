"""
============================================================
JTCA - ETL Pipeline
MongoDB (raw crawl) → PostgreSQL (clean structured data)

Flow:
  1. Fetch unprocessed docs from MongoDB raw_crawls collection
  2. Validate & clean each record (normalize HS codes, strip junk)
  3. Upsert into PostgreSQL tariff_rules
  4. Mark MongoDB docs as processed
  5. Trigger ChromaDB vector store refresh

Usage:
  python -m database.etl_pipeline        # run once manually
  from database.etl_pipeline import run_etl
============================================================
"""

import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Allow direct execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from dotenv import load_dotenv
    load_dotenv()


# ─────────────────────────────────────────────
# Validation & Cleaning
# ─────────────────────────────────────────────
_HS_PATTERN = re.compile(r"^\d{4,10}$")


def _normalize_hs_code(raw: str) -> Optional[str]:
    """
    Normalize HS code:
      - Strip dots, spaces, dashes
      - Pad to 6 digits minimum
      - Return None if invalid
    """
    if not raw:
        return None
    cleaned = re.sub(r"[\s\.\-]", "", str(raw))
    if not cleaned.isdigit():
        return None
    if len(cleaned) < 4:
        return None
    # Normalize to 6 digits (standard HS code length)
    return cleaned[:6].ljust(6, "0")


def _clean_description(raw: str) -> str:
    """Strip excessive whitespace and control characters from description."""
    if not raw:
        return "Unknown Product"
    cleaned = re.sub(r"[\r\n\t]+", " ", str(raw))
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()[:500]


def _validate_tariff_percent(raw) -> Optional[float]:
    """Validate tariff percentage is a float between 0 and 100."""
    try:
        val = float(raw)
        if 0.0 <= val <= 100.0:
            return round(val, 4)
        return None
    except (TypeError, ValueError):
        return None


def clean_and_validate(raw_doc: dict) -> Optional[dict]:
    """
    Clean and validate a raw MongoDB crawl document.
    Returns a clean dict ready for PostgreSQL insert, or None if invalid.
    """
    hs_code = _normalize_hs_code(raw_doc.get("hs_code", ""))
    if not hs_code:
        logger.debug(f"[ETL] Skipping doc {raw_doc.get('_id')}: invalid HS code '{raw_doc.get('hs_code')}'")
        return None

    tariff_percent = _validate_tariff_percent(raw_doc.get("tariff_percent"))
    if tariff_percent is None:
        logger.debug(f"[ETL] Skipping doc {raw_doc.get('_id')}: invalid tariff '{raw_doc.get('tariff_percent')}'")
        return None

    origin = str(raw_doc.get("origin_country", "Unknown")).strip()[:100]
    destination = str(raw_doc.get("destination_country", "USA")).strip()[:100]
    description = _clean_description(raw_doc.get("product_description", ""))
    fta_name = str(raw_doc.get("fta_name", "Web Crawl")).strip()[:200]
    reg_source = str(raw_doc.get("regulation_source", raw_doc.get("source_url", ""))).strip()[:500]

    return {
        "hs_code": hs_code,
        "product_description": description,
        "origin_country": origin,
        "destination_country": destination,
        "tariff_percent": tariff_percent,
        "fta_name": fta_name,
        "regulation_source": reg_source,
        "last_updated": datetime.now().isoformat(),
        "mongo_id": raw_doc.get("_id"),   # Track source document
    }


# ─────────────────────────────────────────────
# ETL Runner
# ─────────────────────────────────────────────
def run_etl(
    batch_size: int = 10000,
    log_callback=None,
    refresh_vector_store: bool = True,
) -> dict:
    """
    Run the ETL pipeline:
      MongoDB (unprocessed) → validate → PostgreSQL → mark processed

    Args:
        batch_size:           Max docs to process per run.
        log_callback:         Optional callable(str) for UI log messages.
        refresh_vector_store: If True, refresh ChromaDB after ETL.

    Returns:
        {
          "fetched": int,
          "valid": int,
          "saved": int,
          "skipped": int,
          "errors": list[str]
        }
    """
    def log(msg: str):
        logger.info(msg)
        if log_callback:
            log_callback(msg)

    log(f"[ETL] Starting pipeline (batch_size={batch_size})...")

    # ── Step 1: Fetch unprocessed docs from MongoDB ──────────
    try:
        from database.mongo_db import get_unprocessed_crawls, mark_bulk_processed, mark_as_processed
    except ImportError as e:
        log(f"[ETL] MongoDB module unavailable: {e}")
        return {"fetched": 0, "valid": 0, "saved": 0, "skipped": 0, "errors": [str(e)]}

    raw_docs = get_unprocessed_crawls(limit=batch_size)
    fetched = len(raw_docs)
    log(f"[ETL] Fetched {fetched} unprocessed raw docs from MongoDB.")

    if fetched == 0:
        log("[ETL] No pending docs. Pipeline complete.")
        return {"fetched": 0, "valid": 0, "saved": 0, "skipped": 0, "errors": []}

    # ── Step 2: Clean & Validate ─────────────────────────────
    try:
        from database.postgres_db import insert_tariff_rule
    except ImportError as e:
        log(f"[ETL] PostgreSQL module unavailable: {e}")
        return {"fetched": fetched, "valid": 0, "saved": 0, "skipped": fetched, "errors": [str(e)]}

    valid_docs = []
    invalid_ids = []
    errors = []

    for doc in raw_docs:
        cleaned = clean_and_validate(doc)
        if cleaned:
            valid_docs.append((doc["_id"], cleaned))
        else:
            invalid_ids.append(doc["_id"])

    skipped = len(invalid_ids)
    log(f"[ETL] Validated: {len(valid_docs)} valid, {skipped} skipped (invalid data).")

    # ── Step 3: Upsert into PostgreSQL ───────────────────────
    saved = 0
    processed_ids = []

    for mongo_id, clean_rule in valid_docs:
        try:
            if insert_tariff_rule(clean_rule):
                saved += 1
                processed_ids.append(mongo_id)
            else:
                errors.append(f"Failed to insert rule from mongo_id={mongo_id}")
        except Exception as e:
            errors.append(f"Error inserting mongo_id={mongo_id}: {e}")
            mark_as_processed(mongo_id, error=str(e))

    log(f"[ETL] Saved {saved}/{len(valid_docs)} rules to PostgreSQL.")

    # ── Step 4: Mark processed in MongoDB ────────────────────
    all_done_ids = processed_ids + invalid_ids  # Mark invalid as "processed" too (won't retry)
    mark_bulk_processed(all_done_ids)
    log(f"[ETL] Marked {len(all_done_ids)} MongoDB docs as processed.")

    # ── Step 5: Refresh ChromaDB vector store ────────────────
    if refresh_vector_store and saved > 0:
        log("[ETL] Refreshing ChromaDB vector store...")
        try:
            from rag.vector_store import upsert_tariff_rules, reset_collection
            from database.postgres_db import get_all_tariff_rules
            reset_collection()
            all_rules = get_all_tariff_rules()
            upsert_tariff_rules(all_rules)
            log(f"[ETL] Vector store updated with {len(all_rules)} total rules.")
        except Exception as e:
            log(f"[ETL] Vector store refresh failed (non-critical): {e}")
            errors.append(f"Vector store refresh: {e}")

    log(f"[ETL] Pipeline complete. fetched={fetched}, valid={len(valid_docs)}, saved={saved}, skipped={skipped}")
    return {
        "fetched": fetched,
        "valid": len(valid_docs),
        "saved": saved,
        "skipped": skipped,
        "errors": errors,
    }


# ─────────────────────────────────────────────
# Self-test (python -m database.etl_pipeline)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    print("=" * 55)
    print(" JTCA ETL Pipeline - Manual Run")
    print("=" * 55)

    # Step 0: Ensure PostgreSQL schema exists
    print("\n[0] Initializing PostgreSQL schema...")
    try:
        from database.postgres_db import initialize_db
        initialize_db()
        print("   [OK] Schema ready.")
    except Exception as e:
        print(f"   [FAIL] Schema init failed: {e}")
        print("   Make sure Docker is running: docker compose up -d")
        sys.exit(1)

    # Insert a dummy raw doc into MongoDB for testing
    print("\n[1] Inserting a test raw doc into MongoDB...")
    try:
        from database.mongo_db import insert_raw_crawl
        test_rule = {
            "hs_code": "8471.30",
            "product_description": "Portable digital ADP machines weighing <= 10 kg",
            "origin_country": "Malaysia",
            "destination_country": "USA",
            "tariff_percent": 0.0,
            "fta_name": "MITI FTA Test",
            "regulation_source": "https://test.example.com",
        }
        doc_id = insert_raw_crawl(test_rule, source_url="https://test.example.com", crawl_run_id="test")
        print(f"   [OK] Inserted MongoDB doc: {doc_id}")
    except Exception as e:
        print(f"   [FAIL] MongoDB insert failed: {e}")

    # Run ETL
    print("\n[2] Running ETL pipeline...")
    result = run_etl(log_callback=lambda m: print(f"   {m}"))
    print(f"\n[3] ETL Result:")
    for k, v in result.items():
        print(f"   {k}: {v}")
