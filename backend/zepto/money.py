"""Money handling for the Zepto-compatible API surface.

Zepto's product payloads express money in paise (`productVariant.mrp: 24500`
for a Rs.245 bottle). Every amount crossing the wire in the `zepto` package is
therefore an integer number of paise; the internal service layer keeps rupees.
"""
from __future__ import annotations

from typing import Optional


def to_paise(rupees: Optional[float]) -> int:
    """Rupees -> paise, rounded to the nearest paisa."""
    if rupees is None:
        return 0
    return int(round(float(rupees) * 100))


def to_rupees(paise: Optional[int]) -> float:
    """Paise -> rupees, rounded to 2 decimals."""
    if paise is None:
        return 0.0
    return round(int(paise) / 100.0, 2)


def format_rupees(paise: Optional[int]) -> str:
    """Human readable form used in server-rendered labels."""
    amount = to_rupees(paise)
    if amount == int(amount):
        return f"\u20b9{int(amount)}"
    return f"\u20b9{amount:.2f}"
