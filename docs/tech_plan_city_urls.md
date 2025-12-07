# Technischer Plan: Extraktion offizieller Stadt-Websites

**Projekt:** NetZeroCities URL-Extraktion  
**Status:** Phase 3A–3D abgeschlossen, Phase 5.1 (Gold-Set) teilweise umgesetzt  
**Letzte Aktualisierung:** Dezember 2025 (Phase 3D: Wikidata-Robustheit)

## Aktueller Stand (Quick Summary)

**✅ Implementiert:**
- Wikidata-Integration als primäre strukturierte Quelle (~70–75% Coverage nach Phase 3D)
- Strategie-Pipeline: Override → Wikidata → Search → Domain-Guessing
- Performance-optimierte SPARQL-Queries (<2s)
- Source-Tracking in Output (`Source: Wikidata` vs. `Source: Search`)
-- Phase 3B & 3C: Search-Quality-Hardening inkl. semantischer Filter (Tourismus, Clubs, Unis, Airports, Hotels, Business, nationale Portale)
- Phase 3D: Wikidata-Robustheit (Retry, Caching, Search-API-Fallback, Rate-Limiting)

**🔄 Nächste Schritte:**
- Phase 5.1: Gold-Set & Evaluierung weiter ausbauen (mehr Städte, CI-Integration)
- Phase 5.2: Iterative Verbesserung anhand Gold-Set und Spotchecks

**📊 Qualität (91 NetZeroCities-Städte, nach Phase 3B/3C):**
- Wikidata-Treffer: sehr hohe Qualität (offizielle Verwaltungsseiten)
- Search-Fallback: deutlich weniger Tourismus-/Spam-Treffer, Restfehler v. a. Events/Branding-Seiten
- Kritische Fälle (z. B. `grieksegids.nl`, `frankrijk.nl`, `budapesttips.nl`, `lisbonwi.gov`, Airports/Hotels) werden nicht mehr als `OK` klassifiziert

---

## 1. Zielsetzung

Aus einer Excel-Datei `data/netzerocities.xlsx` mit ca. 90 Städtenamen (Annahme: mindestens eine Spalte `City`) sollen für jede Stadt die offiziellen städtischen Websites (Startseiten) ermittelt werden. Ergebnis ist u. a. eine vierte Spalte in der Excel-Datei sowie optionale Exportformate (CSV/JSON) mit folgenden Feldern:

- `city` – Stadtname aus der Excel
- `country` / `country_hint` – optional, falls später ergänzt
- `official_url` – identifizierte Startseite der offiziellen Stadt-Website (HTTP/HTTPS)
- `status` – OK / MULTIPLE_CANDIDATES / NOT_FOUND / ERROR
- `notes` – Fehlerbeschreibung, Heuristikhinweise

Skript-Anforderungen:

- Robust, wartbar, erweiterbar
- Saubere Trennung von I/O, Logik und Konfiguration
- Logging, Rate Limits, Fehlerbehandlung
- Kompatibel mit Black/Ruff (PEP8-konform, klare Struktur)

---

## 2. Annahmen zur Eingabedatei

- Pfad: `data/netzerocities.xlsx`
- Struktur (Minimalannahme):
  - Spalte `City` mit dem Stadtnamen (z. B. "Berlin", "München", "Hamburg")
- Optional spätere Erweiterungen:
  - Spalte `Country` (z. B. "Germany")
  - Spalte `Region` / `State` (z. B. "Bavaria")

Das Skript sollte so implementiert werden, dass Spaltennamen konfigurierbar sind, z. B. über eine kleine Konfigurationssektion im Code (oder später via YAML/ENV).

---

## 3. High-Level-Architektur des Skripts

Geplante Hauptmodule/Funktionen (in einer einzelnen Python-Datei, später leicht in Module aufteilbar):

1. **Konfiguration & Konstanten**
   - Pfade: Input-Excel, Output-Excel/CSV/JSON
   - Rate-Limiting-Einstellungen (z. B. minimale Wartezeit zwischen Requests)
   - Timeouts für HTTP-Requests und Suchanfragen
   - User-Agent-String

2. **I/O-Schicht**
   - `load_cities_from_excel(path: str) -> list[dict]`
   - `save_results_to_excel(...)` / `save_results_to_csv(...)` / `save_results_to_json(...)`

3. **Such- & Erkennungslogik**
   - `build_search_query(city: str, country: str | None) -> str`
   - `search_city_official_site(query: str) -> list[SearchResult]`
   - `select_official_city_site(results: list[SearchResult], city: str, country_hint: str | None) -> SelectionResult`

4. **Validierungs- & Heuristikschicht**
   - Domain- und URL-Validierung
   - Heuristiken für "offizielle" Stadtseiten (siehe Abschnitt 5)

5. **Orchestrierung**
   - Hauptschleife über alle Städte
   - Fehlerbehandlung je Stadt (try/except auf Stadtebene, damit der Prozess global weiterläuft)
   - Logging auf INFO/ERROR-Level

6. **CLI-Einstiegspunkt**
   - `if __name__ == "__main__": main()` mit Argumenten (später optional über `argparse`).

---

## 3.1 Projektstruktur & Ordner-Layout

Das Repository folgt einer klassischen `src/`-Struktur. Ziel ist eine klare Trennung von **Code**, **Daten**, **Artefakten** und **Dokumentation**.

Geplante Struktur:

