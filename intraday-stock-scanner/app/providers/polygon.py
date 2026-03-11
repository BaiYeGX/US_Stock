from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone
from typing import Any

import httpx

from app.data.websocket_client import WebsocketClient
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


class PolygonProvider(BaseProvider):
    """Polygon provider with normalized schemas + reconnectable websocket streams."""

    def __init__(self, base_url: str, api_key: str, ws_base_url: str = "wss://socket.polygon.io/stocks") -> None:
        self.base_url = base_url.rstrip("/")
        self.ws_base_url = ws_base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.Client(timeout=10.0)
        self.ws_client = WebsocketClient()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        params["apiKey"] = self.api_key
        try:
            response = self.client.get(f"{self.base_url}{path}", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            raise ProviderError(f"Polygon request failed: {path}") from exc

    def _parse_bar(self, symbol: str, row: dict[str, Any]) -> Bar:
        ts_ms = row.get("t", 0)
        ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        return Bar(
            symbol=symbol,
            ts=ts,
            open=float(row.get("o", 0.0)),
            high=float(row.get("h", 0.0)),
            low=float(row.get("l", 0.0)),
            close=float(row.get("c", 0.0)),
            volume=float(row.get("v", 0.0)),
            vwap=float(row["vw"]) if row.get("vw") is not None else None,
            trades=int(row["n"]) if row.get("n") is not None else None,
        )

    def get_universe_metadata(self) -> list[AssetMeta]:
        data = self._get("/v3/reference/tickers", {"market": "stocks", "active": "true", "limit": 1000})
        out: list[AssetMeta] = []
        for row in data.get("results", []):
            out.append(
                AssetMeta(
                    symbol=row.get("ticker", ""),
                    name=row.get("name", ""),
                    asset_type=(row.get("type", "") or "stock").lower(),
                    exchange=row.get("primary_exchange", ""),
                    is_active=bool(row.get("active", True)),
                    sector=row.get("sic_description"),
                    industry=row.get("sic_code"),
                )
            )
        return out

    def get_grouped_daily(self, day: date) -> list[Bar]:
        data = self._get(f"/v2/aggs/grouped/locale/us/market/stocks/{day.isoformat()}")
        out: list[Bar] = []
        for row in data.get("results", []):
            out.append(self._parse_bar(row.get("T", ""), row))
        return out

    def get_daily_open_close(self, symbol: str, day: date) -> DailyOpenClose:
        data = self._get(f"/v1/open-close/{symbol}/{day.isoformat()}")
        return DailyOpenClose(symbol=symbol, date=day, open=float(data.get("open", 0.0)), close=float(data.get("close", 0.0)))

    def get_historical_bars(self, symbol: str, timeframe: str, start: datetime, end: datetime, adjusted: bool = True) -> list[Bar]:
        mult = 1
        unit = "minute" if timeframe in {"1m", "5m"} else "day"
        if timeframe == "5m":
            mult = 5
        data = self._get(
            f"/v2/aggs/ticker/{symbol}/range/{mult}/{unit}/{start.date().isoformat()}/{end.date().isoformat()}",
            {"adjusted": str(adjusted).lower(), "sort": "asc", "limit": 50000},
        )
        return [self._parse_bar(symbol, row) for row in data.get("results", [])]

    def get_snapshots(self, symbols: list[str]) -> dict[str, Snapshot]:
        data = self._get("/v2/snapshot/locale/us/markets/stocks/tickers", {"tickers": ",".join(symbols)})
        out: dict[str, Snapshot] = {}
        for row in data.get("tickers", []):
            symbol = row.get("ticker", "")
            q = row.get("lastQuote") or {}
            t = row.get("lastTrade") or {}
            out[symbol] = Snapshot(
                symbol=symbol,
                latest_trade=Trade(symbol=symbol, ts=datetime.now(tz=timezone.utc), price=float(t.get("p", 0.0)), size=float(t.get("s", 0.0))) if t else None,
                latest_quote=Quote(symbol=symbol, ts=datetime.now(tz=timezone.utc), bid=float(q.get("p", 0.0)), ask=float(q.get("P", 0.0))) if q else None,
            )
        return out

    def get_news(self, symbols: list[str] | None, start: datetime, end: datetime) -> list[NewsItem]:
        params: dict[str, Any] = {"published_utc.gte": start.isoformat(), "published_utc.lte": end.isoformat(), "limit": 1000}
        if symbols:
            params["ticker"] = ",".join(symbols)
        data = self._get("/v2/reference/news", params)
        return [
            NewsItem(
                id=str(row.get("id", "")),
                ts=datetime.fromisoformat(row.get("published_utc", datetime.now(tz=timezone.utc).isoformat())),
                headline=row.get("title", ""),
                summary=row.get("description"),
                symbols=row.get("tickers", []),
                source=(row.get("publisher") or {}).get("name", "polygon"),
            )
            for row in data.get("results", [])
        ]

    async def _stream(self, channels: list[str], callback):
        import websockets

        async def connect_coro():
            return await websockets.connect(self.ws_base_url, ping_interval=20, ping_timeout=20)

        disconnected = {"flag": False}

        async def on_connect(ws):
            await ws.send(json.dumps({"action": "auth", "params": self.api_key}))
            await ws.send(json.dumps({"action": "subscribe", "params": ",".join(channels)}))
            if disconnected["flag"]:
                await callback({"ev": "SYSTEM", "type": "reconnected"})
                disconnected["flag"] = False

        async def on_message(item: dict):
            await callback(item)

        async def on_disconnect():
            disconnected["flag"] = True

        await self.ws_client.connect_forever(connect_coro=connect_coro, on_connect=on_connect, on_message=on_message, on_disconnect=on_disconnect)

    async def stream_quotes(self, symbols: list[str], callback):
        await self._stream([f"Q.{s}" for s in symbols], callback)

    async def stream_trades(self, symbols: list[str], callback):
        await self._stream([f"T.{s}" for s in symbols], callback)

    async def stream_minute_bars(self, symbols: list[str], callback):
        await self._stream([f"AM.{s}" for s in symbols], callback)

    def healthcheck(self) -> ProviderHealth:
        try:
            self._get("/v1/marketstatus/now")
            return ProviderHealth(ok=True, provider="polygon", detail="ok")
        except ProviderError as exc:
            return ProviderHealth(ok=False, provider="polygon", detail=str(exc))
