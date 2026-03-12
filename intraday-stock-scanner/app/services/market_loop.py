from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.constants import BENCHMARK_MAP
from app.scoring.filters import hard_filter
from app.scoring.intraday_score import compute_ias
from app.services.alert_engine import AlertEngine
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
        self.alert_engine = AlertEngine(cooldown_minutes=5)

    def _refresh_state_features(self, symbol: str) -> None:
        state = self.store.get_or_create(symbol)
        bars = list(state.minute_bars)
        if not bars:
            return

        # open range from first 5 completed minute bars
        if len(bars) >= 5 and state.open_range_high is None:
            first = bars[:5]
            state.open_range_high = max(b.high for b in first)
            state.open_range_low = min(b.low for b in first)

        # session vwap
        total_vol = sum(b.volume for b in bars)
        if total_vol > 0:
            state.vwap_session = sum(b.close * b.volume for b in bars) / total_vol

        # spread proxy from bar range (no L1 quote in minute-bar stream)
        last = bars[-1]
        if last.close > 0:
            state.spread_pct = max(0.0, ((last.high - last.low) / last.close) * 100)

        # minute RVOL proxy: current minute volume vs recent 20 minute average
        if len(bars) >= 21:
            avg20 = sum(b.volume for b in bars[-21:-1]) / 20
            state.rvol = (last.volume / avg20) if avg20 > 0 else None

        # intraday ATR proxy in pct from latest 20 bars
        window = bars[-20:]
        if window and last.close > 0:
            avg_range = sum((b.high - b.low) for b in window) / len(window)
            state.atr20_pct = (avg_range / last.close) * 100

    def _refresh_relative_strength(self) -> None:
        # use 15m return proxy based on available minute bars; benchmark from fixed mapping
        for symbol, state in self.store.symbols.items():
            bars = list(state.minute_bars)
            if len(bars) < 16:
                continue
            symbol_ret = (bars[-1].close / bars[-16].close - 1) if bars[-16].close else 0.0
            bench_symbol = BENCHMARK_MAP.get(symbol)
            if not bench_symbol:
                continue
            bench_state = self.store.symbols.get(bench_symbol)
            if not bench_state:
                continue
            bench_bars = list(bench_state.minute_bars)
            if len(bench_bars) < 16 or bench_bars[-16].close == 0:
                continue
            bench_ret = bench_bars[-1].close / bench_bars[-16].close - 1
            state.rs_vs_benchmark_15m = symbol_ret - bench_ret
            # no sector index stream here, mirror benchmark for now
            state.rs_vs_sector_15m = state.rs_vs_benchmark_15m

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
        self._refresh_state_features(symbol)

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
            self._refresh_state_features(symbol)

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

    def _scan_and_emit_alerts(self, now_utc: datetime) -> None:
        self._refresh_relative_strength()
        pools = {
            "rs_benchmark": [],
            "rs_sector": [],
            "rvol": [],
            "atr20": [],
            "spread": [],
            "dollar5m": [],
            "room": [],
        }
        states = list(self.store.symbols.values())
        for st in states:
            pools["rs_benchmark"].append(st.rs_vs_benchmark_15m or 0.0)
            pools["rs_sector"].append(st.rs_vs_sector_15m or 0.0)
            pools["rvol"].append(st.rvol or 0.0)
            pools["atr20"].append(st.atr20_pct or 0.0)
            pools["spread"].append(st.spread_pct or 0.2)
            pools["dollar5m"].append((st.last_price or 0.0) * max(st.cumulative_volume, 1.0) / 78)
            pools["room"].append(2.0)

        for st in states:
            signal, score, reasons = evaluate_symbol(st, now_utc, pools, self.regime)
            if not signal or score is None:
                if self.repo and reasons and reasons != ["no_setup"]:
                    self.repo.save_rejection(now_utc, st.symbol, "NO_SETUP", ",".join(reasons), {"symbol": st.symbol})
                continue
            plan = self.alert_engine.try_emit(st.symbol, signal, score, now_utc)
            if plan and self.repo:
                self.repo.save_alert(plan, market_regime=self.regime)
                self._alert_count += 1

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
                self._scan_and_emit_alerts(now)
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
    score = compute_ias(
        signal.setup_score,
        state.rs_vs_benchmark_15m or 0,
        state.rs_vs_sector_15m or 0,
        state.rvol or 0,
        state.atr20_pct or 0,
        state.spread_pct or 0.2,
        ((state.last_price or 0.0) * max(state.cumulative_volume, 1.0) / 78),
        regime,
        signal.side,
        80,
        pools,
    )
    return signal, score, []