- `pyproject.toml` – Projektmetadaten, Dependencies, Black/Ruff-Konfiguration
- `.venv/` – lokale virtuelle Umgebung (nicht versioniert)
- `src/`
  - `scraping_cityurls/`
    - `__init__.py`
    - `city_url_extractor.py` – zentrale Orchestrierung und I/O-Logik
    - weitere Module (z. B. `search_logic.py`, `heuristics.py`) für spätere Erweiterung
- `data/`
  - `netzerocities.xlsx` – Eingabedaten (Städtenamen)
  - weitere Input-Dateien nach Bedarf
- `output/`
  - `city_urls.xlsx` – Excel mit ergänzter `OfficialURL`-Spalte
  - `city_urls.csv` – CSV-Export der Ergebnisse
  - `city_urls.json` – JSON-Export der Ergebnisse
- `logs/`
  - `city_url_extractor.log` – Laufzeit-Logs
- `docs/`
  - `tech_plan_city_urls.md` – dieses Dokument
- `tests/`
  - Testmodule (z. B. `test_city_url_extractor.py`)
- `scripts/`
  - optionale CLI-/Helper-Skripte

Wichtige Prinzipien:

- **Keine Daten unter `src/`**: `src/` enthält ausschließlich Python-Code (Module/Packages).
- **Alle laufzeitgenerierten Artefakte** (`output/`, `logs/`) liegen im Projektroot.
- **Inputdaten (`data/`)** werden bewusst getrennt gehalten, um sie klar von Code und Artefakten zu unterscheiden.

---

## 4. Suchstrategie und Fallbacks

### 4.1 Primärstrategie: Websuche über öffentliche Search-Endpoints

Da offizielle APIs (Google Custom Search, Bing API) evtl. nicht verfügbar sind, wird eine pragmatische, aber vorsichtige Lösung benötigt:

- Verwendung von Such-URLs der großen Suchmaschinen (z. B. `https://www.google.com/search?q=...`) ist technisch möglich, aber:
  - rechtlich und technisch heikel (Nutzungsbedingungen, Anti-Bot-Maßnahmen)
  - nicht stabil produktionsreif ohne sorgfältiges Monitoring.

**Empfohlene produktionsnähere Strategie:**

1. **Konfigurierbarer Suchanbieter** (Platzhalter-Strategie):
   - Das Skript abstrahiert die Suche in eine Funktion `perform_search(query: str) -> list[SearchResult]`.
   - Standardimplementierung kann zunächst nur als Platzhalter fungieren und manuell erzeugte Suchergebnisse oder eine interne kleine Mapping-Tabelle nutzen.
   - Später kann diese Funktion durch:
     - Google Custom Search API
     - Bing Web Search API
     - SerpAPI oder ähnliche Dienste
     ersetzt werden.

2. **Manuell unterstützte Phase** (für initiales Projekt):
   - Option: Erste Iteration halbautomatisch:
     - Skript generiert sinnvolle Suchqueries.
     - Ergebnisse werden in einer Zwischen-CSV abgelegt.
     - Menschliche Validierung/Ergänzung möglich.

### 4.2 Fallback-Strategien ohne API

Falls keine API genutzt wird/kann:

- **Heuristische Erkennung über Domain-Patterns**
  - In vielen Ländern haben Städte offizielle Domains mit bestimmten Mustern, z. B.:
    - `cityname.de` (z. B. `berlin.de`)
    - `www.cityname.de`
    - `www.cityname.city.tld`
    - `www.cityname-stadt.de`
  - Das Skript könnte versuchen, aus dem Stadtnamen Domain-Kandidaten zu generieren und diese per HTTP-Request zu prüfen.

- **Kandidatengenerierung aus dem Stadtnamen**
  - Normalisierung: Kleinbuchstaben, Umlaute und Sonderzeichen ersetzen (`ä` → `ae`, `ö` → `oe`, `ü` → `ue`, `ß` → `ss`), Leerzeichen entfernen oder durch `-` ersetzen.
  - Beispiel: "München" → `muenchen.de`, `stadt-muenchen.de`, `muenchen.de` mit/ohne `www.`.

- **Heuristische Filterung über HTML-Inhalt**
  - Wenn eine URL antwortet, kann der HTML-Title und `<meta>`-Tags geprüft werden:
    - Enthält der Seitentitel den Stadtnamen?
    - Enthält der Titel Begriffe wie "Stadt", "Stadtverwaltung", "Stadt [Name]", "City of [Name]"?
    - Enthält die Seite Impressum/Contact mit typischen Begriffen für Kommunalverwaltung?

### 4.3 Mehrere Domains & Mehrsprachigkeit

- Wenn mehrere Domainkandidaten plausibel sind:
  - Bevorzugung von Domains mit:
    - Offiziell wirkenden TLDs (z. B. `.de`, `.gov`, `.gouv.fr`, `.gov.uk` etc., falls Länderkontext bekannt)
    - Keine offensichtlich kommerziellen TLDs (`.com` nur mit Vorsicht, wenn es nicht typisch für die Region ist)
  - Falls mehrere gleich plausible gefunden werden:
    - Markierung `status = MULTIPLE_CANDIDATES`
    - Speicherung aller Kandidaten optional in Zusatzfeldern oder einer separaten Datei.

---

## 5. Heuristiken zur Identifikation offizieller Stadtseiten

Heuristiken sollten getrennt und testbar implementiert werden, z. B. in einer Funktion:

- `score_domain(candidate_url: str, city: str, country_hint: str | None, html_title: str | None, html_text_snippet: str | None) -> float`

Mögliche Scoring-Komponenten:

1. **Domain-Match mit Stadtnamen**
   - Exakte Übereinstimmung von Domainlabel und Stadtnamen (nach Normalisierung)
   - Teilstring-Matches (z. B. `stadtname-...`)

