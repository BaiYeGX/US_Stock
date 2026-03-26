from __future__ import annotations

import asyncio
import json
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.constants import FIXED_SYMBOL_POOL
from app.providers.base import (
    AssetMeta,
    Bar,
    BaseProvider,
    DailyOpenClose,
    NewsItem,
    ProviderHealth,
    Quote,
    Snapshot,
    Trade,
)
from app.utils.exceptions import ProviderError


class FinnhubProvider(BaseProvider):
    """Finnhub provider focused on free-tier friendly small watchlist monitoring."""

    def __init__(self, api_key: str, base_url: str = "https://finnhub.io/api/v1") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _get_json(self, path: str, params: dict[str, str | int | float]) -> dict | list:
        query = dict(params)
        query["token"] = self.api_key
        url = f"{self.base_url}{path}?{urlencode(query)}"
        try:
            req = Request(url, headers={"User-Agent": "intraday-stock-scanner/0.1"})
            with urlopen(req, timeout=12) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise ProviderError(f"Finnhub request failed: {path}") from exc

    def get_quote(self, symbol: str) -> dict:
        data = self._get_json("/quote", {"symbol": symbol})
        if not isinstance(data, dict):
            raise ProviderError("Finnhub quote format invalid")
        return data

    def get_candles(self, symbol: str, resolution: str, start_ts: int, end_ts: int) -> dict:
        data = self._get_json(
            "/stock/candle",
            {"symbol": symbol, "resolution": resolution, "from": start_ts, "to": end_ts},
        )
        if not isinstance(data, dict):
            raise ProviderError("Finnhub candle format invalid")
        return data

    def get_news(self, symbols: list[str] | None, start: datetime, end: datetime) -> list[NewsItem]:
        items: list[NewsItem] = []
        if symbols:
            for symbol in symbols[:10]:
                raw = self._get_json(
                    "/company-news",
                    {
                        "symbol": symbol,
                        "from": start.date().isoformat(),
                        "to": end.date().isoformat(),
                    },
                )
                if isinstance(raw, list):
                    for row in raw[:20]:
                        ts = datetime.fromtimestamp(int(row.get("datetime", time.time())), tz=timezone.utc)
                        items.append(
                            NewsItem(
                                id=str(row.get("id", f"{symbol}-{int(ts.timestamp())}")),
                                ts=ts,
                                headline=row.get("headline", ""),
                                summary=row.get("summary"),
                                symbols=[symbol],
                                source="finnhub",
                            )
                        )
            return items
        raw = self._get_json("/news", {"category": "general"})
        if isinstance(raw, list):
            for row in raw[:30]:
                ts = datetime.fromtimestamp(int(row.get("datetime", time.time())), tz=timezone.utc)
                items.append(
                    NewsItem(
                        id=str(row.get("id", f"general-{int(ts.timestamp())}")),
                        ts=ts,
                        headline=row.get("headline", ""),
                        summary=row.get("summary"),
                        symbols=[],
                        source="finnhub",
                    )
                )
        return items

    # BaseProvider compatibility
    def get_universe_metadata(self) -> list[AssetMeta]:
        etf_symbols = {"QQQ", "SMH", "SPY", "SOXX"}
        return [
            AssetMeta(
                symbol=symbol,
                name=symbol,
                asset_type="etf" if symbol in etf_symbols else "stock",
                exchange="US",
                is_active=True,
                sector=None,
                industry=None,
            )
            for symbol in FIXED_SYMBOL_POOL
        ]

    def get_grouped_daily(self, day: date) -> list[Bar]:
        bars: list[Bar] = []
        ts = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
        for symbol in FIXED_SYMBOL_POOL:
            try:
                q = self.get_quote(symbol)
            except ProviderError:
                continue
            close = float(q.get("c", 0.0))
            open_ = float(q.get("o", close))
            high = float(q.get("h", close))
            low = float(q.get("l", close))
            volume = float(q.get("v", 0.0))
            bars.append(
                Bar(
                    symbol=symbol,
                    ts=ts,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
        return bars

    def get_daily_open_close(self, symbol: str, day: date) -> DailyOpenClose:
        q = self.get_quote(symbol)
        return DailyOpenClose(symbol=symbol, date=day, open=float(q.get("o", 0.0)), close=float(q.get("c", 0.0)))

    def get_historical_bars(self, symbol: str, timeframe: str, start: datetime, end: datetime, adjusted: bool = True) -> list[Bar]:
        resolution = "1"
        if timeframe == "5m":
            resolution = "5"
        elif timeframe == "30m":
            resolution = "30"
        elif timeframe in {"1d", "day"}:
            resolution = "D"
        elif timeframe in {"1w", "week"}:
            resolution = "W"
        raw = self.get_candles(symbol, resolution, int(start.timestamp()), int(end.timestamp()))
        if raw.get("s") != "ok":
            return []
        out: list[Bar] = []
        t_list = raw.get("t", [])
        for idx, t in enumerate(t_list):
            out.append(
                Bar(
                    symbol=symbol,
                    ts=datetime.fromtimestamp(int(t), tz=timezone.utc),
                    open=float(raw.get("o", [0])[idx]),
                    high=float(raw.get("h", [0])[idx]),
                    low=float(raw.get("l", [0])[idx]),
                    close=float(raw.get("c", [0])[idx]),
                    volume=float(raw.get("v", [0])[idx]),
                )
            )
        return out

    def get_snapshots(self, symbols: list[str]) -> dict[str, Snapshot]:
        out: dict[str, Snapshot] = {}
        for symbol in symbols[:200]:
            q = self.get_quote(symbol)
            ts = datetime.now(tz=timezone.utc)
            trade = Trade(symbol=symbol, ts=ts, price=float(q.get("c", 0.0)), size=0.0)
            quote = Quote(symbol=symbol, ts=ts, bid=float(q.get("c", 0.0)), ask=float(q.get("c", 0.0)))
            out[symbol] = Snapshot(symbol=symbol, latest_trade=trade, latest_quote=quote)
        return out

    async def stream_quotes(self, symbols: list[str], callback):
        # free-tier friendly polling fallback: small pool only
        symbols = symbols[:50]
        while True:
            now_ms = int(time.time() * 1000)
            for s in symbols:
                q = self.get_quote(s)
                await callback({"ev": "Q", "sym": s, "bp": q.get("c", 0.0), "ap": q.get("c", 0.0), "t": now_ms})
            await asyncio.sleep(20)

    async def stream_trades(self, symbols: list[str], callback):
        symbols = symbols[:50]
        while True:
            now_ms = int(time.time() * 1000)
            for s in symbols:
                q = self.get_quote(s)
                await callback({"ev": "T", "sym": s, "p": q.get("c", 0.0), "s": 0, "t": now_ms})
            await asyncio.sleep(20)

    async def stream_minute_bars(self, symbols: list[str], callback):
        symbols = symbols[:50]
        while True:
            end = datetime.now(tz=timezone.utc)
            start = end - timedelta(minutes=2)
            for s in symbols:
                bars = self.get_historical_bars(s, "1m", start, end)
                if not bars:
                    continue
                bar = bars[-1]
                await callback(
                    {
                        "ev": "AM",
                        "sym": s,
                        "s": int(bar.ts.timestamp() * 1000),
                        "o": bar.open,
                        "h": bar.high,
                        "l": bar.low,
                        "c": bar.close,
                        "v": bar.volume,
                    }
                )
            await asyncio.sleep(60)

    def get_market_status(self) -> dict:
        raw = self._get_json("/stock/market-status", {"exchange": "US"})
        return raw if isinstance(raw, dict) else {"market": "unknown"}

    def get_earnings_calendar(self, symbol: str, from_date: str, to_date: str) -> list[dict]:
        raw = self._get_json(
            "/calendar/earnings",
            {"symbol": symbol, "from": from_date, "to": to_date},
        )
        if isinstance(raw, dict):
            return raw.get("earningsCalendar", []) or []
        return []

    def healthcheck(self) -> ProviderHealth:
        if not self.api_key:
            return ProviderHealth(ok=False, provider="finnhub", detail="缺少 API Key")
        try:
            _ = self.get_quote("AAPL")
            return ProviderHealth(ok=True, provider="finnhub", detail="ok")
        except ProviderError as exc:
            return ProviderHealth(ok=False, provider="finnhub", detail=str(exc))
