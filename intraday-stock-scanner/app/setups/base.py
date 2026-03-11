from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SetupSignal:
    setup: str
    side: str
    setup_score: float
    entry_low: float
    entry_high: float
    stop: float
    tp1: float
    tp2: float
    invalidate_if: str
    reason: str
    metrics: dict