2. **Stichworte im Titel / Meta-Tags**
   - Enthält `city` (oder Normalform) im `<title>`?
   - Enthält zusätzlich ein Verwaltungsschlüsselwort:
     - deutsch: "Stadt", "Stadtverwaltung", "Gemeinde", "Rathaus", "Landeshauptstadt"
     - englisch: "City of", "Municipality", "Town of"

3. **Content-Signale (optional, bei leichtem Parsing)**
   - Vorkommen von Wörtern wie "Impressum" (deutsch), "Datenschutz", "Kontakt" in Kombination mit `city`.

4. **Negativsignale**
   - Offensichtlich touristische/commerzielle Seiten ohne Verwaltungsbezug ("Hotel", "Travel", "Booking", etc.).
   - Portal-/Verzeichnis-Seiten ("stadtportal", "meinestadt" etc.).

Domain mit höchstem Score wird gewählt, sofern Score über Schwellwert liegt, sonst `NOT_FOUND` oder `MULTIPLE_CANDIDATES`.

---

## 6. Validierungslogik

Ziele der Validierung:

- Sicherstellen, dass URL:
  - mit `http://` oder `https://` beginnt (HTTPS bevorzugen, HTTP auf HTTPS umleiten, falls vorhanden)
  - erreichbar ist (Statuscode 200–399, nach Redirects)
  - nicht offensichtlich eine Fehler- oder Placeholder-Seite ist.

Validierungsschritte:

1. **URL-Normalisierung**
   - Protokoll ergänzen (Standard: `https://`), falls nur Domain vorliegt.

2. **HTTP-Request mit Timeout & Redirect-Follow**
   - Verwendung von `requests` mit:
     - `timeout` (z. B. 5–10 Sekunden)
     - `allow_redirects=True`
   - Akzeptable Statuscodes: 200–399.

3. **Inhaltsprüfung (optional/leichtgewichtig)**
   - Auslesen des `<title>` und evtl. `<meta name="description">`.
   - Matching mit `city` und Heuristiken wie oben beschrieben.

4. **Fehlerfälle**
   - Timeout → `status = ERROR`, `notes = "timeout"`
   - 4xx/5xx → `status = ERROR`, `notes = "HTTP <code>"`
   - Kein Kandidat mit ausreichendem Score → `status = NOT_FOUND`.

---

## 7. Rate-Limiting & Fehlertoleranz

Um respektvoll und stabil zu arbeiten:

- **Rate-Limit**
  - Konfigurierbare Pause zwischen Requests (z. B. 1–3 Sekunden) pro Stadt, insbesondere bei Suchanfragen oder vielen HTTP-Requests.

- **Retry-Logik** (sparsam einsetzen)
  - Bei transienten Fehlern (Timeout, DNS) 1–2 Retries mit Backoff (z. B. 1s, 3s).

- **Globale Fehlerbehandlung**
  - Fehler pro Stadt abfangen und im Ergebnis vermerken, Skript läuft für restliche Städte weiter.

---

## 8. Logging-Konzept

- Verwendung des Standardmoduls `logging`.
- Log-Level:
  - `INFO`: Start/Ende, pro Stadt Start, gefundene URL, Status
  - `WARNING`: mehrere Kandidaten, schwache Scores
  - `ERROR`: Exceptions, Timeouts, nicht erreichbare Domains
- Log-Ausgabe:
  - Konsole (Standard)
  - Optional Logdatei `logs/city_url_extraction.log` (kann später ergänzt werden)

Logformat: Timestamp, Level, City, Message.

---

## 9. Output-Formate

1. **Erweiterte Excel-Ausgabe**
   - Einlesen von `data/netzerocities.xlsx`.
   - Hinzufügen einer neuen Spalte, z. B. `OfficialURL`.
   - Optional weitere Spalten: `Status`, `Notes`.

2. **CSV/JSON-Exports**
   - `output/city_urls.csv`
   - `output/city_urls.json`

Struktur:

- `city`
- `official_url`
- `status`
- `notes`

---

## 10. Fallbacks bei nicht verfügbarer Websuche

Wenn weder APIs noch Suchmaschinen sinnvoll genutzt werden können:

1. **Domain-Pattern-Ansatz**
   - Generierung von 3–10 Domainkandidaten pro Stadt (z. B. `stadtname.tld`, `www.stadtname.tld`, `stadt-stadtname.tld`).
   - Überprüfung der Kandidaten nach Priorität:
     - Zuerst TLDs, die für das Ziel-Land typisch sind (z. B. `.de`).

2. **Manueller Review-Modus**
   - Skript generiert nur Kandidaten + Status "NEEDS_REVIEW".
   - Mensch validiert und trägt die finale URL in Excel nach.

3. **Hybrid-Modus**
   - Wo Heuristiken eine hohe Sicherheit haben (Score > Schwellenwert), wird automatisch akzeptiert.
   - Sonst `MULTIPLE_CANDIDATES` / `NEEDS_REVIEW`.

---

## 11. Code-Struktur & Best Practices (Black, Ruff)

- **Struktur**
  - Eine zentrale Datei, z. B. `city_url_extractor.py`.
  - Klare Funktionsgrenzen, keine überlangen Funktionen.

- **Stil**
  - Black-kompatibles Formatting (max. Line Length 88, doppelte Quotes, etc.).
  - Ruff für Linting: Vermeidung ungenutzter Importe, saubere Typannotationen (PEP 484).

