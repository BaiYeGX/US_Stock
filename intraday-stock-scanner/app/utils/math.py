from __future__ import annotations

from typing import Iterable


def pct_change(current: float, reference: float) -> float:
    if reference == 0:
        return 0.0
    return (current - reference) / reference * 100


def safe_div(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def percentile_rank(value: float, values: Iterable[float]) -> float:
    pool = sorted(values)
    if not pool:
        return 0.0
    lower = sum(1 for v in pool if v <= value)
    return lower / len(pool) * 100
