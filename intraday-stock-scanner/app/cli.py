from __future__ import annotations

import argparse
import asyncio
import os
from datetime import date

from app.db.migrations import create_all
from app.db.session import make_session_factory
from app.journal.replay import replay_alerts
from app.journal.repository import JournalRepository
from app.constants import FIXED_SYMBOL_POOL
from app.providers.base import AssetMeta, BaseProvider, ProviderHealth
from app.providers.finnhub import FinnhubProvider
from app.services.market_loop import RealtimeMarketLoop
from app.services.postmarket_review import run_review
from app.services.premarket_scan import run_premarket_scan
from app.settings import load_settings


class MockProvider(BaseProvider):
    def get_universe_metadata(self):
        return [
            AssetMeta(symbol=s, name=s, asset_type="etf" if s in {"QQQ", "SMH", "SPY", "SOXX"} else "stock", exchange="NASDAQ", is_active=True, sector=None, industry=None)
            for s in FIXED_SYMBOL_POOL
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
    settings = load_settings()
    source = (settings.provider.name or "finnhub").lower()
    if source == "finnhub":
        api_key = os.getenv("FINNHUB_API_KEY", "")
        if not api_key:
            raise RuntimeError("FINNHUB_API_KEY is required for real-time market loop")
        return FinnhubProvider(api_key=api_key)
    if source == "polygon":
        api_key = os.getenv("POLYGON_API_KEY", "")
        if not api_key:
            raise RuntimeError("POLYGON_API_KEY is required for real-time market loop")
        from app.providers.polygon import PolygonProvider
        return PolygonProvider(base_url=settings.provider.rest_base_url, api_key=api_key, ws_base_url=settings.provider.ws_base_url)
    raise RuntimeError(f"Unsupported provider: {source}")


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
        use_mock = not bool(os.getenv("FINNHUB_API_KEY"))
        watchlist = run_premarket_scan(_provider(use_mock), repo, settings, date.fromisoformat(args.scan_date))
        print(f"watchlist size={len(watchlist)}")
    elif args.cmd == "market-loop":
        provider = _provider(args.mock)
        if args.symbols:
            symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        else:
            symbols = list(FIXED_SYMBOL_POOL)
        print(f"starting market loop for {symbols} (mock={args.mock})")
        loop = RealtimeMarketLoop(provider=provider, symbols=symbols, repo=repo)
        asyncio.run(loop.run())
    elif args.cmd == "review":
        summary = run_review(repo.session_factory, date.fromisoformat(args.scan_date))
        print(summary["markdown"])
    elif args.cmd == "replay-alerts":
        rows = replay_alerts(repo.session_factory, date.fromisoformat(args.scan_date))
        print(f"replay alerts={len(rows)}")
        for row in rows[:20]:
            print(f"{row['ts']} {row['symbol']} {row['setup']} score={row['score']} grade={row['grade']}")
    elif args.cmd == "seed-universe":
        print("mock universe seeded logically")
    elif args.cmd == "serve-ui":
        db_url = os.getenv("DATABASE_URL", "sqlite:///./scanner.db")
        try:
            from app.ui.server import create_app
            import uvicorn
            app = create_app(db_url)
            uvicorn.run(app, host=args.host, port=args.port)
        except Exception:
            from app.ui.simple_server import run_simple_ui_server
            run_simple_ui_server(db_url.replace("sqlite:///", ""), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