- **Typisierung**
  - Verwenden von `typing` (`TypedDict`/`dataclass` für `SearchResult`, `SelectionResult`).

- **Konfiguration**
  - Konstante Variablen am Anfang der Datei (z. B. `INPUT_EXCEL_PATH`, `OUTPUT_EXCEL_PATH`, TIMEOUTS, RATE_LIMIT_SECONDS).

---

## 12. Git-Strategie & Workflow

Für ein sauberes Versionsmanagement wird eine leichte, aber klare Git-Strategie verwendet.

**Branching-Modell:**

- `main` / `master`:
  - Stabile, getestete Versionen des Projekts.
  - Wird nur über Pull Requests/Merges aktualisiert.
- Feature-Branches:
  - z. B. `feat/url-heuristics`, `feat/search-integration`, `chore/tooling`.
  - Jede fachliche Änderung oder größere Refaktorierung erfolgt in einem separaten Branch.

**Commit-Konventionen:**

- Präfixe zur schnellen Einordnung:
  - `feat:` – neue Funktionalität (z. B. neue Heuristik, neue Suchstrategie)
  - `fix:` – Bugfix
  - `refactor:` – Struktur-/Codeverbesserung ohne fachliche Änderung
  - `chore:` – Wartung, Tooling, Konfiguration (z. B. Black/Ruff-Anpassungen)
  - `docs:` – Änderungen an Dokumentation (`docs/`)

**Build- und Artefakt-Handling:**

- `.venv/`, `build/`, `dist/`, `*.egg-info/`, `output/`, `logs/` werden in `.gitignore` aufgenommen.
- Nur **Quellcode**, **Konfiguration**, **Dokumentation** und ggf. kleine Beispiel-Inputdateien (z. B. Beispiel-Excel mit Dummy-Daten) werden versioniert.

**Quality-Gates vor Merge:**

- Ausführung von:
  - `ruff check .` – statische Analyse
  - `ruff format .` und/oder `black .` – Formatierung
  - `pytest` – sobald Tests vorhanden sind

Ziel ist eine reproduzierbare, gut wartbare Codebasis, bei der jede fachliche Änderung nachvollziehbar und sauber isoliert ist.

---

## 13. Implementierungsstatus (Dezember 2025)

**Vollständig implementiert:**
- I/O-Layer: Excel-Import/Export, CSV/JSON-Export
- Logging-System mit Konsole + Datei
- Strategie-Pipeline: Override → Wikidata → Search → Domain-Guessing
- HTTP-Validierung mit `requests` + HTML-Parsing via `BeautifulSoup`
- Scoring-System mit Quality-Gate (Threshold 0.65)
- Wikidata-Integration (SPARQL-Queries für P856) inkl. zweistufiger Typ-Filter + Label-Fallback + Search-API-Fallback
- Konstanten-Modularisierung (`constants.py`)
- Dependency-Management via `pyproject.toml` (inkl. `ddgs>=1.0.0`)

**Qualitätsergebnisse (91 NetZeroCities-Städte, nach Phase 3D):**
- Deutlich erhöhter Anteil an Wikidata-Treffern (mehrere vormals schwierige Städte wie Madrid, Seville, Gävle, Umeå, Warsaw nun via Wikidata)
- Search-Fallback weiterhin nur für Restfälle; stark gehärtet durch semantische Filter und Score-Threshold
- NOT_FOUND signalisiert strukturelle Datenlücken (z. B. fehlende P856-Einträge) statt systematischer Fehler

**Identifizierte Verbesserungspotenziale (aktuell):**
- Restfehler im Search-Fallback v. a. durch Events/Branding-/Tourismusportale ohne klaren Verwaltungsbezug
- Einzelne Wikidata-Fälle ohne saubere P856-Property (z. B. Berlin, falls Datensatz unvollständig) → manifestieren sich als NOT_FOUND
- Gold-Set deckt bisher 19 Städte ab und sollte auf weitere Städte/Länder erweitert werden


---

## 18. Phasenbasierte Roadmap

Zur besseren Steuerung der Umsetzung wird die Entwicklung in klar abgegrenzte Phasen unterteilt.

### Phase 0 – Basis-Skeleton (abgeschlossen)

- Aufsetzen des Projekts (`pyproject.toml`, `src/`-Struktur, Logging, Output-Ordner etc.).
- Einlesen der Excel (`netzerocities.xlsx`) und Schreiben der Ergebnisse nach `output/`.
- Dummy-Input (z. B. Berlin) für erste End-to-End-Tests.

### Phase 1 – Heuristische Websuche & Validierung (laufend, erste Iteration abgeschlossen)

- Integration von `duckduckgo-search` als Such-Backend.
- Implementierung von Domain-Guessing-Strategien aus dem Stadtnamen.
- HTTP-Validierung mit `requests` und HTML-Parsing über `BeautifulSoup`.
- Einführung eines ersten Scoring-Modells (Domain-Match, Keywords, TLDs) und konservivem Threshold.
- Quality-Gate: lieber `NOT_FOUND` als offensichtlich falsche URLs.

### Phase 2 – Qualitätsverbesserung durch Country-Kontext & Overrides

- Erweiterung des Input-Schemas um `Country`/`Country_ISO`.
- Aufbau eines Mappings `Country → bevorzugte ccTLDs` und Integration in Scoring & Domain-Guessing.
- Einführung einer kleinen `city_url_overrides.json` als manuell kuratierte Whitelist für wichtige Städte.
- Anpassung des Quality-Gates, sodass bei `NOT_FOUND` keine URL mehr in den Output geschrieben wird (`official_url = None`).

