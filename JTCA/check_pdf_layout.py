import requests
import pdfplumber
import tempfile
import os

url = "https://fta.miti.gov.my/miti-fta/resources/ASEAN-China/TRS_AHTC_2017_ACFTA.pdf"
print("Downloading PDF...")
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
r = requests.get(url, headers=headers, timeout=30)
print(f"Status code: {r.status_code}")
print(f"Length of content: {len(r.content)} bytes")

if r.status_code == 200:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(r.content)
        tmp_path = tmp.name
    
    try:
        with pdfplumber.open(tmp_path) as pdf:
            print(f"Total pages: {len(pdf.pages)}")
            # Let's extract first 3 pages and print them
            for i in range(min(3, len(pdf.pages))):
                print(f"\n--- PAGE {i+1} ---")
                text = pdf.pages[i].extract_text()
                if text:
                    print(text[:1500])
                else:
                    print("[No text extracted]")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
else:
    print("Failed to download PDF")
