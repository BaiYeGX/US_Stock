from datetime import datetime

from app.features.atr import atr_pct
from app.features.relative_strength import relative_strength
from app.features.rvol import rvol_20
from app.features.vwap import session_vwap
from app.providers.base import Bar


def test_vwap():
    bars = [Bar(symbol="A", ts=datetime.now(), open=1, high=1, low=1, close=10, volume=100), Bar(symbol="A", ts=datetime.now(), open=1, high=1, low=1, close=20, volume=100)]
    assert session_vwap(bars) == 15


def test_atr_rvol_rs():
    bars = [Bar(symbol="A", ts=datetime.now(), open=10+i, high=11+i, low=9+i, close=10.5+i, volume=1000) for i in range(25)]
    assert atr_pct(bars, period=20) > 0
    assert rvol_20(2000, 1000) == 2
    assert relative_strength(1.5, 0.5) == 1.0