### Phase 3 – Strukturierte Datenquellen

**Status: Abgeschlossen (Dezember 2025)**

#### Phase 3A: Wikidata-Integration (✅ Implementiert)

- **SPARQL-Query** für Property P856 (official website) auf Wikidata
  - Direkte `wdt:P31` Matches auf City-Typen (Q515, Q1549591, Q208511, Q3957)
  - Performance-optimiert: <2s statt Timeout durch Vermeidung von `wdt:P31/wdt:P279*`
  - Label-Matching in 10 europäischen Sprachen
  - Sortierung nach `wikibase:sitelinks` (Relevanz-Priorisierung)
- **Integration in `find_city_url`**:
  - Strategie-Reihenfolge: Override → Wikidata → Search → Domain-Guessing
  - Graceful Degradation: Wikidata-Fehler brechen Pipeline nicht ab
  - Source-Tracking in Notes: `Source: Wikidata` vs. `Source: Search`
- **Ergebnis (91 NetZeroCities-Städte)**:
  - ~60% erfolgreiche Wikidata-Treffer mit offiziellen URLs
  - Qualität deutlich höher als Search-Fallback
  - Beispiele: Berlin, Klagenfurt, Barcelona, Porto, Ljubljana, Münster, etc.

#### Phase 3B: Search-Quality-Hardening (✅ Abgeschlossen)

**Motivation:** Erste Auswertung zeigte, dass der Search-Fallback zu viele Tourismus-/Reiseportale und generische Seiten als `OK` klassifizierte (z. B. `grieksegids.nl`, `frankrijk.nl`, `budapesttips.nl`).

**Umgesetzte Maßnahmen:**

1. **TLD vs. Country-Hint Scoring (verschärft):**
   - Positiver Boost, wenn TLD zu `country` passt (z. B. Athen + `.gr`, Porto + `.pt`).
   - Malus für fremde ccTLDs (z. B. `.nl` für griechische Stadt), neutrale Behandlung generischer TLDs (`.com`, `.org`, `.eu`, `.net`).

2. **Anti-Tourismus-Heuristiken:**
   - Erweiterte `NEGATIVE_TERMS` um typische Reiseportale/Blogs (`grieksegids`, `budapesttips`, `frankrijk`, `stedentrip`, `citytrip`, `wikivoyage`, `reistips`, `top10`, `what-to-see`).
   - Pfad-Pattern-Malus für Blog-/Guide-/Tourismus-Pfade (`/blog/`, `/guide/`, `/tips/`, `/reistips/`, `/bezienswaardigheden/`, `/stedentrip/`, `/things-to-do/`, `/what-to-see/`, `/top10/`).
   - Hard-Cap für solche Pfade: Score maximal 0.6 (nie `OK`).

3. **Verwaltungs- und TLD-Signale:**
   - Bevorzugung von Domains mit Stadt-ccTLD + Verwaltungsbegriffen im Titel/Host (z. B. `comune`, `ayuntamiento`, `mairie`, `ville`, `municipio`, `stadt`).

**Ergebnis:**
- Problemfälle wie `Ioannina → grieksegids.nl`, `Bordeaux → frankrijk.nl`, `Budapest → budapesttips.nl` fallen unter den Threshold und werden nicht mehr als `OK` akzeptiert.
- Offizielle Domains (`.gov`, `.gouv`, `.gv.`, `.pt`, `.gr`, `.de`, etc.) werden gegenüber generischen `.com`-Seiten bevorzugt.

#### Phase 3C: Selective Overrides & Quick Wins (✅ Abgeschlossen)

**Motivation:** Für politisch/fachlich kritische Metropolen (Paris, Madrid, Copenhagen, Lisbon, Valencia) und schwer heuristisch trennbare Fälle (Clubs, Unis, US-Gov) waren gezielte Overrides und semantische Filter nötig.

**Umgesetzte Maßnahmen:**

- Einführung von `data/city_url_overrides.json` mit manuellen URLs für:
  - `Madrid`, `Valencia`, `Lisbon`, `Copenhagen`, `Paris` (direkt auf offizielle Stadt-/Verwaltungsseiten).
- Erweiterung von `constants.py` um semantische Keyword-Listen:
  - `CLUB_KEYWORDS` (Sportvereine, z. B. `realmadrid`, `valencia cf`, `fc`, `club`)
  - `UNIVERSITY_KEYWORDS` (Unis/Hochschulen, z. B. `university`, `campus`, `hochschule`)
  - `AIRPORT_KEYWORDS` (Flughäfen/Airlines)
  - `RELIGIOUS_KEYWORDS` (Kathedralen/Kirchen)
  - `HOSPITALITY_KEYWORDS` (Hotels/Resorts/Spa)
  - `BUSINESS_KEYWORDS` (Versicherungen/Banken/Consultancies)
  - `NATIONAL_PORTAL_KEYWORDS` (nationale Tourismus-/Brandingportale wie `latvia.eu`, `spain.info`, `visitgreece`, `visitportugal`, `france.fr`, `germany.travel`).
 - Erweiterung des Scoring-Systems (ursprünglich `score_candidate`, jetzt Strategy-basiertes `ScoringEngine` in `scoring.py`) um:
  - **US-.gov-Hard-Reject** für nicht-US-Städte (z. B. `lisbonwi.gov` wird für Lissabon/Portugal verworfen).
  - **Club-/Uni-Penalties** sowie semantische Penalties für Airports/Hotels/Business/Religious-Sites.
  - Hard-Reject für `NATIONAL_PORTAL_KEYWORDS` im Host (Score direkt 0.0).
  - **Aktualisierung 2025-12:** `SemanticPenaltyRule` mit Hard-Reject für Club- und Airport-Hosts (z. B. `fcporto.pt`, `sofia-airport.eu` werden nie mehr als offizielle Stadtseiten akzeptiert).

