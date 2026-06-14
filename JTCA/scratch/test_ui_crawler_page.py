import os
import sys

# Prevent UnicodeEncodeErrors on Windows by forcing stdout/stderr to UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

# Ensure imports work from the JTCA root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from ui.crawler_page import FtaCard, TariffAgreementDialog, CrawlerPage

def get_mock_rules():
    return [
        {
            "hs_code": "847130",
            "product_description": "Laptop computer",
            "origin_country": "Malaysia",
            "destination_country": "USA",
            "tariff_percent": 0.0,
            "fta_name": "USMCA / General",
            "last_updated": "2024-01-15"
        },
        {
            "hs_code": "854231",
            "product_description": "Integrated circuits",
            "origin_country": "Malaysia",
            "destination_country": "USA",
            "tariff_percent": 0.0,
            "fta_name": "ITA Agreement",
            "last_updated": "2024-01-15"
        },
        {
            "hs_code": "853669",
            "product_description": "Connectors",
            "origin_country": "Mexico",
            "destination_country": "USA",
            "tariff_percent": 0.0,
            "fta_name": "USMCA",
            "last_updated": "2024-01-15"
        },
        {
            "hs_code": "850440",
            "product_description": "Power supply",
            "origin_country": "Malaysia",
            "destination_country": "USA",
            "tariff_percent": 1.5,
            "fta_name": "MFN Rate",
            "last_updated": "2024-01-15"
        },
        {
            "hs_code": "854140",
            "product_description": "LED diodes",
            "origin_country": "China",
            "destination_country": "ASEAN",
            "tariff_percent": 0.0,
            "fta_name": "ACFTA",
            "last_updated": "2024-01-15"
        },
        {
            "hs_code": "730890",
            "product_description": "Steel structures",
            "origin_country": "Malaysia",
            "destination_country": "USA",
            "tariff_percent": 25.0,
            "fta_name": "Section 232 Steel",
            "last_updated": "2024-01-15"
        },
        {
            "hs_code": "123456",
            "product_description": "Test bilateral",
            "origin_country": "Malaysia",
            "destination_country": "Japan",
            "tariff_percent": 2.0,
            "fta_name": "MJEPA",
            "last_updated": "2024-01-15"
        },
        {
            "hs_code": "987654",
            "product_description": "Test bilateral MITI",
            "origin_country": "Malaysia",
            "destination_country": "Pakistan",
            "tariff_percent": 3.0,
            "fta_name": "MITI FTA Test",
            "last_updated": "2024-01-15"
        }
    ]

def test_fta_categorization():
    print("Testing FTA categorization...")
    rules = get_mock_rules()

    # 1. Test Regional FTAs dialog
    dialog_regional = TariffAgreementDialog("Regional FTAs", rules)
    print("Regional FTAs found:")
    for key, val in dialog_regional.grouped_rules.items():
        print(f"  - {key}: {len(val)} rules")
    
    assert "USMCA / General" in dialog_regional.grouped_rules
    assert "USMCA" in dialog_regional.grouped_rules
    assert "ACFTA" in dialog_regional.grouped_rules
    assert "ITA Agreement" not in dialog_regional.grouped_rules
    assert "MJEPA" not in dialog_regional.grouped_rules
    print("[OK] Regional FTAs categorization passed.")

    # 2. Test Bilateral FTAs dialog
    dialog_bilateral = TariffAgreementDialog("Bilateral FTAs", rules)
    print("Bilateral FTAs found:")
    for key, val in dialog_bilateral.grouped_rules.items():
        print(f"  - {key}: {len(val)} rules")
        
    assert "MJEPA" in dialog_bilateral.grouped_rules
    assert "MITI FTA Test" in dialog_bilateral.grouped_rules
    assert "ACFTA" not in dialog_bilateral.grouped_rules
    print("[OK] Bilateral FTAs categorization passed.")

    # 3. Test Multilateral & Special Tariffs dialog
    dialog_special = TariffAgreementDialog("Multilateral & Special Tariffs", rules)
    print("Multilateral & Special Tariffs found:")
    for key, val in dialog_special.grouped_rules.items():
        print(f"  - {key}: {len(val)} rules")
        
    assert "ITA Agreement" in dialog_special.grouped_rules
    assert "MFN Rate" in dialog_special.grouped_rules
    assert "Section 232 Steel" in dialog_special.grouped_rules
    assert "MJEPA" not in dialog_special.grouped_rules
    print("[OK] Multilateral & Special Tariffs categorization passed.")

def test_crawler_page_layout():
    print("Testing CrawlerPage setup and card integration...")
    page = CrawlerPage()
    assert page.fta_label is not None
    assert page.fta_cards_frame is not None
    assert page.regional_card is not None
    assert page.bilateral_card is not None
    assert page.special_card is not None
    print("[OK] CrawlerPage layout integration passed.")

if __name__ == "__main__":
    # Setup QApplication for widget testing
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    test_fta_categorization()
    test_crawler_page_layout()
    print("\n[SUCCESS] ALL TESTS PASSED SUCCESSFULLY!")
