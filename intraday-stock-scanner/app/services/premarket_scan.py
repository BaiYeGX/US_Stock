from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.market.universe import filter_universe
from app.scoring.premarket_score import compute_pms


def _safe_percentile_pools(rows: list[dict]) -> dict[str, list[float]]:
    return {
        "gap": [r["gap_pct"] for r in rows],
        "pm_dollar_vol": [r["pm_dollar_vol"] for r in rows],
        "atr": [r["atr"] for r in rows],
        "prev_day_trend": [r["trend"] for r in rows],
    }


def run_premarket_scan(provider, repo, settings, scan_date: date) -> list[dict]:
    metadata = filter_universe(provider.get_universe_metadata(), settings.universe.include_etf)
    rows: list[dict] = []

    end = datetime.combine(scan_date, datetime.min.time(), tzinfo=timezone.utc)
    start = end - timedelta(days=45)

    for idx, asset in enumerate(metadata[: max(settings.universe.watchlist_size * 2, 30)]):
        bars = provider.get_historical_bars(asset.symbol, "1d", start, end)
        if len(bars) >= 2:
            prev_close = bars[-2].close
            last_close = bars[-1].close
            gap = ((last_close - prev_close) / prev_close) * 100 if prev_close else 0.0
            pm_dollar_vol = last_close * bars[-1].volume
            atr_like = ((bars[-1].high - bars[-1].low) / last_close) * 100 if last_close else 0.0
            trend = ((last_close - bars[-5].close) / bars[-5].close) * 100 if len(bars) >= 5 and bars[-5].close else 0.0
        else:
            # deterministic fallback for mock/no-data mode
            gap = 1.0 + idx * 0.02
            pm_dollar_vol = 1_000_000 + idx * 100_000
            atr_like = 2.5 + (idx % 10) * 0.2
            trend = 50 + idx

        rows.append(
            {
                "symbol": asset.symbol,
                "gap_pct": gap,
                "pm_dollar_vol": pm_dollar_vol,
                "atr": atr_like,
                "trend": trend,
            }
        )

    pools = _safe_percentile_pools(rows)
    scored = []
    for r in rows:
        pms = compute_pms(r["gap_pct"], r["pm_dollar_vol"], r["atr"], r["trend"], 20, pools)
        scored.append({**r, "pms_score": pms})

    scored.sort(key=lambda x: x["pms_score"], reverse=True)
    selected = scored[: settings.universe.watchlist_size]
    payload = []
    for rank, row in enumerate(selected, start=1):
        payload.append(
            {
                "symbol": row["symbol"],
                "pms_score": row["pms_score"],
                "pms_rank": rank,
                "gap_pct": row["gap_pct"],
                "pm_dollar_vol": row["pm_dollar_vol"],
                "catalyst_score": 20.0,
                "selected_flag": True,
            }
        )
    repo.save_watchlist(scan_date, payload)
    return payload
