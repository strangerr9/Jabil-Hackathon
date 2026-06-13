"""
============================================================
JTCA - Crawler Service (Crawl4AI)
Scrapes trade agreement portals and populates tariff_rules
Supports: MITI FTA Portal, WTO, ASEAN Trade Repository
============================================================
"""

import asyncio
import logging
import re
import json
import os
import requests
import pdfplumber
import tempfile
from datetime import datetime
from typing import Callable

logger = logging.getLogger(__name__)

try:
    import crawl4ai
    HAS_CRAWL4AI = True
except ImportError:
    HAS_CRAWL4AI = False


# ─────────────────────────────────────────────
# Target URLs for Crawling
# ─────────────────────────────────────────────
CRAWL_TARGETS = [
    {
        "name": "MITI Malaysia FTA",
        "url": "https://www.miti.gov.my/index.php/pages/view/ftas",
        "origin": "Malaysia",
    },
    {
        "name": "WTO Tariff Download",
        "url": "https://www.wto.org/english/tratop_e/tariffs_e/tariff_data_e.htm",
        "origin": "General",
    },
    {
        "name": "ASEAN Trade Repository",
        "url": "https://atr.asean.org/",
        "origin": "ASEAN",
    },
]


# ─────────────────────────────────────────────
# HS Code / Tariff Rate Parsers
# ─────────────────────────────────────────────
def _parse_hs_codes_from_text(text: str, source_url: str, origin: str) -> list[dict]:
    """
    Extract HS codes and tariff percentages from crawled HTML/document text.
    First tries custom LLM-based extraction using Google Gemini,
    then falls back to regex matching for offline/demo/unauthenticated runs.
    """
    # Step 1: Try LLM-based extraction first
    try:
        from llm.gemini_service import extract_rules_from_text
        llm_rules = extract_rules_from_text(text, origin)
        if llm_rules:
            # Overwrite source_url to match crawled portal source
            for r in llm_rules:
                r["regulation_source"] = source_url
            logger.info(f"[Crawler] Extracted {len(llm_rules)} rules using Gemini LLM strategy.")
            return llm_rules
    except Exception as e:
        logger.warning(f"[Crawler] Gemini LLM parsing strategy bypassed/failed: {e}")

    # Step 2: Fallback to regex-based parser
    logger.info("[Crawler] Using regex parsing fallback strategy.")
    rules = []
    now = datetime.now().isoformat()

    # Pattern: HS code (6-10 digits) followed by product text and percentage
    hs_pattern = re.compile(
        r"\b(\d{4}[\.\s]?\d{2}[\.\s]?\d{0,4})\b"
        r"(.{5,150}?)"
        r"(\d{1,2}(?:\.\d{1,2})?)\s*%",
        re.DOTALL,
    )

    for match in hs_pattern.finditer(text):
        raw_hs = re.sub(r"[\s\.]", "", match.group(1))
        if len(raw_hs) < 6:
            continue

        hs_code = raw_hs[:6]  # Normalize to 6 digits
        description = match.group(2).strip()[:200]
        tariff_percent = float(match.group(3))

        if tariff_percent > 100 or tariff_percent < 0:
            continue

        rules.append({
            "hs_code": hs_code,
            "product_description": description,
            "origin_country": origin,
            "destination_country": "USA",
            "tariff_percent": tariff_percent,
            "fta_name": "Web Crawl",
            "regulation_source": source_url,
            "last_updated": now,
        })

    return rules


# ─────────────────────────────────────────────
# Async Crawler
# ─────────────────────────────────────────────
def _is_pdf_url(url: str) -> bool:
    """Return True if the URL points to a PDF file."""
    return url.lower().split("?")[0].strip().endswith(".pdf")


