from __future__ import annotations

from app.setups.base import SetupSignal
from app.state.symbol_state import SymbolState


def detect_vwap_reclaim(state: SymbolState, closes: list[float], now_hhmm: str = "10:30") -> SetupSignal | None:
    if not (state.vwap_session and state.last_price and state.spread_pct is not None):
        return None
    if not ("09:45" <= now_hhmm <= "13:30") or len(closes) < 2:
        return None
    if closes[-2] <= state.vwap_session or closes[-1] <= state.vwap_session:
        return None
    if state.spread_pct > 0.15:
        return None
    entry = state.last_price
    stop = state.vwap_session - 0.05
    risk = entry - stop
    if risk <= 0:
        return None
    return SetupSignal(
        setup="VWAP_RECLAIM",
        side="long",
        setup_score=78,
        entry_low=closes[-1] * 1.0002,
        entry_high=entry,
        stop=stop,
        tp1=entry + risk,
        tp2=entry + 2 * risk,
        invalidate_if="重新跌回VWAP下方且放量转弱",
        reason="回踩VWAP后两根1m收回上方。",
        metrics={"spread_pct": state.spread_pct},
    )
