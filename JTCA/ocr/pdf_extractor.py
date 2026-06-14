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
except ImportError as e:
    HAS_EASYOCR = False
    logger.warning(f"easyocr or PIL/numpy not installed. Scanned PDF support unavailable. Detail: {e}")

# EasyOCR reader is lazy-loaded on first use to avoid slow startup
_easyocr_reader = None

def _get_easyocr_reader():
    """Lazy-load EasyOCR reader only when actually needed."""
    global _easyocr_reader
    if _easyocr_reader is None:
        logger.info("[OCR] Loading EasyOCR reader (first use)...")
        _easyocr_reader = easyocr.Reader(['en'], gpu=False)
        logger.info("[OCR] EasyOCR reader ready.")
    return _easyocr_reader


# ─────────────────────────────────────────────
# Regex Extraction Patterns
# ─────────────────────────────────────────────

# Expanded list of countries for matching in table columns
_COUNTRIES = (
    r"Germany|China|Malaysia|Japan|USA|United\s*States|Taiwan|Mexico|Vietnam|"
    r"Singapore|Thailand|South\s*Korea|India|France|United\s*Kingdom|UK|"
    r"Indonesia|Philippines|Brazil|Netherlands|Poland|Czech\s*Republic|"
    r"Hungary|Italy|Spain|Hong\s*Kong|Australia|Canada|Turkey|Israel"
)

