import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sync_rag")

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from rag.vector_store import reset_collection, upsert_tariff_rules, get_vector_count
    from database.postgres_db import get_all_tariff_rules
    
    logger.info("Initializing RAG database synchronization...")
    
    # 1. Reset the ChromaDB collection
    logger.info("Resetting ChromaDB collection (clearing all vectors)...")
    reset_collection()
    
    # 2. Retrieve current active rules from PostgreSQL database
    logger.info("Fetching active rules from PostgreSQL database...")
    active_rules = get_all_tariff_rules()
    logger.info(f"Found {len(active_rules)} active rules in the PostgreSQL database.")
    
    # 3. Upsert active rules into ChromaDB
    if active_rules:
        logger.info("Indexing and upserting active rules into ChromaDB vector store...")
        upsert_tariff_rules(active_rules)
        logger.info(f"Sync complete. ChromaDB count: {get_vector_count()}")
    else:
        logger.warning("No rules found in database to index.")
        
except Exception as e:
    logger.error(f"Synchronization failed: {e}")
    sys.exit(1)
