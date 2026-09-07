# -*- coding: utf-8 -*-
"""Compute VRBO stats from a LodgingTaxReport CSV.

CAD GST and Alberta pass-through totals come from "Your Taxes | Taxes you pay*"
when that amount is non-zero. Those amounts are already in local currency and
must be CAD. Reservation count and total nights are taken once per Reservation ID.
Host fee (Deductions), Gross booking amount, and Payout come from PayoutSummaryReport
rows and are converted to CAD using the Bank of Canada rate on each Payout date.
Taxable income is Gross booking amount minus Lodging Tax Owner Remits.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fx import LOOKBACK_DAYS, load_rates, money, rate_on_or_before
from occupancy import occupancy_dates
import compute_airbnb_taxable_income as airbnb

TAXES_YOU_PAY_FIELD = "Your Taxes | Taxes you pay*"
LOCAL_CURRENCY_FIELD = "Your Taxes | Local Currency"
TAX_TYPE_FIELD = "Tax type"
RESERVATION_ID_FIELD = "Reservation ID"
NIGHTS_FIELD = "Nights"
CHECKIN_DATE_FIELD = "Check-in date"
VRBO_DATE_FORMAT = "%B %d, %Y"
GST_TAX_TYPE = "Goods and Services Tax"
ALBERTA_TAX_TYPE = "Accommodations Tax"
REQUIRED_LOCAL_CURRENCY = "CAD"
DOWNLOADS_DIR = Path(__file__).resolve().parent / "downloads_from_marketplaces"
LODGING_TAX_GLOB = "LodgingTaxReport*.csv"
PAYOUT_SUMMARY_GLOB = "PayoutSummaryReport*.csv"
GROSS_BOOKING_FIELD = "Gross booking amount"
DEDUCTIONS_FIELD = "Deductions"
PAYOUT_FIELD = "Payout"
LODGING_TAX_OWNER_REMITS_FIELD = "Lodging Tax Owner Remits"
PAYOUT_DATE_FIELD = "Payout date"
PAYOUT_CURRENCY_FIELD = "Payout currency"
REQUIRED_PAYOUT_CURRENCY = "USD"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sum VRBO GST/Alberta pass-through, reservations, and nights."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=None,
        help="Path to a VRBO LodgingTaxReport CSV (default: matching file)",
    )
    parser.add_argument(
        "--payout-summary",
        default=None,
        help="Path to a VRBO PayoutSummaryReport CSV (default: matching file)",
    )
    parser.add_argument(
        "--airbnb-csv",
        default=None,
        help="Path to an Airbnb transaction-history CSV (default: Airbnb default file)",
    )
    return parser.parse_args()


def parse_money(value: str) -> Decimal:
    text = (value or "").strip().replace(",", "")
    if not text:
        return Decimal("0")
    return Decimal(text)


def parse_nights(value: str) -> int:
    text = (value or "").strip()
    if not text:
        return 0
    return int(text)


def parse_vrbo_date(value: str) -> date:
    return datetime.strptime(value.strip(), VRBO_DATE_FORMAT).date()


def occupied_dates_from_vrbo_rows(rows: list[dict[str, str]]) -> set[date]:
    stays: dict[str, tuple[date, int]] = {}
    occupied: set[date] = set()
    for row in rows:
        reservation_id = row[RESERVATION_ID_FIELD].strip()
        start = parse_vrbo_date(row[CHECKIN_DATE_FIELD])
        nights = parse_nights(row.get(NIGHTS_FIELD, ""))
        stay = (start, nights)
        previous = stays.get(reservation_id)
        if previous is not None and previous != stay:
            raise SystemExit(
                f"Fatal: reservation {reservation_id} has conflicting "
                f"check-in/nights {previous} vs {stay}."
            )
        if previous is None:
            stays[reservation_id] = stay
            occupied.update(occupancy_dates(start, nights))
    return occupied


def find_csv(glob_pattern: str) -> Path:
    matches = sorted(DOWNLOADS_DIR.glob(glob_pattern))
    if not matches:
        raise SystemExit(f"No file matching {glob_pattern} in {DOWNLOADS_DIR}")
    if len(matches) > 1:
        names = ", ".join(path.name for path in matches)
        raise SystemExit(
            f"Multiple files matching {glob_pattern} found ({names}); "
            "pass one path explicitly."
        )
    return matches[0]


def find_lodging_tax_csv() -> Path:
    return find_csv(LODGING_TAX_GLOB)


def find_payout_summary_csv() -> Path:
    return find_csv(PAYOUT_SUMMARY_GLOB)


def load_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(mode="r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit(f"No header row found in {csv_path}")
        required = {
            TAXES_YOU_PAY_FIELD,
            LOCAL_CURRENCY_FIELD,
            TAX_TYPE_FIELD,
            RESERVATION_ID_FIELD,
            NIGHTS_FIELD,
            CHECKIN_DATE_FIELD,
        }
        missing = required.difference(reader.fieldnames)
        if missing:
            raise SystemExit(
                f"CSV is missing required columns: {', '.join(sorted(missing))}"
            )
        rows = []
        for row in reader:
            reservation_id = (row.get(RESERVATION_ID_FIELD) or "").strip()
            if not reservation_id or reservation_id.startswith("*"):
                continue
            rows.append(row)
        return rows


def load_payout_summary_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(mode="r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit(f"No header row found in {csv_path}")
        required = {
            GROSS_BOOKING_FIELD,
            DEDUCTIONS_FIELD,
            PAYOUT_FIELD,
            LODGING_TAX_OWNER_REMITS_FIELD,
            PAYOUT_DATE_FIELD,
            PAYOUT_CURRENCY_FIELD,
            RESERVATION_ID_FIELD,
        }
        missing = required.difference(reader.fieldnames)
        if missing:
            raise SystemExit(
                f"CSV is missing required columns: {', '.join(sorted(missing))}"
            )
        rows = []
        for row in reader:
            reservation_id = (row.get(RESERVATION_ID_FIELD) or "").strip()
            if not reservation_id:
                continue
            currency = (row.get(PAYOUT_CURRENCY_FIELD) or "").strip()
            if currency != REQUIRED_PAYOUT_CURRENCY:
                raise SystemExit(
                    f"Fatal: payout currency for {reservation_id} is "
                    f"{currency!r}, not {REQUIRED_PAYOUT_CURRENCY}."
                )
            rows.append(row)
        return rows


def tsv_row(description: str, amount: object, unit: str) -> str:
    return f"{description}\t{amount}\t{unit}"


def compute_stats(rows: list[dict[str, str]]) -> tuple[int, int, Decimal, Decimal]:
    gst_total = Decimal("0")
    alberta_total = Decimal("0")
    nights_by_reservation: dict[str, int] = {}

    for row in rows:
        reservation_id = row[RESERVATION_ID_FIELD].strip()
        nights_by_reservation[reservation_id] = parse_nights(row.get(NIGHTS_FIELD, ""))

        taxes_you_pay = parse_money(row.get(TAXES_YOU_PAY_FIELD, ""))
        if taxes_you_pay == 0:
            continue

        local_currency = (row.get(LOCAL_CURRENCY_FIELD) or "").strip()
        if local_currency != REQUIRED_LOCAL_CURRENCY:
            raise SystemExit(
                f"Fatal: {TAXES_YOU_PAY_FIELD} is {taxes_you_pay} for "
                f"{reservation_id} but {LOCAL_CURRENCY_FIELD} is "
                f"{local_currency!r}, not {REQUIRED_LOCAL_CURRENCY}."
            )

        tax_type = (row.get(TAX_TYPE_FIELD) or "").strip()
        if tax_type == GST_TAX_TYPE:
            gst_total += taxes_you_pay
        elif tax_type == ALBERTA_TAX_TYPE:
            alberta_total += taxes_you_pay
        else:
            raise SystemExit(
                f"Fatal: unknown tax type {tax_type!r} with non-zero "
                f"{TAXES_YOU_PAY_FIELD} {taxes_you_pay} for {reservation_id}."
            )

    return (
        len(nights_by_reservation),
        sum(nights_by_reservation.values()),
        money(gst_total),
        money(alberta_total),
    )


def sum_payout_field_usd_cad(
    rows: list[dict[str, str]], field: str, rates: dict[date, Decimal]
) -> tuple[Decimal, Decimal]:
    usd_total = Decimal("0")
    cad_total = Decimal("0")
    for row in rows:
        usd = parse_money(row.get(field, ""))
        payout_date = parse_vrbo_date(row[PAYOUT_DATE_FIELD])
        _rate_date, rate = rate_on_or_before(rates, payout_date)
        usd_total += usd
        cad_total += usd * rate
    return money(usd_total), money(cad_total)


def taxable_income_usd_cad(
    rows: list[dict[str, str]], rates: dict[date, Decimal]
) -> tuple[Decimal, Decimal]:
    usd_total = Decimal("0")
    cad_total = Decimal("0")
    for row in rows:
        usd = parse_money(row.get(GROSS_BOOKING_FIELD, "")) - parse_money(
            row.get(LODGING_TAX_OWNER_REMITS_FIELD, "")
        )
        payout_date = parse_vrbo_date(row[PAYOUT_DATE_FIELD])
        _rate_date, rate = rate_on_or_before(rates, payout_date)
        usd_total += usd
        cad_total += usd * rate
    return money(usd_total), money(cad_total)


def combined_distinct_occupied_dates(
    vrbo_rows: list[dict[str, str]], airbnb_csv: Path
) -> tuple[int, int, int]:
    if not airbnb_csv.is_file():
        raise SystemExit(f"CSV file not found: {airbnb_csv}")
    airbnb_rows = airbnb.load_csv_rows(airbnb_csv)
    airbnb_reservations = [
        row for row in airbnb_rows if row.get("Type") == airbnb.RESERVATION_TYPE
    ]
    if not airbnb_reservations:
        raise SystemExit(
            f"No {airbnb.RESERVATION_TYPE} rows found in {airbnb_csv}"
        )
    airbnb_dates = airbnb.distinct_occupied_dates(airbnb_reservations)
    vrbo_dates = occupied_dates_from_vrbo_rows(vrbo_rows)
    return (
        len(airbnb_dates),
        len(vrbo_dates),
        len(airbnb_dates | vrbo_dates),
    )


def main() -> int:
    args = parse_args()
    csv_path = (
        Path(args.csv_path).expanduser().resolve()
        if args.csv_path
        else find_lodging_tax_csv()
    )
    if not csv_path.is_file():
        raise SystemExit(f"CSV file not found: {csv_path}")

    rows = load_csv_rows(csv_path)
    if not rows:
        raise SystemExit(f"No reservation rows found in {csv_path}")

    reservation_count, total_nights, cad_gst, cad_alberta = compute_stats(rows)

    payout_path = (
        Path(args.payout_summary).expanduser().resolve()
        if args.payout_summary
        else find_payout_summary_csv()
    )
    if not payout_path.is_file():
        raise SystemExit(f"CSV file not found: {payout_path}")
    payout_rows = load_payout_summary_rows(payout_path)
    if not payout_rows:
        raise SystemExit(f"No payout rows found in {payout_path}")

    payout_dates = [parse_vrbo_date(row[PAYOUT_DATE_FIELD]) for row in payout_rows]
    rates = load_rates(
        min(payout_dates) - timedelta(days=LOOKBACK_DAYS),
        max(payout_dates),
    )
    usd_host_fee, cad_host_fee = sum_payout_field_usd_cad(
        payout_rows, DEDUCTIONS_FIELD, rates
    )
    usd_gross, cad_gross = sum_payout_field_usd_cad(
        payout_rows, GROSS_BOOKING_FIELD, rates
    )
    usd_payout, cad_payout = sum_payout_field_usd_cad(
        payout_rows, PAYOUT_FIELD, rates
    )
    usd_taxable, cad_taxable = taxable_income_usd_cad(payout_rows, rates)
    airbnb_csv = (
        Path(args.airbnb_csv).expanduser().resolve()
        if args.airbnb_csv
        else airbnb.DEFAULT_CSV
    )
    distinct_airbnb, distinct_vrbo, distinct_combined = (
        combined_distinct_occupied_dates(rows, airbnb_csv)
    )

    print(tsv_row("Reservation rows", reservation_count, "reservations"))
    print(tsv_row("Total Nights", total_nights, "nights"))
    print(tsv_row("Distinct Occupied Dates (Airbnb)", distinct_airbnb, "days"))
    print(tsv_row("Distinct Occupied Dates (VRBO)", distinct_vrbo, "days"))
    print(tsv_row("Distinct Occupied Dates", distinct_combined, "days"))
    print(tsv_row("USD Taxable Income", f"{usd_taxable:.2f}", "USD"))
    print(tsv_row("CAD Taxable Income", f"{cad_taxable:.2f}", "CAD"))
    print(tsv_row("CAD GST Pass Through", f"{cad_gst:.2f}", "CAD"))
    print(tsv_row("CAD Alberta Pass Through", f"{cad_alberta:.2f}", "CAD"))
    print(tsv_row("USD Host Fee", f"{usd_host_fee:.2f}", "USD"))
    print(tsv_row("CAD Host Fee", f"{cad_host_fee:.2f}", "CAD"))
    print(tsv_row("USD Gross booking amount", f"{usd_gross:.2f}", "USD"))
    print(tsv_row("CAD Gross booking amount", f"{cad_gross:.2f}", "CAD"))
    print(tsv_row("USD Payout", f"{usd_payout:.2f}", "USD"))
    print(tsv_row("CAD Payout", f"{cad_payout:.2f}", "CAD"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
