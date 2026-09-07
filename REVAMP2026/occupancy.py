# -*- coding: utf-8 -*-
"""Calendar occupancy helpers shared by marketplace reports."""

from __future__ import annotations

from datetime import date, timedelta


def occupancy_dates(start: date, nights: int) -> set[date]:
    """Return occupied dates for a stay: start date plus the next nights-1 days."""
    if nights <= 0:
        return set()
    return {start + timedelta(days=offset) for offset in range(nights)}
