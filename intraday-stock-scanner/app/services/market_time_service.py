from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


NY = ZoneInfo("America/New_York")


@dataclass
class ExchangeSessionState:
    exchange_tz_now: datetime
    market_status: str
    is_open: bool


class MarketTimeService:
    def classify_from_status(self, payload: dict) -> ExchangeSessionState:
        now = datetime.now(tz=NY)
        status = str(payload.get("market", "")).lower()
        if status in {"open"}:
            label = "开盘"
            is_open = True
        elif status in {"closed"}:
            label = "收盘"
            is_open = False
        elif status in {"premarket"}:
            label = "盘前"
            is_open = False
        elif status in {"postmarket"}:
            label = "盘后"
            is_open = False
        else:
            # fallback based on payload fields
            if payload.get("isOpen") is True:
                label = "开盘"
                is_open = True
            else:
                label = "收盘"
                is_open = False
        return ExchangeSessionState(exchange_tz_now=now, market_status=label, is_open=is_open)
