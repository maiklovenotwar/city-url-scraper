#!/usr/bin/env python3
"""Evaluate current extraction results against a small Gold-Set.

Usage:
    python scripts/evaluate_results.py

It reads:
- data/gold_set.csv           (city,country_hint,expected_url_pattern)
- output/city_urls.csv        (city,official_url,status,notes)

For each Gold-Set city, it checks:
- whether a URL was found (status in {OK, MULTIPLE})
- whether the found URL contains the expected_url_pattern (substring match)

Then it prints a per-city table and a final accuracy summary.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"

GOLD_SET_PATH = DATA_DIR / "gold_set.csv"
RESULTS_PATH = OUTPUT_DIR / "city_urls.csv"


@dataclass
class GoldEntry:
    city: str
    country_hint: str
    expected_pattern: str


@dataclass
class ResultEntry:
    city: str
    official_url: str | None
    status: str
    notes: str | None


def load_gold_set(path: Path) -> list[GoldEntry]:
    entries: list[GoldEntry] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            city = (row.get("city") or "").strip()
            if not city:
                continue
            entries.append(
                GoldEntry(
                    city=city,
                    country_hint=(row.get("country_hint") or "").strip(),
                    expected_pattern=(row.get("expected_url_pattern") or "").strip(),
                )
            )
    return entries


def load_results(path: Path) -> dict[str, ResultEntry]:
    """Load current results and index by normalized city name."""
    results: dict[str, ResultEntry] = {}
    if not path.exists():
        return results

    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            city = (row.get("city") or "").strip()
            if not city:
                continue
            key = city.lower()
            official_url = (row.get("official_url") or "").strip() or None
            status = (row.get("status") or "").strip()
            notes = (row.get("notes") or "").strip() or None
            results[key] = ResultEntry(city=city, official_url=official_url, status=status, notes=notes)

    return results


def evaluate(gold: list[GoldEntry], results: dict[str, ResultEntry]) -> None:
    total = len(gold)
    correct = 0

    print("=" * 80)
    print("Gold-Set Evaluation")
    print("=" * 80)
    print()
    print(f"Gold-Set entries: {total}")
    print(f"Results file: {RESULTS_PATH}")
    print()

    header = f"{'City':25} | {'Found URL':55} | {'Match'}"
    print(header)
    print("-" * len(header))

    for entry in gold:
        key = entry.city.lower()
        result = results.get(key)

        if result is None:
            found_url = "<no result>"
            match = False
        else:
            found_url = result.official_url or "<none>"
            # Only consider found if status OK or MULTIPLE and we have a URL
            if result.status in {"OK", "MULTIPLE"} and result.official_url:
                match = entry.expected_pattern.lower() in result.official_url.lower()
            else:
                match = False

        if match:
            correct += 1
            match_str = "✅"
        else:
            match_str = "❌"

        print(f"{entry.city:25} | {found_url[:55]:55} | {match_str}")

    print()
    print("=" * 80)
    accuracy = (correct / total * 100.0) if total else 0.0
    print(f"Accuracy: {correct}/{total} ({accuracy:.1f}%)")
    print("=" * 80)


def main() -> None:
    if not GOLD_SET_PATH.exists():
        raise SystemExit(f"Gold-Set file not found: {GOLD_SET_PATH}")
    if not RESULTS_PATH.exists():
        raise SystemExit(f"Results file not found: {RESULTS_PATH}")

    gold = load_gold_set(GOLD_SET_PATH)
    results = load_results(RESULTS_PATH)
    evaluate(gold, results)


if __name__ == "__main__":
    main()
