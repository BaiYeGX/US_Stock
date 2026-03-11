from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.scoring.filters import hard_filter
from app.scoring.intraday_score import compute_ias
from app.setups.hod_breakout import detect_hod_breakout
from app.setups.orb import detect_orb
from app.setups.vwap_reclaim import detect_vwap_reclaim
from app.state.state_store import StateStore


class RealtimeMarketLoop:
    """Realtime loop: streaming minute bars + reconnect backfill + setup scan."""

    def __init__(self, provider, symbols: list[str]) -> None:
        self.provider = provider
        self.symbols = symbols
        self.store = StateStore()
        self.last_bar_ts: dict[str, datetime] = {}
        self.regime = "choppy"
        self._reconnected = False

    async def _on_minute_bar(self, event: dict) -> None:
        if event.get("ev") == "SYSTEM" and event.get("type") == "reconnected":
            self._reconnected = True
            return
        if event.get("ev") != "AM":
            return
        symbol = event.get("sym")
        if not symbol:
            return
        state = self.store.get_or_create(symbol)
        ts = datetime.fromtimestamp(float(event.get("s", 0)) / 1000, tz=timezone.utc)
        close = float(event.get("c", 0.0))
        high = float(event.get("h", close))
        low = float(event.get("l", close))
        vol = float(event.get("v", 0.0))
        from app.providers.base import Bar

        bar = Bar(symbol=symbol, ts=ts, open=float(event.get("o", close)), high=high, low=low, close=close, volume=vol, vwap=float(event.get("vw", close)))
        state.minute_bars.append(bar)
        state.last_price = close
        state.intraday_high = high if state.intraday_high is None else max(state.intraday_high, high)
        state.intraday_low = low if state.intraday_low is None else min(state.intraday_low, low)
        state.cumulative_volume += vol
        self.last_bar_ts[symbol] = ts

    async def _backfill_after_reconnect(self) -> None:
        now = datetime.now(tz=timezone.utc)
        for symbol in self.symbols:
            start = self.last_bar_ts.get(symbol, now - timedelta(minutes=30))
            bars = self.provider.get_historical_bars(symbol, "1m", start, now)
            if not bars:
                continue
            state = self.store.get_or_create(symbol)
            known = {b.ts for b in state.minute_bars}
            for bar in bars:
                if bar.ts in known:
                    continue
                state.minute_bars.append(bar)
                state.last_price = bar.close
                state.intraday_high = bar.high if state.intraday_high is None else max(state.intraday_high, bar.high)
                state.intraday_low = bar.low if state.intraday_low is None else min(state.intraday_low, bar.low)
                state.cumulative_volume += bar.volume
                self.last_bar_ts[symbol] = bar.ts

    async def run(self) -> None:
        async def callback(event):
            await self._on_minute_bar(event)

        async def runner():
            await self.provider.stream_minute_bars(self.symbols, callback)

        # provider stream handles reconnect; we periodically run scans and backfill.
        task = asyncio.create_task(runner())
        try:
            while True:
                await asyncio.sleep(60)
                if self._reconnected:
                    await self._backfill_after_reconnect()
                    self._reconnected = False
        finally:
            task.cancel()


def evaluate_symbol(state, now: datetime, pools: dict[str, list[float]], regime: str) -> tuple[object | None, float | None, list[str]]:
    signal = detect_orb(state, now.strftime("%H:%M")) or detect_vwap_reclaim(state, [b.close for b in state.minute_bars], now.strftime("%H:%M")) or detect_hod_breakout(state, now.strftime("%H:%M"))
    if not signal:
        return None, None, ["no_setup"]
    risk_pct = abs(signal.entry_high - signal.stop) / signal.entry_high * 100
    fr = hard_filter(state, state.last_price or 0, 50_000_000, 0.15, 1.5, 2.5, 1.2, risk_pct)
    if not fr.passed:
        return None, None, fr.reasons
    score = compute_ias(signal.setup_score, state.rs_vs_benchmark_15m or 0, state.rs_vs_sector_15m or 0, state.rvol or 0, state.atr20_pct or 0, state.spread_pct or 0.2, 3_000_000, regime, signal.side, 80, pools)
    return signal, score, []
