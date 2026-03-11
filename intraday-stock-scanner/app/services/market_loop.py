from __future__ import annotations

from datetime import datetime

from app.scoring.filters import hard_filter
from app.scoring.intraday_score import compute_ias
from app.setups.hod_breakout import detect_hod_breakout
from app.setups.orb import detect_orb
from app.setups.vwap_reclaim import detect_vwap_reclaim


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
