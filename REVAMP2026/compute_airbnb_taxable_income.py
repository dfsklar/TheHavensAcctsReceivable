# -*- coding: utf-8 -*-
"""Compute USD and CAD totals from an Airbnb transaction CSV.

Taxable income is the sum of Gross earnings on rows with Type == Reservation.
Host fee is the sum of Service fee on those same rows.
Paid out is the sum of Paid out on rows with Type == Payout (USD only).
Pass Through Tot amounts are checked against 5% GST (marketplace-remitted) or 9%
GST PLUS ALBERTA (5% GST + 4% Alberta, Alberta-not-remitted-by-marketplace)
of the matching Reservation Gross earnings, tolerating differences of up to 10 cents.
CAD conversion uses the Bank of Canada daily FXUSDCAD rate for each row's Date.
Weekend and holiday dates use the last preceding published rate.
GST and Alberta CAD totals split each Pass Through amount: the full amount is GST
when it is 5%; when it is 9% GST PLUS ALBERTA, 5/9 is GST and 4/9 is Alberta.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

BOC_VALET_URL = (
    "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json"
    "?start_date={start}&end_date={end}"
)
RESERVATION_TYPE = "Reservation"
PAYOUT_TYPE = "Payout"
PASS_THROUGH_TYPE = "Pass Through Tot"
GROSS_EARNINGS_FIELD = "Gross earnings"
SERVICE_FEE_FIELD = "Service fee"
PAID_OUT_FIELD = "Paid out"
AMOUNT_FIELD = "Amount"
CONFIRMATION_FIELD = "Confirmation code"
DATE_FIELD = "Date"
PASS_THROUGH_GST_RATE = Decimal("0.05")
PASS_THROUGH_ALBERTA_RATE = Decimal("0.04")
PASS_THROUGH_GST_PLUS_ALBERTA_RATE = (
    PASS_THROUGH_GST_RATE + PASS_THROUGH_ALBERTA_RATE
)
PASS_THROUGH_TOLERANCE = Decimal("0.10")
CSV_DATE_FORMAT = "%m/%d/%Y"
MONEY_QUANTIZE = Decimal("0.01")
LOOKBACK_DAYS = 14
DEFAULT_CSV = Path(__file__).resolve().parent / (
    "downloads_from_marketplaces/airbnb_01_2025-12_2025.csv"
)
RATE_CACHE_DIR = Path(__file__).resolve().parent / ".fx_cache"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sum Airbnb taxable income, host fees, and paid-out totals."
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


def load_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(mode="r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit(f"No header row found in {csv_path}")
        required = {
            DATE_FIELD,
            "Type",
            GROSS_EARNINGS_FIELD,
            SERVICE_FEE_FIELD,
            PAID_OUT_FIELD,
            AMOUNT_FIELD,
            CONFIRMATION_FIELD,
        }
        missing = required.difference(reader.fieldnames)
        if missing:
            raise SystemExit(
                f"CSV is missing required columns: {', '.join(sorted(missing))}"
            )
        return list(reader)


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


def sum_field_usd(rows: list[dict[str, str]], field: str) -> Decimal:
    total = Decimal("0")
    for row in rows:
        total += parse_money(row.get(field, ""))
    return money(total)


def sum_field_usd_cad(
    rows: list[dict[str, str]], rates: dict[date, Decimal], field: str
) -> tuple[Decimal, Decimal]:
    usd_total = Decimal("0")
    cad_total = Decimal("0")
    for row in rows:
        usd = parse_money(row.get(field, ""))
        row_date = parse_csv_date(row[DATE_FIELD])
        _rate_date, rate = rate_on_or_before(rates, row_date)
        usd_total += usd
        cad_total += usd * rate
    return money(usd_total), money(cad_total)


def convert_usd_amounts(
    amounts: list[tuple[date, Decimal]], rates: dict[date, Decimal]
) -> Decimal:
    cad_total = Decimal("0")
    for row_date, usd in amounts:
        _rate_date, rate = rate_on_or_before(rates, row_date)
        cad_total += usd * rate
    return money(cad_total)


def rows_by_confirmation(
    rows: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        code = (row.get(CONFIRMATION_FIELD) or "").strip()
        if code:
            grouped[code].append(row)
    return grouped


def within_tolerance(actual: Decimal, expected: Decimal) -> bool:
    return abs(actual - expected) <= PASS_THROUGH_TOLERANCE


@dataclass
class PassThroughClassification:
    alberta_specials: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    gst_portions: list[tuple[date, Decimal]] = field(default_factory=list)
    alberta_portions: list[tuple[date, Decimal]] = field(default_factory=list)


def classify_pass_through(
    reservation_rows: list[dict[str, str]],
    pass_through_rows: list[dict[str, str]],
) -> PassThroughClassification:
    """Classify pass-throughs and split each amount into GST vs Alberta portions."""
    reservations = rows_by_confirmation(reservation_rows)
    pass_throughs = rows_by_confirmation(pass_through_rows)
    result = PassThroughClassification()

    for code in sorted(set(reservations) | set(pass_throughs)):
        reservation_matches = reservations.get(code, [])
        pass_through_matches = pass_throughs.get(code, [])

        if len(reservation_matches) != 1 or len(pass_through_matches) != 1:
            guest = (
                reservation_matches[0].get("Guest")
                if reservation_matches
                else pass_through_matches[0].get("Guest")
            )
            result.errors.append(
                f"{code} ({guest}): expected one Reservation and one "
                f"Pass Through Tot; found {len(reservation_matches)} "
                f"Reservation and {len(pass_through_matches)} Pass Through Tot"
            )
            continue

        reservation = reservation_matches[0]
        pass_through = pass_through_matches[0]
        gross = parse_money(reservation.get(GROSS_EARNINGS_FIELD, ""))
        actual = parse_money(pass_through.get(AMOUNT_FIELD, ""))
        expected_gst = money(gross * PASS_THROUGH_GST_RATE)
        expected_gst_plus_alberta = money(gross * PASS_THROUGH_GST_PLUS_ALBERTA_RATE)
        guest = reservation.get("Guest", "")
        listing = reservation.get("Listing", "")
        label = f"{code} ({guest}; {listing})"
        row_date = parse_csv_date(pass_through[DATE_FIELD])

        if within_tolerance(actual, expected_gst):
            result.gst_portions.append((row_date, actual))
            continue
        if within_tolerance(actual, expected_gst_plus_alberta):
            gst_usd = money(
                actual
                * PASS_THROUGH_GST_RATE
                / PASS_THROUGH_GST_PLUS_ALBERTA_RATE
            )
            alberta_usd = actual - gst_usd
            result.gst_portions.append((row_date, gst_usd))
            result.alberta_portions.append((row_date, alberta_usd))
            result.alberta_specials.append(
                f"{label}: Pass Through Tot {actual:.2f} is 9% GST PLUS ALBERTA "
                f"(5% GST + 4% Alberta) of Gross Earnings {gross:.2f} "
                f"(Alberta-not-remitted-by-marketplace)"
            )
            continue

        result.errors.append(
            f"{label}: Pass Through Tot {actual:.2f} is neither 5% GST "
            f"({expected_gst:.2f}) nor 9% GST PLUS ALBERTA "
            f"({expected_gst_plus_alberta:.2f}) of Gross Earnings {gross:.2f}"
        )

    return result


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv_path).expanduser().resolve()
    if not csv_path.is_file():
        raise SystemExit(f"CSV file not found: {csv_path}")

    rows = load_csv_rows(csv_path)
    reservation_rows = [row for row in rows if row.get("Type") == RESERVATION_TYPE]
    payout_rows = [row for row in rows if row.get("Type") == PAYOUT_TYPE]
    pass_through_rows = [row for row in rows if row.get("Type") == PASS_THROUGH_TYPE]
    if not reservation_rows:
        raise SystemExit(f"No {RESERVATION_TYPE} rows found in {csv_path}")

    row_dates = [parse_csv_date(row[DATE_FIELD]) for row in reservation_rows]
    row_dates.extend(parse_csv_date(row[DATE_FIELD]) for row in pass_through_rows)
    start = min(row_dates) - timedelta(days=LOOKBACK_DAYS)
    end = max(row_dates)
    rates = load_rates(start, end)

    usd_taxable, cad_taxable = sum_field_usd_cad(
        reservation_rows, rates, GROSS_EARNINGS_FIELD
    )
    usd_host_fee, cad_host_fee = sum_field_usd_cad(
        reservation_rows, rates, SERVICE_FEE_FIELD
    )
    usd_paid_out = sum_field_usd(payout_rows, PAID_OUT_FIELD)
    classified = classify_pass_through(reservation_rows, pass_through_rows)
    cad_gst_pass_through = convert_usd_amounts(classified.gst_portions, rates)
    cad_alberta_pass_through = convert_usd_amounts(classified.alberta_portions, rates)

    print(f"CSV: {csv_path}")
    print(f"Reservation rows: {len(reservation_rows)}")
    print(f"USD Taxable Income: {usd_taxable:.2f}")
    print(f"CAD Taxable Income: {cad_taxable:.2f}")
    print(f"USD Host Fee: {usd_host_fee:.2f}")
    print(f"CAD Host Fee: {cad_host_fee:.2f}")
    print(f"USD Paid Out: {usd_paid_out:.2f}")
    print(f"CAD GST Pass Through: {cad_gst_pass_through:.2f}")
    print(f"CAD Alberta Pass Through: {cad_alberta_pass_through:.2f}")

    print()
    print(
        "Alberta-not-remitted-by-marketplace "
        f"(9% GST PLUS ALBERTA): {len(classified.alberta_specials)}"
    )
    if classified.alberta_specials:
        for line in classified.alberta_specials:
            print(f"  {line}")
    print(
        "Pass-through errors (neither 5% GST nor 9% GST PLUS ALBERTA): "
        f"{len(classified.errors)}"
    )
    if classified.errors:
        for line in classified.errors:
            print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