**Beispiele aus dem Produktiv-Run:**
- Madrid, Valencia, Lisbon → stabil über Overrides auf offizielle Stadtseiten.
- Sofia → Airport- und Tourismus-Seiten fallen unter das Quality-Gate und werden nicht mehr als `OK` akzeptiert.
- Porto → Club-/Tourismus-Seiten (`fcporto.pt` etc.) werden nicht mehr akzeptiert; offizielle Stadtseite `cm-porto.pt` wird bevorzugt.
- Seville → Kathedralen-/Tourismus-Seiten fallen unter den Threshold.
- Riga, Vilnius → Stadt-/City-Marketing-Portale (`riga.lv`, `govilnius.lt`) werden korrekt bevorzugt.

**Aktuelle QA (Gold-Set, 19 Städte, Stand Dezember 2025):**
- **Exact Match Rate:** 14/19 ≈ **73.7%**.
- Kritische False Positives (Airport-/Club-Domains) sind im Gold-Set vollständig eliminiert.
- Verbleibende Fehlerfälle sind v. a. Such-/Disambiguation-Probleme (z. B. Berlin als `NOT_FOUND`, Madrid/Sofia/Warsaw mit Wikipedia- oder generischen `.com`-Treffern).

#### Phase 3D: Wikidata-Erweiterung & Robustheit (✅ Weitgehend abgeschlossen)

**Ziel:** Die Abhängigkeit vom Search-Fallback weiter reduzieren, indem Wikidata-Abfragen robuster und toleranter gegenüber Label-Varianten werden.

**Umgesetzte Maßnahmen (2025-12):**

- **Zweistufige SPARQL-Strategie:**
  - Strikte Typ-Filterung auf eine kuratierte Menge von city-ähnlichen Typen (`Q515` Stadt, `Q5119` Hauptstadt, `Q1221156` deutscher Stadtstaat, `Q200250` Metropole, `Q133442` Hauptstadt einer politischen Entität etc.) mit Sortierung nach `wikibase:sitelinks`.
  - Fallback-Query ohne `P31`-Filter, nur Label + `P856` + `sitelinks`, weiterhin deterministisch sortiert.

- **Wikidata Search API Fallback:**
  - Einsatz von `wbsearchentities` mit Query `"{city} {country}"`, um Labelvarianten wie "Seville"/"Sevilla" oder "Vitoria"/"Vitoria-Gasteiz" robust zu finden.
  - Für die gefundene `id` (z. B. `Q64` für Berlin) wird gezielt `P856` abgefragt.

- **Stabilität & Performance:**
  - Globale Rate-Limiting-Schicht für alle Wikidata/Wikimedia-Requests.
  - Retry-Logik mit Exponential Backoff bei Timeouts/Fehlern.
  - Persistenter JSON-Cache (`data/wikidata_cache.json`) für alle `query_wikidata`-Ergebnisse (inkl. negativer Treffer), um wiederholte Läufe deutlich zu beschleunigen und deterministisch zu machen.
  - Performance-Optimierung in der Pipeline: Wikidata-URLs werden als ausreichend vertrauenswürdig betrachtet und nicht mehr über `validate_and_parse_url` voll heruntergeladen.

**Ergebnis:**

- Deutlich mehr Städte werden direkt über Wikidata gefunden (inkl. vormals schwieriger Fälle wie Madrid, Seville, Gävle, Umeå, Warsaw, Porto, Dublin, Krakow etc.).
- Berlin kann – abhängig vom aktuellen Wikidata-Datensatz – über die Search-API + P856-Query als `https://www.berlin.de/` gefunden werden; bei fehlendem/instabilem P856 manifestiert sich dies korrekt als `NOT_FOUND`.
- Die Laufzeit über alle 91 NetZeroCities-Städte ist trotz Rate-Limiting praktikabel, während zweite/weitere Läufe durch den Cache sehr schnell werden.

**Offen (Optionen für spätere Iterationen):**

- Ergänzende Nutzung von Wikipedia-Sitelinks für Städte ohne P856.
- Datenseitige Qualitätssicherung in Wikidata (fehlende/falsche P856-Einträge melden oder korrigieren).

---

### Phase 4 – LLM-gestützte Validierung (optional)

- Einführung eines Moduls `llm_validation` mit konfigurierbarem Provider (API-Key/Modell via Config/ENV).
- Klassifikation der Top-N-Kandidaten pro Stadt in Kategorien (`OFFICIAL_CITY_WEBSITE`, `TOURISM_OR_TRAVEL`, `BUSINESS_OR_UNIVERSITY`, `OTHER_OR_SPAM`).
- Integration der LLM-Labels in das Quality-Gate (Ausschluss von Tourismus-/SEO-Seiten, Stärkung offizieller Treffer).
- Kosten- und Fehlertoleranz-Mechanismen (z. B. Deaktivieren der LLM-Schicht per Config, Fallback auf rein heuristischen Modus).

### Phase 5 – Feinschliff & Monitoring

#### 5.1 Gold-Set für Evaluierung (🎯 Nächster Schwerpunkt)

**Ziel:** Objektive Messung der Pipeline-Qualität nach jeder Änderung (insbesondere nach Scoring-/Heuristik-Anpassungen in Phase 3B/3C und künftiger Phase 3D).

