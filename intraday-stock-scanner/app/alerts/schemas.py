from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass
class AlertPlan:
    ts: datetime
    symbol: str
    side: str
    setup: str
    score: float
    grade: str
    entry_low: float
    entry_high: float
    stop: float
    tp1: float
    tp2: float
    risk_pct: float
    rr_tp1: float
    rr_tp2: float
    invalidate_if: str
    reason: str
    metrics: dict[str, float | str | int | None]

    def model_dump(self, mode: str | None = None, exclude: set[str] | None = None) -> dict:
        data = asdict(self)
        if exclude:
            for k in exclude:
                data.pop(k, None)
        return data