async def _crawl_pdf_url(
    url: str,
    origin: str,
    log_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """
    Download and extract PDF content directly using requests and pdfplumber.
    This bypasses browser anti-bot issues and crawl4ai pypdf strategy bugs.
    """
    def log(msg):
        logger.info(msg)
        if log_callback:
            log_callback(msg)

    log(f"[Crawler] Detected PDF URL - downloading directly: {url}")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            log(f"[Crawler] Failed to download PDF (HTTP {r.status_code}): {url}")
            return []

        # Save binary to temporary file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(r.content)
            tmp_path = tmp.name

        try:
            log(f"[Crawler] Saved temporary PDF. Extracting text page-by-page...")
            all_text = []
            with pdfplumber.open(tmp_path) as pdf:
                total_pages = len(pdf.pages)
                for idx, page in enumerate(pdf.pages, 1):
                    if idx % 10 == 0 or idx == total_pages:
                        log(f"[Crawler] Extracting page {idx} / {total_pages}...")
                    page_text = page.extract_text()
                    if page_text:
                        all_text.append(page_text)
            
            text = "\n".join(all_text)
            log(f"[Crawler] PDF extracted {len(text)} characters.")
            
            rules = _parse_hs_codes_from_text(text, url, origin)
            log(f"[Crawler] Extracted {len(rules)} tariff rules from PDF.")
            return rules
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        log(f"[Crawler] PDF download/parse error for {url}: {e}")
        return []


async def _crawl_webpage_url(
    url: str,
    origin: str,
    log_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """Crawl a standard webpage URL and extract tariff rules."""
    def log(msg):
        logger.info(msg)
        if log_callback:
            log_callback(msg)

    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        log(f"[Crawler] Fetching webpage: {url}")

        browser_config = BrowserConfig(headless=True, verbose=False)
        run_config = CrawlerRunConfig(
            word_count_threshold=10,
            excluded_tags=["nav", "footer", "header", "script", "style"],
            remove_overlay_elements=True,
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)

            if not result.success:
                log(f"[Crawler] Failed to fetch: {url}")
                return []

            text = result.markdown or result.cleaned_html or ""
            rules = _parse_hs_codes_from_text(text, url, origin)
            log(f"[Crawler] Extracted {len(rules)} rules from {url}")
            return rules

    except ImportError:
        log("[Crawler] crawl4ai not installed. Please run: pip install crawl4ai")
        return []
    except Exception as e:
        log(f"[Crawler] Error crawling {url}: {e}")
        return []


async def _crawl_single_url(
    url: str,
    origin: str,
    log_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """
    Smart dispatcher — detects PDF vs webpage and routes accordingly.
    - PDF URLs  → PDFContentScrapingStrategy (crawl4ai native)
    - Web URLs  → standard AsyncWebCrawler
    """
    def log(msg):
        logger.info(msg)
        if log_callback:
            log_callback(msg)

    if not HAS_CRAWL4AI:
        log("[Crawler] crawl4ai not installed. Cannot crawl.")
        return []

    if _is_pdf_url(url):
        return await _crawl_pdf_url(url, origin, log_callback)
    else:
        return await _crawl_webpage_url(url, origin, log_callback)


async def run_crawler_async(
    log_callback: Callable[[str], None] | None = None,
) -> dict:
    """
    Run full crawl cycle across all configured targets.

    Args:
        log_callback: Optional function to receive real-time log messages

    Returns:
        {
            "rules_found": int,
            "rules_saved": int,
            "sources_crawled": int,
            "errors": list[str]
        }
    """
    from database.db import insert_tariff_rule
    from rag.vector_store import upsert_tariff_rules, reset_collection
    from database.db import get_all_tariff_rules

    def log(msg):
        logger.info(msg)
        if log_callback:
            log_callback(msg)

    if not HAS_CRAWL4AI:
        log("[Crawler] crawl4ai not installed. Using seed data fallback.")
        return {
            "rules_found": 0,
            "rules_saved": 0,
            "sources_crawled": 0,
            "errors": ["crawl4ai is not installed."],
        }

    log("[Crawler] Starting crawl cycle...")
    all_rules = []
    errors = []

    for target in CRAWL_TARGETS:
        log(f"[Crawler] Target: {target['name']} ({target['url']})")
        try:
            rules = await _crawl_single_url(
                url=target["url"],
                origin=target["origin"],
                log_callback=log_callback,
            )
            all_rules.extend(rules)
        except Exception as e:
            err = f"Error on {target['name']}: {e}"
            errors.append(err)
            log(f"[Crawler] {err}")

    # Insert new rules into SQLite
    saved = 0
    for rule in all_rules:
        if insert_tariff_rule(rule):
            saved += 1

    log(f"[Crawler] Saved {saved} / {len(all_rules)} rules to database.")

    # Refresh vector store
    if saved > 0:
        log("[Crawler] Re-indexing vector store...")
        try:
            reset_collection()
            all_db_rules = get_all_tariff_rules()
            upsert_tariff_rules(all_db_rules)
            log(f"[Crawler] Vector store updated with {len(all_db_rules)} rules.")
        except Exception as e:
            log(f"[Crawler] Vector store update failed: {e}")

    log("[Crawler] Crawl cycle complete.")
    return {
        "rules_found": len(all_rules),
        "rules_saved": saved,
        "sources_crawled": len(CRAWL_TARGETS),
        "errors": errors,
    }


def run_crawler_sync(log_callback: Callable[[str], None] | None = None) -> dict:
    """Synchronous wrapper for async crawler (for use in Qt threads)."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_crawler_async(log_callback))
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Crawler sync error: {e}")
        return {"rules_found": 0, "rules_saved": 0, "sources_crawled": 0, "errors": [str(e)]}


async def crawl_custom_source_async(
    url: str,
    origin: str,
    log_callback: Callable[[str], None] | None = None,
) -> dict:
    """Crawl a custom source URL and update the SQLite/Chroma DB rule systems."""
    from database.db import insert_tariff_rule
    from rag.vector_store import upsert_tariff_rules, reset_collection
    from database.db import get_all_tariff_rules

    def log(msg):
        logger.info(msg)
        if log_callback:
            log_callback(msg)

    if not HAS_CRAWL4AI:
        log("[Crawler] crawl4ai not installed. Cannot run custom crawl.")
        return {
            "rules_found": 0,
            "rules_saved": 0,
            "sources_crawled": 0,
            "errors": ["crawl4ai is not installed."],
        }

    log(f"[Crawler] Starting custom crawl on: {url} (Origin: {origin})")
    try:
        rules = await _crawl_single_url(
            url=url,
            origin=origin,
            log_callback=log_callback,
        )
    except Exception as e:
        log(f"[Crawler] Custom crawl error: {e}")
        return {
            "rules_found": 0,
            "rules_saved": 0,
            "sources_crawled": 0,
            "errors": [str(e)],
        }

    saved = 0
    for rule in rules:
        if insert_tariff_rule(rule):
            saved += 1

    log(f"[Crawler] Saved {saved} / {len(rules)} custom rules to database.")

    if saved > 0:
        log("[Crawler] Re-indexing vector store...")
        try:
            reset_collection()
            all_db_rules = get_all_tariff_rules()
            upsert_tariff_rules(all_db_rules)
            log(f"[Crawler] Vector store updated with {len(all_db_rules)} rules.")
        except Exception as e:
            log(f"[Crawler] Vector store update failed: {e}")

    return {
        "rules_found": len(rules),
        "rules_saved": saved,
        "sources_crawled": 1,
        "errors": [],
    }


def crawl_custom_source_sync(
    url: str,
    origin: str,
    log_callback: Callable[[str], None] | None = None,
) -> dict:
    """Synchronous wrapper for custom crawler (for Qt threads)."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(crawl_custom_source_async(url, origin, log_callback))
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Custom crawler sync error: {e}")
        return {"rules_found": 0, "rules_saved": 0, "sources_crawled": 0, "errors": [str(e)]}
