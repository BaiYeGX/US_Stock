from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExchangeSession:
    label: str
    is_regular_open: bool
    has_regular_closed: bool


def classify_market_status(payload: dict) -> ExchangeSession:
    market = str(payload.get("market", "")).lower()
    if market == "open":
        return ExchangeSession(label="常规盘中", is_regular_open=True, has_regular_closed=False)
    if market == "premarket":
        return ExchangeSession(label="盘前", is_regular_open=False, has_regular_closed=False)
    if market == "postmarket":
        return ExchangeSession(label="盘后", is_regular_open=False, has_regular_closed=True)
    if market == "closed":
        return ExchangeSession(label="收盘", is_regular_open=False, has_regular_closed=True)
    is_open = bool(payload.get("isOpen", False))
    return ExchangeSession(label="常规盘中" if is_open else "收盘", is_regular_open=is_open, has_regular_closed=not is_open)