PATTERNS = {
    "part_number": [
        # Explicit label first (most reliable) - require separator
        r"(?i)(?:Manufacturing[^\S\n]*Part[^\S\n]*(?:Number|#)|Mfg\.?[^\S\n]*Part[^\S\n]*#|MPN|Part[^\S\n]*(?:Number|No\.?|#)|P/N)[^\S\n]*[:\-][^\S\n]*([A-Z0-9][A-Z0-9\-_.]{3,30})",
        r"(?i)(?:Item[^\S\n]*Code|SKU)[^\S\n]*[:\-][^\S\n]*([A-Z0-9][A-Z0-9\-_.]{3,30})",
        # Tab-separated table: first column is part#
        r"^([A-Z][A-Z0-9\-_.]{2,30})\t",
        # Single-space table row: ALL-CAPS part# at line start, followed by mixed-case description
        # Must NOT be a known invoice label word (Shipment, Supplier, Invoice, Plant, Footer...)
        r"^(?!(?:Shipment|Supplier|Invoice|Plant|Material|Shipping|Country|WTO|FTA|Footer|Compliance|Generated|Page)\b)([A-Z][A-Z0-9\-]{2,30})(?=\s+[A-Z][a-z])",
    ],
    "product_description": [
        # Explicit label — [^\S\n]* prevents crossing newlines - require separator
        r"(?i)(?:Product[^\S\n]*Description|Item[^\S\n]*Description|Description[^\S\n]*of[^\S\n]*Goods|Goods[^\S\n]*Description|Commodity)[^\S\n]*[:\-][^\S\n]*([^\n]{10,200})",
        # Tab-separated table: 2nd column (after part# tab)
        r"^[A-Z][A-Z0-9\-_.]{2,30}\t([^\t\n]{5,200})\t",
        # Single-space table: part# space Description space COUNTRY space value
        # Use lookahead: description ends right before a known country word
        r"^[A-Z][A-Z0-9\-]{2,30}\s+([A-Za-z][A-Za-z0-9 \-/,&]{3,120})(?=\s+(?:" + _COUNTRIES + r")\s+[\d])",
        # Generic label fallback — must have colon separator
        r"(?i)(?:Description|Product|Item)[^\S\n]*:[^\S\n]*([^\n]{10,200})",
    ],
    "country_of_origin": [
        # Explicit label — [^\S\n]* prevents crossing newlines - require separator
        r"(?i)(?:Country[^\S\n]*of[^\S\n]*Origin|COO|Origin[^\S\n]*Country)[^\S\n]*[:\-][^\S\n]*([A-Za-z][A-Za-z ]{2,30}?)(?:\n|$|,|\|)",
        r"(?i)(?:Made[^\S\n]*in|Manufactured[^\S\n]*in|Produced[^\S\n]*in)[^\S\n]*[:\-][^\S\n]*([A-Za-z][A-Za-z ]{2,30})(?:\n|$|,)",
        # Tab-separated table: 3rd column
        r"^[A-Z][A-Z0-9\-_.]{2,30}\t[^\t\n]{5,200}\t(" + _COUNTRIES + r")(?:\t|\n|$)",
        # Single-space table: country right before a numeric value (the declared value)
        r"^[A-Z][A-Z0-9\-]{2,30}\s+[A-Za-z][A-Za-z0-9 \-/,&]{3,120}\s+(" + _COUNTRIES + r")\s+[\d]",
        # Broad standalone country (last resort)
        r"(?i)\b(" + _COUNTRIES + r")\b",
    ],
    "declared_value": [
        # Currency prefix e.g. $12,450.00
        r"\$\s*([\d,]+\.\d{2})\b",
        # Number followed by currency suffix e.g. "12,450.00 USD"
        r"(?i)([\d,]+\.\d{2})\s*(?:USD|EUR|MYR|SGD|GBP|JPY)\b",
        # Currency prefix without $ e.g. "USD 12,450.00"
        r"(?i)(?:USD|EUR|MYR|SGD|GBP)\s+([\d,]+\.\d{2})\b",
        # Single-space table: number at end of data row (after country)
        r"(?i)(?:" + _COUNTRIES + r")\s+([\d,]+\.\d{2})\b",
        # Explicit label
        r"(?i)(?:Declared[^\S\n]*Value|Invoice[^\S\n]*Value|Total[^\S\n]*Value|Unit[^\S\n]*(?:Price|Value)|Value)[^\S\n]*[:\-][^\S\n]*(?:USD|MYR|EUR|SGD|GBP|JPY|\$|\u20ac|\u00a3)?[^\S\n]*([\d,]+\.?\d*)",
        # Bare number like 12,450.00 or 12000.00
        r"\b(\d{1,6},\d{3}\.\d{2})\b",
        r"\b(\d{3,7}\.\d{2})\b",
    ],
    "shipment_id": [
        r"(?i)(?:Shipment\s*(?:ID|Number|No\.?|#))\s*[:\-]?\s*([A-Z]{2,6}[-][0-9]{3,8})",
        r"\b([A-Z]{2,6}-\d{3,8})\b",  # e.g. DEU-8842
        r"\b(SHIP-\d{8}-\w+)\b",
    ],
    "material_type": [
        r"(?i)(?:Material\s*Type|Material|Mat\.?\s*Type)\s*[:\-]?\s*\b([A-Z]{3,6})\b",
        r"\b(ZROH|HALB|FERT|ROH|ZHAL|HAWA|NLAG)\b",
    ],
    "plant_code": [
        # Explicit label — any 2 letters + 2 digits: EU09, US02, SG01, HU10
        r"(?i)(?:Plant\s*(?:Code|No\.?|#)?)\s*[:\-]?\s*\b([A-Z]{2}\d{2})\b",
    ],
    "supplier_name": [
        # [^\S\n]* prevents crossing to next line
        r"(?i)(?:Supplier[^\S\n]*(?:Name)?|Vendor[^\S\n]*(?:Name)?|Sold[^\S\n]*by|Manufacturer)[^\S\n]*[:\-][^\S\n]*([A-Za-z0-9][A-Za-z0-9 .\-&,]{1,60}?)(?:[^\S\n]{2,}|\n|$)",
        r"\b(EMERSON|SIEMENS|IBMRSS|ABB|HONEYWELL|SCHNEIDER|ROCKWELL|BOSCH|PHILIPS|SAMSUNG|LG|SONY|PANASONIC)\b",
    ],
    "shipping_country": [
        # Stop at next label keyword or end-of-line — do NOT use \s (crosses newlines)
        # Pattern: label colon VALUE  where value is 1 word (country name)
        r"(?i)(?:Shipping[^\S\n]*Country|Ship(?:ping)?[^\S\n]*From|Exported[^\S\n]*From|Country[^\S\n]*of[^\S\n]*Export)[^\S\n]*[:\-][^\S\n]*(" + _COUNTRIES + r")(?:[^\S\n]|\n|$|,)",
    ],
    "wto_member_status": [
        r"(?i)(?:WTO[^\S\n]*(?:Member)?[^\S\n]*(?:Status)?)[^\S\n]*[:\-][^\S\n]*\b(Yes|No|Y|N)\b",
    ],
    "fta_applicable": [
        # Use [A-Za-z0-9 \-] NOT [\s] — \s includes \n which causes cross-line capture!
        # e.g. correctly captures "EU-Japan EPA" or "ACFTA" or "No"
        r"(?i)(?:FTA[^\S\n]*Applicable|FTA[^\S\n]*Name|Free[^\S\n]*Trade[^\S\n]*Agreement)[^\S\n]*[:\-][^\S\n]*([A-Za-z0-9][A-Za-z0-9 \-]{1,40}?)(?:[^\S\n]{2,}|\n|$)",
        r"(?i)(?:Applicable[^\S\n]*FTA)[^\S\n]*[:\-][^\S\n]*([A-Za-z0-9][A-Za-z0-9 \-]{1,40}?)(?:[^\S\n]{2,}|\n|$)",
        r"(?i)\bFTA[^\S\n]*[:\-][^\S\n]*([A-Za-z0-9][A-Za-z0-9 \-]{1,40}?)(?:[^\S\n]{2,}|\n|$)",
    ],
}

