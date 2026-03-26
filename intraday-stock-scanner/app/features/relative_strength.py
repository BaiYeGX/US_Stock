from __future__ import annotations


def relative_strength(asset_ret: float, benchmark_ret: float) -> float:
    return asset_ret - benchmark_ret
