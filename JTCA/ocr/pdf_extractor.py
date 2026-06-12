"""
============================================================
JTCA - OCR / PDF Extraction Module
Extracts trade data from supplier PDFs using:
  - pdfplumber (text-based PDFs)
  - pytesseract (scanned/image PDFs, fallback)
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
    import pytesseract
    from PIL import Image
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
    logger.warning("pytesseract not installed. Scanned PDF support unavailable.")


# ─────────────────────────────────────────────
# Regex Extraction Patterns
# ─────────────────────────────────────────────
PATTERNS = {
    "part_number": [
        r"(?:Part\s*(?:Number|No\.?|#)\s*[:\-]?\s*)([A-Z0-9\-_]{4,30})",
        r"(?:P/N|PN)\s*[:\-]?\s*([A-Z0-9\-_]{4,30})",
        r"(?:Item\s*Code|SKU)\s*[:\-]?\s*([A-Z0-9\-_]{4,30})",
    ],
    "product_description": [
        r"(?:Description|Product\s*Description|Item\s*Description)\s*[:\-]?\s*([^\n]{10,200})",
        r"(?:Goods\s*Description|Commodity)\s*[:\-]?\s*([^\n]{10,200})",
        r"(?:Product|Item)\s*[:\-]?\s*([^\n]{10,200})",
    ],
    "country_of_origin": [
        r"(?:Country\s*of\s*Origin|COO|Origin\s*Country)\s*[:\-]?\s*([A-Za-z\s]{3,50})",
        r"(?:Made\s*in|Manufactured\s*in|Produced\s*in)\s*[:\-]?\s*([A-Za-z\s]{3,50})",
        r"(?:Origin)\s*[:\-]?\s*([A-Za-z\s]{3,50})",
    ],
    "declared_value": [
        r"(?:Declared\s*Value|Invoice\s*Value|Total\s*Value|Unit\s*Value|Value)\s*[:\-]?\s*(?:USD|MYR|EUR|SGD|\$)?\s*([\d,]+\.?\d*)",
        r"(?:Amount|Total\s*Amount)\s*[:\-]?\s*(?:USD|MYR|EUR|\$)?\s*([\d,]+\.?\d*)",
        r"\$\s*([\d,]+\.?\d+)",
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


def _extract_text_tesseract(pdf_path: str) -> str:
    """Fallback: render PDF pages as images and run OCR."""
    if not HAS_TESSERACT:
        return ""
    try:
        # Try importing pdf2image for rendering
        from pdf2image import convert_from_path  # type: ignore
        pages = convert_from_path(pdf_path, dpi=300)
        all_text = []
        for page_img in pages:
            text = pytesseract.image_to_string(page_img)
            all_text.append(text)
        return "\n".join(all_text)
    except ImportError:
        logger.warning("pdf2image not installed; skipping Tesseract OCR.")
        return ""
    except Exception as e:
        logger.error(f"Tesseract OCR error: {e}")
        return ""


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────
def extract_from_pdf(pdf_path: str) -> dict:
    """
    Main extraction function.

    Priority:
      1. pdfplumber (text PDF)
      2. pytesseract (scanned PDF)
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

    # Fallback to Tesseract if pdfplumber yields minimal text
    if len(raw_text.strip()) < 50:
        logger.info("pdfplumber yielded minimal text — trying Tesseract OCR...")
        raw_text = _extract_text_tesseract(str(path))
        method = "tesseract"

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
        "raw_text": "",
        "extraction_method": "none",
    }
