"""Scoring strategies for evaluating candidate city URLs.

This module implements Refactoring Phase B: the monolithic ``score_candidate``
function from ``city_url_extractor.py`` is replaced by a Strategy-based
``ScoringEngine`` composed of small, testable rules.

The goal of this refactor is to preserve the existing scoring behaviour as
weitgehend wie möglich, aber jede Regel klar zu kapseln.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol
from urllib.parse import ParseResult, urlparse

from .constants import (
    AIRPORT_KEYWORDS,
    BUSINESS_KEYWORDS,
    CLUB_KEYWORDS,
    COUNTRY_TLD_MAP,
    HOSPITALITY_KEYWORDS,
    NATIONAL_PORTAL_KEYWORDS,
    NEGATIVE_TERMS,
    OFFICIAL_KEYWORDS,
    RELIGIOUS_KEYWORDS,
    UNIVERSITY_KEYWORDS,
)

HARD_REJECT = -1000.0


@dataclass
class ScoringContext:
    city: str
    url: str
    title: str
    text_snippet: str
    country: Optional[str]
    parsed_url: ParseResult
    host: str
    path: str


class ScoringRule(Protocol):
    """Interface for individual scoring rules.

    The rule returns a score adjustment. ``HARD_REJECT`` (-1000.0) means the
    candidate should be rejected immediately.
    """

    def apply(self, context: ScoringContext, current_score: float) -> float:  # pragma: no cover - interface
        ...


class HardBlacklistRule:
    """Hard reject for clearly unwanted hosts.

    - Hosts containing any ``NEGATIVE_TERMS``
    - Hosts containing any ``NATIONAL_PORTAL_KEYWORDS``
    """

    def apply(self, context: ScoringContext, current_score: float) -> float:
        host = context.host
        for term in NEGATIVE_TERMS:
            if term in host:
                return HARD_REJECT
        for term in NATIONAL_PORTAL_KEYWORDS:
            if term in host:
                return HARD_REJECT
        return 0.0


class USGovMismatchRule:
    """Hard reject .gov domains for non-US cities.

    In der bisherigen Logik wurden .gov-Domains nur für US-Städte erlaubt.
    """

    def apply(self, context: ScoringContext, current_score: float) -> float:
        host = context.host
        country = context.country

        if country is None:
            return 0.0

        if host.endswith(".gov"):
            country_normalized = country.strip().lower()
            if country_normalized not in {"united states", "usa", "us"}:
                return HARD_REJECT

        return 0.0


class TourismTitleRule:
    """Penalise obviously touristic titles (best things to do, travel guide, etc.)."""

    _NEGATIVE_TITLE_SNIPPETS = [
        "best things to do",
        "top 10",
        "travel guide",
        "hotel",
        "weather",
        "wetter",
    ]

    def apply(self, context: ScoringContext, current_score: float) -> float:
        title = context.title
        if any(snippet in title for snippet in self._NEGATIVE_TITLE_SNIPPETS):
            return -0.3
        return 0.0


class TourismPathRule:
    """Penalise blog/guide/tourism paths and host-level visit/travel markers.

    Im ursprünglichen Code wurde bei ``visit``/``touris``/``travel`` im Host
    frühzeitig ein sehr niedriger Score zurückgegeben. Im Strategy-Modell
    approximieren wir dieses Verhalten durch einen zusätzlichen Malus.
    """

    _TOURISM_PATH_KEYWORDS = [
        "blog",
        "article",
        "guide",
        "tips",
        "reistips",
        "bezienswaardigheden",
        "reisen",
        "tourism",
        "stedentrip",
        "things-to-do",
        "what-to-see",
        "top10",
    ]

    def apply(self, context: ScoringContext, current_score: float) -> float:
        path = context.path
        adjustment = 0.0

        if any(keyword in path for keyword in self._TOURISM_PATH_KEYWORDS):
            # Basis-Malus wie zuvor
            adjustment -= 0.2
            # Hard-Cap: tourism/blog paths can never reach OK threshold (0.6)
            projected = current_score + adjustment
            if projected > 0.6:
                # Zusätzlicher Malus, um auf 0.6 zu kappen
                adjustment -= projected - 0.6

        return adjustment


class VisitHostRule:
    """Approximate the old early-return behaviour for visit/travel hosts.

    Im ursprünglichen Code wurde bei ``visit``/``touris``/``travel`` im Host
    sofort ein Score von 0.1 zurückgegeben. Hier setzen wir den Score
    entsprechend auf 0.1 (unabhängig von anderen Regeln).
    """

    def apply(self, context: ScoringContext, current_score: float) -> float:
        host = context.host
        if "visit" in host or "touris" in host or "travel" in host:
            # Set score to exactly 0.1
            return 0.1 - current_score
        return 0.0


class CityNameMatchRule:
    """Boost if the city name appears in the host label."""

    def apply(self, context: ScoringContext, current_score: float) -> float:
        city_clean = context.city.lower().replace(" ", "").replace("-", "")
        host_clean = context.host.replace(".", "").replace("-", "")
        if city_clean and city_clean in host_clean:
            return 0.2
        return 0.0


class OfficialSignalRule:
    """Boost for official/municipality keywords in the title."""

    def apply(self, context: ScoringContext, current_score: float) -> float:
        title = context.title
        if any(kw in title for kw in OFFICIAL_KEYWORDS):
            return 0.35
        return 0.0


class GovernmentTLDRule:
    """Boost for government-like hosts (.gov/.gouv/.gv./.mil)."""

    def apply(self, context: ScoringContext, current_score: float) -> float:
        host = context.host
        if ".gov" in host or ".gouv" in host or ".gv." in host or ".mil" in host:
            return 0.3
        return 0.0


class CountryTLDRule:
    """Bonus for matching country TLD, malus for foreign ccTLD.

    Implementiert die bestehende Logik:
    - +0.25 bei passender TLD
    - -0.25 bei fremder Country-TLD (nicht neutral)
    """

    def apply(self, context: ScoringContext, current_score: float) -> float:
        country = context.country
        host = context.host

        if not country:
            return 0.0

        country_key = country.strip()
        expected_tlds = COUNTRY_TLD_MAP.get(country_key)
        if not expected_tlds:
            return 0.0

        if any(host.endswith(tld) for tld in expected_tlds):
            return 0.25

        # Fremde Country-TLDs bestrafen (nicht neutral)
        all_country_tlds: set[str] = set()
        for tlds in COUNTRY_TLD_MAP.values():
            all_country_tlds.update(tlds)

        neutral_tlds = {".com", ".org", ".eu", ".net"}
        is_neutral = any(host.endswith(tld) for tld in neutral_tlds)

        if not is_neutral and any(host.endswith(tld) for tld in all_country_tlds):
            return -0.25

        return 0.0


class GenericTLDMalusRule:
    """Malus für generische TLDs (.com, .net, .info, .biz, .org)."""

    def apply(self, context: ScoringContext, current_score: float) -> float:
        host = context.host
        if host.endswith((".com", ".net", ".info", ".biz", ".org")):
            return -0.15
        return 0.0


class SemanticPenaltyRule:
    """Penalties for clubs, universities, airports, hospitality, business, religion."""

    def apply(self, context: ScoringContext, current_score: float) -> float:
        host = context.host
        title = context.title
        adjustment = 0.0

        # Clubs and airports are never official city portals: hard reject on host match
        if any(kw in host for kw in CLUB_KEYWORDS):
            return HARD_REJECT

        if any(kw in host for kw in AIRPORT_KEYWORDS):
            return HARD_REJECT

        # The remaining categories get strong penalties but are not absolute blockers
        if any(kw in host or kw in title for kw in CLUB_KEYWORDS):
            adjustment -= 0.4
        if any(kw in host or kw in title for kw in UNIVERSITY_KEYWORDS):
            adjustment -= 0.5
        if any(kw in host or kw in title for kw in HOSPITALITY_KEYWORDS):
            adjustment -= 0.4
        if any(kw in host or kw in title for kw in BUSINESS_KEYWORDS):
            adjustment -= 0.4
        if any(kw in host or kw in title for kw in RELIGIOUS_KEYWORDS):
            adjustment -= 0.4

        return adjustment


class WikipediaRule:
    """Hard-reject Wikipedia and Wikivoyage as official city websites.
    
    Wikipedia articles are never official city portals, even if they contain
    accurate information. This rule ensures they are filtered out early.
    """

    def apply(self, context: ScoringContext, current_score: float) -> float:
        host = context.host
        if "wikipedia.org" in host or "wikivoyage.org" in host:
            return HARD_REJECT
        return 0.0


class EuropeanCCTLDHintRule:
    """Leichter Bonus für europäische ccTLDs (entspricht altem +0.1)."""

    _EU_TLDS = (
        ".de",
        ".fr",
        ".it",
        ".es",
        ".pl",
        ".nl",
        ".be",
        ".at",
        ".dk",
        ".se",
        ".fi",
        ".pt",
        ".gr",
        ".ro",
        ".hr",
    )

    def apply(self, context: ScoringContext, current_score: float) -> float:
        host = context.host
        if host.endswith(self._EU_TLDS):
            return 0.1
        return 0.0


class ScoringEngine:
    """Composite scoring engine based on a list of rules."""

    def __init__(self, rules: List[ScoringRule], base_score: float = 0.5) -> None:
        self.rules = rules
        self.base_score = base_score

    def _build_context(self, city: str, url_data: dict, country: Optional[str]) -> ScoringContext:
        raw_url = url_data.get("url", "") or ""
        parsed = urlparse(raw_url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        title = (url_data.get("title") or "").lower()
        text_snippet = (url_data.get("text_snippet") or "").lower()

        return ScoringContext(
            city=city,
            url=raw_url,
            title=title,
            text_snippet=text_snippet,
            country=country,
            parsed_url=parsed,
            host=host,
            path=path,
        )

    def score(self, city: str, url_data: dict, country: Optional[str] = None) -> float:
        context = self._build_context(city=city, url_data=url_data, country=country)

        score = self.base_score
        for rule in self.rules:
            adjustment = rule.apply(context, score)
            if adjustment == HARD_REJECT:
                return 0.0
            score += adjustment

        # Clamp score to [0.0, 1.0]
        if score < 0.0:
            return 0.0
        if score > 1.0:
            return 1.0
        return score


DEFAULT_SCORING_ENGINE = ScoringEngine(
    rules=[
        HardBlacklistRule(),
        USGovMismatchRule(),
        WikipediaRule(),
        VisitHostRule(),
        TourismTitleRule(),
        TourismPathRule(),
        CityNameMatchRule(),
        OfficialSignalRule(),
        GovernmentTLDRule(),
        EuropeanCCTLDHintRule(),
        CountryTLDRule(),
        GenericTLDMalusRule(),
        SemanticPenaltyRule(),
    ]
)
