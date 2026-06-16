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
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash")

# ─────────────────────────────────────────────
# Gemini Client (lazy init)
# ─────────────────────────────────────────────
_client = None


def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY not set. Check your .env file.")
            raise EnvironmentError("GEMINI_API_KEY is not configured.")
        try:
            from google import genai
            _client = genai.Client(api_key=GEMINI_API_KEY)
            logger.info("Google GenAI client configured.")
        except ImportError:
            logger.error("google-genai not installed.")
            raise
    return _client


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
- CRITICAL: You must ONLY recommend an HS Code if it is explicitly present in the retrieved "TARIFF KNOWLEDGE BASE CONTEXT" above. If the context is empty or does not contain a suitable HS Code for the product, you MUST return HS Code "000000" and confidence_score 0 to route it for manual human review. Do NOT use your general pre-trained knowledge to suggest or invent HS codes that are not in the retrieved context.
"""


def build_prompt(
    product_description: str,
    part_number: str,
    country_of_origin: str,
    destination_country: str,
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
Destination Country: {destination_country}
Declared Value: USD {declared_value:,.2f}

{rag_context}

=== TASK ===
Based on the shipment information and the retrieved tariff knowledge base context above,
provide your HS Code classification and tariff recommendation.

Respond with ONLY the JSON object.
"""


# ─────────────────────────────────────────────
# Response Parser
def _parse_partial_json(text: str) -> dict:
    """
    Attempt to extract fields using regex if JSON parsing fails.
    This is extremely useful when responses are truncated but contain valid fields.
    """
    # Initialize with default fallback values
    data = {
        "suggested_hs_code": "000000",
        "suggested_tariff_percent": 0.0,
        "confidence_score": 0,
        "reasoning_trace": ["Partial classification recovered from truncated response."],
        "fta_applicable": "Unknown",
        "regulation_source": "",
        "shipment_id": "",
        "material_type": "ZROH",
        "plant_code": "US02",
        "supplier_name": "EMERSON",
        "shipping_country": "Malaysia",
        "wto_member_status": "Yes",
    }
    
    # Regex patterns for key-value extraction (supports quotes, single quotes, or bare numbers)
    patterns = {
        "suggested_hs_code": r'"suggested_hs_code"\s*:\s*["\']?(\d+)["\']?',
        "suggested_tariff_percent": r'"suggested_tariff_percent"\s*:\s*["\']?([\d.]+)["\']?',
        "confidence_score": r'"confidence_score"\s*:\s*["\']?(\d+)["\']?',
        "fta_applicable": r'"fta_applicable"\s*:\s*["\']?([^"\']*)["\']?',
        "regulation_source": r'"regulation_source"\s*:\s*["\']?([^"\']*)["\']?',
        "shipment_id": r'"shipment_id"\s*:\s*["\']?([^"\']*)["\']?',
        "material_type": r'"material_type"\s*:\s*["\']?([^"\']*)["\']?',
        "plant_code": r'"plant_code"\s*:\s*["\']?([^"\']*)["\']?',
        "supplier_name": r'"supplier_name"\s*:\s*["\']?([^"\']*)["\']?',
        "shipping_country": r'"shipping_country"\s*:\s*["\']?([^"\']*)["\']?',
        "wto_member_status": r'"wto_member_status"\s*:\s*["\']?([^"\']*)["\']?',
    }
    
    for field, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            val = match.group(1).strip()
            if field == "suggested_tariff_percent":
                try:
                    data[field] = float(val)
                except ValueError:
                    pass
            elif field == "confidence_score":
                try:
                    data[field] = int(val)
                except ValueError:
                    pass
            else:
                data[field] = val
                
    # If suggested_hs_code was successfully recovered but confidence remains 0,
    # set a reasonable non-zero confidence score for manual review rather than discarding it.
    if data["suggested_hs_code"] != "000000" and data["confidence_score"] == 0:
        data["confidence_score"] = 50  # Moderate confidence for partial parsing
        data["reasoning_trace"].append("Note: Response was truncated; confidence score set to 50% for manual review.")
        
    return data


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
        logger.error(f"Raw response: {repr(text)}")
        # Try to parse partially before falling back entirely
        parsed_partial = _parse_partial_json(text)
        if parsed_partial["suggested_hs_code"] != "000000":
            logger.info(f"Successfully recovered partial classification from truncated response: HS={parsed_partial['suggested_hs_code']}")
            return parsed_partial
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


