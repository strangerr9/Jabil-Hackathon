import os
import sys

# Ensure imports work from the JTCA root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import get_dashboard_stats, get_all_tariff_rules
from rag.vector_store import get_vector_count

def check_databases():
    print("\n" + "="*50)
    print("JTCA DATABASE STATUS REPORT")
    print("="*50)
    
    # 1. Check SQLite Database
    try:
        stats = get_dashboard_stats()
        rules = get_all_tariff_rules()
        print("\n--- SQLite Database (Relational Data) ---")
        print(f"Total Shipments:    {stats.get('total', 0)}")
        print(f"Pending Review:     {stats.get('pending', 0)}")
        print(f"Approved Shipments: {stats.get('approved', 0)}")
        print(f"Rejected Shipments: {stats.get('rejected', 0)}")
        print(f"Tariff Rules Seeded:{len(rules)}")
    except Exception as e:
        print(f"\n--- SQLite Database ---")
        print(f"Error reading SQLite: {e}")

    # 2. Check ChromaDB (Vector Database)
    try:
        vector_count = get_vector_count()
        print("\n--- ChromaDB (Vector Knowledge Base) ---")
        print(f"Total AI Embeddings (Tariff Rules): {vector_count}")
    except Exception as e:
        print(f"\n--- ChromaDB (Vector Knowledge Base) ---")
        print(f"Error reading ChromaDB: {e}")

    print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    check_databases()
