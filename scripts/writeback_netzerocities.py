from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_EXCEL = PROJECT_ROOT / "data" / "netzerocities.xlsx"
RESULTS_CSV = PROJECT_ROOT / "output" / "city_urls.csv"
OUTPUT_EXCEL = PROJECT_ROOT / "output" / "netzerocities_with_urls.xlsx"


def _norm_city(value: object) -> str:
    """Normalize a city value for joining.

    We keep it intentionally simple: strip whitespace and cast to string.
    Case-sensitive Join ist hier akzeptabel, da die Quellen aus demselben
    System stammen.
    """

    return str(value).strip()


def _normalize_column_name(name: str) -> str:
    """Normalize Excel column names to match logical names.

    - Entfernt führende/trailing Spaces
    - Wandelt geschützte Leerzeichen (\xa0) in normale Leerzeichen um
    """

    return name.replace("\xa0", " ").strip()


def writeback_netzerocities() -> None:
    """Join scraper results back into netzerocities.xlsx.

    - Liest die Eingabe-Excel aus data/netzerocities.xlsx.
    - Liest die Ergebnisse aus output/city_urls.csv.
    - Joint per City-Name und schreibt eine neue Excel-Datei unter
      output/netzerocities_with_urls.xlsx mit befüllten Spalten
      `official_url`, `status`, `notes`.
    """

    if not INPUT_EXCEL.exists():
        raise FileNotFoundError(f"Input Excel not found: {INPUT_EXCEL}")

    if not RESULTS_CSV.exists():
        raise FileNotFoundError(f"Results CSV not found: {RESULTS_CSV}")

    df_cities = pd.read_excel(INPUT_EXCEL)
    df_results = pd.read_csv(RESULTS_CSV)

    # City-Spalte robust ermitteln: Excel verwendet aktuell "Cities\xa0".
    # Wir normalisieren alle Spaltennamen und suchen die, die logisch "Cities"
    # entspricht.
    normalized_columns = {
        _normalize_column_name(col): col for col in df_cities.columns
    }

    logical_city_name = "Cities"
    if logical_city_name not in normalized_columns:
        raise KeyError(
            f"Could not find a city column matching '{logical_city_name}' in "
            f"{INPUT_EXCEL}, found columns: {list(df_cities.columns)}",
        )

    city_column = normalized_columns[logical_city_name]

    df_cities["__city_key"] = df_cities[city_column].apply(_norm_city)
    df_results["__city_key"] = df_results["city"].apply(_norm_city)

    df_merged = df_cities.merge(
        df_results[["__city_key", "official_url", "status", "notes"]],
        on="__city_key",
        how="left",
        suffixes=("", "_scraper"),
    )

    # Schreibe/überschreibe die drei Ergebnis-Spalten in der Excel.
    df_merged["official_url"] = df_merged["official_url"]
    df_merged["status"] = df_merged["status"]
    df_merged["notes"] = df_merged["notes"]

    df_merged = df_merged.drop(columns=["__city_key"])

    OUTPUT_EXCEL.parent.mkdir(parents=True, exist_ok=True)
    df_merged.to_excel(OUTPUT_EXCEL, index=False)


def main() -> None:
    writeback_netzerocities()


if __name__ == "__main__":
    main()
