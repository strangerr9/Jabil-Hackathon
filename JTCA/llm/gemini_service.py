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
from datetime import datetime
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
Your task is to analyze product information and recommend the most accurate HS Code, tariff rate, and confidence score, as well as extract key trade fields.

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
  "fta_applicable": "FTA name or None (e.g., ACFTA, CSFTA, Domestic, No)",
  "regulation_source": "URL or reference",
  "shipment_id": "JPN-XXXX",
  "material_type": "ZROH / HALB / FERT / etc.",
  "plant_code": "US02 / HU07 / etc.",
  "supplier_name": "Supplier name",
  "shipping_country": "Shipping country",
  "wto_member_status": "Yes / No"
}

Rules:
- confidence_score must be an integer 0-100
- suggested_tariff_percent must be a number (e.g., 5.0, 25.0, 0.0)
- suggested_hs_code must be 6-digit string
- reasoning_trace must be a list of 3-5 strings explaining your decision
- If origin country has an FTA with the destination, note it in fta_applicable
- If fields like shipment_id, material_type, plant_code, supplier_name, shipping_country, or wto_member_status are mentioned or can be inferred from the document description/text, extract them. Otherwise, default them sensibly based on standard Jabil trade practices (e.g., Material: ZROH, Plant: US02, Supplier: EMERSON, Shipping Country: Malaysia, WTO: Yes).
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
            "shipment_id": str(data.get("shipment_id", "")),
            "material_type": str(data.get("material_type", "ZROH")),
            "plant_code": str(data.get("plant_code", "US02")),
            "supplier_name": str(data.get("supplier_name", "EMERSON")),
            "shipping_country": str(data.get("shipping_country", "Malaysia")),
            "wto_member_status": str(data.get("wto_member_status", "Yes")),
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
        "shipment_id": "",
        "material_type": "ZROH",
        "plant_code": "US02",
        "supplier_name": "EMERSON",
        "shipping_country": "Malaysia",
        "wto_member_status": "Yes",
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
        hs_code, tariff, material = "847130", 0.0, "ZROH"
    elif any(kw in desc_lower for kw in ["pcb", "printed circuit", "circuit board"]):
        hs_code, tariff, material = ("847330", 25.0, "HALB") if "china" in origin.lower() else ("847330", 0.0, "HALB")
    elif any(kw in desc_lower for kw in ["processor", "cpu", "integrated circuit", "semiconductor"]):
        hs_code, tariff, material = ("854231", 25.0, "ZROH") if "china" in origin.lower() else ("854231", 0.0, "ZROH")
    elif any(kw in desc_lower for kw in ["display", "lcd", "screen", "panel"]):
        hs_code, tariff, material = "901380", 0.0, "FERT"
    elif any(kw in desc_lower for kw in ["battery", "accumulator"]):
        hs_code, tariff, material = "850710", 27.5, "ZROH"
    elif any(kw in desc_lower for kw in ["power supply", "converter", "psu"]):
        hs_code, tariff, material = "850440", 1.5, "ZROH"
    elif any(kw in desc_lower for kw in ["suppresor", "voltage"]):
        hs_code, tariff, material = "8533400000", 0.0, "ZROH"
    elif any(kw in desc_lower for kw in ["sensor", "temperature"]):
        hs_code, tariff, material = "902519", 0.0, "FERT"
    else:
        hs_code, tariff, material = "847190", 0.0, "ZROH"

    confidence = 88 if origin.lower() in ["malaysia", "mexico", "usa"] else 75

    # Match supplier and plant code based on product description keyword
    supplier = "EMERSON" if "sensor" in desc_lower or "suppresor" in desc_lower else "IBMRSS"
    plant = "HU07" if "sensor" in desc_lower or "monitor" in desc_lower else ("SG23" if "pcb" in desc_lower or "circuit" in desc_lower else "US02")

    ship_id = "JPN-1005" if "suppresor" in desc_lower else ("JPN-1007" if "monitor" in desc_lower else ("JPN-1001" if "sensor" in desc_lower else "JPN-1002"))

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
        "fta_applicable": "ACFTA" if "suppresor" in desc_lower else ("CSFTA" if "sensor" in desc_lower else ("Domestic" if "pcb" in desc_lower else "No")),
        "regulation_source": "https://hts.usitc.gov/",
        "shipment_id": ship_id,
        "material_type": material,
        "plant_code": plant,
        "supplier_name": supplier,
        "shipping_country": "Malaysia" if origin.lower() != "taiwan" else "Hong Kong",
        "wto_member_status": "Yes",
    }


def extract_rules_from_text(text: str, origin: str) -> list[dict]:
    """
    Call Gemini API to extract structured tariff rules from crawled document text.
    Returns a list of dicts formatted for database insertion.
    """
    if not GEMINI_API_KEY:
        logger.warning("No Gemini API key for crawler parsing — using regex fallback.")
        return []

    prompt = f"""You are an expert trade compliance data extraction specialist.
Analyze the following crawled web page / document content and extract a list of import tariff rules.

For each rule, extract:
- hs_code: 6-digit HS Code string
- product_description: description of the product or product category
- tariff_percent: Float tariff percentage rate (e.g., 2.5, 0.0, 25.0)
- fta_name: Name of the free trade agreement or trade program (e.g. ACFTA, USMCA, MFN, General, None)

Response format:
You MUST respond with ONLY a valid JSON list of objects — no markdown, no explanation outside the JSON.
Format example:
[
  {{
    "hs_code": "854233",
    "product_description": "Electronic integrated circuits, amplifiers",
    "tariff_percent": 25.0,
    "fta_name": "Section 301"
  }}
]

If no rules are found in the text, return an empty list: [].

=== CRAWLED TEXT ===
{text[:30000]}
"""

    try:
        genai = _get_genai()
        model = genai.GenerativeModel(MODEL_NAME)
        # Use low temperature for deterministic parsing
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.0}
        )
        resp_text = response.text.strip()
        # Clean markdown wrappers if present
        resp_text = re.sub(r"^```(?:json)?\s*", "", resp_text, flags=re.MULTILINE)
        resp_text = re.sub(r"\s*```$", "", resp_text, flags=re.MULTILINE)
        resp_text = resp_text.strip()
        
        extracted = json.loads(resp_text)
        if isinstance(extracted, list):
            rules = []
            for item in extracted:
                hs = str(item.get("hs_code", "")).strip().replace(".", "")[:6]
                if not hs.isdigit() or len(hs) < 4:
                    continue
                rules.append({
                    "hs_code": hs,
                    "product_description": str(item.get("product_description", ""))[:200],
                    "origin_country": origin,
                    "destination_country": "USA",
                    "tariff_percent": float(item.get("tariff_percent", 0.0)),
                    "fta_name": str(item.get("fta_name", "Web Extract")),
                    "regulation_source": "Web Crawl",
                    "last_updated": datetime.now().isoformat(),
                })
            logger.info(f"Successfully extracted {len(rules)} structured rules from crawled text using Gemini.")
            return rules
        return []
    except Exception as e:
        logger.error(f"Failed to extract rules using Gemini: {e}")
        return []

