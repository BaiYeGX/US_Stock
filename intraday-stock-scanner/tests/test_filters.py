from app.scoring.filters import hard_filter


def test_filter_reject_spread(trend_state):
    trend_state.spread_pct = 0.2
    result = hard_filter(trend_state, 100, 50_000_000, 0.15, 1.5, 2.5, 1.2, 0.5)
    assert not result.passed
    assert "spread_too_wide" in result.reasons
