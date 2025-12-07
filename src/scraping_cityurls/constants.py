"""
Constants and configuration values for city URL extraction.

This module contains all keyword lists, domain patterns, and scoring thresholds
used by the city URL extraction pipeline.
"""

from typing import List

# HTTP Configuration
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

# Official Keywords (Multilingual)
# These terms indicate official government/municipality websites
OFFICIAL_KEYWORDS: list[str] = [
    # English
    "official website",
    "official city",
    "municipality",
    "city council",
    "town hall",
    "govt",
    # German
    "offizielle webseite",
    "stadtverwaltung",
    "rathaus",
    "gemeinde",
    "landeshauptstadt",
    "buergerservice",
    # French
    "site officiel",
    "mairie",
    "ville de",
    "metropole",
    "commune",
    # Spanish / Italian / Portuguese
    "ayuntamiento",
    "ajuntament",
    "comune",
    "citta di",
    "camara municipal",
    "municipio",
    # Polish / Eastern Europe
    "urząd",
    "miasto",
    "gmina",
    "magistrat",
    "samosprava",
    # Nordic
    "kommune",
    "stad",
    "kaupunki",
]

# Negative Terms (Blacklist)
# URLs containing these terms are likely NOT official city websites
NEGATIVE_TERMS: list[str] = [
    # Generic Portals & Social Media
    "wikipedia",
    "facebook",
    "instagram",
    "twitter",
    "linkedin",
    "youtube",
    "pinterest",
    "tripadvisor",
    "booking.com",
    "airbnb",
    "skyscanner",
    "lonelyplanet",
    "britannica",
    "skyscrapercity",
    "timeout.com",
    "worldtravelguide",
    "wikitravel",
    "foursquare",
    "hostelworld",
    "kayak",
    "expedia",
    "culture_trip",
    "thecrazytourist",
    # Domain Parking / Spam Indicators
    "sedo",
    "domain",
    "parking",
    "forsale",
    "kaufen",
    "ww1",
    "ww16",
    "ww2",
    # Tourism-related terms in URL (often private sites)
    "visit",
    "tourism",
    "tourist",
    "travel",
    "guide",
    "holiday",
    "vacation",
    "entdecken",
    "erleben",
    "urlaub",
    "reisen",
    "sightseeing",
    "what-to-do",
    "bezoek",
    "toerisme",
    "tourisme",
    "turismo",
    # Specific travel blog/portal domains (from findings)
    "grieksegids",
    "budapesttips",
    "frankrijk",
    "reistips",
    "stedentrip",
    "citytrip",
    "wikivoyage",
    "top10",
    "what-to-see",
]

# Sports Clubs & Teams Keywords
# URLs containing these terms are likely sports clubs, not city websites
CLUB_KEYWORDS: list[str] = [
    "fc",
    "cf",
    "club",
    "realmadrid",
    "real-madrid",
    "athletic",
    "sport",
    "soccer",
    "football",
    "basket",
    "racing",
    "united",
    "valencia cf",
    "valladolid",
]

# University & Education Keywords
# URLs containing these terms are likely universities, not city websites
UNIVERSITY_KEYWORDS: list[str] = [
    "university",
    "universit",
    "campus",
    "college",
    "uni-",
    "hochschule",
    "akademie",
    "polytechnic",
    "education",
    "student",
]

# Airport-related keywords
AIRPORT_KEYWORDS: list[str] = [
    "airport",
    "aeroport",
    "aeroporto",
    "flughafen",
    "airlines",
    "airline",
    "aviation",
]

# Religious sites (churches, cathedrals, etc.)
RELIGIOUS_KEYWORDS: list[str] = [
    "cathedral",
    "church",
    "basilica",
    "monastery",
    "saint",
    "sankt",
    "sanctuary",
]

# Hospitality / tourism businesses (hotels, resorts, spas)
HOSPITALITY_KEYWORDS: list[str] = [
    "hotel",
    "resort",
    "spa",
    "apartments",
    "hostel",
    "accommodation",
    "booking",
]

# Generic business domains (banks, insurers, consultancies, law firms)
BUSINESS_KEYWORDS: list[str] = [
    "insurance",
    "seguro",
    "assurance",
    "bank",
    "consulting",
    "law",
    "gmbh",
    "ltd",
    "inc",
]

# National tourism/branding portals (not city-specific)
NATIONAL_PORTAL_KEYWORDS: list[str] = [
    "latvia.eu",
    "spain.info",
    "visitgreece",
    "visitportugal",
    "france.fr",
    "germany.travel",
]

# Government TLDs
# Top-level domains typically used by government institutions
GOVERNMENT_TLDS = [
    ".gov",
    ".gob",
    ".gouv",
    ".gv.",
]

# European Country-Code TLDs
# Common TLDs for European countries
EUROPEAN_CC_TLDS = [
    ".de",
    ".fr",
    ".es",
    ".it",
    ".pl",
    ".nl",
    ".be",
    ".at",
    ".dk",
    ".se",
    ".no",
    ".fi",
    ".cz",
    ".sk",
    ".hu",
    ".pt",
    ".ie",
    ".gr",
    ".eu",
    ".uk",
]

# Country to TLD Mapping
# Maps country names (and variations) to their typical TLDs
COUNTRY_TLD_MAP: dict[str, List[str]] = {
    "Germany": [".de"],
    "Deutschland": [".de"],
    "DE": [".de"],
    "France": [".fr", ".gouv.fr"],
    "Frankreich": [".fr"],
    "FR": [".fr"],
    "Austria": [".at", ".gv.at"],
    "Österreich": [".at"],
    "AT": [".at"],
    "Spain": [".es"],
    "Spanien": [".es"],
    "ES": [".es"],
    "Italy": [".it"],
    "Italien": [".it"],
    "IT": [".it"],
    "Poland": [".pl", ".gov.pl"],
    "Polen": [".pl"],
    "PL": [".pl"],
    "Sweden": [".se"],
    "Schweden": [".se"],
    "SE": [".se"],
    "Finland": [".fi"],
    "Finnland": [".fi"],
    "FI": [".fi"],
    "Portugal": [".pt"],
    "PT": [".pt"],
    "Netherlands": [".nl"],
    "Niederlande": [".nl"],
    "NL": [".nl"],
    "Belgium": [".be"],
    "Belgien": [".be"],
    "BE": [".be"],
    "Denmark": [".dk"],
    "Dänemark": [".dk"],
    "DK": [".dk"],
    "Greece": [".gr", ".gov.gr"],
    "Griechenland": [".gr"],
    "GR": [".gr"],
}

# Scoring Configuration
# Minimum score required for a URL to be accepted as official
SCORE_THRESHOLD = 0.65
