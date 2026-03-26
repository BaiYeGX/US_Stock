from __future__ import annotations

from app.utils.enums import Regime


def classify_regime(price: float, vwap: float, net_ret_30m: float, higher_highs: bool, higher_lows: bool) -> str:
    if price > vwap and net_ret_30m > 0.2 and higher_highs and higher_lows:
        return Regime.TREND_UP.value
    if price < vwap and net_ret_30m < -0.2 and (not higher_highs) and (not higher_lows):
        return Regime.TREND_DOWN.value
    return Regime.CHOPPY.value
