from __future__ import annotations

from datetime import datetime

from app.utils.time import in_window


def is_market_open(ts: datetime) -> bool:
    return in_window(ts, "09:30", "16:00")
