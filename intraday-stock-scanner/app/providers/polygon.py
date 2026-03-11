from __future__ import annotations

from datetime import date, datetime

import httpx

from app.providers.base import (
    AssetMeta,
    Bar,
    BaseProvider,
    DailyOpenClose,
    NewsItem,
    ProviderHealth,
    Snapshot,
)
from app.utils.exceptions import ProviderError


class PolygonProvider(BaseProvider):
    """Polygon provider skeleton with normalized return schemas."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.Client(timeout=10.0)

    def _get(self, path: str, params: dict | None = None) -> dict:
        params = params or {}
        params["apiKey"] = self.api_key
        try:
            response = self.client.get(f"{self.base_url}{path}", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            raise ProviderError(f"Polygon request failed: {path}") from exc

    def get_universe_metadata(self) -> list[AssetMeta]:
        return []

    def get_grouped_daily(self, day: date) -> list[Bar]:
        return []

    def get_daily_open_close(self, symbol: str, day: date) -> DailyOpenClose:
        return DailyOpenClose(symbol=symbol, date=day, open=0.0, close=0.0)

    def get_historical_bars(self, symbol: str, timeframe: str, start: datetime, end: datetime, adjusted: bool = True) -> list[Bar]:
        return []

    def get_snapshots(self, symbols: list[str]) -> dict[str, Snapshot]:
        return {s: Snapshot(symbol=s) for s in symbols}

    def get_news(self, symbols: list[str] | None, start: datetime, end: datetime) -> list[NewsItem]:
        return []

    async def stream_quotes(self, symbols: list[str], callback):
        return None

    async def stream_trades(self, symbols: list[str], callback):
        return None

    async def stream_minute_bars(self, symbols: list[str], callback):
        return None

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=True, provider="polygon", detail="configured")
