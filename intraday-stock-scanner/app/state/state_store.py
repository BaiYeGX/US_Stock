from __future__ import annotations

from app.state.symbol_state import SymbolState


class StateStore:
    def __init__(self) -> None:
        self.symbols: dict[str, SymbolState] = {}

    def get_or_create(self, symbol: str) -> SymbolState:
        if symbol not in self.symbols:
            self.symbols[symbol] = SymbolState(symbol=symbol)
        return self.symbols[symbol]
