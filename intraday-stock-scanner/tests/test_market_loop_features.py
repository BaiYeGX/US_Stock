from __future__ import annotations

from datetime import datetime, timezone

from app.services.market_loop import RealtimeMarketLoop


class DummyProvider:
    async def stream_minute_bars(self, symbols, callback):
        return None


def _event(sym: str, minute: int, o: float, h: float, l: float, c: float, v: float):
    ts = datetime(2026, 1, 5, 15, minute, tzinfo=timezone.utc)
    return {"ev": "AM", "sym": sym, "s": int(ts.timestamp() * 1000), "o": o, "h": h, "l": l, "c": c, "v": v}


def test_refresh_state_features_updates_core_fields():
    loop = RealtimeMarketLoop(provider=DummyProvider(), symbols=["NVDA"])

    import asyncio

    for i in range(25):
        asyncio.run(loop._on_minute_bar(_event("NVDA", i % 60, 100 + i, 101 + i, 99 + i, 100.5 + i, 1000 + i)))

    st = loop.store.get_or_create("NVDA")
    assert st.vwap_session is not None
    assert st.spread_pct is not None
    assert st.rvol is not None
    assert st.atr20_pct is not None
    assert st.open_range_high is not None
    assert st.open_range_low is not None


def test_refresh_relative_strength_sets_rs_fields():
    loop = RealtimeMarketLoop(provider=DummyProvider(), symbols=["NVDA", "SMH"])

    import asyncio

    for i in range(20):
        asyncio.run(loop._on_minute_bar(_event("NVDA", i % 60, 100, 101, 99, 100 + i * 0.1, 1000)))
        asyncio.run(loop._on_minute_bar(_event("SMH", i % 60, 50, 51, 49, 50 + i * 0.05, 1000)))

    loop._refresh_relative_strength()
    st = loop.store.get_or_create("NVDA")
    assert st.rs_vs_benchmark_15m is not None
    assert st.rs_vs_sector_15m is not None


def test_update_regime_from_benchmark_trend():
    loop = RealtimeMarketLoop(provider=DummyProvider(), symbols=["QQQ"])

    import asyncio

    for i in range(40):
        # persistent upward drift
        asyncio.run(loop._on_minute_bar(_event("QQQ", i % 60, 100, 102, 99, 100 + i * 0.2, 2000)))

    loop._update_regime()
    assert loop.regime in {"trend_up", "choppy"}
