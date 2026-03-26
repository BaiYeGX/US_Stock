from app.setups.orb import detect_orb


def test_orb_detect(trend_state):
    sig = detect_orb(trend_state, "10:00")
    assert sig is not None
    assert sig.setup == "ORB"
