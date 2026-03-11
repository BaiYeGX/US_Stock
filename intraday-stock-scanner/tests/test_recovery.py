from datetime import datetime, timedelta, timezone

from app.providers.base import Bar
from app.services.market_loop import RealtimeMarketLoop


class DummyProvider:
    def __init__(self):
        self.calls = 0

    def get_historical_bars(self, symbol, timeframe, start, end, adjusted=True):
        self.calls += 1
        return [
            Bar(symbol=symbol, ts=start + timedelta(minutes=1), open=1, high=2, low=1, close=1.5, volume=100),
            Bar(symbol=symbol, ts=start + timedelta(minutes=2), open=1.5, high=2, low=1.4, close=1.8, volume=120),
        ]

    async def stream_minute_bars(self, symbols, callback):
        return None


def test_backfill_after_reconnect():
    provider = DummyProvider()
    loop = RealtimeMarketLoop(provider=provider, symbols=["NVDA"])
    loop.last_bar_ts["NVDA"] = datetime.now(tz=timezone.utc) - timedelta(minutes=3)

    import asyncio

    asyncio.run(loop._backfill_after_reconnect())
    state = loop.store.get_or_create("NVDA")
    assert len(state.minute_bars) >= 2
    assert provider.calls == 1
