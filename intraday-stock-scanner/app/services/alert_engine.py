from __future__ import annotations

from datetime import datetime, timedelta

from app.alerts.dispatcher import dispatch
from app.alerts.planner import build_plan


class AlertEngine:
    def __init__(self, cooldown_minutes: int = 5) -> None:
        self.cooldown = timedelta(minutes=cooldown_minutes)
        self._last_emit: dict[tuple[str, str], datetime] = {}

    def try_emit(self, symbol: str, signal, score: float, now: datetime):
        key = (symbol, signal.setup)
        last = self._last_emit.get(key)
        if last and now - last < self.cooldown:
            return None
        plan = build_plan(symbol, signal, score, now)
        if plan:
            self._last_emit[key] = now
            dispatch(plan)
        return plan
