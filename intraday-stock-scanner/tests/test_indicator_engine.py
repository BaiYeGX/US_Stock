from datetime import datetime, timedelta, timezone

from app.providers.base import Bar
from app.services.indicator_engine import adx14, atr14, ema, pullback_days, rsi14, sma


def _bars(n: int) -> list[Bar]:
    out = []
    ts0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    for i in range(n):
        o = price
        h = o + 1.2 + (i % 3) * 0.1
        l = o - 0.8
        c = o + 0.4
        v = 1_000_000 + i * 10_000
        out.append(Bar(symbol="NVDA", ts=ts0 + timedelta(days=i), open=o, high=h, low=l, close=c, volume=v))
        price = c
    return out


def test_sma_ema():
    values = [1, 2, 3, 4, 5]
    assert sma(values, 5) == 3
    assert round(ema(values, 3), 4) == 4.0


def test_atr_rsi_adx():
    bars = _bars(40)
    atr = atr14(bars)
    rsi = rsi14([b.close for b in bars])
    adx = adx14(bars)
    assert atr is not None and atr > 0
    assert rsi is not None and 0 <= rsi <= 100
    assert adx is not None and 0 <= adx <= 100


def test_pullback_days_daily_bar_based():
    highs = [10, 11, 12, 13, 12.5, 12.2]
    assert pullback_days(highs) == 2
