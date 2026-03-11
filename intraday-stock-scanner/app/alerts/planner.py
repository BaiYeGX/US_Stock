from __future__ import annotations

from datetime import datetime

from app.alerts.schemas import AlertPlan
from app.scoring.ranking import grade_from_score
from app.setups.base import SetupSignal


def build_plan(symbol: str, signal: SetupSignal, score: float, now: datetime, min_rr_tp1: float = 1.0) -> AlertPlan | None:
    entry_ref = signal.entry_high
    risk = abs(entry_ref - signal.stop)
    if risk <= 0:
        return None
    rr1 = abs(signal.tp1 - entry_ref) / risk
    rr2 = abs(signal.tp2 - entry_ref) / risk
    if rr1 + 1e-9 < min_rr_tp1:
        return None
    risk_pct = risk / entry_ref * 100
    return AlertPlan(
        ts=now,
        symbol=symbol,
        side=signal.side,
        setup=signal.setup,
        score=round(score, 2),
        grade=grade_from_score(score),
        entry_low=round(signal.entry_low, 2),
        entry_high=round(signal.entry_high, 2),
        stop=round(signal.stop, 2),
        tp1=round(signal.tp1, 2),
        tp2=round(signal.tp2, 2),
        risk_pct=round(risk_pct, 2),
        rr_tp1=round(rr1, 2),
        rr_tp2=round(rr2, 2),
        invalidate_if=signal.invalidate_if,
        reason=signal.reason,
        metrics=signal.metrics,
    )
