# Usage Guide

Dieses Dokument beschreibt, wie du den City URL Scraper im Alltag benutzt.

## 1. Setup

### 1.1 Virtuelle Umgebung & Installation

```bash
cd path/zum/projekt
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .
```

Voraussetzung: Python 3.11 (oder kompatibel). Abhängigkeiten sind in `pyproject.toml` definiert.

### 1.2 Eingabedaten

- Haupteingabe: `data/netzerocities.xlsx`
  - Spalte `Cities` (technisch: `Cities\xa0`) enthält die Stadtnamen.
  - Zusätzliche Spalten (z. B. `Label`, `Location knowledge repository`) werden durch den Scraper nicht verändert.
  - Du kannst manuell die Spalten `official_url`, `status`, `notes` anlegen – sie werden vom Writeback-Skript befüllt.

---

## 2. End-to-End Extraktion

Zentrales Kommando:

```bash
python -m scraping_cityurls.city_url_extractor
```

### 2.1 Was passiert dabei?

Für jede Stadt in `data/netzerocities.xlsx`:

1. **Overrides prüfen** (`data/city_url_overrides.json`)
   - Wenn ein manueller Eintrag existiert, wird dieser direkt als `OK` übernommen.

2. **Wikidata-Strategie**
   - SPARQL-Query gegen `https://query.wikidata.org/sparql`:
     - Strikter Typfilter auf city-ähnliche Q-Typen (Stadt, Hauptstadt, Metropole etc.).
     - Sortierung nach `wikibase:sitelinks` und deterministische Zweitsortierung nach `?item`.
   - Fallback-Query ohne Typfilter (nur Label + `P856` + `sitelinks`).
   - Falls beide leer sind: **Wikidata Search API**-Fallback:
     - `wbsearchentities` mit Suchstring `"{city} {country_hint}"` (englisch).
     - Für die gefundene `id` wird gezielt `P856` abgefragt.
   - Alle Wikidata-Resultate werden in `data/wikidata_cache.json` gecacht.
   - Gefundene Wikidata-URLs werden **ohne weitere HTML-Validierung** direkt als `OK` angenommen.

3. **Search-Fallback (DuckDuckGo)**
   - Wenn weder Overrides noch Wikidata eine URL liefern, wird eine Websuche durchgeführt.
   - Es werden mehrere Kandidaten-URLs gesammelt.
   - Jede URL wird mit `validate_and_parse_url` validiert (HTTP-Request, HTML-Title extrahiert).
   - Das Scoring-System (`ScoringEngine`) bewertet die Kandidaten anhand von Host, Pfad, TLD, Titel und Country-Hints.

4. **Domain-Guessing**
   - Falls die Suche keine brauchbaren Kandidaten liefert, werden aus dem Stadtnamen plausible Domains generiert (z. B. `stadtname.tld`, `www.stadtname.de`) und ebenfalls validiert + gescored.

5. **Quality Gate**
   - Liegt der beste Score über einem Schwellenwert, wird die URL als `OK` angenommen.
   - Bei mehreren ähnlich guten Treffern: `status = MULTIPLE`.
   - Wenn kein Kandidat den Threshold erreicht: `status = NOT_FOUND`.

### 2.2 Outputs

Nach einem Lauf findest du im Ordner `output/`:

- `city_urls.xlsx`
- `city_urls.csv`
- `city_urls.json`

Jeder Eintrag enthält mindestens:

- `city`
- `official_url` (oder leer bei NOT_FOUND)
- `status` (`OK`, `MULTIPLE`, `NOT_FOUND`, `ERROR`)
- `notes` (z. B. "Source: Wikidata" oder "Source: Search, Score=0.80").

---

## 3. Gold-Set Evaluierung

Für die objektive Qualitätsmessung gibt es ein kleines Gold-Set.

### 3.1 Gold-Set-Datei

