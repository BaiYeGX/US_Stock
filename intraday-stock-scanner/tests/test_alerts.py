from datetime import datetime

from app.alerts.planner import build_plan
from app.setups.base import SetupSignal


def test_alert_plan():
    sig = SetupSignal(setup="ORB", side="long", setup_score=80, entry_low=100, entry_high=100.2, stop=99.8, tp1=100.6, tp2=101.0, invalidate_if="x", reason="y", metrics={})
    plan = build_plan("NVDA", sig, 85, datetime.now())
    assert plan is not None
    assert plan.grade == "A"
