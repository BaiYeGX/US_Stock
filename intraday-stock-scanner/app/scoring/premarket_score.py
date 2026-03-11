from __future__ import annotations

from app.utils.math import percentile_rank


def compute_pms(gap: float, pm_dollar_vol: float, atr20_pct: float, prev_day_trend: float, catalyst: float, pools: dict[str, list[float]]) -> float:
    gap_s = percentile_rank(abs(gap), [abs(v) for v in pools["gap"]])
    vol_s = percentile_rank(pm_dollar_vol, pools["pm_dollar_vol"])
    atr_s = percentile_rank(atr20_pct, pools["atr"])
    trend_s = percentile_rank(prev_day_trend, pools["prev_day_trend"])
    cat_s = max(0.0, min(100.0, catalyst))
    return 0.30 * gap_s + 0.25 * vol_s + 0.20 * atr_s + 0.15 * trend_s + 0.10 * cat_s
