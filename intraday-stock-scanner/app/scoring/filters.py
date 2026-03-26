from __future__ import annotations

from dataclasses import dataclass

from app.state.symbol_state import SymbolState


@dataclass
class FilterResult:
    passed: bool
    reasons: list[str]


def hard_filter(state: SymbolState, price: float, avg_dollar_volume_20d: float, max_spread: float, min_rvol: float, min_atr20: float, max_risk_pct: float, risk_pct: float) -> FilterResult:
    reasons: list[str] = []
    if not 5 <= price <= 250:
        reasons.append("price_out_of_range")
    if avg_dollar_volume_20d < 30_000_000:
        reasons.append("low_avg_dollar_volume")
    if state.spread_pct is None or state.spread_pct > max_spread:
        reasons.append("spread_too_wide")
    if (state.rvol or 0) < min_rvol:
        reasons.append("low_rvol")
    if (state.atr20_pct or 0) < min_atr20:
        reasons.append("low_atr20")
    if risk_pct > max_risk_pct:
        reasons.append("risk_too_large")
    return FilterResult(passed=not reasons, reasons=reasons)