class TariffRecommendation(BaseModel):
    suggested_hs_code: str
    suggested_tariff_percent: float
    confidence_score: int
    reasoning_trace: List[str]
    fta_applicable: str
    regulation_source: str
    shipment_id: str
    material_type: str
    plant_code: str
    supplier_name: str
    shipping_country: str
    wto_member_status: str


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────
def get_tariff_recommendation(
    product_description: str,
    part_number: str = "",
    country_of_origin: str = "",
    destination_country: str = "Malaysia",
    declared_value: float = 0.0,
    rag_context: str = "",
) -> dict:
    """
    Call Gemini API to get tariff recommendation.

    Args:
        product_description: Product text description
        part_number: Supplier part number
        country_of_origin: ISO country or full name
        destination_country: Country of import/destination
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
        return _demo_response(product_description, country_of_origin, destination_country)

    try:
        client = _get_client()
        from google.genai import types

        prompt = build_prompt(
            product_description=product_description,
            part_number=part_number,
            country_of_origin=country_of_origin,
            destination_country=destination_country,
            declared_value=declared_value,
            rag_context=rag_context,
        )

        logger.info(f"Calling Gemini for: {product_description[:60]}")
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                top_p=0.8,
                max_output_tokens=2048,
                response_mime_type="application/json",
                response_schema=TariffRecommendation,
            ),
        )
        result = _parse_gemini_response(response.text)
        logger.info(f"Gemini response — HS: {result['suggested_hs_code']}, Confidence: {result['confidence_score']}%")
        return result

    except EnvironmentError:
        return _demo_response(product_description, country_of_origin, destination_country)
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return _fallback_response()


def _demo_response(description: str, origin: str, destination: str = "Malaysia") -> dict:
    """
    Demo fallback response when no API key is configured.
    Uses simple keyword matching for realistic demo behavior.
    """
    desc_lower = description.lower()
    origin_lower = origin.lower().strip()
    dest_lower = destination.lower().strip()

    # List of ASEAN member states
    asean_countries = {
        "brunei", "cambodia", "indonesia", "laos", "malaysia",
        "myanmar", "philippines", "singapore", "thailand", "vietnam"
    }

    # Determine FTA applicability dynamically based on origin and destination
    if origin_lower and dest_lower:
        if origin_lower == dest_lower:
            fta = "Domestic"
        elif (origin_lower == "china" and dest_lower in asean_countries) or (dest_lower == "china" and origin_lower in asean_countries):
            if dest_lower == "singapore" or origin_lower == "singapore":
                fta = "CSFTA"
            else:
                fta = "ACFTA"
        elif (origin_lower == "japan" and dest_lower in ["germany", "france", "italy", "spain", "netherlands", "poland"]) or \
             (dest_lower == "japan" and origin_lower in ["germany", "france", "italy", "spain", "netherlands", "poland"]):
            fta = "EU-Japan EPA"
        else:
            fta = "No"
    else:
        # Keyword-based fallback for backward compatibility
        fta = "ACFTA" if "suppresor" in desc_lower else ("CSFTA" if "sensor" in desc_lower else ("Domestic" if "pcb" in desc_lower else "No"))

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

    confidence = 88 if origin_lower in ["malaysia", "mexico", "usa"] or origin_lower in asean_countries else 75

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
            f"Origin: {origin} | Destination: {destination}",
            f"HS Code {hs_code} matches product category based on description keywords",
            f"Trade Agreement: {fta} applied for {origin} -> {destination}",
            "Demo mode — connect Gemini API key for full AI reasoning",
        ],
        "fta_applicable": fta,
        "regulation_source": "https://fta.miti.gov.my/" if fta == "ACFTA" else "https://hts.usitc.gov/",
        "shipment_id": ship_id,
        "material_type": material,
        "plant_code": plant,
        "supplier_name": supplier,
        "shipping_country": destination,
        "wto_member_status": "Yes",
    }


class ExtractedTariffRule(BaseModel):
    hs_code: str
    product_description: str
    tariff_percent: float
    fta_name: str


def extract_rules_from_text(text: str, origin: str, destination: str = "Global", fta_name: str = "Web Extract") -> list[dict]:
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
        client = _get_client()
        from google.genai import types

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=List[ExtractedTariffRule],
            )
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
                    "destination_country": destination,
                    "tariff_percent": float(item.get("tariff_percent", 0.0)),
                    "fta_name": fta_name or str(item.get("fta_name", "Web Extract")),
                    "regulation_source": "Web Crawl",
                    "last_updated": datetime.now().isoformat(),
                })
            logger.info(f"Successfully extracted {len(rules)} structured rules from crawled text using Gemini.")
            return rules
        return []
    except Exception as e:
        logger.error(f"Failed to extract rules using Gemini: {e}")
        return []


def ask_assistant_question(query: str, rag_context: str) -> str:
    """
    Sends the user's natural language question and RAG context to Gemini to get a friendly conversational reply.
    """
    if not GEMINI_API_KEY:
        return _demo_assistant_response(query)

    system_instructions = (
        "You are an expert trade compliance assistant named JTCA Compliance Assistant. "
        "Your goal is to help users find HS Codes, product descriptions, and trade agreements (FTAs) "
        "applicable to their query. Use the retrieved regulations context below to provide accurate, "
        "compliance-based recommendations.\n\n"
        "If the context does not contain enough information to resolve the query, state this clearly, but try to suggest the closest matches if possible. "
        "Be helpful, professional, and clear. Format your response in clean Markdown. "
        "Always highlight the HS code, tariff percentage, and trade agreement/FTA name clearly (e.g., using bold text or bullet points)."
    )

    prompt = f"""{system_instructions}

