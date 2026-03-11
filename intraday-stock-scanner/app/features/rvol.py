from __future__ import annotations


def rvol_20(current_volume: float, avg_volume_20: float) -> float:
    if avg_volume_20 <= 0:
        return 0.0
    return current_volume / avg_volume_20