# Known country name normalizations
COUNTRY_ALIASES = {
    "MY": "Malaysia", "MYS": "Malaysia", "MALAYSIA": "Malaysia",
    "CN": "China", "CHN": "China", "PRC": "China", "CHINA": "China",
    "US": "USA", "USA": "USA", "UNITED STATES": "USA", "UNITED STATES OF AMERICA": "USA",
    "MX": "Mexico", "MEX": "Mexico", "MEXICO": "Mexico",
    "VN": "Vietnam", "VNM": "Vietnam", "VIETNAM": "Vietnam",
    "TH": "Thailand", "THA": "Thailand", "THAILAND": "Thailand",
    "SG": "Singapore", "SGP": "Singapore", "SINGAPORE": "Singapore",
    "IN": "India", "IND": "India", "INDIA": "India",
    "JP": "Japan", "JPN": "Japan", "JAPAN": "Japan",
    "DE": "Germany", "DEU": "Germany", "GERMANY": "Germany",
    "KR": "South Korea", "KOR": "South Korea", "SOUTH KOREA": "South Korea",
    "TW": "Taiwan", "TWN": "Taiwan", "TAIWAN": "Taiwan",
    "HK": "Hong Kong", "HKG": "Hong Kong", "HONG KONG": "Hong Kong",
    "FR": "France", "FRA": "France", "FRANCE": "France",
    "GB": "United Kingdom", "GBR": "United Kingdom", "UK": "United Kingdom", "UNITED KINGDOM": "United Kingdom",
    "ID": "Indonesia", "IDN": "Indonesia", "INDONESIA": "Indonesia",
    "PH": "Philippines", "PHL": "Philippines", "PHILIPPINES": "Philippines",
    "BR": "Brazil", "BRA": "Brazil", "BRAZIL": "Brazil",
    "NL": "Netherlands", "NLD": "Netherlands", "NETHERLANDS": "Netherlands",
    "PL": "Poland", "POL": "Poland", "POLAND": "Poland",
    "CZ": "Czech Republic", "CZE": "Czech Republic", "CZECH REPUBLIC": "Czech Republic",
    "HU": "Hungary", "HUN": "Hungary", "HUNGARY": "Hungary",
    "IT": "Italy", "ITA": "Italy", "ITALY": "Italy",
    "ES": "Spain", "ESP": "Spain", "SPAIN": "Spain",
    "AU": "Australia", "AUS": "Australia", "AUSTRALIA": "Australia",
    "CA": "Canada", "CAN": "Canada", "CANADA": "Canada",
    "TR": "Turkey", "TUR": "Turkey", "TURKEY": "Turkey",
    "IL": "Israel", "ISR": "Israel", "ISRAEL": "Israel",
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


def _preprocess_text(text: str) -> str:
    """
    Clean raw extracted text before regex matching:
    - Remove pure all-caps table header rows (no digits, 3+ words)
    - Normalize whitespace within lines but preserve line breaks
    """
    cleaned_lines = []
    # Pattern: line is pure header if all tokens are UPPER, no digits, 3+ words
    header_pattern = re.compile(r'^[A-Z\s/#&]{10,}$')
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        # Skip lines that look like column headers (all caps, no digits, no colons)
        if (header_pattern.match(stripped)
                and not re.search(r'\d', stripped)
                and ':' not in stripped
                and len(stripped.split()) >= 3):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


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

    # Pre-process: strip table header rows to avoid false matches
    clean_text = _preprocess_text(text)

    # Try matching standard Jabil invoice line item row first (highly robust)
    row_pattern = r"^\s*(?!(?:Shipment|Supplier|Invoice|Plant|Material|Shipping|Country|WTO|FTA|Footer|Compliance|Generated|Page)\b)([A-Z0-9][A-Z0-9\-_.]{2,30})\s+(.+?)\s+\b(" + _COUNTRIES + r")\b\s+(\d{1,8}(?:\.\d{2})?)\s*$"
    row_match = re.search(row_pattern, clean_text, re.MULTILINE | re.IGNORECASE)
    if row_match:
        result["part_number"] = row_match.group(1).strip()
        result["product_description"] = row_match.group(2).strip()
        result["country_of_origin"] = _normalize_country(row_match.group(3).strip())
        result["declared_value"] = _clean_value(row_match.group(4).strip())
        logger.info(f"Successfully matched table row: Part={result['part_number']}, Desc={result['product_description']}, Country={result['country_of_origin']}, Value={result['declared_value']}")

    for field, patterns in PATTERNS.items():
        if result[field]:  # Skip if already extracted by table row regex
            continue
        for pattern in patterns:
            match = re.search(pattern, clean_text, re.MULTILINE)
            if match:
                raw = match.group(1).strip().strip(".,;\n\r")
                if field == "declared_value":
                    result[field] = _clean_value(raw)
                elif field in ("country_of_origin", "shipping_country"):
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
                # Extract tables with tab-separated columns for better regex matching
                tables = page.extract_tables()
                for table in (tables or []):
                    for row in table:
                        # Use tab to preserve column boundaries
                        row_text = "\t".join(
                            str(cell).strip() for cell in row if cell and str(cell).strip()
                        )
                        if row_text:
                            all_text.append(row_text)
        return "\n".join(all_text)
    except Exception as e:
        logger.error(f"pdfplumber extraction error: {e}")
        return ""


def _extract_text_easyocr(pdf_path: str) -> str:
    """Fallback: render PDF pages as images and run EasyOCR (lazy-loaded)."""
    if not HAS_EASYOCR:
        return ""
    try:
        from pdf2image import convert_from_path  # type: ignore
        pages = convert_from_path(pdf_path, dpi=300)
        ocr = _get_easyocr_reader()
        all_text = []
        for page_img in pages:
            img_np = np.array(page_img)
            text_list = ocr.readtext(img_np, detail=0)
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
