from app.market.regime import classify_regime
from app.utils.time import in_window
from datetime import datetime


def test_market_regime_choppy(choppy_regime_data):
    regime = classify_regime(**choppy_regime_data)
    assert regime == "choppy"


def test_time_window():
    ts = datetime(2026,3,11,10,0)
    assert in_window(ts, "09:30", "10:15")
