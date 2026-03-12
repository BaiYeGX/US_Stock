from datetime import datetime, timedelta, timezone

from app.providers.base import Bar
from app.services.risk_engine import RiskConfig, compute_risk
from app.services.score_engine import ScoreConfig, compute_symbol_score


def _trend_bars(symbol: str, n: int = 80) -> list[Bar]:
    arr = []
    p = 100.0
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        o = p
        c = o + 0.6
        h = c + 0.5
        l = o - 0.3
        arr.append(Bar(symbol=symbol, ts=t0 + timedelta(days=i), open=o, high=h, low=l, close=c, volume=8_000_000 + i * 50_000))
        p = c
    return arr


def test_compute_risk():
    r = compute_risk(110, 105, 107, 2.0, RiskConfig(max_risk_usd=12, target1_r=2, target2_r=3))
    assert round(r.entry, 2) == 110.1
    assert round(r.stop0, 2) == 104.6
    assert round(r.r_t, 2) == 5.5
    assert r.suggested_size == 2


def test_buy_eligible_false_when_earnings_missing_and_action_unheld_only_candidate():
    daily = _trend_bars("NVDA")
    bench = _trend_bars("SMH")
    row = compute_symbol_score(
        symbol="NVDA",
        daily=daily,
        benchmark_daily=bench,
        benchmark_weekly=bench,
        days_to_earnings=None,
        is_held=False,
        position=None,
        cfg=ScoreConfig(),
    )
    assert row["BuyEligible"] is False
    assert row["CandidateAction"] == "NO_BUY"
    assert row["PositionAction"] == ""


def test_held_symbol_prioritizes_position_action():
    daily = _trend_bars("NVDA")
    bench = _trend_bars("SMH")
    pos = {
        "isHeld": True,
        "EntryFilled": 120.0,
        "EntryDate": "2026-01-10",
        "HeldPositionSizeShares": 10,
        "R_init": 2.0,
        "HighestCloseSinceEntry": 122.0,
        "TrailStop_t": 200.0,  # force close below trail stop
        "HoldingDays": 2,
    }
    row = compute_symbol_score(
        symbol="NVDA",
        daily=daily,
        benchmark_daily=bench,
        benchmark_weekly=bench,
        days_to_earnings=10,
        is_held=True,
        position=pos,
        cfg=ScoreConfig(),
    )
    assert row["PositionAction"] == "MUST_SELL"
    assert row["Action"] == "MUST_SELL"
