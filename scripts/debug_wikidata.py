"""Debug script to inspect Wikidata SPARQL responses."""

import json
import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)


def debug_wikidata_query(city: str) -> None:
    """Execute SPARQL query and show full response."""
    
    escaped_label = city.replace('"', '\\"')
    
    query = f"""
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX wikibase: <http://wikiba.se/ontology#>

SELECT ?item ?website ?sitelinks WHERE {{
  # Direct instance-of match (Q515=city, Q1549591=big city, etc.)
  # Much faster than wdt:P31/wdt:P279* which caused timeouts
  VALUES ?cityType {{ wd:Q515 wd:Q1549591 wd:Q208511 wd:Q3957 }}
  ?item wdt:P31 ?cityType .
  
  # Label matching
  ?item rdfs:label ?label .
  FILTER (LANG(?label) IN ('en', 'de', 'fr', 'es', 'it', 'pl', 'pt', 'nl', 'sv', 'fi'))
  FILTER (STR(?label) = "{escaped_label}")
  
  # Must have official website
  ?item wdt:P856 ?website .
  
  # Sitelinks for sorting
  ?item wikibase:sitelinks ?sitelinks .
}}
ORDER BY DESC(?sitelinks)
LIMIT 1
"""
    
    print(f"\n{'='*80}")
    print(f"DEBUG: Querying Wikidata for '{city}'")
    print(f"{'='*80}")
    
    print("\n--- SPARQL QUERY ---")
    print(query)
    
    endpoint = "https://query.wikidata.org/sparql"
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": USER_AGENT,
    }
    
    try:
        response = requests.get(
            endpoint,
            params={"query": query},
            headers=headers,
            timeout=15,
        )
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Request failed: {e}")
        return
    
    print(f"\n--- HTTP RESPONSE ---")
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    
    if response.status_code != 200:
        print(f"\n❌ Non-200 status code")
        print(f"Response text: {response.text[:500]}")
        return
    
    try:
        data = response.json()
    except ValueError as e:
        print(f"\n❌ JSON decode error: {e}")
        print(f"Response text: {response.text[:500]}")
        return
    
    print(f"\n--- PARSED JSON ---")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    bindings = data.get("results", {}).get("bindings", [])
    print(f"\n--- BINDINGS COUNT: {len(bindings)} ---")
    
    if bindings:
        print("\n✅ Found result(s):")
        for i, binding in enumerate(bindings, 1):
            item = binding.get("item", {}).get("value", "N/A")
            website = binding.get("website", {}).get("value", "N/A")
            sitelinks = binding.get("sitelinks", {}).get("value", "N/A")
            print(f"  [{i}] Item: {item}")
            print(f"      Website: {website}")
            print(f"      Sitelinks: {sitelinks}")
    else:
        print("\n❌ No bindings found - Query returned empty result")
        print("\nPossible reasons:")
        print("  1. City name doesn't match exactly (case-sensitive)")
        print("  2. City doesn't have P856 (official website) property")
        print("  3. City label is in a different form (e.g., 'Klagenfurt am Wörthersee')")


def main() -> None:
    """Test with Berlin and Klagenfurt."""
    cities = ["Berlin", "Klagenfurt"]
    
    for city in cities:
        debug_wikidata_query(city)
    
    print(f"\n{'='*80}")
    print("DEBUG SESSION COMPLETED")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
