#!/usr/bin/env python3
"""
Verification script for Phase 3B: Search Quality Hardening

Tests that problematic URLs identified in the analysis are now correctly rejected.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scraping_cityurls.city_url_extractor import score_candidate

# Test cases: URLs that should be rejected (score < 0.65)
PROBLEMATIC_URLS = [
    {
        "city": "Ioannina",
        "country": "Greece",
        "url": "https://reismonkey.nl/blogs/news/cluj-napoca-roemenie",
        "title": "Cluj-Napoca travel guide",
        "reason": "NL domain for Romanian city + blog path"
    },
    {
        "city": "Ioannina",
        "country": "Greece",
        "url": "https://grieksegids.nl/ioannina",
        "title": "Ioannina travel information",
        "reason": "grieksegids.nl in NEGATIVE_TERMS"
    },
    {
        "city": "Bordeaux",
        "country": "France",
        "url": "https://frankrijk.nl/bordeaux",
        "title": "Bordeaux travel guide",
        "reason": "frankrijk.nl in NEGATIVE_TERMS"
    },
    {
        "city": "Budapest",
        "country": "Hungary",
        "url": "https://budapesttips.nl/attractions",
        "title": "Budapest tips and tricks",
        "reason": "budapesttips in NEGATIVE_TERMS"
    },
    {
        "city": "Athens",
        "country": "Greece",
        "url": "https://visitathens.nl/blog/top-10-things-to-do",
        "title": "Top 10 things to do in Athens",
        "reason": "NL domain for Greek city + blog path + tourism keywords"
    },
]

# Test cases: URLs that should still be accepted (score >= 0.65)
LEGITIMATE_URLS = [
    {
        "city": "Berlin",
        "country": "Germany",
        "url": "https://www.berlin.de/",
        "title": "Berlin.de - Das offizielle Hauptstadtportal",
        "reason": "Official .de domain with official keywords"
    },
    {
        "city": "Vienna",
        "country": "Austria",
        "url": "https://www.wien.gv.at/",
        "title": "Stadt Wien - Rathaus",
        "reason": "Government domain .gv.at"
    },
    {
        "city": "Porto",
        "country": "Portugal",
        "url": "https://www.cm-porto.pt/",
        "title": "Câmara Municipal do Porto",
        "reason": "Official .pt domain with municipality keywords"
    },
]


def test_url(city: str, country: str, url: str, title: str, expected_reject: bool, reason: str):
    """Test a single URL and report results."""
    url_data = {"url": url, "title": title}
    score = score_candidate(city, url_data, country)
    
    threshold = 0.65
    is_rejected = score < threshold
    
    status = "✅" if is_rejected == expected_reject else "❌"
    expectation = "REJECT" if expected_reject else "ACCEPT"
    actual = "REJECTED" if is_rejected else "ACCEPTED"
    
    print(f"{status} {city} ({country})")
    print(f"   URL: {url}")
    print(f"   Score: {score:.2f} | Expected: {expectation} | Actual: {actual}")
    print(f"   Reason: {reason}")
    print()
    
    return is_rejected == expected_reject


def main():
    print("=" * 80)
    print("Phase 3B Verification: Search Quality Hardening")
    print("=" * 80)
    print()
    
    print("Testing PROBLEMATIC URLs (should be REJECTED, score < 0.65):")
    print("-" * 80)
    problematic_results = [
        test_url(
            case["city"],
            case["country"],
            case["url"],
            case["title"],
            expected_reject=True,
            reason=case["reason"]
        )
        for case in PROBLEMATIC_URLS
    ]
    
    print()
    print("Testing LEGITIMATE URLs (should be ACCEPTED, score >= 0.65):")
    print("-" * 80)
    legitimate_results = [
        test_url(
            case["city"],
            case["country"],
            case["url"],
            case["title"],
            expected_reject=False,
            reason=case["reason"]
        )
        for case in LEGITIMATE_URLS
    ]
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    total_tests = len(problematic_results) + len(legitimate_results)
    passed_tests = sum(problematic_results) + sum(legitimate_results)
    
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print()
    
    if passed_tests == total_tests:
        print("✅ All tests passed! Phase 3B implementation successful.")
        return 0
    else:
        print("❌ Some tests failed. Review scoring logic.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
