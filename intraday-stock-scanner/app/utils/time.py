from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo


def now_et() -> datetime:
    return datetime.now(tz=ZoneInfo("America/New_York"))


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def in_window(ts: datetime, start: str, end: str) -> bool:
    t = ts.timetz().replace(tzinfo=None)
    return parse_hhmm(start) <= t <= parse_hhmm(end)
