from __future__ import annotations

import argparse
import os
from datetime import date

from app.db.migrations import create_all
from app.db.session import make_session_factory
from app.journal.repository import JournalRepository
from app.providers.base import AssetMeta, BaseProvider, ProviderHealth
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


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("premarket-scan")
    p1.add_argument("--scan-date", required=True)
    sub.add_parser("market-loop")
    p3 = sub.add_parser("review")
    p3.add_argument("--scan-date", required=True)
    p4 = sub.add_parser("replay-alerts")
    p4.add_argument("--scan-date", required=True)
    sub.add_parser("seed-universe")

    args = parser.parse_args()
    settings = load_settings()
    repo = _repo()

    if args.cmd == "premarket-scan":
        watchlist = run_premarket_scan(MockProvider(), repo, settings, date.fromisoformat(args.scan_date))
        print(f"watchlist size={len(watchlist)}")
    elif args.cmd == "market-loop":
        print("market loop skeleton ready")
    elif args.cmd == "review":
        summary = run_review(repo.session_factory, date.fromisoformat(args.scan_date))
        print(summary["markdown"])
    elif args.cmd == "replay-alerts":
        print(f"replay for {args.scan_date} not yet wired")
    elif args.cmd == "seed-universe":
        print("mock universe seeded logically")


if __name__ == "__main__":
    main()
