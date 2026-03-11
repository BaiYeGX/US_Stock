from __future__ import annotations

from app.providers.base import Bar


def session_vwap(bars: list[Bar]) -> float | None:
    dollar = sum(b.close * b.volume for b in bars)
    volume = sum(b.volume for b in bars)
    if volume == 0:
        return None
    return dollar / volume
