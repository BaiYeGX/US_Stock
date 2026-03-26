from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from app.providers.base import Bar


EPS = 1e-9


def _safe(v: float | None) -> float | None:
    if v is None:
        return None
    if not isfinite(v):
        return None
    return v


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return _safe(sum(values[-period:]) / period)


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return _safe(e)


def atr14(bars: list[Bar], period: int = 14) -> float | None:
    if len(bars) < period + 1:
        return None
    trs: list[float] = []
    for i in range(1, len(bars)):
        cur = bars[i]
        prev = bars[i - 1]
        tr = max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close))
        trs.append(tr)
    if len(trs) < period:
        return None
    return _safe(sum(trs[-period:]) / period)


def rsi14(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(len(values) - period, len(values)):
        diff = values[i] - values[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(abs(min(diff, 0.0)))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss <= EPS:
        return 100.0
    rs = avg_gain / avg_loss
    return _safe(100 - (100 / (1 + rs)))


def adx14(bars: list[Bar], period: int = 14) -> float | None:
    # Simplified ADX implementation (Wilder-style approximation)
    if len(bars) < period * 2:
        return None
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    tr: list[float] = []
    for i in range(1, len(bars)):
        up = bars[i].high - bars[i - 1].high
        down = bars[i - 1].low - bars[i].low
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        tr.append(max(bars[i].high - bars[i].low, abs(bars[i].high - bars[i - 1].close), abs(bars[i].low - bars[i - 1].close)))

    if len(tr) < period:
        return None
    tr_n = sum(tr[-period:])
    if tr_n <= EPS:
        return None
    plus_di = 100 * (sum(plus_dm[-period:]) / tr_n)
    minus_di = 100 * (sum(minus_dm[-period:]) / tr_n)
    denom = plus_di + minus_di
    if denom <= EPS:
        return 0.0
    dx = 100 * abs(plus_di - minus_di) / denom
    return _safe(dx)


def highest(values: list[float], period: int, offset: int = 0) -> float | None:
    end = len(values) - offset
    start = end - period
    if start < 0:
        return None
    return _safe(max(values[start:end]))


def lowest(values: list[float], period: int, offset: int = 0) -> float | None:
    end = len(values) - offset
    start = end - period
    if start < 0:
        return None
    return _safe(min(values[start:end]))


def mean(values: list[float], period: int, offset: int = 0) -> float | None:
    end = len(values) - offset
    start = end - period
    if start < 0:
        return None
    return _safe(sum(values[start:end]) / period)


def pullback_days(highs: list[float]) -> int | None:
    # Use latest completed bar as t; HHV5_prev from t-1
    if len(highs) < 6:
        return None
    t = len(highs) - 1
    hhv5_prev = max(highs[t - 5 : t])
    k = None
    for idx in range(t - 1, max(-1, t - 6), -1):
        if abs(highs[idx] - hhv5_prev) <= 1e-9:
            k = idx
            break
    if k is None:
        return None
    return t - k


def sanitize_number(v: float | None) -> float | None:
    return _safe(v)