=== RETRIEVED REGULATIONS CONTEXT ===
{rag_context}

=== USER QUERY ===
{query}

Provide your response in clear markdown format. Avoid general chat boilerplate; start directly with the analysis/answers.
"""

    try:
        client = _get_client()
        logger.info(f"Calling Gemini assistant for query: '{query[:50]}'")
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini assistant API error: {e}")
        return f"Error communicating with Gemini: {e}\n\nHere is a local search of retrieved regulations:\n\n{rag_context}"


def _demo_assistant_response(query: str) -> str:
    """
    Demo fallback assistant response when no API key is configured.
    Uses keyword matching for realistic simulation.
    """
    query_lower = query.lower()
    
    response = "### 🤖 JTCA Compliance Assistant (Demo Mode)\n\n"
    response += "> **Note**: Gemini API key is not configured. Running in local simulation mode.\n\n"
    
    if "pcb" in query_lower or "printed circuit" in query_lower or "circuit board" in query_lower:
        response += (
            "Based on the knowledge base, here are the recommendations for **Printed Circuit Boards (PCB / PCBA)**:\n\n"
            "- **Suggested HS Code**: `8473.30`\n"
            "- **Description**: Parts and accessories of automatic data processing machines, printed circuit boards.\n"
            "- **Tariff Rates & Agreements**:\n"
            "  - **Origin: Malaysia -> Destination: USA**:\n"
            "    - Tariff: **0.0%** under the **ITA Agreement** (Information Technology Agreement).\n"
            "  - **Origin: China -> Destination: USA**:\n"
            "    - Tariff: **25.0%** under the **Section 301 Tariff**.\n\n"
            "**Compliance Notes**:\n"
            "Ensure that you have proper certificate of origin documents to claim the 0% rate under the ITA. "
            "Shipments from China are subject to the additional Section 301 duties unless an exclusion applies."
        )
    elif "laptop" in query_lower or "notebook" in query_lower or "computer" in query_lower:
        response += (
            "Here is the classification and trade agreement info for **Laptop / Notebook Computers**:\n\n"
            "- **Suggested HS Code**: `8471.30`\n"
            "- **Description**: Portable automatic data processing machines, weighing not more than 10 kg.\n"
            "- **Tariff Rates & Agreements**:\n"
            "  - **Origin: Malaysia -> Destination: USA**:\n"
            "    - Tariff: **0.0%** under **USMCA / General MFN**.\n"
            "  - **Origin: Vietnam -> Destination: Malaysia**:\n"
            "    - Tariff: **0.0%** under the **ATIGA** (ASEAN Trade in Goods Agreement).\n\n"
            "**Compliance Notes**:\n"
            "Laptops generally benefit from duty-free status in most major jurisdictions under WTO ITA or bilateral trade agreements."
        )
    elif "processor" in query_lower or "cpu" in query_lower or "integrated circuit" in query_lower:
        response += (
            "Here are the details for **Processors / CPUs / Integrated Circuits**:\n\n"
            "- **Suggested HS Code**: `8542.31`\n"
            "- **Description**: Electronic integrated circuits, processors and controllers.\n"
            "- **Tariff Rates & Agreements**:\n"
            "  - **Origin: Malaysia -> Destination: USA**:\n"
            "    - Tariff: **0.0%** under the **ITA Agreement**.\n"
            "  - **Origin: China -> Destination: USA**:\n"
            "    - Tariff: **25.0%** under **Section 301**.\n\n"
            "**Compliance Notes**:\n"
            "Integrated circuits are high-priority items under dual-use export control laws (ECCN classification might be required in addition to HS Code)."
        )
    elif "battery" in query_lower or "accumulator" in query_lower:
        response += (
            "Here is the compliance details for **Electrical Batteries / Accumulators**:\n\n"
            "- **Suggested HS Code**: `8507.10`\n"
            "- **Description**: Lead-acid accumulators, of a kind used for starting piston engines.\n"
            "- **Tariff Rates & Agreements**:\n"
            "  - **Origin: Malaysia -> Destination: USA**:\n"
            "    - Tariff: **27.5%** under General **MFN Rate**.\n\n"
            "**Compliance Notes**:\n"
            "Batteries are classified as Hazardous Materials (Class 9) for shipping and require proper MSDS documentation."
        )
    elif "power supply" in query_lower or "psu" in query_lower or "converter" in query_lower:
        response += (
            "Here is the tariff and agreement classification for **Static Converters / Power Supply Units (PSU)**:\n\n"
            "- **Suggested HS Code**: `8504.40`\n"
            "- **Description**: Static converters, power supply units, switching power supply.\n"
            "- **Tariff Rates & Agreements**:\n"
            "  - **Origin: Malaysia -> Destination: USA**:\n"
            "    - Tariff: **1.5%** under General **MFN Rate**.\n\n"
            "**Compliance Notes**:\n"
            "No specific trade agreements apply for Malaysia to USA other than MFN. Standard customs declaration applies."
        )
    elif "sensor" in query_lower:
        response += (
            "Here are the details for **Sensors / Temperature Sensors**:\n\n"
            "- **Suggested HS Code**: `9025.19` or `9031.80`\n"
            "- **Description**: Liquid-in glass thermometers, other instruments.\n"
            "- **Tariff Rates & Agreements**:\n"
            "  - **Origin: Japan -> Destination: Singapore**:\n"
            "    - Tariff: **0.0%** under **CSFTA** (Japan-Singapore Agreement).\n\n"
            "**Compliance Notes**:\n"
            "Temperature instruments are subject to technical standard certifications in some destinations."
        )
    elif "agreement" in query_lower or "fta" in query_lower or "acfta" in query_lower or "usmca" in query_lower:
        response += (
            "The knowledge base contains several reference **Free Trade Agreements (FTAs)**:\n\n"
            "1. **ACFTA** (ASEAN-China Free Trade Area): Reduces tariffs to 0% for most trade between China and ASEAN members (like Malaysia).\n"
            "2. **USMCA** (United States-Mexico-Canada Agreement): Facilitates duty-free trade in North America.\n"
            "3. **ITA Agreement** (Information Technology Agreement): A WTO agreement that eliminates duties on IT and electronics products globally.\n"
            "4. **ATIGA** (ASEAN Trade in Goods Agreement): Eliminates tariffs on intra-ASEAN trade.\n\n"
            "Specify the product name and route (e.g. *China to Malaysia*) to check details."
        )
    else:
        response += (
            f"I received your query: *\"{query}\"*\n\n"
            "No specific match was found in the demo dataset. Here is what I can help you find:\n"
            "- **HS Codes & Tariffs** for `PCB`, `Laptop`, `Processor`, `Battery`, `Power Supply`, `Sensor`.\n"
            "- **Agreements** like `ACFTA`, `USMCA`, `ATIGA`, `ITA`.\n\n"
            "Try asking: *\"What is the HS Code and agreement for PCBs?\"* or *\"Tell me about ACFTA\"*.\n\n"
            "*(For fully customized answers, please add a valid `GEMINI_API_KEY` in the `.env` file)*"
        )
        
    return response


