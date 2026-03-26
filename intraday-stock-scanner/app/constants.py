from __future__ import annotations

FIXED_SYMBOL_POOL: list[str] = [
    "NVDA",
    "AMD",
    "QQQ",
    "SMH",
    "AVGO",
    "TSM",
    "AMZN",
    "META",
    "MSFT",
    "GOOGL",
    "SPY",
    "SOXX",
]

BENCHMARK_MAP: dict[str, str] = {
    "NVDA": "SMH",
    "AMD": "SMH",
    "AVGO": "SMH",
    "TSM": "SMH",
    "SMH": "SMH",
    "SOXX": "SMH",
    "AMZN": "QQQ",
    "META": "QQQ",
    "MSFT": "QQQ",
    "GOOGL": "QQQ",
    "QQQ": "QQQ",
    "SPY": "SPY",
}

UNIQUE_SYMBOLS: list[str] = sorted(set(FIXED_SYMBOL_POOL))
