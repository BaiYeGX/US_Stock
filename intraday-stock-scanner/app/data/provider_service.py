from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.providers.finnhub import FinnhubProvider


@dataclass
class CacheItem:
    value: object
    expires_at: float


class MarketDataService:
    """Unified data service layer for UI/backend use.

    All market requests should go through this service instead of direct vendor URL calls.
    """

    def __init__(self) -> None:
        self._quote_cache: dict[str, CacheItem] = {}
        self._candle_cache: dict[str, CacheItem] = {}
        self._news_cache: dict[str, CacheItem] = {}
        self._last_call: dict[str, float] = {}

    def _provider(self, source: str, api_key: str):
        source = (source or "finnhub").lower()
        if source == "finnhub":
            return FinnhubProvider(api_key=api_key)
        raise ValueError("暂不支持该数据源")

    def _rate_limit(self, key: str, min_interval_sec: float = 0.2) -> None:
        now = time.time()
        last = self._last_call.get(key, 0.0)
        if now - last < min_interval_sec:
            time.sleep(min_interval_sec - (now - last))
        self._last_call[key] = time.time()

    def get_quote(self, source: str, api_key: str, symbol: str, ttl: int = 30) -> dict:
        symbol = symbol.upper().strip()
        ck = f"{source}:quote:{symbol}"
        cached = self._quote_cache.get(ck)
        now = time.time()
        if cached and cached.expires_at > now:
            return cached.value  # type: ignore[return-value]
        self._rate_limit(f"{source}:quote")
        p = self._provider(source, api_key)
        value = p.get_quote(symbol)
        self._quote_cache[ck] = CacheItem(value=value, expires_at=now + ttl)
        return value

    def get_candles(
        self,
        source: str,
        api_key: str,
        symbol: str,
        resolution: str,
        from_ts: int,
        to_ts: int,
        ttl: int = 60,
    ) -> dict:
        symbol = symbol.upper().strip()
        ck = f"{source}:candles:{symbol}:{resolution}:{from_ts}:{to_ts}"
        cached = self._candle_cache.get(ck)
        now = time.time()
        if cached and cached.expires_at > now:
            return cached.value  # type: ignore[return-value]
        self._rate_limit(f"{source}:candles")
        p = self._provider(source, api_key)
        value = p.get_candles(symbol, resolution, from_ts, to_ts)
        self._candle_cache[ck] = CacheItem(value=value, expires_at=now + ttl)
        return value

    def get_news(self, source: str, api_key: str, symbol: str | None = None, ttl: int = 120) -> list[dict]:
        key_symbol = (symbol or "general").upper()
        ck = f"{source}:news:{key_symbol}"
        cached = self._news_cache.get(ck)
        now = time.time()
        if cached and cached.expires_at > now:
            return cached.value  # type: ignore[return-value]
        self._rate_limit(f"{source}:news", 0.5)
        p = self._provider(source, api_key)
        start = datetime.now(tz=timezone.utc) - timedelta(days=3)
        end = datetime.now(tz=timezone.utc)
        items = p.get_news([key_symbol] if symbol else None, start, end)
        value = [
            {
                "id": n.id,
                "ts": n.ts.isoformat(),
                "headline": n.headline,
                "summary": n.summary,
                "symbols": n.symbols,
                "source": n.source,
            }
            for n in items[:50]
        ]
        self._news_cache[ck] = CacheItem(value=value, expires_at=now + ttl)
        return value

    def health_check(self, source: str, api_key: str) -> dict:
        p = self._provider(source, api_key)
        h = p.healthcheck()
        return {"ok": h.ok, "provider": h.provider, "detail": h.detail}
