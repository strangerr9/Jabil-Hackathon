"""
============================================================
JTCA - RAG Retrieval Module
Queries ChromaDB for top-K similar tariff rules
============================================================
"""

import logging
from rag.embeddings import HAS_SENTENCE_TRANSFORMERS, encode_text, build_query_text
from rag.vector_store import HAS_CHROMADB, get_collection

logger = logging.getLogger(__name__)


def query_similar(
    product_description: str,
    origin_country: str = "",
    top_k: int = 5,
) -> list[dict]:
    """
    Find top-K similar tariff rules from the vector store.

    Args:
        product_description: Text description of the product
        origin_country: Country of origin to narrow search
        top_k: Number of results to retrieve

    Returns:
        List of dicts with tariff rule metadata and similarity distance
    """
    if not HAS_SENTENCE_TRANSFORMERS or not HAS_CHROMADB:
        logger.warning("RAG skipped: sentence-transformers or chromadb not installed.")
        return []

    try:
        collection = get_collection()
        if collection is None or collection.count() == 0:
            logger.warning("Vector store is empty or unavailable. Initialize with seed data first.")
            return []

        query_text = build_query_text(product_description, origin_country)
        query_embedding = encode_text(query_text)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        retrieved = []
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        documents = results.get("documents", [[]])[0]

        for meta, dist, doc in zip(metadatas, distances, documents):
            # Convert cosine distance to similarity score (0-100)
            similarity = round((1 - dist) * 100, 1)
            retrieved.append({
                "hs_code": meta.get("hs_code", ""),
                "product_description": meta.get("product_description", ""),
                "origin_country": meta.get("origin_country", ""),
                "destination_country": meta.get("destination_country", "USA"),
                "tariff_percent": float(meta.get("tariff_percent", 0.0)),
                "fta_name": meta.get("fta_name", ""),
                "regulation_source": meta.get("regulation_source", ""),
                "similarity_score": similarity,
                "document": doc,
            })

        logger.info(f"Retrieved {len(retrieved)} matches for: '{product_description[:50]}'")
        return retrieved

    except Exception as e:
        logger.error(f"RAG retrieval error: {e}")
        return []


def format_context_for_llm(retrieved: list[dict]) -> str:
    """
    Format retrieved tariff rules into a structured context string
    for use in the Gemini prompt.

    Args:
        retrieved: List of retrieved tariff rule dicts

    Returns:
        Formatted multi-line string for LLM context
    """
    if not retrieved:
        return "No relevant tariff rules found in knowledge base."

    lines = ["=== RETRIEVED TARIFF KNOWLEDGE BASE CONTEXT ===\n"]
    for i, rule in enumerate(retrieved, 1):
        lines.append(f"[Rule {i}] Similarity: {rule['similarity_score']}%")
        lines.append(f"  HS Code: {rule['hs_code']}")
        lines.append(f"  Description: {rule['product_description']}")
        lines.append(f"  Origin: {rule['origin_country']} -> {rule['destination_country']}")
        lines.append(f"  Tariff Rate: {rule['tariff_percent']}%")
        lines.append(f"  FTA: {rule['fta_name']}")
        lines.append(f"  Source: {rule['regulation_source']}")
        lines.append("")

    return "\n".join(lines)
