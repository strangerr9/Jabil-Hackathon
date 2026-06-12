"""
============================================================
JTCA - RAG Vector Store Module
ChromaDB integration for HS Code knowledge base
============================================================
"""

import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).parent.parent
CHROMA_PATH = str(_BASE_DIR / os.getenv("CHROMA_PATH", "data/chroma_store"))
COLLECTION_NAME = "jtca_tariff_rules"

_client = None
_collection = None


def _get_client():
    """Lazy-initialize ChromaDB persistent client."""
    global _client
    if _client is None:
        try:
            import chromadb
            Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)
            _client = chromadb.PersistentClient(path=CHROMA_PATH)
            logger.info(f"ChromaDB client initialized at: {CHROMA_PATH}")
        except ImportError:
            logger.error("chromadb not installed.")
            raise
        except Exception as e:
            logger.error(f"ChromaDB init error: {e}")
            raise
    return _client


def get_collection():
    """Get or create the tariff rules collection."""
    global _collection
    if _collection is None:
        client = _get_client()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Collection '{COLLECTION_NAME}' ready. Count: {_collection.count()}")
    return _collection


def upsert_tariff_rules(rules: list[dict]):
    """
    Upsert tariff rules from SQLite into ChromaDB vector store.

    Args:
        rules: List of tariff rule dicts from database
    """
    if not rules:
        logger.warning("No rules to upsert.")
        return

    from rag.embeddings import encode_batch, build_query_text

    collection = get_collection()

    documents = []
    embeddings = []
    metadatas = []
    ids = []

    # Build text documents for embedding
    for rule in rules:
        doc_text = (
            f"{rule.get('product_description', '')} "
            f"HS:{rule.get('hs_code', '')} "
            f"Origin:{rule.get('origin_country', '')} "
            f"FTA:{rule.get('fta_name', '')}"
        )
        documents.append(doc_text)
        metadatas.append({
            "hs_code": str(rule.get("hs_code", "")),
            "product_description": str(rule.get("product_description", ""))[:500],
            "origin_country": str(rule.get("origin_country", "")),
            "destination_country": str(rule.get("destination_country", "USA")),
            "tariff_percent": float(rule.get("tariff_percent", 0.0)),
            "fta_name": str(rule.get("fta_name", "")),
            "regulation_source": str(rule.get("regulation_source", "")),
        })
        ids.append(f"rule_{rule.get('id', len(ids))}")

    # Batch encode
    embeddings = encode_batch(documents)

    # Upsert into ChromaDB
    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    logger.info(f"Upserted {len(rules)} tariff rules into ChromaDB.")


def get_vector_count() -> int:
    """Return the number of documents in the vector store."""
    try:
        return get_collection().count()
    except Exception:
        return 0


def reset_collection():
    """Delete and recreate the collection (useful for re-indexing)."""
    global _collection
    try:
        client = _get_client()
        client.delete_collection(COLLECTION_NAME)
        _collection = None
        get_collection()  # Recreate
        logger.info("Collection reset.")
    except Exception as e:
        logger.error(f"Failed to reset collection: {e}")
