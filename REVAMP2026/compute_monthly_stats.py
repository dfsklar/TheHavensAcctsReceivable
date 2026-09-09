# -*- coding: utf-8 -*-
"""Run Airbnb and VRBO monthly stats, then total payroll and prepay.

Provide the three marketplace files for the month:
  1. Airbnb transaction-history CSV
  2. VRBO LodgingTaxReport CSV
  3. VRBO PayoutSummaryReport CSV
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

from fx import money

SCRIPT_DIR = Path(__file__).resolve().parent
AIRBNB_SCRIPT = SCRIPT_DIR / "compute_airbnb_taxable_income.py"
VRBO_SCRIPT = SCRIPT_DIR / "compute_vrbo_taxable_income.py"
PAYROLL_LABEL = "payroll per employee"
PREPAY_LABEL = "prepay per employee"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Airbnb and VRBO stats for a month and total payroll/prepay."
        )
    )
    parser.add_argument("airbnb_csv", help="Airbnb transaction-history CSV")
    parser.add_argument("lodging_tax_csv", help="VRBO LodgingTaxReport CSV")
    parser.add_argument("payout_summary_csv", help="VRBO PayoutSummaryReport CSV")
    return parser.parse_args()


def require_file(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SystemExit(f"CSV file not found: {resolved}")
    return resolved


def run_script(script: Path, args: list[str]) -> str:
    command = [sys.executable, str(script), *args]
    result = subprocess.run(
        command,
        cwd=SCRIPT_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        err = result.stderr.strip() or f"exit {result.returncode}"
        raise SystemExit(f"{script.name} failed:\n{err}")
    return result.stdout


def tsv_amount(output: str, description: str) -> Decimal:
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0] == description:
            return Decimal(parts[1])
    raise SystemExit(f"Did not find TSV row {description!r} in script output.")


def print_section(title: str, output: str) -> None:
    print(title)
    print(output, end="" if output.endswith("\n") else "\n")
    if not output.endswith("\n"):
        print()
    print()


def main() -> int:
    args = parse_args()
    airbnb_csv = require_file(Path(args.airbnb_csv))
    lodging_tax_csv = require_file(Path(args.lodging_tax_csv))
    payout_summary_csv = require_file(Path(args.payout_summary_csv))

    airbnb_out = run_script(
        AIRBNB_SCRIPT,
        [str(airbnb_csv), "--vrbo-csv", str(lodging_tax_csv)],
    )
    vrbo_out = run_script(
        VRBO_SCRIPT,
        [
            str(lodging_tax_csv),
            "--payout-summary",
            str(payout_summary_csv),
            "--airbnb-csv",
            str(airbnb_csv),
        ],
    )

    print_section("Airbnb", airbnb_out)
    print_section("VRBO", vrbo_out)

    total_payroll = money(
        tsv_amount(airbnb_out, PAYROLL_LABEL) + tsv_amount(vrbo_out, PAYROLL_LABEL)
    )
    total_prepay = money(
        tsv_amount(airbnb_out, PREPAY_LABEL) + tsv_amount(vrbo_out, PREPAY_LABEL)
    )
    print("Combined")
    print(f"{PAYROLL_LABEL}\t{total_payroll:.2f}\tCAD")
    print(f"{PREPAY_LABEL}\t{total_prepay:.2f}\tCAD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
