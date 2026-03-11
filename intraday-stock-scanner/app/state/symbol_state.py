from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from app.providers.base import Bar, Quote


@dataclass
class SymbolState:
    symbol: str
    last_price: float | None = None
    last_quote: Quote | None = None
    minute_bars: deque[Bar] = field(default_factory=lambda: deque(maxlen=390))
    five_minute_bars: deque[Bar] = field(default_factory=lambda: deque(maxlen=120))
    intraday_high: float | None = None
    intraday_low: float | None = None
    open_range_high: float | None = None
    open_range_low: float | None = None
    vwap_session: float | None = None
    cumulative_volume: float = 0.0
    spread_pct: float | None = None
    rvol: float | None = None
    atr20_pct: float | None = None
    rs_vs_benchmark_15m: float | None = None
    rs_vs_sector_15m: float | None = None
    market_regime: str | None = None
    last_triggered_setup: str | None = None
    last_alert_ts: datetime | None = None
    setup_flags: dict[str, bool] = field(default_factory=dict)
