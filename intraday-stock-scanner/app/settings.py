from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppSettings:
    timezone: str = "America/New_York"
    benchmark_symbols: list[str] = field(default_factory=lambda: ["SPY", "QQQ"])
    sector_etf_map: dict[str, str] = field(default_factory=dict)
    market_hours: dict[str, str] = field(default_factory=lambda: {"open": "09:30", "close": "16:00"})


@dataclass
class ProviderSettings:
    name: str = "polygon"
    rest_base_url: str = ""
    ws_base_url: str = ""
    api_key_env: str = "POLYGON_API_KEY"
    use_adjusted: bool = True


@dataclass
class UniverseSettings:
    min_price: float = 5
    max_price: float = 250
    min_avg_dollar_volume_20d: float = 30_000_000
    min_atr20_pct: float = 2.5
    watchlist_size: int = 100
    include_etf: bool = True
    exclude_symbols: list[str] = field(default_factory=list)
    include_symbols_override: list[str] = field(default_factory=list)


@dataclass
class FilterSettings:
    max_spread_pct: float = 0.15
    min_rvol_20: float = 1.5
    require_complete_data: bool = True


@dataclass
class ScannerSettings:
    app: AppSettings = field(default_factory=AppSettings)
    provider: ProviderSettings = field(default_factory=ProviderSettings)
    universe: UniverseSettings = field(default_factory=UniverseSettings)
    filters: FilterSettings = field(default_factory=FilterSettings)
    regime: dict[str, Any] = field(default_factory=lambda: {"lookback_minutes": 30, "choppy_vwap_band_pct": 0.15})
    setups: dict[str, Any] = field(default_factory=dict)
    scoring: dict[str, Any] = field(default_factory=dict)
    alerts: dict[str, Any] = field(default_factory=lambda: {"cooldown_minutes": 5, "min_rr_tp1": 1.0, "output_text": True, "output_json": True})
    journal: dict[str, Any] = field(default_factory=lambda: {"horizons_minutes": [5, 10, 20, 30]})


def load_settings(path: str = "config/default.yaml") -> ScannerSettings:
    return ScannerSettings()
