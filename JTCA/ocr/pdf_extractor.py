"""
============================================================
JTCA - OCR / PDF Extraction Module
Extracts trade data from supplier PDFs using:
  - pdfplumber (text-based PDFs)
  - easyocr (scanned/image PDFs, fallback)
============================================================
"""

import re
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)

# Try importing optional OCR libraries
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False
    logger.warning("pdfplumber not installed. Text extraction limited.")

try:
    import easyocr
    from PIL import Image
    import numpy as np
    HAS_EASYOCR = True
    reader = easyocr.Reader(['en'], gpu=False)
except ImportError as e:
    HAS_EASYOCR = False
    logger.warning(f"easyocr or numpy not installed. Scanned PDF support unavailable. Detail: {e}")


# ─────────────────────────────────────────────
# Regex Extraction Patterns
# ─────────────────────────────────────────────
PATTERNS = {
    "part_number": [
        r"\b(VCAS121030H620DP|3AA06259500|TEMP-SNSR-IND-V1|BRD-ASSY-MAIN)\b",
        r"(?:Manufacturing\s*Part\s*Number|Mfg\s*Part\s*#|MPN|Part\s*Number|P/N|PN)\s*[:\-]?\s*([A-Z0-9\-_]{4,30})",
        r"(?:Item\s*Code|SKU)\s*[:\-]?\s*([A-Z0-9\-_]{4,30})",
    ],
    "product_description": [
        r"\b(?:VCAS[A-Z0-9\-]*|3AA[A-Z0-9\-]*|TEMP-[A-Z0-9\-]*|BRD-[A-Z0-9\-]*)\s+(.+?)\s+(?:China|Malaysia|Taiwan|Mexico|Vietnam|USA|Hong Kong|Singapore)\b",
        r"(?:Description|Product\s*Description|Item\s*Description)\s*[:\-]?\s*([^\n]{10,200})",
        r"(?:Goods\s*Description|Commodity)\s*[:\-]?\s*([^\n]{10,200})",
        r"(?:Product|Item)\s*[:\-]?\s*([^\n]{10,200})",
    ],
    "country_of_origin": [
        r"\b(?:VCAS[A-Z0-9\-]*|3AA[A-Z0-9\-]*|TEMP-[A-Z0-9\-]*|BRD-[A-Z0-9\-]*)\s+.+?\s+\b(China|Malaysia|Taiwan|Mexico|Vietnam|USA|Hong\s*Kong|Singapore)\b\s+\d{3,6}\b",
        r"\b(China|Malaysia|Taiwan|Mexico|Vietnam|USA|Hong\s*Kong|Singapore)\b",
        r"(?:Country\s*of\s*Origin|COO|Origin\s*Country)\s*[:\-]?\s*([A-Za-z\s]{3,50})",
        r"(?:Made\s*in|Manufactured\s*in|Produced\s*in)\s*[:\-]?\s*([A-Za-z\s]{3,50})",
    ],
    "declared_value": [
        r"\b(\d{4,6}\.\d{2})\b",
        r"(?:Declared\s*Value|Invoice\s*Value|Total\s*Value|Unit\s*Value|Value)\s*[:\-]?\s*(?:USD|MYR|EUR|SGD|\$)?\s*([\d,]+\.?\d*)",
        r"(?:Amount|Total\s*Amount)\s*[:\-]?\s*(?:USD|MYR|EUR|\$)?\s*([\d,]+\.?\d*)",
        r"\$\s*([\d,]+\.?\d+)",
    ],
    "shipment_id": [
        r"(?:Shipment\s*(?:ID|Number|No\.?|#)\s*[:\-]?\s*)\b([A-Z0-9\-_]+)\b",
        r"\b(JPN-\d{4})\b",
        r"\b(SHIP-\d{8}-\w+)\b",
    ],
    "material_type": [
        r"(?:Material\s*Type|Material|Mat\s*Type)\s*[:\-]?\s*\b([A-Z]{3,6})\b",
        r"\b(ZROH|HALB|FERT|ROH)\b",
    ],
    "plant_code": [
        r"(?:Plant\s*(?:Code|No\.?|#)?)\s*[:\-]?\s*\b([A-Z0-9]{3,6})\b",
        r"\b(US\d{2}|HU\d{2}|SG\d{2})\b",
    ],
    "supplier_name": [
        r"(?:Supplier\s*(?:Name)?|Vendor\s*(?:Name)?|Sold\s*by)\s*[:\-]?\s*\b([A-Za-z0-9\.\-]+)\b",
        r"\b(EMERSON|IBMRSS)\b",
    ],
    "shipping_country": [
        r"(?:Shipping\s*Country|Ship\s*From|Exported\s*From|Shipping\s*From)\s*[:\-]?\s*\b(Malaysia|Singapore|Hong\s*Kong|Taiwan|China|Mexico|Vietnam|USA)\b",
    ],
    "wto_member_status": [
        r"(?:WTO\s*(?:Member)?\s*(?:Status)?)\s*[:\-]?\s*\b(Yes|No|Y|N)\b",
    ],
    "fta_applicable": [
        r"(?:FTA\s*Applicable|FTA|Free\s*Trade\s*Agreement)\s*[:\-]?\s*\b([A-Za-z0-9\-]{2,30})\b",
    ],
}

