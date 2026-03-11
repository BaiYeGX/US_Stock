from __future__ import annotations

from app.utils.math import percentile_rank


def market_alignment_score(regime: str, side: str, sector_aligned: bool = True) -> float:
    if regime == "choppy":
        return 50.0
    if regime == "trend_up" and side == "long" and sector_aligned:
        return 95.0
    if regime == "trend_down" and side == "short" and sector_aligned:
        return 95.0
    return 20.0


def compute_ias(setup_score: float, rs_benchmark: float, rs_sector: float, rvol: float, atr20_pct: float, spread_pct: float, current_5m_dollar_vol: float, regime: str, side: str, room_score: float, pools: dict[str, list[float]]) -> float:
    rs_score = 0.7 * percentile_rank(rs_benchmark, pools["rs_benchmark"]) + 0.3 * percentile_rank(rs_sector, pools["rs_sector"])
    activity = 0.7 * percentile_rank(rvol, pools["rvol"]) + 0.3 * percentile_rank(atr20_pct, pools["atr20"])
    liquidity = 0.6 * (100 - percentile_rank(spread_pct, pools["spread"])) + 0.4 * percentile_rank(current_5m_dollar_vol, pools["dollar5m"])
    align = market_alignment_score(regime, side)
    return 0.25 * setup_score + 0.20 * rs_score + 0.20 * activity + 0.15 * liquidity + 0.10 * align + 0.10 * room_score
