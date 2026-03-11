from __future__ import annotations

from app.setups.base import SetupSignal
from app.state.symbol_state import SymbolState


def detect_orb(state: SymbolState, now_hhmm: str = "10:00") -> SetupSignal | None:
    if not (state.open_range_high and state.vwap_session and state.last_price and state.spread_pct is not None):
        return None
    if not ("09:35" <= now_hhmm <= "10:15"):
        return None
    if state.last_price <= state.open_range_high * 1.001:
        return None
    if state.last_price <= state.vwap_session or state.spread_pct > 0.15:
        return None
    entry = state.last_price
    stop = min(state.open_range_high, state.vwap_session) - 0.05
    risk = entry - stop
    if risk <= 0:
        return None
    return SetupSignal(
        setup="ORB",
        side="long",
        setup_score=80,
        entry_low=state.open_range_high * 1.0005,
        entry_high=entry,
        stop=stop,
        tp1=entry + risk,
        tp2=entry + min(2 * risk, entry * 0.03),
        invalidate_if="跌回开盘区间上沿且2根1m无法收回",
        reason="ORB放量突破开盘区间且站上VWAP。",
        metrics={"spread_pct": state.spread_pct},
    )
