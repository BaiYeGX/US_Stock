from __future__ import annotations

from app.providers.base import AssetMeta


def filter_universe(meta: list[AssetMeta], include_etf: bool = True) -> list[AssetMeta]:
    out = []
    for a in meta:
        if not a.is_active:
            continue
        if a.asset_type == "stock" or (include_etf and a.asset_type == "etf"):
            out.append(a)
    return out
