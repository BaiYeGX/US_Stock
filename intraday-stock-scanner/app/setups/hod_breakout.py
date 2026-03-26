from __future__ import annotations

from app.setups.base import SetupSignal
from app.state.symbol_state import SymbolState


def detect_hod_breakout(state: SymbolState, now_hhmm: str = "10:30", params: dict | None = None) -> SetupSignal | None:
    cfg = params or {}
    windows = cfg.get("windows", [["10:00", "11:30"], ["14:00", "15:30"]])
    proximity_to_hod_pct = float(cfg.get("proximity_to_hod_pct", 0.3))
    max_spread_pct = float(cfg.get("max_spread_pct", 0.15))

    if not (state.intraday_high and state.last_price and state.vwap_session and state.spread_pct is not None):
        return None
    in_window = any(start <= now_hhmm <= end for start, end in windows)
    if not in_window:
        return None
    distance = (state.intraday_high - state.last_price) / state.intraday_high * 100
    if distance > proximity_to_hod_pct or state.last_price <= state.vwap_session or state.spread_pct > max_spread_pct:
        return None
    entry = max(state.last_price, state.intraday_high * 1.0005)
    stop = state.intraday_high * 0.996
    risk = entry - stop
    if risk <= 0:
        return None
    return SetupSignal(
        setup="HOD_BREAKOUT",
        side="long",
        setup_score=75,
        entry_low=state.intraday_high * 1.0005,
        entry_high=entry,
        stop=stop,
        tp1=entry + risk,
        tp2=entry + min(2 * risk, entry * 0.03),
        invalidate_if="突破后快速跌回整理区",
        reason="临近日高且维持在VWAP上方。",
        metrics={"distance_to_hod_pct": distance},
    )
