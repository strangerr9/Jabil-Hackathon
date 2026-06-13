"""
============================================================
JTCA - Services: Approval Engine
Routes shipments based on confidence score threshold
============================================================
"""

import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = int(os.getenv("CONFIDENCE_THRESHOLD", "90"))


def route_shipment(confidence_score: float) -> str:
    """
    Determine shipment status based on AI confidence score.

    Business Rules:
        confidence >= CONFIDENCE_THRESHOLD  → "Approved"
        confidence <  CONFIDENCE_THRESHOLD  → "Pending Review"

    Args:
        confidence_score: AI confidence 0-100

    Returns:
        Status string: "Approved" or "Pending Review"
    """
    if confidence_score >= CONFIDENCE_THRESHOLD:
        status = "Approved"
    else:
        status = "Pending Review"

    logger.info(
        f"Routing: confidence={confidence_score} -> status={status} "
        f"(threshold={CONFIDENCE_THRESHOLD})"
    )
    return status


def get_confidence_badge(confidence_score: float) -> tuple[str, str]:
    """
    Return display text and color for confidence badge.

    Returns:
        (label_text, hex_color)
    """
    if confidence_score >= 90:
        return f"{confidence_score:.0f}%", "#10B981"   # Green
    elif confidence_score >= 75:
        return f"{confidence_score:.0f}%", "#F59E0B"   # Amber
    elif confidence_score >= 50:
        return f"{confidence_score:.0f}%", "#EF4444"   # Red-ish warning
    else:
        return f"{confidence_score:.0f}%", "#6B7280"   # Gray — very low


def get_status_color(status: str) -> str:
    """Return hex color for status display."""
    colors = {
        "Approved": "#10B981",
        "Pending Review": "#F59E0B",
        "Rejected": "#EF4444",
    }
    return colors.get(status, "#6B7280")
