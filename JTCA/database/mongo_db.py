"""
============================================================
JTCA - MongoDB Module
Stores RAW crawl data before ETL processing.

Collections:
  raw_crawls  → unprocessed tariff data from crawler
  crawl_runs  → metadata about each crawl session

Usage:
  from database.mongo_db import insert_raw_crawl, get_unprocessed_crawls
============================================================
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Lazy import so app still starts if pymongo isn't installed ──
try:
    from pymongo import MongoClient
    from pymongo.collection import Collection
    from bson import ObjectId
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False
    logger.warning("[MongoDB] pymongo not installed. Run: pip install pymongo>=4.7.0")


# ─────────────────────────────────────────────
# Connection
# ─────────────────────────────────────────────
_client: Optional["MongoClient"] = None


def get_mongo_client() -> "MongoClient":
    """Return a cached MongoClient. Reads MONGO_URI from env."""
    global _client
    if not HAS_PYMONGO:
        raise ImportError("pymongo is not installed. Run: pip install pymongo>=4.7.0")
    if _client is None:
        uri = os.getenv("MONGO_URI", "mongodb://jtca_user:jtca_pass@localhost:27017/")
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # Ping to confirm connection
        _client.admin.command("ping")
        logger.info("[MongoDB] Connected successfully.")
    return _client


def get_db():
    """Return the JTCA raw database."""
    db_name = os.getenv("MONGO_DB_NAME", "jtca_raw")
    return get_mongo_client()[db_name]


def get_raw_crawls_collection() -> "Collection":
    return get_db()["raw_crawls"]


def get_crawl_runs_collection() -> "Collection":
    return get_db()["crawl_runs"]


# ─────────────────────────────────────────────
# Raw Crawl Operations
# ─────────────────────────────────────────────
def insert_raw_crawl(rule: dict, source_url: str, crawl_run_id: str = "") -> Optional[str]:
    """
    Insert a single raw tariff rule from the crawler.
    Returns the inserted MongoDB document ID as string, or None on failure.

    Args:
        rule:         The raw parsed rule dict from the crawler.
        source_url:   The URL this was crawled from.
        crawl_run_id: Optional ID linking to a crawl_runs session.
    """
    if not HAS_PYMONGO:
        logger.warning("[MongoDB] pymongo not installed. Skipping raw insert.")
        return None
    try:
        collection = get_raw_crawls_collection()
        doc = {
            **rule,
            "source_url": source_url,
            "crawl_run_id": crawl_run_id,
            "crawled_at": datetime.now(timezone.utc),
            "processed": False,        # ETL flag — False until pipeline runs
            "etl_error": None,         # Populated if ETL fails on this doc
        }
        result = collection.insert_one(doc)
        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"[MongoDB] Failed to insert raw crawl: {e}")
        return None


def insert_raw_crawls_bulk(rules: list[dict], source_url: str, crawl_run_id: str = "") -> int:
    """
    Bulk insert a list of raw rules. Returns count of successfully inserted docs.
    """
    if not HAS_PYMONGO or not rules:
        return 0
    try:
        collection = get_raw_crawls_collection()
        now = datetime.now(timezone.utc)
        docs = [
            {
                **rule,
                "source_url": source_url,
                "crawl_run_id": crawl_run_id,
                "crawled_at": now,
                "processed": False,
                "etl_error": None,
            }
            for rule in rules
        ]
        result = collection.insert_many(docs, ordered=False)
        logger.info(f"[MongoDB] Bulk inserted {len(result.inserted_ids)} raw crawl docs.")
        return len(result.inserted_ids)
    except Exception as e:
        logger.error(f"[MongoDB] Bulk insert failed: {e}")
        return 0


def get_unprocessed_crawls(limit: int = 10000) -> list[dict]:
    """
    Fetch raw crawl docs that have not been processed by ETL yet.
    Returns list of dicts with '_id' as string.
    """
    if not HAS_PYMONGO:
        return []
    try:
        collection = get_raw_crawls_collection()
        cursor = collection.find({"processed": False}).limit(limit)
        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])  # Convert ObjectId → string
            results.append(doc)
        return results
    except Exception as e:
        logger.error(f"[MongoDB] Failed to fetch unprocessed crawls: {e}")
        return []


def mark_as_processed(mongo_id: str, error: str = None):
    """
    Mark a raw crawl document as processed (or failed).
    Called by ETL pipeline after successfully writing to PostgreSQL.
    """
    if not HAS_PYMONGO:
        return
    try:
        collection = get_raw_crawls_collection()
        collection.update_one(
            {"_id": ObjectId(mongo_id)},
            {
                "$set": {
                    "processed": True if not error else False,
                    "etl_error": error,
                    "etl_processed_at": datetime.now(timezone.utc),
                }
            },
        )
    except Exception as e:
        logger.error(f"[MongoDB] Failed to mark doc {mongo_id} as processed: {e}")


def mark_bulk_processed(mongo_ids: list[str]):
    """Bulk-mark a list of MongoDB IDs as processed."""
    if not HAS_PYMONGO or not mongo_ids:
        return
    try:
        collection = get_raw_crawls_collection()
        object_ids = [ObjectId(mid) for mid in mongo_ids]
        collection.update_many(
            {"_id": {"$in": object_ids}},
            {"$set": {"processed": True, "etl_processed_at": datetime.now(timezone.utc)}},
        )
    except Exception as e:
        logger.error(f"[MongoDB] Bulk mark processed failed: {e}")


# ─────────────────────────────────────────────
# Crawl Run Session
# ─────────────────────────────────────────────
def start_crawl_run(targets: list[str]) -> str:
    """
    Record the start of a crawl session.
    Returns the crawl run ID string.
    """
    if not HAS_PYMONGO:
        return ""
    try:
        collection = get_crawl_runs_collection()
        doc = {
            "started_at": datetime.now(timezone.utc),
            "finished_at": None,
            "targets": targets,
            "rules_found": 0,
            "rules_saved": 0,
            "status": "running",
            "errors": [],
        }
        result = collection.insert_one(doc)
        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"[MongoDB] Failed to start crawl run: {e}")
        return ""


def finish_crawl_run(run_id: str, rules_found: int, rules_saved: int, errors: list[str]):
    """Update a crawl run session with final stats."""
    if not HAS_PYMONGO or not run_id:
        return
    try:
        collection = get_crawl_runs_collection()
        collection.update_one(
            {"_id": ObjectId(run_id)},
            {
                "$set": {
                    "finished_at": datetime.now(timezone.utc),
                    "rules_found": rules_found,
                    "rules_saved": rules_saved,
                    "status": "completed" if not errors else "completed_with_errors",
                    "errors": errors,
                }
            },
        )
    except Exception as e:
        logger.error(f"[MongoDB] Failed to finish crawl run {run_id}: {e}")


def get_raw_crawl_stats() -> dict:
    """Return counts of total / processed / pending raw docs."""
    if not HAS_PYMONGO:
        return {"total": 0, "processed": 0, "pending": 0}
    try:
        collection = get_raw_crawls_collection()
        total = collection.count_documents({})
        processed = collection.count_documents({"processed": True})
        return {"total": total, "processed": processed, "pending": total - processed}
    except Exception as e:
        logger.error(f"[MongoDB] Stats query failed: {e}")
        return {"total": 0, "processed": 0, "pending": 0}


def clear_raw_crawls() -> int:
    """Delete all documents in raw_crawls and crawl_runs collections. Returns deleted crawl count."""
    if not HAS_PYMONGO:
        return 0
    try:
        db = get_db()
        # Clear crawls
        res_crawls = db["raw_crawls"].delete_many({})
        # Clear run sessions
        db["crawl_runs"].delete_many({})
        logger.info(f"[MongoDB] Cleared {res_crawls.deleted_count} raw crawls and all runs.")
        return res_crawls.deleted_count
    except Exception as e:
        logger.error(f"[MongoDB] Failed to clear raw crawls: {e}")
        return 0


# ─────────────────────────────────────────────
# Self-test (python -m database.mongo_db)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from dotenv import load_dotenv
    load_dotenv()

    print("Testing MongoDB connection...")
    try:
        client = get_mongo_client()
        print("✅ Connected to MongoDB!")
        stats = get_raw_crawl_stats()
        print(f"   Raw crawls: {stats['total']} total, {stats['pending']} pending ETL")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("   Make sure Docker is running: docker-compose up -d")
