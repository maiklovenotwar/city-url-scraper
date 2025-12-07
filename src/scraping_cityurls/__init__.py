"""
scraping_cityurls: Tools zur Extraktion offizieller Stadt-Websites.

Öffentliche API:
- run_extraction(): führt den Standard-Extraktionslauf aus.
"""

from .city_url_extractor import main as run_extraction  # noqa: F401

__all__ = ["run_extraction"]