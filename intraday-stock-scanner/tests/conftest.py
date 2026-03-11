from datetime import datetime

import pytest

from app.providers.base import Bar
from app.state.symbol_state import SymbolState


@pytest.fixture
def trend_state() -> SymbolState:
    s = SymbolState(symbol="NVDA", last_price=101.5, open_range_high=100.8, vwap_session=100.5, intraday_high=101.6, spread_pct=0.05, rvol=2.1, atr20_pct=3.5, rs_vs_benchmark_15m=1.2, rs_vs_sector_15m=0.9)
    s.minute_bars.extend([
        Bar(symbol="NVDA", ts=datetime(2026,3,11,10,0), open=100, high=101, low=99.8, close=100.6, volume=1000),
        Bar(symbol="NVDA", ts=datetime(2026,3,11,10,1), open=100.6, high=101.6, low=100.5, close=101.5, volume=2200),
    ])
    return s


@pytest.fixture
def choppy_regime_data():
    return dict(price=100.01, vwap=100.0, net_ret_30m=0.01, higher_highs=False, higher_lows=True)
