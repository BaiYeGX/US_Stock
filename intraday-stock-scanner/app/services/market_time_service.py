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

    @staticmethod
    def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
        d = date(year, month, 1)
        while d.weekday() != weekday:
            d += timedelta(days=1)
        d += timedelta(days=(n - 1) * 7)
        return d

    @staticmethod
    def _last_weekday(year: int, month: int, weekday: int) -> date:
        if month == 12:
            d = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            d = date(year, month + 1, 1) - timedelta(days=1)
        while d.weekday() != weekday:
            d -= timedelta(days=1)
        return d

    @staticmethod
    def _observed(d: date) -> date:
        if d.weekday() == 5:  # Saturday
            return d - timedelta(days=1)
        if d.weekday() == 6:  # Sunday
            return d + timedelta(days=1)
        return d

    def _us_market_holidays(self, year: int) -> set[date]:
        # Core US market holidays (without Good Friday for simplicity)
        new_year = self._observed(date(year, 1, 1))
        mlk = self._nth_weekday(year, 1, 0, 3)
        presidents = self._nth_weekday(year, 2, 0, 3)
        memorial = self._last_weekday(year, 5, 0)
        juneteenth = self._observed(date(year, 6, 19))
        independence = self._observed(date(year, 7, 4))
        labor = self._nth_weekday(year, 9, 0, 1)
        thanksgiving = self._nth_weekday(year, 11, 3, 4)
        christmas = self._observed(date(year, 12, 25))
        return {
            new_year,
            mlk,
            presidents,
            memorial,
            juneteenth,
            independence,
            labor,
            thanksgiving,
            christmas,
        }

    def _is_trading_day(self, d: date) -> bool:
        if d.weekday() >= 5:
            return False
        holidays = self._us_market_holidays(d.year)
        return d not in holidays

    def _previous_trading_day(self, d: date) -> date:
        d = d - timedelta(days=1)
        while not self._is_trading_day(d):
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
