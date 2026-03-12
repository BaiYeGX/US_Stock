from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.market_loop import RealtimeMarketLoop


class DummyProvider:
    async def stream_minute_bars(self, symbols, callback):
        return None


class DummyRepo:
    def __init__(self):
        self.alerts = []
        self.rejections = []

    def save_alert(self, plan, market_regime=None):
        self.alerts.append((plan, market_regime))

    def save_rejection(self, ts, symbol, setup, reason, metrics):
        self.rejections.append((symbol, reason))


def test_scan_and_emit_alerts(monkeypatch):
    repo = DummyRepo()
    loop = RealtimeMarketLoop(provider=DummyProvider(), symbols=["NVDA"], repo=repo)
    st = loop.store.get_or_create("NVDA")
    st.last_price = 100

    fake_signal = SimpleNamespace(setup="ORB")
    monkeypatch.setattr("app.services.market_loop.evaluate_symbol", lambda state, now, pools, regime: (fake_signal, 85.0, []))
    monkeypatch.setattr(loop.alert_engine, "try_emit", lambda symbol, signal, score, now: {"symbol": symbol, "score": score})

    loop._scan_and_emit_alerts(datetime.now(tz=timezone.utc))

    assert len(repo.alerts) == 1
    assert repo.alerts[0][0]["symbol"] == "NVDA"


def test_scan_records_rejection(monkeypatch):
    repo = DummyRepo()
    loop = RealtimeMarketLoop(provider=DummyProvider(), symbols=["NVDA"], repo=repo)
    st = loop.store.get_or_create("NVDA")
    st.last_price = 100

    monkeypatch.setattr("app.services.market_loop.evaluate_symbol", lambda state, now, pools, regime: (None, None, ["spread_too_wide"]))

    loop._scan_and_emit_alerts(datetime.now(tz=timezone.utc))
    assert len(repo.rejections) == 1
