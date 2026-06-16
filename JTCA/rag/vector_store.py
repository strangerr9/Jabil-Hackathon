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

try:
    import chromadb
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False
    logger.warning("chromadb not installed. Vector store operations will be bypassed.")


def _get_client():
    """Lazy-initialize ChromaDB persistent client."""
    global _client
    if not HAS_CHROMADB:
        return None
    if _client is None:
        try:
            Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)
            _client = chromadb.PersistentClient(path=CHROMA_PATH)
            logger.info(f"ChromaDB client initialized at: {CHROMA_PATH}")
        except Exception as e:
            logger.error(f"ChromaDB init error: {e}")
            raise
    return _client


def get_collection():
    """Get or create the tariff rules collection."""
    global _collection
    if not HAS_CHROMADB:
        return None
    if _collection is None:
        client = _get_client()
        if client:
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
    if not HAS_CHROMADB:
        logger.warning("ChromaDB not available. Skipping upsert.")
        return

    from rag.embeddings import HAS_SENTENCE_TRANSFORMERS, encode_batch, build_query_text

    if not HAS_SENTENCE_TRANSFORMERS:
        logger.warning("Sentence-transformers not available. Skipping upsert.")
        return

    if not rules:
        logger.warning("No rules to upsert.")
        return

    collection = get_collection()
    if not collection:
        logger.warning("Collection not available. Skipping upsert.")
        return

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

    # Get ChromaDB max batch size or use a safe default
    client = _get_client()
    max_batch_size = 5000
    if client and hasattr(client, "get_max_batch_size"):
        try:
            max_batch_size = client.get_max_batch_size()
        except Exception as e:
            logger.warning(f"Could not retrieve max batch size: {e}")

    # Upsert into ChromaDB in chunks
    for i in range(0, len(rules), max_batch_size):
        chunk_ids = ids[i : i + max_batch_size]
        chunk_docs = documents[i : i + max_batch_size]
        chunk_embs = embeddings[i : i + max_batch_size]
        chunk_meta = metadatas[i : i + max_batch_size]

        collection.upsert(
            ids=chunk_ids,
            documents=chunk_docs,
            embeddings=chunk_embs,
            metadatas=chunk_meta,
        )

    logger.info(f"Upserted {len(rules)} tariff rules into ChromaDB in batches of size {max_batch_size}.")


def get_vector_count() -> int:
    """Return the number of documents in the vector store."""
    if not HAS_CHROMADB:
        return 0
    try:
        col = get_collection()
        return col.count() if col else 0
    except Exception:
        return 0


def reset_collection():
    """Delete and recreate the collection (useful for re-indexing)."""
    global _collection
    if not HAS_CHROMADB:
        logger.warning("ChromaDB not available. Skipping reset.")
        return
    try:
        client = _get_client()
        if client:
            client.delete_collection(COLLECTION_NAME)
            _collection = None
            get_collection()  # Recreate
            logger.info("Collection reset.")
    except Exception as e:
        logger.error(f"Failed to reset collection: {e}")
