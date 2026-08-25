from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from random import uniform
from typing import List, Optional, TypedDict

import pandas as pd
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

from .constants import (
    SCORE_THRESHOLD,
    USER_AGENT,
)
from .scoring import DEFAULT_SCORING_ENGINE

# Wikidata caching and rate limiting
WIKIDATA_CACHE_FILE = Path("data/wikidata_cache.json")
_last_wikidata_request = 0.0
WIKIDATA_RATE_LIMIT = 1.0  # Minimum seconds between requests


class CityData(TypedDict, total=False):
    city: str
    country: Optional[str]


class ExtractionResult(TypedDict, total=False):
    city: str
    official_url: Optional[str]
    status: str
    notes: Optional[str]


@dataclass
class Config:
    base_dir: Path
    input_excel_path: Path
    output_excel_path: Path
    output_csv_path: Path
    output_json_path: Path
    logs_dir: Path
    log_file_path: Path
    http_timeout_seconds: int = 10
    rate_limit_seconds: float = 1.0


def setup_logging(config: Config) -> logging.Logger:
    config.logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("city_url_extractor")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers in case of multiple setup calls
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(config.log_file_path)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("duckduckgo_search").setLevel(logging.WARNING)

    return logger


def load_cities(path: Path, logger: logging.Logger) -> List[CityData]:
    if not path.exists():
        msg = f"Input Excel file not found at: {path}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    try:
        df = pd.read_excel(path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to read Excel file %s: %s", path, exc)
        raise

    candidate_columns = ["cities", "city"]
    normalized_map = {str(col).strip().lower(): col for col in df.columns}

    city_column: Optional[str] = None

    for candidate in candidate_columns:
        if candidate in normalized_map:
            city_column = normalized_map[candidate]
            break

    if city_column is None:
        msg = (
            "Expected one of logical columns 'Cities' or 'City' not found in Excel file. "
            f"Available columns: {list(df.columns)}"
        )
        logger.error(msg)
        raise ValueError(msg)

    logger.info("Using column '%s' for city names", city_column)

    country_column: Optional[str] = None
    if "country" in normalized_map:
        country_column = normalized_map["country"]

    df = df.dropna(subset=[city_column])  # type: ignore[assignment]

    cities: List[CityData] = []
    for idx, value in enumerate(df[city_column].astype(str)):
        value = value.strip()
        if not value:
            continue
        city_data: CityData = {"city": value}
        if country_column is not None:
            raw_country = str(df.iloc[idx][country_column])
            raw_country = raw_country.strip()
            if raw_country:
                city_data["country"] = raw_country
        cities.append(city_data)

    logger.info("Loaded %d cities from %s", len(cities), path)
    return cities


def save_results(results: List[ExtractionResult], output_excel_path: Path, output_csv_path: Path, output_json_path: Path, logger: logging.Logger) -> None:
    if not results:
        logger.warning("No results to save. Skipping output files.")
        return

    df = pd.DataFrame(results)

    try:
        output_excel_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(output_excel_path, index=False)
        logger.info("Saved results to Excel: %s", output_excel_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to write Excel results to %s: %s", output_excel_path, exc)

    try:
        df.to_csv(output_csv_path, index=False)
        logger.info("Saved results to CSV: %s", output_csv_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to write CSV results to %s: %s", output_csv_path, exc)

    try:
        df.to_json(output_json_path, orient="records", force_ascii=False, indent=2)
        logger.info("Saved results to JSON: %s", output_json_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to write JSON results to %s: %s", output_json_path, exc)


def validate_and_parse_url(url: str, timeout: int) -> Optional[dict]:
    logger = logging.getLogger("city_url_extractor")
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    except requests.exceptions.RequestException as exc:  # noqa: BLE001
        logger.debug("Request failed for %s: %s", url, exc)
        time.sleep(uniform(1, 2))
        return None

    try:
        status_ok = 200 <= response.status_code < 400
        if not status_ok:
            logger.debug("Non-success status %s for %s", response.status_code, url)
            time.sleep(uniform(1, 2))
            return None

        final_url = str(response.url)
        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        title_tag = soup.title.string if soup.title and soup.title.string else ""
        title = title_tag.strip()
        text = soup.get_text(separator=" ", strip=True)
        text_snippet = text[:200]
    finally:
        time.sleep(uniform(1, 2))

    return {
        "url": final_url,
        "title": title,
        "text_snippet": text_snippet,
    }
    # score_candidate was migrated to the Strategy-based ScoringEngine in
    # scoring.py (DEFAULT_SCORING_ENGINE).


def load_overrides(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    overrides: dict[str, str] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            overrides[key] = value
    return overrides


def _load_wikidata_cache() -> dict[str, str]:
    """Load the Wikidata cache from disk.
    
    Returns a dict mapping cache keys to URLs (empty string for None results).
    """
    if not WIKIDATA_CACHE_FILE.exists():
        return {}
    try:
        with WIKIDATA_CACHE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def _save_wikidata_cache(cache: dict[str, str]) -> None:
    """Save the Wikidata cache to disk."""
    WIKIDATA_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with WIKIDATA_CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def _wikidata_rate_limited_request(url: str, params: dict[str, str], logger: logging.Logger, timeout: int = 10) -> Optional[requests.Response]:
    """Helper to perform a rate-limited HTTP request to Wikidata/Wikimedia APIs."""

    global _last_wikidata_request

    # Enforce global rate limit across SPARQL + API calls
    elapsed = time.time() - _last_wikidata_request
    if elapsed < WIKIDATA_RATE_LIMIT:
        time.sleep(WIKIDATA_RATE_LIMIT - elapsed)

    _last_wikidata_request = time.time()

    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        return response
    except requests.exceptions.RequestException as exc:  # noqa: BLE001
        logger.debug("Wikidata API request failed: %s", exc)
        return None


def _search_wikidata_entity(city: str, country_hint: Optional[str], logger: logging.Logger) -> Optional[str]:
    """Fallback search using the Wikidata wbsearchentities API.

    This helps with label variants like "Seville" vs "Sevilla" or
    "Vitoria" vs "Vitoria-Gasteiz" by searching in English with a
    combined "city country" query.
    """

    search_query = city.strip()
    if country_hint:
        search_query = f"{search_query} {country_hint.strip()}"

    if not search_query:
        return None

    logger.debug("Wikidata search API fallback for query: %s", search_query)

    params = {
        "action": "wbsearchentities",
        "search": search_query,
        "language": "en",
        "format": "json",
        "limit": "1",
    }

    response = _wikidata_rate_limited_request("https://www.wikidata.org/w/api.php", params, logger, timeout=5)
    if response is None:
        return None

    if not (200 <= response.status_code < 300):
        logger.debug("Wikidata search API returned status %s for %s", response.status_code, search_query)
        return None

    try:
        data = response.json()
    except ValueError:  # JSON decode error
        logger.debug("Failed to decode Wikidata search API response for %s", search_query)
        return None

    search_results = data.get("search", [])
    if not search_results:
        logger.debug("Wikidata search API found no entities for %s", search_query)
        return None

    first = search_results[0]
    entity_id = first.get("id")
    if isinstance(entity_id, str) and entity_id:
        return entity_id

    return None


def _execute_sparql(query: str, logger: logging.Logger, max_retries: int = 2) -> Optional[dict]:
    """Execute a SPARQL query against Wikidata with retry logic and rate limiting.

    Returns the decoded JSON dict on success, or None on any HTTP/parse error.
    """
    global _last_wikidata_request

    for attempt in range(max_retries + 1):
        try:
            response = _wikidata_rate_limited_request(
                "https://query.wikidata.org/sparql",
                params={"query": query},
                logger=logger,
                timeout=10,
            )
        except requests.exceptions.Timeout:
            logger.debug("Wikidata timeout on attempt %d/%d", attempt + 1, max_retries + 1)
            if attempt < max_retries:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s
                time.sleep(wait_time)
                continue
            return None
        except requests.exceptions.RequestException as exc:  # noqa: BLE001
            logger.debug("Wikidata request failed on attempt %d/%d: %s", attempt + 1, max_retries + 1, exc)
            if attempt < max_retries:
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue
            return None

        if response is None:
            if attempt < max_retries:
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue
            return None

        if not (200 <= response.status_code < 300):
            logger.debug("Wikidata returned status %s on attempt %d/%d", response.status_code, attempt + 1, max_retries + 1)
            if attempt < max_retries:
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue
            return None

        try:
            data = response.json()
            return data
        except ValueError:  # JSON decode error
            logger.debug("Failed to decode Wikidata response JSON on attempt %d/%d", attempt + 1, max_retries + 1)
            if attempt < max_retries:
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue
            return None

    return None


def query_wikidata(city: str, country_hint: Optional[str] = None) -> Optional[str]:
    """Query Wikidata for the official website (P856) of a city.

    Two-step strategy (Phase 3D):

    1. Strict type-filtered query using a curated list of city-like types
       (city, capital city, metropolis, state of Germany, etc.).
    2. If that yields no result, fall back to a more permissive query that only
       matches by label + P856 and sorts by sitelinks (popularity). This
       ensures we still find major cities like Berlin, even if their primary
       type is more complex (e.g. state + capital).
    """

    logger = logging.getLogger("city_url_extractor")

    label = city.strip()
    if not label:
        return None

    # Check cache first
    cache = _load_wikidata_cache()
    cache_key = f"{label}|{country_hint or ''}"
    if cache_key in cache:
        cached_url = cache[cache_key]
        if cached_url:  # Non-empty string means we have a URL
            logger.debug("Wikidata cache hit for %s", label)
            return cached_url
        else:  # Empty string means we cached a None result
            logger.debug("Wikidata cache hit (no result) for %s", label)
            return None

    # Escape quotes for SPARQL string literal
    escaped_label = label.replace("\"", "\\\"")

    # Step 1: strict type-filtered query with deterministic sorting
    strict_query = f"""
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX wikibase: <http://wikiba.se/ontology#>

SELECT ?item ?website ?sitelinks WHERE {{
  # Direct instance-of match for various city types
  # Q515=city, Q1549591=big city, Q208511=district, Q3957=town
  # Q5119=capital city, Q1221156=state of Germany (Berlin/Hamburg/Bremen)
  # Q200250=metropolis, Q133442=capital of political entity
  VALUES ?cityType {{ wd:Q515 wd:Q1549591 wd:Q208511 wd:Q3957 wd:Q5119 wd:Q1221156 wd:Q200250 wd:Q133442 }}
  ?item wdt:P31 ?cityType .
  
  # Label matching with language filter
  ?item rdfs:label ?label .
  FILTER (LANG(?label) IN ('en', 'de', 'fr', 'es', 'it', 'pl', 'pt', 'nl', 'sv', 'fi'))
  FILTER (STR(?label) = "{escaped_label}")
  
  # Must have official website
  ?item wdt:P856 ?website .
  
  # Sitelinks for sorting (prioritize notable cities)
  ?item wikibase:sitelinks ?sitelinks .
}}
ORDER BY DESC(?sitelinks) ASC(?item)
LIMIT 1
"""

    data = _execute_sparql(strict_query, logger)
    if data is not None:
        bindings = data.get("results", {}).get("bindings", [])
        if bindings:
            website = bindings[0].get("website", {}).get("value")
            if isinstance(website, str) and website:
                logger.debug("Wikidata (strict) found website for %s: %s", city, website)
                # Cache the result
                cache[cache_key] = website
                _save_wikidata_cache(cache)
                return website

    # Step 2: fallback query without P31 cityType filter, only label + P856 with deterministic sorting
    fallback_query = f"""
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX wikibase: <http://wikiba.se/ontology#>

SELECT ?item ?website ?sitelinks WHERE {{
  ?item rdfs:label ?label .
  FILTER (LANG(?label) IN ('en', 'de', 'fr', 'es', 'it', 'pl', 'pt', 'nl', 'sv', 'fi'))
  FILTER (STR(?label) = "{escaped_label}")

  # Must have official website
  ?item wdt:P856 ?website .

  # Sitelinks for sorting (prioritize notable entities)
  ?item wikibase:sitelinks ?sitelinks .
}}
ORDER BY DESC(?sitelinks) ASC(?item)
LIMIT 1
"""

    data_fallback = _execute_sparql(fallback_query, logger)
    if data_fallback is not None:
        bindings_fallback = data_fallback.get("results", {}).get("bindings", [])
        if bindings_fallback:
            website = bindings_fallback[0].get("website", {}).get("value")
            if isinstance(website, str) and website:
                logger.debug("Wikidata (fallback) found website for %s: %s", city, website)
                # Cache the result
                cache[cache_key] = website
                _save_wikidata_cache(cache)
                return website

    # Step 3: Wikidata Search API fallback to resolve label variants
    entity_id = _search_wikidata_entity(city=label, country_hint=country_hint, logger=logger)
    if entity_id:
        # Query P856 for the specific entity ID
        entity_query = f"""
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>

SELECT ?website WHERE {{
  wd:{entity_id} wdt:P856 ?website .
}}
LIMIT 1
"""

        data_entity = _execute_sparql(entity_query, logger)
        if data_entity is not None:
            bindings_entity = data_entity.get("results", {}).get("bindings", [])
            if bindings_entity:
                website = bindings_entity[0].get("website", {}).get("value")
                if isinstance(website, str) and website:
                    logger.debug("Wikidata (search+entity) found website for %s: %s", city, website)
                    cache[cache_key] = website
                    _save_wikidata_cache(cache)
                    return website

    # Cache negative result (no website found)
    logger.debug("Wikidata found no website for %s (strict + fallback + search)", city)
    cache[cache_key] = ""  # Empty string indicates cached None
    _save_wikidata_cache(cache)
    return None


def strategy_search_engine(city: str) -> List[str]:
    query = f"{city} official website"
    results: List[str] = []

    try:
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=5):
                href = item.get("href") or item.get("url")
                if not href:
                    continue
                if href not in results:
                    results.append(href)
                if len(results) >= 3:
                    break
    except Exception:  # noqa: BLE001
        logger = logging.getLogger("city_url_extractor")
        logger.debug("DuckDuckGo search failed for '%s'", city)

    return results


def _normalize_city_for_domain(city: str) -> str:
    city_l = city.lower()
    cleaned = "".join(ch for ch in city_l if ch.isalnum())
    return cleaned


def strategy_guess_domain(city: str) -> List[str]:
    base = _normalize_city_for_domain(city)
    if not base:
        return []

    hosts = [
        f"www.{base}.de",
        f"www.{base}.com",
        f"www.{base}.eu",
        f"www.{base}.org",
        f"{base}.gov",
    ]

    urls = [f"https://{h}" for h in hosts]
    return urls


def find_city_url(city_name: str, country_hint: Optional[str], overrides: dict[str, str]) -> ExtractionResult:
    """
    Find the official URL for a city using multiple strategies in order of reliability.

    Strategy order (with graceful degradation):
    1. Manual overrides (highest trust)
    2. Wikidata structured data (high trust, if available)
    3. Web search + heuristic scoring (fallback)
    4. Domain guessing (last resort)

    Args:
        city_name: Name of the city to search for
        country_hint: Optional country context for better matching
        overrides: Manual URL mappings from override file

    Returns:
        ExtractionResult with found URL or NOT_FOUND status
    """
    logger = logging.getLogger("city_url_extractor")

    # Strategy 1: Check manual overrides first (highest priority)
    if city_name in overrides:
        override_url = overrides[city_name]
        data = validate_and_parse_url(override_url, timeout=10)
        if data:
            return ExtractionResult(
                city=city_name,
                official_url=data.get("url"),
                status="OK",
                notes="Source: Override",
            )

    # Strategy 2: Try Wikidata structured data (NEW - Phase 3)
    # Graceful degradation: if Wikidata fails, continue with web search
    # Performance optimization (Phase 3D): Wikidata URLs are trusted enough to
    # skip full HTML validation. This avoids an extra HTTP roundtrip per city.
    try:
        wikidata_url = query_wikidata(city_name, country_hint)
        if wikidata_url:
            logger.info("Found candidate via Wikidata for %s: %s", city_name, wikidata_url)
            return ExtractionResult(
                city=city_name,
                official_url=wikidata_url,
                status="OK",
                notes="Source: Wikidata",
            )
    except Exception as exc:  # noqa: BLE001
        # Don't let Wikidata errors break the entire pipeline
        logger.debug("Wikidata query failed for %s: %s", city_name, exc)

    # Strategy 3 & 4: Fallback to web search + domain guessing
    candidates: List[str] = strategy_search_engine(city_name)
    if not candidates:
        logger.info("No search engine results for %s, using domain guessing.", city_name)
        candidates = strategy_guess_domain(city_name)
    else:
        candidates.extend(strategy_guess_domain(city_name))

    if not candidates:
        return ExtractionResult(
            city=city_name,
            official_url=None,
            status="NOT_FOUND",
            notes="No URL candidates generated.",
        )

    evaluated: List[tuple[float, dict]] = []
    max_validated = 5
    for cand in candidates[:max_validated]:
        data = validate_and_parse_url(cand, timeout=10)
        if not data:
            continue
        score = DEFAULT_SCORING_ENGINE.score(city_name, data, country_hint)
        evaluated.append((score, data))

    if not evaluated:
        return ExtractionResult(
            city=city_name,
            official_url=None,
            status="NOT_FOUND",
            notes="No candidate passed validation.",
        )

    evaluated.sort(key=lambda x: x[0], reverse=True)
    best_score, best_data = evaluated[0]

    if best_score < SCORE_THRESHOLD:
        return ExtractionResult(
            city=city_name,
            official_url=best_data.get("url"),
            status="NOT_FOUND",
            notes=f"Best score below threshold: {best_score:.2f}",
        )

    status = "OK"
    notes = f"Source: Search, Score={best_score:.2f}"

    if len(evaluated) > 1:
        second_score = evaluated[1][0]
        if abs(best_score - second_score) < 0.1 and second_score >= SCORE_THRESHOLD:
            status = "MULTIPLE"
            notes = f"Source: Search, Multiple good candidates, best score={best_score:.2f}, second={second_score:.2f}"

    return ExtractionResult(
        city=city_name,
        official_url=best_data.get("url"),
        status=status,
        notes=notes,
    )


def ensure_input_file(config: Config, logger: logging.Logger) -> None:
    if config.input_excel_path.exists():
        return

    logger.info("Input file %s does not exist. Creating dummy file for test run.", config.input_excel_path)

    config.input_excel_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame({"City": ["Berlin"]})

    try:
        df.to_excel(config.input_excel_path, index=False)
        logger.info("Dummy Excel file created at %s", config.input_excel_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to create dummy Excel file at %s: %s", config.input_excel_path, exc)
        raise


def main() -> None:
    # Von src/scraping_cityurls/ zwei Ebenen nach oben zum Projektroot
    project_root = Path(__file__).resolve().parents[2]

    config = Config(
        base_dir=project_root,
        input_excel_path=project_root / "data" / "netzerocities.xlsx",
        output_excel_path=project_root / "output" / "city_urls.xlsx",
        output_csv_path=project_root / "output" / "city_urls.csv",
        output_json_path=project_root / "output" / "city_urls.json",
        logs_dir=project_root / "logs",
        log_file_path=project_root / "logs" / "city_url_extractor.log",
    )

    logger = setup_logging(config)

    logger.info("Starting city URL extraction process.")

    # Verification step: ensure input file exists, create dummy if necessary.
    try:
        ensure_input_file(config, logger)
    except Exception:
        logger.error("Aborting due to failure while ensuring input file.")
        return

    try:
        cities = load_cities(config.input_excel_path, logger)
    except Exception:
        logger.error("Aborting due to failure while loading cities.")
        return

    overrides_path = config.base_dir / "data" / "city_url_overrides.json"
    overrides = load_overrides(overrides_path)

    results: List[ExtractionResult] = []

    for city_data in cities:
        city_name = city_data["city"]
        country_hint = city_data.get("country")
        logger.info("Processing city: %s", city_name)

        result = find_city_url(city_name=city_name, country_hint=country_hint, overrides=overrides)
        results.append(result)

    save_results(
        results=results,
        output_excel_path=config.output_excel_path,
        output_csv_path=config.output_csv_path,
        output_json_path=config.output_json_path,
        logger=logger,
    )

    logger.info("City URL extraction process finished.")


if __name__ == "__main__":
    main()
