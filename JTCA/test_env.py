import sys

print("Checking environment...")

try:
    import crawl4ai
    print("crawl4ai: OK")
except ImportError as e:
    print(f"crawl4ai: FAILED ({e})")

try:
    import chromadb
    print("chromadb: OK")
except ImportError as e:
    print(f"chromadb: FAILED ({e})")

try:
    import sentence_transformers
    print("sentence_transformers: OK")
except ImportError as e:
    print(f"sentence_transformers: FAILED ({e})")

try:
    import pdfplumber
    print("pdfplumber: OK")
except ImportError as e:
    print(f"pdfplumber: FAILED ({e})")

try:
    import pytesseract
    pytesseract.get_tesseract_version()
    print("pytesseract: OK")
except Exception as e:
    print(f"pytesseract: FAILED ({e})")

try:
    import easyocr
    print("easyocr: OK")
except ImportError as e:
    print(f"easyocr: FAILED ({e})")