**Aufbau (Status: Erste Version implementiert, Dezember 2025):**
- Aktuelles Gold-Set mit 19 Städten (`data/gold_set.csv`) und manuell recherchierten URL-Patterns.
- Abdeckung verschiedener Länder, Größen, Schwierigkeitsgrade und Problemklassen (Wikidata-Treffer, Search-Fallback, NOT_FOUND).
- Evaluationsskript `scripts/evaluate_results.py` vergleicht `output/city_urls.csv` mit dem Gold-Set.
  - Baseline-Run nach Phase 3B/3C: **14/19 korrekte Treffer (73.7% Accuracy)**.
  - Aktueller Run nach Phase 3D (Wikidata-Robustheit, Wikidata-Search-Fallback, Wikipedia-Hard-Reject): **17/19 korrekte Treffer (89.5% Accuracy)**.
    - Fehlerfälle im Gold-Set sind bewusst streng definiert (z. B. Berlin als `NOT_FOUND`, wenn Wikidata kein stabiles P856 liefert, sowie Florence mit strictem Pattern `firenze.it`).

**Metriken:**
- **Exact Match Rate**: `predicted_url == expected_url`
- **Acceptable Match Rate**: gleiche Domain, anderer Pfad/Subdomain
- **False Positive Rate**: falsche URL als `OK` klassifiziert
- **False Negative Rate**: korrekte URL als `NOT_FOUND` klassifiziert

**Prozess:**
1. Vor Scoring- oder Wikidata-Änderung: Baseline-Lauf über das Gold-Set.
2. Nach Änderung: Vergleichs-Lauf und Auswertung der Metriken.
3. Nur bei objektiv gleichbleibender oder verbesserter Qualität: Änderung dauerhaft übernehmen.

#### 5.2 Iterative Verbesserung

- Systematischer Spotcheck von Stichproben (z.B. 10–20 Städte je Land) gegen manuell recherchierte URLs
- Anpassung von Scoring-Gewichten, Black-/Whitelists und Thresholds auf Basis der Testergebnisse
- Ergänzung von Tests (Unit-Tests für Heuristiken, Integrationstests für die Pipeline)
- Dokumentation von Scoring-Regeln mit Begründung (gegen Magic Numbers)

#### 5.3 Priorisierung nach Impact

**Nicht alle Städte sind gleich wichtig.** Fokus auf:
- **Tier 1 (Kritisch)**: Hauptstädte, große Metropolen (Paris, Madrid, Berlin, etc.)
- **Tier 2 (Wichtig)**: Regionale Zentren, NetZeroCities-Koordinatoren
- **Tier 3 (Nice-to-have)**: Kleinere Städte

Qualitätsziel:
- Tier 1: >95% korrekte URLs
- Tier 2: >85% korrekte URLs
- Tier 3: >70% korrekte URLs

---

Diese Roadmap macht transparent, welcher Reifegrad aktuell erreicht ist (**Phase 3A abgeschlossen**, Phase 3B–3D in Planung) und welche Ausbaustufen geplant sind, um die fachliche Qualität der extrahierten Stadt-URLs schrittweise zu erhöhen.

---

## 19. Code-Qualitäts-Refactoring (Parallelphase)

Parallel zur funktionalen Entwicklung muss die Code-Qualität kontinuierlich gesichert werden. Nach einer Analyse der aktuellen Implementierung (Stand Phase 3) wurden folgende strukturelle Probleme identifiziert:

### 19.1 Identifizierte Probleme

**God Function: `score_candidate` (83 Zeilen)**
- Zu viele Verantwortlichkeiten: Blacklist-Check, Tourism-Check, City-Matching, Keyword-Detection, TLD-Checks, Country-Context, Maluses, Path-Analysis
- Magic Numbers ohne dokumentierte Begründung (`+0.2`, `+0.35`, `-0.3`, etc.)
- Schwer testbar und erweiterbar

**Große Funktionen: `query_wikidata` (76 Zeilen), `find_city_url` (72 Zeilen)**
- Vermischung von Query-Building, HTTP-Requests und Response-Parsing
- Business-Logik inline statt separierbar

**Konstanten-Flut (190 Zeilen)**
- `OFFICIAL_KEYWORDS`, `NEGATIVE_TERMS`, `COUNTRY_TLD_MAP` etc. machen die Hauptdatei unübersichtlich
- Erschwert Wartung (neue Sprachen/Länder hinzufügen)

### 19.2 Refactoring-Roadmap

#### **Refactoring Phase A – Modularisierung (Prio 1)**

**Ziel:** Konstanten und domänenspezifische Logik auslagern, ohne Funktionalität zu ändern.

**Schritte:**
1. **Konstanten auslagern** (`src/scraping_cityurls/constants.py`)
   - `OFFICIAL_KEYWORDS`, `NEGATIVE_TERMS`, `COUNTRY_TLD_MAP`, `GOVERNMENT_TLDS`, `EUROPEAN_CC_TLDS`, `SCORE_THRESHOLD`
   - Reduziert `city_url_extractor.py` von ~740 auf ~550 Zeilen
   - Zero Breaking Changes, reine Umorganisation

2. **Wikidata-Logik auslagern** (`src/scraping_cityurls/wikidata.py`)
   - Klasse `WikidataClient` mit Methoden:
     - `query_city_website(city, country) -> Optional[str]`
     - `_build_query(city, country) -> str`
     - `_execute_query(query) -> dict`
     - `_parse_website(response) -> Optional[str]`
   - Bessere Testbarkeit, klare Verantwortlichkeiten

