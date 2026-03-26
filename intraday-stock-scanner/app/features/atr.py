from __future__ import annotations

from app.providers.base import Bar


def atr_pct(bars: list[Bar], period: int = 20) -> float:
    if len(bars) < period + 1:
        return 0.0
    trs: list[float] = []
    for i in range(1, period + 1):
        cur = bars[-i]
        prev = bars[-i - 1]
        tr = max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close))
        trs.append(tr)
    atr = sum(trs) / len(trs)
    ref = bars[-1].close
    return (atr / ref) * 100 if ref else 0.0
