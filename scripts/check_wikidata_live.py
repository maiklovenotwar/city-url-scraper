from scraping_cityurls.city_url_extractor import query_wikidata


def main() -> None:
    for city, country in [("Berlin", "Germany"), ("Klagenfurt", "Austria")]:
        url = query_wikidata(city, country_hint=country)
        print(f"{city} ({country}): {url}")


if __name__ == "__main__":
    main()
