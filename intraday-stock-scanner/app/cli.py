from __future__ import annotations

import argparse
import asyncio
import os
from datetime import date

from app.db.migrations import create_all
from app.db.session import make_session_factory
from app.journal.repository import JournalRepository
from app.providers.base import AssetMeta, BaseProvider, ProviderHealth
from app.services.market_loop import RealtimeMarketLoop
from app.services.postmarket_review import run_review
from app.services.premarket_scan import run_premarket_scan
from app.settings import load_settings


class MockProvider(BaseProvider):
    def get_universe_metadata(self):
        return [
            AssetMeta(symbol="NVDA", name="NVIDIA", asset_type="stock", exchange="NASDAQ", is_active=True, sector="Semiconductors", industry="Semis"),
            AssetMeta(symbol="AAPL", name="Apple", asset_type="stock", exchange="NASDAQ", is_active=True, sector="Technology", industry="Consumer"),
            AssetMeta(symbol="TSLA", name="Tesla", asset_type="stock", exchange="NASDAQ", is_active=True, sector="Auto", industry="EV"),
        ]

    def get_grouped_daily(self, day): return []
    def get_daily_open_close(self, symbol, day): raise NotImplementedError
    def get_historical_bars(self, symbol, timeframe, start, end, adjusted=True): return []
    def get_snapshots(self, symbols): return {}
    def get_news(self, symbols, start, end): return []
    async def stream_quotes(self, symbols, callback): return None
    async def stream_trades(self, symbols, callback): return None
    async def stream_minute_bars(self, symbols, callback): return None
    def healthcheck(self): return ProviderHealth(ok=True, provider="mock", detail="ok")


def _repo():
    db_url = os.getenv("DATABASE_URL", "sqlite:///./scanner.db")
    session_factory = make_session_factory(db_url)
    with session_factory() as conn:
        create_all(conn)
    return JournalRepository(session_factory)


def _provider(use_mock: bool):
    if use_mock:
        return MockProvider()
    api_key = os.getenv("POLYGON_API_KEY", "")
    if not api_key:
        raise RuntimeError("POLYGON_API_KEY is required for real-time market loop")
    settings = load_settings()
    from app.providers.polygon import PolygonProvider
    return PolygonProvider(base_url=settings.provider.rest_base_url, api_key=api_key, ws_base_url=settings.provider.ws_base_url)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("premarket-scan")
    p1.add_argument("--scan-date", required=True)
    p2 = sub.add_parser("market-loop")
    p2.add_argument("--symbols", default="")
    p2.add_argument("--mock", action="store_true")
    p3 = sub.add_parser("review")
    p3.add_argument("--scan-date", required=True)
    p4 = sub.add_parser("replay-alerts")
    p4.add_argument("--scan-date", required=True)
    sub.add_parser("seed-universe")
    p5 = sub.add_parser("serve-ui")
    p5.add_argument("--host", default="127.0.0.1")
    p5.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()
    settings = load_settings()
    repo = _repo()

    if args.cmd == "premarket-scan":
        watchlist = run_premarket_scan(MockProvider(), repo, settings, date.fromisoformat(args.scan_date))
        print(f"watchlist size={len(watchlist)}")
    elif args.cmd == "market-loop":
        provider = _provider(args.mock)
        if args.symbols:
            symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        else:
            symbols = ["NVDA", "AAPL", "TSLA"] if args.mock else ["SPY", "QQQ", "NVDA", "AAPL", "TSLA"]
        print(f"starting market loop for {symbols} (mock={args.mock})")
        loop = RealtimeMarketLoop(provider=provider, symbols=symbols)
        asyncio.run(loop.run())
    elif args.cmd == "review":
        summary = run_review(repo.session_factory, date.fromisoformat(args.scan_date))
        print(summary["markdown"])
    elif args.cmd == "replay-alerts":
        print(f"replay for {args.scan_date} not yet wired")
    elif args.cmd == "seed-universe":
        print("mock universe seeded logically")
    elif args.cmd == "serve-ui":
        from app.ui.server import create_app
        try:
            import uvicorn
        except Exception as exc:
            raise RuntimeError("uvicorn is required for serve-ui") from exc
        app = create_app(os.getenv("DATABASE_URL", "sqlite:///./scanner.db"))
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
