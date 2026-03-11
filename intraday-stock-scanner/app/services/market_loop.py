from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.scoring.filters import hard_filter
from app.scoring.intraday_score import compute_ias
from app.setups.hod_breakout import detect_hod_breakout
from app.setups.orb import detect_orb
from app.setups.vwap_reclaim import detect_vwap_reclaim
from app.state.state_store import StateStore

NY_TZ = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


def _minutes_from_open(ts_et: datetime) -> int:
    current = ts_et.hour * 60 + ts_et.minute
    open_min = MARKET_OPEN.hour * 60 + MARKET_OPEN.minute
    return current - open_min


def half_hour_slot_index(ts_et: datetime) -> int | None:
    """Return slot index from open(0) every 30m until close(13)."""
    t = ts_et.timetz().replace(tzinfo=None)
    if t < MARKET_OPEN or t > MARKET_CLOSE:
        return None
    minutes = _minutes_from_open(ts_et)
    idx = minutes // 30
    return max(0, min(13, idx))


def slot_time_label(slot_index: int) -> str:
    minutes = slot_index * 30
    base = datetime(2000, 1, 1, MARKET_OPEN.hour, MARKET_OPEN.minute)
    return (base + timedelta(minutes=minutes)).strftime("%H:%M")


class RealtimeMarketLoop:
    """Realtime loop: streaming minute bars + reconnect backfill + setup scan + 30m snapshots."""

    def __init__(self, provider, symbols: list[str], repo=None) -> None:
        self.provider = provider
        self.symbols = symbols
        self.repo = repo
        self.store = StateStore()
        self.last_bar_ts: dict[str, datetime] = {}
        self.regime = "choppy"
        self._reconnected = False
        self._recorded_slots: set[tuple[str, int]] = set()
        self._alert_count = 0

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

    def _record_interval_snapshot(self, now_utc: datetime) -> None:
        if not self.repo:
            return
        now_et = now_utc.astimezone(NY_TZ)
        slot = half_hour_slot_index(now_et)
        if slot is None:
            return
        trade_date = now_et.date().isoformat()
        key = (trade_date, slot)
        if key in self._recorded_slots:
            return

        states = list(self.store.symbols.values())
        symbol_count = len(states)
        active = [s for s in states if s.last_price is not None]
        active_symbol_count = len(active)
        avg_last_price = round(sum(s.last_price or 0 for s in active) / active_symbol_count, 4) if active_symbol_count else 0.0
        ranked = sorted(active, key=lambda s: s.cumulative_volume, reverse=True)
        top_symbols = [s.symbol for s in ranked[:5]]
        payload = {
            "market_regime": self.regime,
            "symbols": [s.symbol for s in states],
            "top_by_volume": top_symbols,
            "captured_at_et": now_et.isoformat(),
        }
        self.repo.save_interval_snapshot(
            trade_date=trade_date,
            slot_index=slot,
            slot_time=slot_time_label(slot),
            generated_at=now_utc.isoformat(),
            symbol_count=symbol_count,
            active_symbol_count=active_symbol_count,
            top_symbols=top_symbols,
            avg_last_price=avg_last_price,
            alert_count=self._alert_count,
            payload=payload,
        )
        self._recorded_slots.add(key)

    async def run(self) -> None:
        async def callback(event):
            await self._on_minute_bar(event)

        async def runner():
            await self.provider.stream_minute_bars(self.symbols, callback)

        task = asyncio.create_task(runner())
        try:
            while True:
                now = datetime.now(tz=timezone.utc)
                self._record_interval_snapshot(now)
                if self._reconnected:
                    await self._backfill_after_reconnect()
                    self._reconnected = False
                await asyncio.sleep(30)
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