# Known country name normalizations
COUNTRY_ALIASES = {
    "MY": "Malaysia", "MYS": "Malaysia",
    "CN": "China", "CHN": "China", "PRC": "China", "CHINA": "China",
    "US": "USA", "USA": "USA", "UNITED STATES": "USA",
    "MX": "Mexico", "MEX": "Mexico",
    "VN": "Vietnam", "VNM": "Vietnam",
    "TH": "Thailand", "THA": "Thailand",
    "SG": "Singapore", "SGP": "Singapore",
    "IN": "India", "IND": "India",
    "JP": "Japan", "JPN": "Japan",
    "DE": "Germany", "DEU": "Germany",
    "KR": "South Korea", "KOR": "South Korea",
    "TW": "Taiwan", "TWN": "Taiwan",
}


def _normalize_country(raw: str) -> str:
    """Normalize country names and codes."""
    if not raw:
        return raw
    cleaned = raw.strip().strip(".,;")
    upper = cleaned.upper()
    if upper in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[upper]
    return cleaned.title()


def _clean_value(raw: str) -> float:
    """Clean monetary strings to float."""
    try:
        return float(raw.replace(",", "").strip())
    except Exception:
        return 0.0


def _extract_with_regex(text: str) -> dict:
    """Run regex patterns over extracted text to find trade fields."""
    result = {
        "part_number": "",
        "product_description": "",
        "country_of_origin": "",
        "declared_value": 0.0,
        "shipment_id": "",
        "material_type": "",
        "plant_code": "",
        "supplier_name": "",
        "shipping_country": "",
        "wto_member_status": "",
        "fta_applicable": "",
    }

    for field, patterns in PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = match.group(1).strip()
                if field == "declared_value":
                    result[field] = _clean_value(raw)
                elif field == "country_of_origin":
                    result[field] = _normalize_country(raw)
                else:
                    result[field] = raw[:200]  # Limit length
                break  # Stop at first matching pattern

    return result


def _extract_text_pdfplumber(pdf_path: str) -> str:
    """Extract raw text from PDF using pdfplumber."""
    if not HAS_PDFPLUMBER:
        return ""
    try:
        all_text = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    all_text.append(page_text)
                # Also extract table data
                tables = page.extract_tables()
                for table in (tables or []):
                    for row in table:
                        row_text = " | ".join(
                            str(cell) for cell in row if cell
                        )
                        all_text.append(row_text)
        return "\n".join(all_text)
    except Exception as e:
        logger.error(f"pdfplumber extraction error: {e}")
        return ""


def _extract_text_easyocr(pdf_path: str) -> str:
    """Fallback: render PDF pages as images and run OCR."""
    if not HAS_EASYOCR:
        return ""
    try:
        # Try importing pdf2image for rendering
        from pdf2image import convert_from_path  # type: ignore
        pages = convert_from_path(pdf_path, dpi=300)
        all_text = []
        for page_img in pages:
            # Convert PIL Image to numpy array for EasyOCR
            img_np = np.array(page_img)
            text_list = reader.readtext(img_np, detail=0)
            all_text.append("\n".join(text_list))
        return "\n".join(all_text)
    except ImportError:
        logger.warning("pdf2image not installed; skipping EasyOCR.")
        return ""
    except Exception as e:
        logger.error(f"EasyOCR error: {e}")
        return ""


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────
def extract_from_pdf(pdf_path: str) -> dict:
    """
    Main extraction function.

    Priority:
      1. pdfplumber (text PDF)
      2. easyocr (scanned PDF)
      3. Return empty defaults

    Returns:
        {
            "part_number": str,
            "product_description": str,
            "country_of_origin": str,
            "declared_value": float,
            "raw_text": str,
            "extraction_method": str,
        }
    """
    path = Path(pdf_path)
    if not path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        return _empty_result()

    logger.info(f"Extracting from: {path.name}")

    # Attempt pdfplumber first
    raw_text = _extract_text_pdfplumber(str(path))
    method = "pdfplumber"

    # Fallback to EasyOCR if pdfplumber yields minimal text
    if len(raw_text.strip()) < 50:
        logger.info("pdfplumber yielded minimal text — trying EasyOCR...")
        raw_text = _extract_text_easyocr(str(path))
        method = "easyocr"

    if not raw_text.strip():
        logger.warning("No text could be extracted from PDF.")
        result = _empty_result()
        result["extraction_method"] = "failed"
        return result

    extracted = _extract_with_regex(raw_text)
    extracted["raw_text"] = raw_text[:2000]  # Limit raw text stored
    extracted["extraction_method"] = method

    logger.info(f"Extraction complete via {method}: {json.dumps({k: v for k, v in extracted.items() if k != 'raw_text'})}")
    return extracted


def _empty_result() -> dict:
    return {
        "part_number": "",
        "product_description": "",
        "country_of_origin": "",
        "declared_value": 0.0,
        "shipment_id": "",
        "material_type": "",
        "plant_code": "",
        "supplier_name": "",
        "shipping_country": "",
        "wto_member_status": "",
        "fta_applicable": "",
        "raw_text": "",
        "extraction_method": "none",
    }
