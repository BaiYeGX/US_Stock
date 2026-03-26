from app.setups.hod_breakout import detect_hod_breakout


def test_hod_breakout_detect(trend_state):
    sig = detect_hod_breakout(trend_state, "10:30")
    assert sig is not None
