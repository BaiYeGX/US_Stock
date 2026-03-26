from __future__ import annotations


def spread_pct(bid: float, ask: float) -> float:
    mid = (bid + ask) / 2
    if mid <= 0:
        return 100.0
    return (ask - bid) / mid * 100


def quote_quality_flag(spread: float, max_spread: float = 0.15) -> bool:
    return spread <= max_spread
