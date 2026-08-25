# Architecture Overview

Dieses Dokument beschreibt die innere Struktur des City URL Scrapers.

## 1. High-Level Overview

Der Scraper folgt grob dieser Pipeline:

```text
Excel (netzerocities.xlsx)
    ↓  (load_cities_from_excel)
pro Stadt: find_city_url
    ↓
Override-Strategie
    ↓ (falls kein Treffer)
Wikidata-Strategie (SPARQL + Search API + Cache)
    ↓ (falls kein Treffer)
Search-Strategie (DuckDuckGo + Scoring)
    ↓ (falls kein Treffer)
Domain-Guessing-Strategie
    ↓
Quality Gate (ScoringEngine)
    ↓
Output (city_urls.xlsx/csv/json, Writeback in netzerocities.xlsx)
```

## 2. Module

### 2.1 `src/scraping_cityurls/city_url_extractor.py`

Zentrale Orchestrierung.

Wichtige Verantwortlichkeiten:

- Excel einlesen und Ergebnisse schreiben.
- Logging initialisieren.
- Pro Stadt die Strategien in Reihenfolge ausführen.
- Hilfsfunktionen für Suche, Domain-Guessing und URL-Validierung.

Wichtige Funktionen/Typen (Auszug):

- `find_city_url(city_name: str, country_hint: Optional[str]) -> ExtractionResult`
  - Kern-Orchestrierer für eine Stadt.
  - Reihenfolge:
    1. Overrides (`city_url_overrides.json`).
    2. Wikidata (`query_wikidata`).
    3. Search + Domain-Guessing.
    4. Scoring & Quality Gate.
- `query_wikidata(city: str, country_hint: Optional[str]) -> Optional[str]`
  - Abfrage der offiziellen Website (`P856`) über mehrere SPARQL-Queries + Search API.
  - Nutzt internen Cache (`wikidata_cache.json`).
- `strategy_search_engine(city: str) -> list[str]`
  - Erzeugt eine Suchanfrage und ermittelt Kandidaten-URLs über DuckDuckGo.
- `strategy_guess_domain(city: str) -> list[str]`
  - Generiert plausible Domains aus dem Stadtnamen (Normalisierung, TLD-Kombinationen).
- `validate_and_parse_url(url: str, timeout: int) -> dict | None`
  - Führt einen HTTP-Request durch, folgt Redirects, extrahiert Titel etc.

### 2.2 `src/scraping_cityurls/scoring.py`

Implementiert das Scoring-System als Strategy Pattern.

- `ScoringContext`
  - Enthält alle relevanten Informationen zu einem Kandidaten:
    - Stadtname, URL, Host, Pfad, HTML-Titel,
    - optional Country-Hint.
- `ScoringRule` (Protocol)
  - Jede Regel implementiert `apply(context, current_score) -> float`.
  - Spezielle Rückgabe `HARD_REJECT = -1000.0` markiert Kandidaten als unzulässig.
- Konkrete Regeln (Auswahl):
  - `HardBlacklistRule` – verwirft offensichtliche Spam-/Portalhosts.
  - `USGovMismatchRule` – lehnt `.gov`-Seiten für Nicht-US-Städte ab.
  - `WikipediaRule` – Hard-Reject für `wikipedia.org` und `wikivoyage.org`.
  - `VisitHostRule`, `TourismTitleRule`, `TourismPathRule` – Tourismus-/Blogseiten werden stark abgestraft.
  - `CityNameMatchRule` – Bonus, wenn der Stadtname im Host vorkommt.
  - `OfficialSignalRule` – Bonus für Verwaltungsbegriffe im Titel/Host.
  - `GovernmentTLDRule` – Bonus für `.gov`, `.gouv`, `.gv.` etc.
  - `CountryTLDRule`, `EuropeanCCTLDHintRule`, `GenericTLDMalusRule` – TLD-basierte Bewertung.
  - `SemanticPenaltyRule` – stärkere Penalties bzw. Hard-Rejects für Club-, Uni-, Airport-, Hospitality-, Business-, Religious-Sites.

- `ScoringEngine`
  - Aggregiert eine Liste von Regeln.
  - Startet bei einem Basis-Score und wendet nacheinander alle Regeln an.
  - Bricht bei `HARD_REJECT` sofort ab.

