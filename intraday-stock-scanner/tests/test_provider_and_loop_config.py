from __future__ import annotations

from datetime import datetime, timezone

from app.constants import FIXED_SYMBOL_POOL
from app.providers.finnhub import FinnhubProvider
from app.services.market_loop import evaluate_symbol
from app.settings import load_settings
from app.state.symbol_state import SymbolState


def test_finnhub_universe_metadata_uses_fixed_pool():
    provider = FinnhubProvider(api_key="demo")
    metadata = provider.get_universe_metadata()
    assert [m.symbol for m in metadata] == FIXED_SYMBOL_POOL


def test_evaluate_symbol_respects_setup_enable_switch():
    settings = load_settings()
    settings.setups["orb"]["enabled"] = False
    settings.setups["vwap_reclaim"]["enabled"] = False
    settings.setups["hod_breakout"]["enabled"] = False

    state = SymbolState(symbol="NVDA")
    state.last_price = 100.0
    state.open_range_high = 99.0
    state.vwap_session = 98.0
    state.spread_pct = 0.05
    state.intraday_high = 100.5
    state.cumulative_volume = 5_000_000

    signal, score, reasons = evaluate_symbol(
        state,
        now=datetime(2026, 1, 5, 15, 40, tzinfo=timezone.utc),
        pools={"rs_benchmark": [0], "rs_sector": [0], "rvol": [1], "atr20": [3], "spread": [0.05], "dollar5m": [10_000_000], "room": [2]},
        regime="choppy",
        settings=settings,
    )

    assert signal is None
    assert score is None
    assert reasons == ["no_setup"]