#### **Refactoring Phase B – Scoring-System (✅ Implementiert)**

**Ziel:** `score_candidate` von einer monolithischen Funktion in ein erweiterbares, testbares System überführen.

**Design: Strategy Pattern**
```python
# src/scraping_cityurls/scoring.py

@dataclass
class ScoringContext:
    city: str
    url: str
    host: str
    path: str
    title: str
    country: Optional[str]
    # ... weitere Kontextfelder

class ScoringRule(Protocol):
    """Interface für einzelne Scoring-Regeln."""
    def apply(self, context: ScoringContext) -> float:
        """Gibt Score-Adjustment zurück. -1000.0 = Hard Reject."""
        ...

class BlacklistRule(ScoringRule):
    def apply(self, context: ScoringContext) -> float:
        if any(term in context.host for term in NEGATIVE_TERMS):
            return -1000.0  # Hard Reject
        return 0.0

class GovernmentTLDRule(ScoringRule):
    def apply(self, context: ScoringContext) -> float:
        if any(tld in context.host for tld in [".gov", ".gouv", ".gv."]):
            return 0.3
        return 0.0

class CityNameMatchRule(ScoringRule):
    def apply(self, context: ScoringContext) -> float:
        city_clean = context.city.lower().replace(" ", "").replace("-", "")
        host_clean = context.host.replace(".", "").replace("-", "")
        if city_clean in host_clean:
            return 0.2
        return 0.0

# ... weitere Rules

class ScoringEngine:
    def __init__(self, rules: List[ScoringRule], base_score: float = 0.5):
        self.rules = rules
        self.base_score = base_score
    
    def score(self, context: ScoringContext) -> float:
        score = self.base_score
        for rule in self.rules:
            adjustment = rule.apply(context)
            if adjustment == -1000.0:  # Hard Reject
                return 0.0
            score += adjustment
        return max(0.0, min(1.0, score))
```

**Vorteile:**
- Jede Regel einzeln unit-testbar
- Neue Regeln hinzufügen ohne bestehende zu ändern (Open/Closed Principle)
- Weights konfigurierbar (später aus Config-File)
- Debugging: welche Regel hat wie viel beigetragen?

**Zeitaufwand:** ~30 Minuten  
**Risiko:** Minimal (nur Importe ändern sich)  
**Status:** ✅ Abgeschlossen (Dezember 2025)

#### **Refactoring Phase C – Helper-Funktionen extrahieren (Prio 3)**

**Ziel:** Weitere God-Functions aufbrechen.

**Maßnahmen:**
- `find_city_url`: Trennung in Orchestrierung + einzelne Strategien
  - `_try_override_strategy`
  - `_try_wikidata_strategy`
  - `_try_search_engine_strategy`
  - `_try_domain_guess_strategy`
  - `_evaluate_candidates`
  - `_apply_quality_gate`

- `validate_and_parse_url`: Trennung in
  - `_fetch_url(url, timeout) -> requests.Response | None`
  - `_parse_html_metadata(response) -> dict`

**Zeitaufwand:** 1 Stunde  
**Risiko:** Gering  
**Zeitpunkt:** Nach Refactoring Phase B

#### **Refactoring Phase D – Konfiguration externalisieren (Prio 4)**

**Ziel:** Magic Numbers und Thresholds konfigurierbar machen.

**Implementierung:**
- Neue Datei `config/scoring_weights.yaml`:
  ```yaml
  scoring:
    base_score: 0.5
    threshold: 0.65
    rules:
      city_match: 0.2
      official_keywords: 0.35
      government_tld: 0.3
      country_tld_bonus: 0.25
      country_tld_malus: -0.2
      generic_tld_malus: -0.15
      tourism_keywords: -0.3
      blog_path: -0.2
  ```

- Laden via `pyyaml` in `Config`-Dataclass
- Scoring-Rules nutzen diese Weights statt Hard-Coded-Werte

**Zeitaufwand:** 1 Stunde  
**Risiko:** Gering  
**Zeitpunkt:** Nach Refactoring Phase B

### 19.3 Test-Strategie für Refactorings

Für jede Refactoring-Phase:

1. **Vor Refactoring:** Snapshot der aktuellen Ergebnisse
   - Skript auf alle Städte laufen lassen
   - Output speichern als `output/city_urls_before_refactoring.json`

2. **Nach Refactoring:** Vergleichs-Run
   - Erneut laufen lassen
   - Diff zwischen Vorher/Nachher prüfen
   - Bei identischem Output: Refactoring erfolgreich ohne Regression

3. **Unit-Tests ergänzen:**
   - Nach Phase B: Tests für jede `ScoringRule`
   - Test-Fixtures mit bekannten URLs und erwarteten Scores
   - Regression-Tests für Edge-Cases

### 19.4 Zusammenfassung Refactoring-Phasen

| Phase | Zeitaufwand | Risiko | Status | Priorität |
|-------|-------------|--------|--------|-----------|
| **Phase A: Modularisierung** | 30 Min | Minimal | ✅ Abgeschlossen | Prio 1 |
| **Phase B: Scoring-System** | 1–2h | Mittel | ✅ Abgeschlossen | Prio 2 |
| **Phase C: Helper-Extraktion** | 1h | Gering | 📋 Geplant | Prio 3 |
| **Phase D: Config externalisieren** | 1h | Gering | 📋 Geplant | Prio 4 |

**Gesamtziel:** Wartbare, testbare, erweiterbare Codebasis ohne "God Functions" oder "Ravioli Code".
