# -*- coding: utf-8 -*-
"""Distinct occupied calendar dates across Airbnb and VRBO reservations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import compute_airbnb_taxable_income as airbnb
import compute_vrbo_taxable_income as vrbo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count distinct occupied dates across Airbnb and VRBO."
    )
    parser.add_argument(
        "--airbnb-csv",
        default=None,
        help="Path to an Airbnb transaction-history CSV",
    )
    parser.add_argument(
        "--vrbo-csv",
        default=None,
        help="Path to a VRBO LodgingTaxReport CSV",
    )
    return parser.parse_args()


def airbnb_occupied_dates(csv_path: Path) -> set:
    rows = airbnb.load_csv_rows(csv_path)
    reservation_rows = [
        row for row in rows if row.get("Type") == airbnb.RESERVATION_TYPE
    ]
    if not reservation_rows:
        raise SystemExit(f"No {airbnb.RESERVATION_TYPE} rows found in {csv_path}")
    return airbnb.distinct_occupied_dates(reservation_rows)


def vrbo_occupied_dates(csv_path: Path) -> set:
    rows = vrbo.load_csv_rows(csv_path)
    if not rows:
        raise SystemExit(f"No reservation rows found in {csv_path}")
    return vrbo.occupied_dates_from_vrbo_rows(rows)


def main() -> int:
    args = parse_args()
    airbnb_csv = (
        Path(args.airbnb_csv).expanduser().resolve()
        if args.airbnb_csv
        else airbnb.DEFAULT_CSV
    )
    vrbo_csv = (
        Path(args.vrbo_csv).expanduser().resolve()
        if args.vrbo_csv
        else vrbo.find_lodging_tax_csv()
    )
    if not airbnb_csv.is_file():
        raise SystemExit(f"CSV file not found: {airbnb_csv}")
    if not vrbo_csv.is_file():
        raise SystemExit(f"CSV file not found: {vrbo_csv}")

    airbnb_dates = airbnb_occupied_dates(airbnb_csv)
    vrbo_dates = vrbo_occupied_dates(vrbo_csv)
    combined = airbnb_dates | vrbo_dates

    print(airbnb.tsv_row("Distinct Occupied Dates (Airbnb)", len(airbnb_dates), "days"))
    print(airbnb.tsv_row("Distinct Occupied Dates (VRBO)", len(vrbo_dates), "days"))
    print(
        airbnb.tsv_row(
            "Distinct Occupied Dates",
            len(combined),
            "days",
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
