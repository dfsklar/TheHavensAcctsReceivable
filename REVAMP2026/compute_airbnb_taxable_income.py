# -*- coding: utf-8 -*-
"""Compute USD and CAD taxable income from an Airbnb transaction CSV.

Taxable income is the sum of Gross earnings on rows with Type == Reservation.
CAD conversion uses the Bank of Canada daily FXUSDCAD rate for each row's Date.
Weekend and holiday dates use the last preceding published rate.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

BOC_VALET_URL = (
    "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json"
    "?start_date={start}&end_date={end}"
)
RESERVATION_TYPE = "Reservation"
GROSS_EARNINGS_FIELD = "Gross earnings"
DATE_FIELD = "Date"
CSV_DATE_FORMAT = "%m/%d/%Y"
MONEY_QUANTIZE = Decimal("0.01")
LOOKBACK_DAYS = 14
DEFAULT_CSV = Path(__file__).resolve().parent / (
    "downloads_from_marketplaces/airbnb_01_2025-12_2025.csv"
)
RATE_CACHE_DIR = Path(__file__).resolve().parent / ".fx_cache"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sum Reservation Gross earnings in USD and CAD."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=str(DEFAULT_CSV),
        help="Path to an Airbnb transaction-history CSV",
    )
    return parser.parse_args()


def parse_csv_date(value: str) -> date:
    return datetime.strptime(value.strip(), CSV_DATE_FORMAT).date()


def parse_money(value: str) -> Decimal:
    text = (value or "").strip()
    if not text:
        return Decimal("0")
    return Decimal(text)


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTIZE, rounding=ROUND_HALF_UP)


def load_reservation_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(mode="r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit(f"No header row found in {csv_path}")
        required = {DATE_FIELD, "Type", GROSS_EARNINGS_FIELD}
        missing = required.difference(reader.fieldnames)
        if missing:
            raise SystemExit(
                f"CSV is missing required columns: {', '.join(sorted(missing))}"
            )
        return [row for row in reader if row.get("Type") == RESERVATION_TYPE]


def fetch_boc_rates(start: date, end: date) -> dict[date, Decimal]:
    url = BOC_VALET_URL.format(start=start.isoformat(), end=end.isoformat())
    request = urllib.request.Request(url, headers={"User-Agent": "TheHavensAcctsReceivable"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(f"Could not fetch Bank of Canada FX rates: {exc}") from exc

    rates: dict[date, Decimal] = {}
    for observation in payload.get("observations", []):
        value = observation.get("FXUSDCAD", {}).get("v")
        if not value:
            continue
        rates[date.fromisoformat(observation["d"])] = Decimal(value)
    if not rates:
        raise SystemExit(
            f"Bank of Canada returned no FXUSDCAD rates between {start} and {end}."
        )
    return rates


def cached_rate_path(start: date, end: date) -> Path:
    RATE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return RATE_CACHE_DIR / f"FXUSDCAD_{start.isoformat()}_{end.isoformat()}.json"


def load_rates(start: date, end: date) -> dict[date, Decimal]:
    cache_path = cached_rate_path(start, end)
    if cache_path.exists():
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        return {date.fromisoformat(key): Decimal(value) for key, value in raw.items()}

    rates = fetch_boc_rates(start, end)
    cache_path.write_text(
        json.dumps(
            {key.isoformat(): str(value) for key, value in sorted(rates.items())},
            indent=2,
        ),
        encoding="utf-8",
    )
    return rates


def rate_on_or_before(rates: dict[date, Decimal], target: date) -> tuple[date, Decimal]:
    cursor = target
    while cursor >= min(rates):
        if cursor in rates:
            return cursor, rates[cursor]
        cursor -= timedelta(days=1)
    raise SystemExit(
        f"No Bank of Canada FXUSDCAD rate on or before {target.isoformat()}."
    )


def compute_taxable_income(
    rows: list[dict[str, str]], rates: dict[date, Decimal]
) -> tuple[Decimal, Decimal]:
    usd_total = Decimal("0")
    cad_total = Decimal("0")
    for row in rows:
        usd = parse_money(row.get(GROSS_EARNINGS_FIELD, ""))
        row_date = parse_csv_date(row[DATE_FIELD])
        _rate_date, rate = rate_on_or_before(rates, row_date)
        usd_total += usd
        cad_total += usd * rate
    return money(usd_total), money(cad_total)


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv_path).expanduser().resolve()
    if not csv_path.is_file():
        raise SystemExit(f"CSV file not found: {csv_path}")

    rows = load_reservation_rows(csv_path)
    if not rows:
        raise SystemExit(f"No {RESERVATION_TYPE} rows found in {csv_path}")

    row_dates = [parse_csv_date(row[DATE_FIELD]) for row in rows]
    start = min(row_dates) - timedelta(days=LOOKBACK_DAYS)
    end = max(row_dates)
    rates = load_rates(start, end)

    usd_taxable, cad_taxable = compute_taxable_income(rows, rates)

    print(f"CSV: {csv_path}")
    print(f"Reservation rows: {len(rows)}")
    print(f"USD Taxable Income: {usd_taxable:.2f}")
    print(f"CAD Taxable Income: {cad_taxable:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
