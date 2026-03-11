from __future__ import annotations

from datetime import date

from app.market.universe import filter_universe
from app.scoring.premarket_score import compute_pms


def run_premarket_scan(provider, repo, settings, scan_date: date) -> list[dict]:
    metadata = filter_universe(provider.get_universe_metadata(), settings.universe.include_etf)
    pools = {"gap": [], "pm_dollar_vol": [], "atr": [], "prev_day_trend": []}
    rows: list[dict] = []
    for idx, asset in enumerate(metadata[: max(settings.universe.watchlist_size * 2, 30)]):
        gap = 1.0 + idx * 0.02
        pm_dollar_vol = 1_000_000 + idx * 100_000
        atr = 2.5 + (idx % 10) * 0.2
        trend = 50 + idx
        pools["gap"].append(gap)
        pools["pm_dollar_vol"].append(pm_dollar_vol)
        pools["atr"].append(atr)
        pools["prev_day_trend"].append(trend)
        rows.append({"symbol": asset.symbol, "gap_pct": gap, "pm_dollar_vol": pm_dollar_vol, "atr": atr, "trend": trend})
    scored = []
    for r in rows:
        pms = compute_pms(r["gap_pct"], r["pm_dollar_vol"], r["atr"], r["trend"], 20, pools)
        scored.append({**r, "pms_score": pms})
    scored.sort(key=lambda x: x["pms_score"], reverse=True)
    selected = scored[: settings.universe.watchlist_size]
    payload = []
    for rank, row in enumerate(selected, start=1):
        payload.append({"symbol": row["symbol"], "pms_score": row["pms_score"], "pms_rank": rank, "gap_pct": row["gap_pct"], "pm_dollar_vol": row["pm_dollar_vol"], "catalyst_score": 20.0, "selected_flag": True})
    repo.save_watchlist(scan_date, payload)
    return payload
