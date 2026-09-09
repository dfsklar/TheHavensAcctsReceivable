# -*- coding: utf-8 -*-
"""Bank of Canada USD/CAD rates for per-row conversion.

Any missing, unreadable, or implausible FXUSDCAD data aborts immediately.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

BOC_VALET_URL = (
    "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json"
    "?start_date={start}&end_date={end}"
)
LOOKBACK_DAYS = 14
MONEY_QUANTIZE = Decimal("0.01")
RATE_CACHE_DIR = Path(__file__).resolve().parent / ".fx_cache"
# Daily USD/CAD has stayed inside this band for decades. Values outside it
# mean the feed is inverted, scaled, or otherwise not a usable FXUSDCAD rate.
MIN_FXUSDCAD = Decimal("0.80")
MAX_FXUSDCAD = Decimal("2.00")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTIZE, rounding=ROUND_HALF_UP)


def _abort(message: str) -> None:
    raise SystemExit(f"Fatal: {message}")


def parse_fxusdcad(value: object, rate_date: str) -> Decimal:
    text = str(value).strip() if value is not None else ""
    if not text:
        _abort(f"Bank of Canada FXUSDCAD is missing for {rate_date}.")
    try:
        rate = Decimal(text)
    except (InvalidOperation, ValueError, TypeError):
        _abort(
            f"Bank of Canada FXUSDCAD for {rate_date} is not a number: {value!r}."
        )
    if not rate.is_finite() or rate <= 0:
        _abort(
            f"Bank of Canada FXUSDCAD for {rate_date} is not a positive finite rate: {rate}."
        )
    if rate < MIN_FXUSDCAD or rate > MAX_FXUSDCAD:
        _abort(
            f"Bank of Canada FXUSDCAD for {rate_date} looks erroneous: {rate} "
            f"(expected between {MIN_FXUSDCAD} and {MAX_FXUSDCAD})."
        )
    return rate


def parse_rate_date(value: object) -> date:
    text = str(value).strip() if value is not None else ""
    if not text:
        _abort("Bank of Canada FXUSDCAD observation is missing a date.")
    try:
        return date.fromisoformat(text)
    except ValueError:
        _abort(f"Bank of Canada FXUSDCAD date is not ISO-8601: {value!r}.")


def validate_rates(rates: dict[date, Decimal], start: date, end: date) -> None:
    if not rates:
        _abort(f"No Bank of Canada FXUSDCAD rates between {start} and {end}.")
    for rate_date, rate in rates.items():
        parse_fxusdcad(rate, rate_date.isoformat())
    latest = max(rates)
    if latest < start:
        _abort(
            f"Bank of Canada FXUSDCAD data ends on {latest.isoformat()}, "
            f"before the needed start date {start.isoformat()}."
        )


def observations_to_rates(payload: object, start: date, end: date) -> dict[date, Decimal]:
    if not isinstance(payload, dict):
        _abort("Bank of Canada FXUSDCAD response is not a JSON object.")
    observations = payload.get("observations")
    if not isinstance(observations, list) or not observations:
        _abort(
            f"Bank of Canada returned no FXUSDCAD observations between {start} and {end}."
        )

    rates: dict[date, Decimal] = {}
    for observation in observations:
        if not isinstance(observation, dict):
            _abort("Bank of Canada FXUSDCAD observation is not a JSON object.")
        rate_date = parse_rate_date(observation.get("d"))
        fx = observation.get("FXUSDCAD")
        if not isinstance(fx, dict):
            _abort(f"Bank of Canada FXUSDCAD value is missing for {rate_date.isoformat()}.")
        rates[rate_date] = parse_fxusdcad(fx.get("v"), rate_date.isoformat())
    validate_rates(rates, start, end)
    return rates


def fetch_boc_rates(start: date, end: date) -> dict[date, Decimal]:
    if start > end:
        _abort(f"FX date range is invalid: {start} to {end}.")
    url = BOC_VALET_URL.format(start=start.isoformat(), end=end.isoformat())
    request = urllib.request.Request(url, headers={"User-Agent": "TheHavensAcctsReceivable"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = getattr(response, "status", None)
            if status not in (None, 200):
                _abort(f"Bank of Canada FXUSDCAD HTTP status {status} from {url}.")
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        _abort(f"Bank of Canada FXUSDCAD HTTP {exc.code} from {url}.")
    except urllib.error.URLError as exc:
        _abort(f"Bank of Canada FXUSDCAD is not available: {exc}.")
    except TimeoutError:
        _abort("Bank of Canada FXUSDCAD request timed out.")
    except OSError as exc:
        _abort(f"Bank of Canada FXUSDCAD is not available: {exc}.")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        _abort("Bank of Canada FXUSDCAD response is not valid JSON.")
    return observations_to_rates(payload, start, end)


def cached_rate_path(start: date, end: date) -> Path:
    RATE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return RATE_CACHE_DIR / f"FXUSDCAD_{start.isoformat()}_{end.isoformat()}.json"


def load_cached_rates(cache_path: Path, start: date, end: date) -> dict[date, Decimal]:
    try:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
    except OSError as exc:
        _abort(f"Could not read FXUSDCAD cache {cache_path}: {exc}.")
    except json.JSONDecodeError:
        _abort(f"FXUSDCAD cache {cache_path} is not valid JSON.")
    if not isinstance(raw, dict) or not raw:
        _abort(f"FXUSDCAD cache {cache_path} has no rates.")

    rates: dict[date, Decimal] = {}
    for key, value in raw.items():
        rate_date = parse_rate_date(key)
        rates[rate_date] = parse_fxusdcad(value, rate_date.isoformat())
    validate_rates(rates, start, end)
    return rates


def load_rates(start: date, end: date) -> dict[date, Decimal]:
    cache_path = cached_rate_path(start, end)
    if cache_path.exists():
        return load_cached_rates(cache_path, start, end)

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
    if not rates:
        _abort(f"No Bank of Canada FXUSDCAD rates available for {target.isoformat()}.")
    cursor = target
    oldest = min(rates)
    while cursor >= oldest:
        if cursor in rates:
            rate = parse_fxusdcad(rates[cursor], cursor.isoformat())
            age = (target - cursor).days
            if age > LOOKBACK_DAYS:
                _abort(
                    f"Bank of Canada FXUSDCAD for {target.isoformat()} is stale: "
                    f"nearest published rate is {cursor.isoformat()} ({age} days earlier)."
                )
            return cursor, rate
        cursor -= timedelta(days=1)
    _abort(f"No Bank of Canada FXUSDCAD rate on or before {target.isoformat()}.")


def convert_usd_amounts(
    amounts: list[tuple[date, Decimal]], rates: dict[date, Decimal]
) -> Decimal:
    cad_total = Decimal("0")
    for row_date, usd in amounts:
        _rate_date, rate = rate_on_or_before(rates, row_date)
        cad_total += usd * rate
    return money(cad_total)
