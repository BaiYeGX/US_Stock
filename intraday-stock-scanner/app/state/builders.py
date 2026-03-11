from __future__ import annotations

from app.providers.base import Snapshot
from app.state.symbol_state import SymbolState


def build_state_from_snapshot(snapshot: Snapshot) -> SymbolState:
    state = SymbolState(symbol=snapshot.symbol)
    if snapshot.latest_trade:
        state.last_price = snapshot.latest_trade.price
    if snapshot.latest_quote:
        state.last_quote = snapshot.latest_quote
        mid = (snapshot.latest_quote.bid + snapshot.latest_quote.ask) / 2
        state.spread_pct = (snapshot.latest_quote.ask - snapshot.latest_quote.bid) / mid * 100 if mid else None
    if snapshot.minute_bar:
        state.minute_bars.append(snapshot.minute_bar)
    return state
