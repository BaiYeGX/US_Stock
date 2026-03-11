from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class AssetMeta:
    symbol: str
    name: str
    asset_type: str
    exchange: str
    is_active: bool
    sector: str | None = None
    industry: str | None = None


@dataclass
class Bar:
    symbol: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float | None = None
    trades: int | None = None


@dataclass
class Quote:
    symbol: str
    ts: datetime
    bid: float
    ask: float
    bid_size: float | None = None
    ask_size: float | None = None


@dataclass
class Trade:
    symbol: str
    ts: datetime
    price: float
    size: float


@dataclass
class Snapshot:
    symbol: str
    latest_trade: Trade | None = None
    latest_quote: Quote | None = None
    minute_bar: Bar | None = None
    daily_bar: Bar | None = None
    prev_daily_bar: Bar | None = None


@dataclass
class NewsItem:
    id: str
    ts: datetime
    headline: str
    summary: str | None
    symbols: list[str]
    source: str


@dataclass
class DailyOpenClose:
    symbol: str
    date: date
    open: float
    close: float


@dataclass
class ProviderHealth:
    ok: bool
    provider: str
    detail: str


class BaseProvider(ABC):
    @abstractmethod
    def get_universe_metadata(self) -> list[AssetMeta]: ...

    @abstractmethod
    def get_grouped_daily(self, day: date) -> list[Bar]: ...

    @abstractmethod
    def get_daily_open_close(self, symbol: str, day: date) -> DailyOpenClose: ...

    @abstractmethod
    def get_historical_bars(self, symbol: str, timeframe: str, start: datetime, end: datetime, adjusted: bool = True) -> list[Bar]: ...

    @abstractmethod
    def get_snapshots(self, symbols: list[str]) -> dict[str, Snapshot]: ...

    @abstractmethod
    def get_news(self, symbols: list[str] | None, start: datetime, end: datetime) -> list[NewsItem]: ...

    @abstractmethod
    async def stream_quotes(self, symbols: list[str], callback): ...

    @abstractmethod
    async def stream_trades(self, symbols: list[str], callback): ...

    @abstractmethod
    async def stream_minute_bars(self, symbols: list[str], callback): ...

    @abstractmethod
    def healthcheck(self) -> ProviderHealth: ...