- Datei: `data/gold_set.csv`
- Spalten:
  - `city`
  - `country_hint`
  - `expected_url_pattern` (Substrat, z. B. `berlin.de` oder `firenze.it`)

### 3.2 Evaluierung ausführen

```bash
python scripts/evaluate_results.py
```

- Liest `output/city_urls.csv` und `data/gold_set.csv`.
- Vergleicht gefundene URLs pro Stadt mit dem erwarteten Pattern.
- Gibt eine Tabelle und eine Accuracy-Zahl aus.

Beispiel (Stand Dezember 2025):

- 17/19 korrekte Treffer → 89.5 % Accuracy.

---

## 4. Writeback in `netzerocities.xlsx`

Um die Ergebnisse direkt zurück in die ursprüngliche Excel zu schreiben, gibt es:

```bash
python scripts/writeback_netzerocities.py
```

### 4.1 Verhalten

- Liest `data/netzerocities.xlsx`.
- Liest `output/city_urls.csv`.
- Normalisiert die City-Spalte (`Cities\xa0` → `Cities`).
- Joint pro Stadt und befüllt/überschreibt in einem neuen File:
  - `official_url`
  - `status`
  - `notes`

Die Ausgabe liegt in:

- `output/netzerocities_with_urls.xlsx`

Die Originaldatei `data/netzerocities.xlsx` bleibt unverändert.

---

## 5. Wikidata Debugging & Cache

### 5.1 Live-Wikidata testen

Um einzelne Städte gegen Wikidata zu testen:

```bash
python scripts/check_wikidata_live.py
```

- Nutzt direkt `query_wikidata` für eine kleine Menge an Teststädten.
- Praktisch für Debugging von Label-Problemen (z. B. Berlin, Klagenfurt).

### 5.2 Wikidata-Cache zurücksetzen

- Cache-Datei: `data/wikidata_cache.json`
- Enthält ein Mapping `"{city}|{country_hint}" → URL oder leere Zeichenkette`.
- Um einen frischen Wikidata-Run zu erzwingen:

```bash
rm data/wikidata_cache.json
```

> Hinweis: Auch `None`-Ergebnisse werden gecacht (als `""`). Das sorgt für stabile und schnelle Läufe, kann beim Debugging aber zu "klebrigen" NOT_FOUNDs führen.

---

## 6. Troubleshooting

### 6.1 Lauf ist sehr langsam

Mögliche Ursachen:

- Viele HTTP-Validierungen im Search-Fallback (für jede Kandidaten-URL).
- Rate-Limiting und Retries in Wikidata.

Tipps:

- Prüfen, wie viele Städte tatsächlich über Wikidata kommen (`notes`/Logs anschauen).
- Bei reinem Debug-Run ggf. kleinere Testmenge nutzen (Excel filtern oder temporäre Test-Excel erstellen).

### 6.2 Berlin wird als `NOT_FOUND` angezeigt

- Ursache ist meist ein fehlendes oder instabiles `P856` in Wikidata.
- Vorgehen:
  - `rm data/wikidata_cache.json`
  - `python scripts/check_wikidata_live.py`
  - Wenn dort keine URL zurückkommt → Datenproblem in Wikidata.
  - Optional ein Override für Berlin setzen.

### 6.3 Search liefert offensichtlich falsche Seiten (Tourismus, Club, Uni)

- Diese Fälle sollten durch das Scoring-System und semantische Regeln weitgehend abgefangen werden.
- Wenn im Einzelfall doch etwas durchrutscht:
  - Query + Resultat merken.
  - Entweder Scoring-Regeln in `scoring.py` anpassen.
  - Oder einen gezielten Override ergänzen.

---

## 7. Weitere Dokumentation

- Technischer Gesamtplan, Roadmap & Architekturdetails:
  - `docs/tech_plan_city_urls.md`
- Interne Architekturübersicht (Module, Datenflüsse):
  - `docs/architecture.md`
