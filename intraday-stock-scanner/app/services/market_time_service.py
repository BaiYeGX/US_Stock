from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.services.exchange_session import classify_market_status


NY = ZoneInfo("America/New_York")
SH = ZoneInfo("Asia/Shanghai")


@dataclass
class ExchangeSessionState:
    exchange_tz_now: datetime
    market_status: str
    is_open: bool


class MarketTimeService:
    def now_ny(self) -> datetime:
        return datetime.now(tz=NY)

    def now_shanghai(self) -> datetime:
        return datetime.now(tz=SH)

    def to_shanghai_display(self, dt: datetime | None) -> str:
        if dt is None:
            return "数据不足"
        return dt.astimezone(SH).strftime("%Y-%m-%d %H:%M:%S")

    def to_newyork_display(self, dt: datetime | None) -> str:
        if dt is None:
            return "数据不足"
        return dt.astimezone(NY).strftime("%Y-%m-%d %H:%M:%S")

    def get_exchange_date(self) -> str:
        return self.now_ny().date().isoformat()

    def classify_from_status(self, payload: dict) -> ExchangeSessionState:
        now = self.now_ny()
        session = classify_market_status(payload)
        return ExchangeSessionState(exchange_tz_now=now, market_status=session.label, is_open=session.is_regular_open)

    def current_exchange_session(self, payload: dict) -> str:
        return classify_market_status(payload).label

    def has_regular_session_closed_today(self, payload: dict) -> bool:
        return classify_market_status(payload).has_regular_closed

    def get_today_close_trigger_window(self, payload: dict) -> bool:
        session_closed = self.has_regular_session_closed_today(payload)
        now_ny = self.now_ny().time()
        return session_closed and now_ny >= time(16, 1)

    def ny_close_timestamp(self, exchange_date: str) -> str:
        d = date.fromisoformat(exchange_date)
        close_dt = datetime(d.year, d.month, d.day, 16, 0, tzinfo=NY)
        return close_dt.isoformat()

    def _previous_trading_day(self, d: date) -> date:
        # weekend-aware fallback when full exchange calendar is unavailable
        d = d - timedelta(days=1)
        while d.weekday() >= 5:  # 5/6 => Sat/Sun
            d -= timedelta(days=1)
        return d

    def get_latest_completed_exchange_date(self, payload: dict | None = None) -> str:
        now = self.now_ny()
        today = now.date()
        if payload is not None and self.has_regular_session_closed_today(payload):
            return today.isoformat()
        if now.time() < time(16, 0):
            return self._previous_trading_day(today).isoformat()
        return today.isoformat()
