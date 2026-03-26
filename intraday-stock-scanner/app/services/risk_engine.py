from __future__ import annotations

from dataclasses import dataclass

from app.services.indicator_engine import EPS


@dataclass
class RiskConfig:
    max_risk_usd: float = 12.0
    target1_r: float = 2.0
    target2_r: float = 3.0


@dataclass
class RiskResult:
    entry: float | None
    stop0: float | None
    r_t: float | None
    target1: float | None
    target2: float | None
    suggested_size: int


def compute_risk(
    high_t: float | None,
    l_lv3: float | None,
    sma20_t: float | None,
    atr14_t: float | None,
    cfg: RiskConfig,
) -> RiskResult:
    if high_t is None or l_lv3 is None or sma20_t is None or atr14_t is None:
        return RiskResult(None, None, None, None, None, 0)

    entry = high_t + 0.05 * atr14_t
    stop0 = min(l_lv3 - 0.20 * atr14_t, sma20_t - 0.50 * atr14_t)
    r_t = entry - stop0
    if r_t <= EPS:
        return RiskResult(entry, stop0, None, None, None, 0)
    size = int(cfg.max_risk_usd // r_t)
    t1 = entry + cfg.target1_r * r_t
    t2 = entry + cfg.target2_r * r_t
    return RiskResult(entry, stop0, r_t, t1, t2, max(0, size))
