# -*- coding: utf-8 -*-
"""Bank of Canada USD/CAD rates for per-row conversion."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

BOC_VALET_URL = (
    "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json"
    "?start_date={start}&end_date={end}"
)
LOOKBACK_DAYS = 14
MONEY_QUANTIZE = Decimal("0.01")
RATE_CACHE_DIR = Path(__file__).resolve().parent / ".fx_cache"


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTIZE, rounding=ROUND_HALF_UP)


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


def convert_usd_amounts(
    amounts: list[tuple[date, Decimal]], rates: dict[date, Decimal]
) -> Decimal:
    cad_total = Decimal("0")
    for row_date, usd in amounts:
        _rate_date, rate = rate_on_or_before(rates, row_date)
        cad_total += usd * rate
    return money(cad_total)
