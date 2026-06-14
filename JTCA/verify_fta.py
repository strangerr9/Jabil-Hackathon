import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from llm.gemini_service import get_tariff_recommendation

def test_fta(origin, destination, expected_fta):
    print(f"Testing: Origin={origin} -> Destination={destination}")
    # Force demo mode by passing a product that gets demo classified
    res = get_tariff_recommendation(
        product_description="SUPPRESOR VOLTAGE SMD 30V 1.2J",
        part_number="VCAS121030H620DP",
        country_of_origin=origin,
        destination_country=destination,
        declared_value=5000.0,
        rag_context=""
    )
    fta = res.get("fta_applicable", "No")
    print(f"  Got FTA: {fta} (Expected: {expected_fta})")
    assert fta == expected_fta, f"[FAIL] Expected {expected_fta}, got {fta}"
    print("  [OK]")

if __name__ == "__main__":
    print("=== Testing ACFTA/ASEAN Dynamic FTA Logic ===")
    
    # Malaysia destination (original case)
    test_fta("China", "Malaysia", "ACFTA")
    
    # Singapore destination
    test_fta("China", "Singapore", "CSFTA")
    
    # Vietnam destination
    test_fta("China", "Vietnam", "ACFTA")
    
    # Non-ASEAN (e.g. USA)
    test_fta("China", "USA", "No")
    
    # EU-Japan EPA
    test_fta("Japan", "Germany", "EU-Japan EPA")
    test_fta("France", "Japan", "EU-Japan EPA")
    
    # Domestic
    test_fta("Malaysia", "Malaysia", "Domestic")
    test_fta("Singapore", "Singapore", "Domestic")
    
    print("\n[OK] All test cases passed successfully!")
