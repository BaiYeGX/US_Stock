from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import ast
import os


@dataclass
class AppSettings:
    timezone: str = "America/New_York"
    benchmark_symbols: list[str] = field(default_factory=lambda: ["SPY", "QQQ"])
    sector_etf_map: dict[str, str] = field(default_factory=dict)
    market_hours: dict[str, str] = field(default_factory=lambda: {"open": "09:30", "close": "16:00"})


@dataclass
class ProviderSettings:
    name: str = "finnhub"
    rest_base_url: str = ""
    ws_base_url: str = ""
    api_key_env: str = "FINNHUB_API_KEY"
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


def _parse_scalar(raw: str) -> Any:
    text = raw.strip()
    if text == "":
        return ""
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    # strip simple quoted strings first
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    # numeric
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        pass
    # inline list/dict
    if text.startswith("[") or text.startswith("{"):
        try:
            return ast.literal_eval(text)
        except Exception:
            return text
    return text


def _simple_yaml_load(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip("\n")
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        content = line.strip()

        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()

        parent = stack[-1][1]

        if content.startswith("- "):
            item = _parse_scalar(content[2:])
            if isinstance(parent, list):
                parent.append(item)
            continue

        if ":" not in content:
            continue

        key, value = content.split(":", 1)
        key = key.strip()
        value = value.strip()

        if value == "":
            # nested mapping by default
            next_container: Any = {}
            if isinstance(parent, dict):
                parent[key] = next_container
            stack.append((indent, next_container))
        else:
            parsed = _parse_scalar(value)
            if isinstance(parent, dict):
                parent[key] = parsed

    return root


def _load_yaml(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    data = _simple_yaml_load(p.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings(path: str = "config/default.yaml") -> ScannerSettings:
    raw = _load_yaml(path)
    env_provider = os.getenv("SCANNER_PROVIDER", "").strip().lower()
    if env_provider:
        raw = _merge(raw, {"provider": {"name": env_provider}})

    app_raw = raw.get("app", {})
    provider_raw = raw.get("provider", {})
    universe_raw = raw.get("universe", {})
    filters_raw = raw.get("filters", {})

    default = ScannerSettings()
    return ScannerSettings(
        app=AppSettings(**{**default.app.__dict__, **app_raw}),
        provider=ProviderSettings(**{**default.provider.__dict__, **provider_raw}),
        universe=UniverseSettings(**{**default.universe.__dict__, **universe_raw}),
        filters=FilterSettings(**{**default.filters.__dict__, **filters_raw}),
        regime={**default.regime, **raw.get("regime", {})},
        setups=raw.get("setups", {}) or {},
        scoring=raw.get("scoring", {}) or {},
        alerts={**default.alerts, **(raw.get("alerts", {}) or {})},
        journal={**default.journal, **(raw.get("journal", {}) or {})},
    )
