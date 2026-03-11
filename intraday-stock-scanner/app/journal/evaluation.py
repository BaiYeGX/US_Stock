from __future__ import annotations


def evaluate_outcome(entry: float, stop: float, tp1: float, tp2: float, future_prices: list[float]) -> dict:
    hit_tp1 = hit_tp2 = hit_sl = False
    for p in future_prices:
        if p <= stop:
            hit_sl = True
            break
        if p >= tp2:
            hit_tp2 = True
            break
        if p >= tp1:
            hit_tp1 = True
    mfe = max(future_prices) - entry if future_prices else 0
    mae = min(future_prices) - entry if future_prices else 0
    return {"hit_tp1_first": hit_tp1, "hit_tp2_first": hit_tp2, "hit_sl_first": hit_sl, "mfe_pct": (mfe / entry) * 100 if entry else 0, "mae_pct": (mae / entry) * 100 if entry else 0}