### 2.3 `src/scraping_cityurls/constants.py`

- Zentraler Ort für:
  - Keyword-Listen (offizielle Begriffe, negative Begriffe, Club/Uni/Airport etc.).
  - Länderspezifische TLD-Mappings.
  - Scoring-Thresholds.
  - User-Agent-String.

Trennung von Konfiguration und Logik macht es einfacher, neue Länder/Heuristiken anzupassen.

### 2.4 Helper-Skripte (`scripts/`)

- `check_wikidata_live.py`
  - Minimaler Einstieg in `query_wikidata`.
- `evaluate_results.py`
  - Gold-Set-Auswertung (Vergleich `city_urls.csv` vs. `gold_set.csv`).
- `writeback_netzerocities.py`
  - Join von `city_urls.csv` zurück nach `netzerocities.xlsx`.
- Weitere `verify_*.py`-Skripte
  - Dienen zur Prüfung einzelner Phasen (3B, 3C, 3D).

---

## 3. Wikidata-Schicht im Detail

Der Zugriff auf Wikidata ist bewusst robust ausgelegt:

### 3.1 SPARQL-Abfragen

`query_wikidata` baut zwei SPARQL-Queries:

1. **Strikte Query**
   - Filtert nach city-ähnlichen Typen (`?item wdt:P31 ?cityType`).
   - Nutzt eine kuratierte Menge von Q-IDs (Stadt, Hauptstadt, Stadtstaat etc.).
   - Sortiert nach `DESC(?sitelinks) ASC(?item)`.

2. **Fallback-Query**
   - Lässt den `P31`-Filter weg.
   - Nutzt nur Label + `P856` + `sitelinks`.
   - Ebenfalls deterministisch sortiert.

### 3.2 Search API Fallback

Wenn beide SPARQL-Queries keine Website liefern:

- `wbsearchentities` auf `https://www.wikidata.org/w/api.php` mit Suchstring
  `"{city} {country_hint}"`.
- Aus dem ersten Treffer wird die `id` (z. B. `Q64`) extrahiert.
- Anschließend wird eine gezielte SPARQL-Query auf `wd:{id} wdt:P856 ?website` ausgeführt.

### 3.3 Caching, Rate-Limiting, Retry

- `wikidata_cache.json` speichert pro Key `"{city}|{country_hint}"` die gefundene URL oder `""` für `None`.
- `_last_wikidata_request` und `WIKIDATA_RATE_LIMIT` begrenzen die Frequenz.
- `_execute_sparql` enthält eine Retry-Schleife mit Exponential Backoff.

Ergebnis:

- Erster Run füllt den Cache (langsamer, aber robust).
- Weitere Runs sind deterministisch und deutlich schneller.

---

## 4. Datenflüsse

### 4.1 Input → Extraktion → Output

```text
netzerocities.xlsx
    ↓
load_cities_from_excel
    ↓
for each city: find_city_url
    ↓
ExtractionResult(city, official_url, status, notes)
    ↓
output/city_urls.(xlsx|csv|json)
```

### 4.2 Gold-Set Evaluierung

```text
data/gold_set.csv         output/city_urls.csv
           ↓                          ↓
       evaluate_results.py (Vergleich pro Stadt)
           ↓
      Accuracy, Tabelle, Metriken
```

### 4.3 Writeback

```text
netzerocities.xlsx   +   output/city_urls.csv
             ↓
  writeback_netzerocities.py (Join per City)
             ↓
output/netzerocities_with_urls.xlsx
```

---

## 5. Erweiterbarkeit

Die aktuelle Architektur erleichtert:

- Hinzufügen neuer Strategien (z. B. LLM-Reranker) durch Ergänzen einer weiteren Pipeline-Stufe in `find_city_url`.
- Anpassung von Heuristiken, ohne die Kernlogik zu verändern (Änderungen in `constants.py` und neuen `ScoringRule`-Implementierungen).
- Austausch des Such-Backends (z. B. SerpAPI statt DuckDuckGo), solange `strategy_search_engine` dieselbe Signatur behält.

Für tiefere, phasenbasierte Planung und Refactorings siehe `docs/tech_plan_city_urls.md`.
