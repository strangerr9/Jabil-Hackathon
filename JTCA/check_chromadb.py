import os
import sys

# Ensure imports work from the JTCA root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag.vector_store import get_collection

def view_chromadb():
    collection = get_collection()
    if collection is None:
        print("ChromaDB is not installed or unavailable.")
        return
        
    count = collection.count()
    print(f"==================================================")
    print(f"CHROMADB VECTOR DATABASE VIEW")
    print(f"==================================================")
    print(f"Total Embeddings in Collection: {count}\n")
    
    if count == 0:
        print("Vector store is empty.")
        return
        
    # Retrieve first 10 items from collection
    results = collection.peek(limit=10)
    
    print("--- FIRST 10 RECORDS ---")
    ids = results.get("ids", [])
    metadatas = results.get("metadatas", [])
    documents = results.get("documents", [])
    
    for idx, (item_id, meta, doc) in enumerate(zip(ids, metadatas, documents), 1):
        print(f"\n[{idx}] ID: {item_id}")
        print(f"  HS Code:     {meta.get('hs_code')}")
        print(f"  Description: {meta.get('product_description')}")
        print(f"  Origin:      {meta.get('origin_country')} -> {meta.get('destination_country')}")
        print(f"  Tariff Rate: {meta.get('tariff_percent')}%")
        print(f"  FTA:         {meta.get('fta_name')}")
        print(f"  Document Vector Text:\n    {repr(doc)}")
    
    print(f"\n==================================================")

if __name__ == "__main__":
    view_chromadb()
