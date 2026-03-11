from app.setups.vwap_reclaim import detect_vwap_reclaim


def test_vwap_reclaim_detect(trend_state):
    sig = detect_vwap_reclaim(trend_state, [100.6, 100.7], "10:30")
    assert sig is not None
