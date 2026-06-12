"""
============================================================
JTCA - Gemini LLM Service
Generates structured tariff recommendations using Google Gemini
API key loaded from GEMINI_API_KEY environment variable
============================================================
"""

import json
import logging
import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.0-flash"

# ─────────────────────────────────────────────
# Gemini Client (lazy init)
# ─────────────────────────────────────────────
_genai = None


def _get_genai():
    global _genai
    if _genai is None:
        if not GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY not set. Check your .env file.")
            raise EnvironmentError("GEMINI_API_KEY is not configured.")
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            _genai = genai
            logger.info("Gemini AI client configured.")
        except ImportError:
            logger.error("google-generativeai not installed.")
            raise
    return _genai


# ─────────────────────────────────────────────
# Prompt Builder
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert trade compliance and customs classification specialist with 20 years of experience.
Your task is to analyze product information and recommend the most accurate HS Code, tariff rate, and confidence score.

You MUST respond with ONLY a valid JSON object — no markdown, no explanation outside the JSON.

Response format:
{
  "suggested_hs_code": "XXXXXX",
  "suggested_tariff_percent": 0.0,
  "confidence_score": 85,
  "reasoning_trace": [
    "Step 1: ...",
    "Step 2: ...",
    "Step 3: ...",
    "Step 4: ..."
  ],
  "fta_applicable": "FTA name or None",
  "regulation_source": "URL or reference"
}

Rules:
- confidence_score must be an integer 0-100
- suggested_tariff_percent must be a number (e.g., 5.0, 25.0, 0.0)
- suggested_hs_code must be 6-digit string
- reasoning_trace must be a list of 3-5 strings explaining your decision
- If origin country has an FTA with the destination, note it in fta_applicable
"""


def build_prompt(
    product_description: str,
    part_number: str,
    country_of_origin: str,
    declared_value: float,
    rag_context: str,
) -> str:
    """Build the structured prompt for Gemini."""
    return f"""
{SYSTEM_PROMPT}

=== SHIPMENT INFORMATION ===
Part Number: {part_number or 'Unknown'}
Product Description: {product_description}
Country of Origin: {country_of_origin}
Destination Country: USA
Declared Value: USD {declared_value:,.2f}

{rag_context}

=== TASK ===
Based on the shipment information and the retrieved tariff knowledge base context above,
provide your HS Code classification and tariff recommendation.

Respond with ONLY the JSON object.
"""


# ─────────────────────────────────────────────
# Response Parser
# ─────────────────────────────────────────────
def _parse_gemini_response(text: str) -> dict:
    """
    Parse Gemini's response text into a structured dict.
    Handles markdown-wrapped JSON and raw JSON.
    """
    # Strip markdown code blocks if present
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    text = text.strip()

    try:
        data = json.loads(text)
        # Validate and normalize fields
        return {
            "suggested_hs_code": str(data.get("suggested_hs_code", "000000")),
            "suggested_tariff_percent": float(data.get("suggested_tariff_percent", 0.0)),
            "confidence_score": int(data.get("confidence_score", 0)),
            "reasoning_trace": list(data.get("reasoning_trace", [])),
            "fta_applicable": str(data.get("fta_applicable", "None")),
            "regulation_source": str(data.get("regulation_source", "")),
        }
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini JSON response: {e}")
        logger.debug(f"Raw response: {text}")
        return _fallback_response()


def _fallback_response() -> dict:
    """Return a safe fallback when parsing fails."""
    return {
        "suggested_hs_code": "000000",
        "suggested_tariff_percent": 0.0,
        "confidence_score": 0,
        "reasoning_trace": [
            "AI parsing error — manual review required.",
            "Could not extract structured response from Gemini.",
        ],
        "fta_applicable": "Unknown",
        "regulation_source": "",
    }


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────
def get_tariff_recommendation(
    product_description: str,
    part_number: str = "",
    country_of_origin: str = "",
    declared_value: float = 0.0,
    rag_context: str = "",
) -> dict:
    """
    Call Gemini API to get tariff recommendation.

    Args:
        product_description: Product text description
        part_number: Supplier part number
        country_of_origin: ISO country or full name
        declared_value: Monetary value in USD
        rag_context: Pre-formatted RAG context string

    Returns:
        {
            "suggested_hs_code": str,
            "suggested_tariff_percent": float,
            "confidence_score": int,
            "reasoning_trace": list[str],
            "fta_applicable": str,
            "regulation_source": str,
        }
    """
    if not GEMINI_API_KEY:
        logger.warning("No Gemini API key — returning demo response.")
        return _demo_response(product_description, country_of_origin)

    try:
        genai = _get_genai()
        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            generation_config={
                "temperature": 0.2,  # Low temperature for consistent structured output
                "top_p": 0.8,
                "max_output_tokens": 1024,
            },
        )

        prompt = build_prompt(
            product_description=product_description,
            part_number=part_number,
            country_of_origin=country_of_origin,
            declared_value=declared_value,
            rag_context=rag_context,
        )

        logger.info(f"Calling Gemini for: {product_description[:60]}")
        response = model.generate_content(prompt)
        result = _parse_gemini_response(response.text)
        logger.info(f"Gemini response — HS: {result['suggested_hs_code']}, Confidence: {result['confidence_score']}%")
        return result

    except EnvironmentError:
        return _demo_response(product_description, country_of_origin)
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return _fallback_response()


def _demo_response(description: str, origin: str) -> dict:
    """
    Demo fallback response when no API key is configured.
    Uses simple keyword matching for realistic demo behavior.
    """
    desc_lower = description.lower()

    # Simple keyword-based classification for demo
    if any(kw in desc_lower for kw in ["laptop", "notebook", "computer", "pc"]):
        hs_code, tariff = "847130", 0.0
    elif any(kw in desc_lower for kw in ["pcb", "printed circuit", "circuit board"]):
        hs_code, tariff = ("847330", 25.0) if "china" in origin.lower() else ("847330", 0.0)
    elif any(kw in desc_lower for kw in ["processor", "cpu", "integrated circuit", "semiconductor"]):
        hs_code, tariff = ("854231", 25.0) if "china" in origin.lower() else ("854231", 0.0)
    elif any(kw in desc_lower for kw in ["display", "lcd", "screen", "panel"]):
        hs_code, tariff = "901380", 0.0
    elif any(kw in desc_lower for kw in ["battery", "accumulator"]):
        hs_code, tariff = "850710", 27.5
    elif any(kw in desc_lower for kw in ["power supply", "converter", "psu"]):
        hs_code, tariff = "850440", 1.5
    else:
        hs_code, tariff = "847190", 0.0

    confidence = 88 if origin.lower() in ["malaysia", "mexico", "usa"] else 75

    return {
        "suggested_hs_code": hs_code,
        "suggested_tariff_percent": tariff,
        "confidence_score": confidence,
        "reasoning_trace": [
            f"Product analyzed: '{description[:60]}'",
            f"Origin country identified as {origin}",
            f"HS Code {hs_code} matches product category based on description keywords",
            f"Applicable tariff rate: {tariff}% based on origin-destination trade rules",
            "Demo mode — connect Gemini API key for full AI reasoning",
        ],
        "fta_applicable": "ITA Agreement" if tariff == 0.0 else "Section 301",
        "regulation_source": "https://hts.usitc.gov/",
    }
