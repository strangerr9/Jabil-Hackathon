import requests
import pdfplumber
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crawler.crawl4ai_service import _parse_hs_codes_from_text

url = "https://fta.miti.gov.my/miti-fta/resources/ASEAN-China/TRS_AHTC_2017_ACFTA.pdf"
print("Downloading PDF sample for parsing verification...")
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
r = requests.get(url, headers=headers, timeout=30)

if r.status_code == 200:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(r.content)
        tmp_path = tmp.name
    
    try:
        print("Scanning PDF pages for Chapter 84/85 headings...")
        all_text = []
        with pdfplumber.open(tmp_path) as pdf:
            total_pages = len(pdf.pages)
            pages_to_parse = []
            for idx, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                # Check for chapter 84/85 formats
                if any(h in text for h in ["85.42", "85.41", "85.34", "85.36", "85.04", "84.71", "84.73"]):
                    pages_to_parse.append((idx, text))
                    if len(pages_to_parse) >= 3:
                        break
            
            if not pages_to_parse:
                print("No matching pages found for chapters 84/85. Parsing first 2 pages.")
                for i in range(min(2, total_pages)):
                    t = pdf.pages[i].extract_text()
                    if t:
                        all_text.append(t)
            else:
                print(f"Found matching pages: {[p[0]+1 for p in pages_to_parse]}")
                for p in pages_to_parse:
                    all_text.append(p[1])
        
        combined_text = "\n".join(all_text)
        print(f"Extracted {len(combined_text)} characters of text.")
        
        # Test our new parser
        print("Running _parse_hs_codes_from_text...")
        rules = _parse_hs_codes_from_text(combined_text, url, "ACFTA")
        
        print(f"\nExtracted {len(rules)} rules! Showing first 10 rules:")
        for idx, rule in enumerate(rules[:10], 1):
            print(f"{idx}. HS: {rule['hs_code']} | Desc: {rule['product_description']} | FTA: {rule['fta_name']} | Rate: {rule['tariff_percent']}% | Origin: {rule['origin_country']} | Dest: {rule['destination_country']}")
            
        assert len(rules) > 0, "No rules extracted!"
        print("\n[OK] Upgraded MITI/ACFTA parser verified working!")
        
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
else:
    print("Failed to download PDF")
