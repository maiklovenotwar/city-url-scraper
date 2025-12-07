from unittest.mock import MagicMock, patch

import requests

from scraping_cityurls.city_url_extractor import query_wikidata


def _make_response(status_code: int, json_data: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    if json_data is not None:
        response.json.return_value = json_data
    else:
        response.json.side_effect = ValueError("No JSON")
    return response


def test_query_wikidata_success() -> None:
    # Updated to match new SPARQL query response structure
    bindings = [
        {
            "website": {"type": "uri", "value": "https://berlin.de"},
            "sitelinks": {"type": "literal", "value": "234"},
        }
    ]
    json_payload = {"results": {"bindings": bindings}}

    with patch("scraping_cityurls.city_url_extractor.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, json_payload)

        result = query_wikidata("Berlin")

    assert result == "https://berlin.de"


def test_query_wikidata_no_result() -> None:
    json_payload = {"results": {"bindings": []}}

    with patch("scraping_cityurls.city_url_extractor.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, json_payload)

        result = query_wikidata("Nowhere City")

    assert result is None


def test_query_wikidata_network_error() -> None:
    with patch("scraping_cityurls.city_url_extractor.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.Timeout()

        result = query_wikidata("Berlin")

    assert result is None
