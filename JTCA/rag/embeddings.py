"""
============================================================
JTCA - RAG Embeddings Module
Wraps SentenceTransformers for text embedding generation
Model: all-MiniLM-L6-v2
============================================================
"""

import logging
import numpy as np
from typing import Union

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
_model = None  # Singleton model instance

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    logger.warning("sentence-transformers not installed. RAG embeddings fallback will be used.")


def get_model():
    """Lazy-load SentenceTransformer model (singleton)."""
    global _model
    if not HAS_SENTENCE_TRANSFORMERS:
        return None
    if _model is None:
        try:
            logger.info(f"Loading SentenceTransformer model: {MODEL_NAME}")
            _model = SentenceTransformer(MODEL_NAME)
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    return _model


def encode_text(text: str) -> list[float]:
    """
    Encode a single text string into an embedding vector.

    Args:
        text: Input text to embed

    Returns:
        List of floats representing the embedding vector
    """
    model = get_model()
    if model is None:
        return []
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def encode_batch(texts: list[str]) -> list[list[float]]:
    """
    Encode a batch of texts.

    Args:
        texts: List of text strings

    Returns:
        List of embedding vectors
    """
    model = get_model()
    if model is None:
        return [[] for _ in texts]
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return embeddings.tolist()


def build_query_text(product_description: str, origin_country: str = "") -> str:
    """
    Combine product info into a single query string for embedding.

    Args:
        product_description: Text description of the product
        origin_country: Country of origin (optional)

    Returns:
        Combined query text
    """
    parts = [product_description.strip()]
    if origin_country.strip():
        parts.append(f"origin: {origin_country.strip()}")
    return " | ".join(parts)
