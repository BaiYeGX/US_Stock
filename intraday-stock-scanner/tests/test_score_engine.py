from datetime import datetime, timedelta, timezone

from app.providers.base import Bar
from app.services.score_engine import Center, Down, I, ScoreConfig, Up, clip100, compute_symbol_score


def _bars(symbol: str, n: int = 80, slope: float = 0.4) -> list[Bar]:
    arr = []
    p = 100.0
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        o = p
        c = o + slope
        h = c + 0.4
        l = o - 0.2
        arr.append(Bar(symbol=symbol, ts=t0 + timedelta(days=i), open=o, high=h, low=l, close=c, volume=9_000_000 + i * 30_000))
        p = c
    return arr


def test_norm_functions_and_clip100():
    assert Up(5, 0, 10) == 0.5
    assert Down(3, 0, 10) == 0.7
    assert Center(2, 2, 2) == 1
    assert I(True) == 1 and I(False) == 0
    assert clip100(120) == 100
    assert clip100(-5) == 0


def test_buy_sell_breakdown_and_room20r_mapping():
    daily = _bars("NVDA")
    bench = _bars("SMH")
    pos = {
        "isHeld": True,
        "EntryFilled": 110.0,
        "EntryDate": "2026-01-10",
        "HeldPositionSizeShares": 5,
        "R_init": 1.5,
        "HighestCloseSinceEntry": 130.0,
        "TrailStop_t": 80.0,
        "HoldingDays": 4,
    }
    row = compute_symbol_score("NVDA", daily, bench, bench, 8, True, pos, cfg=ScoreConfig())
    assert "MR" in row["buy_breakdown"]
    assert "TF" in row["buy_breakdown"]
    assert row["Risk_Reward_Ratio"] is None or row["Risk_Reward_Ratio"] <= 3.0
    assert row["fields"]["PullbackDays"] is None or isinstance(row["fields"]["PullbackDays"], int)
