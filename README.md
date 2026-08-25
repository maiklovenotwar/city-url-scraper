# City URL Scraper

Extrahiert offizielle Stadt-Websites (Portale der Stadtverwaltungen) für die NetZeroCities-Städte.

## Features

- Liest NetZeroCities-Input aus `data/netzerocities.xlsx`.
- Mehrstufige Strategie-Pipeline:
  - **Overrides**: manuelle Korrekturen aus `data/city_url_overrides.json`.
  - **Wikidata**: strukturierte Abfragen von `P856` (official website) mit SPARQL.
  - **Wikidata Search API**: Fallback bei Label-Varianten (z. B. "Seville"/"Sevilla").
  - **Websuche + Heuristiken**: DuckDuckGo-Suche mit hartem Quality-Gate.
  - **Domain-Guessing**: generierte Domains für Restfälle.
- Scoring-System nach Strategy-Pattern in `src/scraping_cityurls/scoring.py`.
- Qualitätskontrolle über ein Gold-Set (`data/gold_set.csv`) und `scripts/evaluate_results.py`.
- Logging und deterministische, gecachte Wikidata-Abfragen.

## Installation

Voraussetzungen:

- Python 3.11 (oder kompatibel)
- `pip` / `uv` / `poetry` o. Ä.

```bash
# Im Projekt-Root
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .
```

Die Abhängigkeiten sind in `pyproject.toml` definiert.

## Zentrale Komponenten

### Paket `scraping_cityurls`

- `city_url_extractor.py`
  - Einstiegspunkt für die End-to-End-Extraktion.
  - Liest `data/netzerocities.xlsx`.
  - Iteriert über alle Städte und ruft `find_city_url` auf.
  - Speichert Ergebnisse nach:
    - `output/city_urls.xlsx`
    - `output/city_urls.csv`
    - `output/city_urls.json`
- `constants.py`
  - Zentraler Ort für Schlüsselkonstanten (User-Agent, TLD-Mappings, Keyword-Listen, Score-Thresholds usw.).
- `scoring.py`
  - Strategy-basiertes Scoring-System für Kandidaten-URLs (`ScoringEngine`).
  - Einzelne `ScoringRule`-Klassen für:
    - Blacklists / Hard-Rejects (z. B. Flughäfen, Clubs, nationale Portale).
    - Host-/Path-/TLD-Heuristiken.
    - Wikipedia-Hard-Reject (`WikipediaRule`).

### Scripts

- `scripts/check_wikidata_live.py`
  - Direktaufruf von `query_wikidata` für ausgewählte Städte (z. B. Berlin, Klagenfurt).
  - Hilft beim Debuggen der Wikidata-Integration.
- `scripts/evaluate_results.py`
  - Vergleicht `output/city_urls.csv` mit `data/gold_set.csv`.
  - Gibt Accuracy und detaillierte Zeile-pro-Stadt-Auswertung aus.
- `scripts/writeback_netzerocities.py`
  - Joint `output/city_urls.csv` zurück in `data/netzerocities.xlsx`.
  - Schreibt eine angereicherte Datei `output/netzerocities_with_urls.xlsx` mit den Spalten `official_url`, `status`, `notes`.

## Weitere Dokumentation

- **Nutzung & Workflows:** `docs/usage.md`
- **Architektur & Interna:** `docs/architecture.md`
- **Technischer Entwicklungsplan & Roadmap:** `docs/tech_plan_city_urls.md`

Weitere Helper-Skripte unter `scripts/` unterstützen die Verifikation einzelner Phasen (3B, 3C, 3D).

## Typische Workflows

### 1. Vollständigen Extraktionslauf starten

```bash
python -m scraping_cityurls.city_url_extractor
```

- Nutzt alle Strategien (Override → Wikidata → Search → Domain-Guessing).
- Schreibt Logs nach `logs/city_url_extractor.log` (sofern konfiguriert).

### 2. Ergebnisse auswerten (Gold-Set)

```bash
python scripts/evaluate_results.py
```

- Nutzt `data/gold_set.csv` (aktuell 19 Städte) und `output/city_urls.csv`.
- Stand Dezember 2025: 17/19 Exact Matches (89.5 %).

### 3. Ergebnisse zurück in die NetZeroCities-Excel schreiben

```bash
python scripts/writeback_netzerocities.py
```

- Liest `data/netzerocities.xlsx`.
- Joint pro Stadt mit `output/city_urls.csv`.
- Schreibt `output/netzerocities_with_urls.xlsx` mit befüllten Spalten.

## Wikidata-Robustheit (Phase 3D)

- Zweistufige SPARQL-Strategie:
  - Strikter Typfilter auf city-ähnliche Q-Typen + Sortierung nach `wikibase:sitelinks`.
  - Fallback-Query ohne `P31`, nur Label + `P856` + `sitelinks`.
- Wikidata Search API (`wbsearchentities`) als dritter Fallback, um Label-Varianten zu lösen.
- Stabilität:
  - Rate-Limiting (Mindestabstand zwischen Requests).
  - Retry mit Exponential Backoff.
  - Persistenter JSON-Cache `data/wikidata_cache.json`.
- Performance:
  - Für Wikidata-URLs wird keine HTML-Validierung mehr ausgeführt; sie werden direkt als `OK` übernommen.

## Qualitätssicherung

- Gold-Set (`data/gold_set.csv`) mit URL-Patterns für 19 Referenzstädte.
- Evaluationsskript `scripts/evaluate_results.py` zur objektiven Messung.
- Tech-Plan unter `docs/tech_plan_city_urls.md` beschreibt:
  - Roadmap (Phasen 0–5).
  - Heuristiken, Scoring-Regeln, Wikidata-Strategie.
  - Refactoring- und Qualitätsziele.

## Lizenz

Noch nicht festgelegt. Bitte vor externer Nutzung/Veröffentlichung klären.
