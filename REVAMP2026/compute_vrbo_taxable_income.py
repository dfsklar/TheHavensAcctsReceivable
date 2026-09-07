# -*- coding: utf-8 -*-
"""Compute VRBO stats from a LodgingTaxReport CSV.

CAD GST and Alberta pass-through totals come from "Your Taxes | Taxes you pay*"
when that amount is non-zero. Those amounts are already in local currency and
must be CAD. Reservation count and total nights are taken once per Reservation ID.
"""

from __future__ import annotations

import argparse
import csv
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

TAXES_YOU_PAY_FIELD = "Your Taxes | Taxes you pay*"
LOCAL_CURRENCY_FIELD = "Your Taxes | Local Currency"
TAX_TYPE_FIELD = "Tax type"
RESERVATION_ID_FIELD = "Reservation ID"
NIGHTS_FIELD = "Nights"
GST_TAX_TYPE = "Goods and Services Tax"
ALBERTA_TAX_TYPE = "Accommodations Tax"
REQUIRED_LOCAL_CURRENCY = "CAD"
MONEY_QUANTIZE = Decimal("0.01")
DOWNLOADS_DIR = Path(__file__).resolve().parent / "downloads_from_marketplaces"
LODGING_TAX_GLOB = "LodgingTaxReport*.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sum VRBO GST/Alberta pass-through, reservations, and nights."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=None,
        help="Path to a VRBO LodgingTaxReport CSV (default: newest matching file)",
    )
    return parser.parse_args()


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTIZE, rounding=ROUND_HALF_UP)


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


def find_lodging_tax_csv() -> Path:
    matches = sorted(DOWNLOADS_DIR.glob(LODGING_TAX_GLOB))
    if not matches:
        raise SystemExit(
            f"No file matching {LODGING_TAX_GLOB} in {DOWNLOADS_DIR}"
        )
    if len(matches) > 1:
        names = ", ".join(path.name for path in matches)
        raise SystemExit(
            f"Multiple LodgingTaxReport files found ({names}); "
            "pass one path explicitly."
        )
    return matches[0]


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
    print(tsv_row("Reservation rows", reservation_count, "reservations"))
    print(tsv_row("Total Nights", total_nights, "nights"))
    print(tsv_row("CAD GST Pass Through", f"{cad_gst:.2f}", "CAD"))
    print(tsv_row("CAD Alberta Pass Through", f"{cad_alberta:.2f}", "CAD"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
