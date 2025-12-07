"""Test script to verify Wikidata integration in find_city_url pipeline."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scraping_cityurls.city_url_extractor import find_city_url


def test_integration() -> None:
    """Test that Wikidata is used as primary strategy."""
    
    print("="*80)
    print("Testing Wikidata Integration in find_city_url")
    print("="*80)
    
    test_cities = [
        ("Berlin", "Germany"),
        ("Klagenfurt", "Austria"),
        ("Paris", "France"),
    ]
    
    overrides = {}  # Empty overrides to test Wikidata path
    
    for city, country in test_cities:
        print(f"\n--- Testing: {city} ({country}) ---")
        
        result = find_city_url(
            city_name=city,
            country_hint=country,
            overrides=overrides
        )
        
        print(f"Status: {result['status']}")
        print(f"URL: {result.get('official_url', 'N/A')}")
        print(f"Notes: {result.get('notes', 'N/A')}")
        
        # Verify that Wikidata was used
        notes = result.get('notes', '')
        if 'Source: Wikidata' in notes:
            print("✅ SUCCESS: Wikidata was used as primary source")
        elif 'Source: Search' in notes:
            print("⚠️  WARNING: Fell back to web search (Wikidata didn't find anything)")
        elif result['status'] == 'NOT_FOUND':
            print("❌ NOT_FOUND: Neither Wikidata nor search found a valid URL")
        else:
            print(f"ℹ️  Other source: {notes}")
    
    print("\n" + "="*80)
    print("Integration test completed")
    print("="*80)


if __name__ == "__main__":
    test_integration()
