from __future__ import annotations

from app.db.migrations import create_all
from app.db.session import make_session_factory
from app.services.after_hours_review_service import AfterHoursReviewService
from app.services.close_snapshot_service import CloseSnapshotService


def _db(tmp_path):
    db_url = f"sqlite:///{tmp_path}/t.db"
    sf = make_session_factory(db_url)
    with sf() as conn:
        create_all(conn)
    return sf


def _fake_snapshot():
    return {
        "rows": [{"Symbol": "NVDA", "BuyScore": 80, "SellScore": 20, "Action": "STRONG_WATCH_BUY", "fields": {}}],
        "overview": {"market_status": "收盘"},
    }


def test_capture_not_duplicate_same_exchange_date(tmp_path):
    sf = _db(tmp_path)
    svc = CloseSnapshotService(sf)
    svc.scoreboard.build_scoreboard = lambda source, api_key: _fake_snapshot()
    svc.scoreboard.data_service._provider = lambda source, api_key: type("P", (), {"get_market_status": lambda self: {"market": "closed"}})()

    r1 = svc.capture("finnhub", "k")
    r2 = svc.capture("finnhub", "k")
    assert r1["ok"] is True
    assert r2["created"] is False


def test_after_hours_does_not_mutate_official_scores(monkeypatch):
    s = {"rows": [{"Symbol": "NVDA", "BuyScore": 88, "SellScore": 40, "Entry": 100, "fields": {}}], "overview": {"market_status": "盘后"}}
    ah = AfterHoursReviewService()
    monkeypatch.setattr(ah.data, "get_quote", lambda source, api_key, symbol, ttl=20: {"c": 101})
    out = ah.build("finnhub", "k", s)
    assert s["rows"][0]["BuyScore"] == 88
    assert s["rows"][0]["SellScore"] == 40
    assert out["items"][0]["symbol"] == "NVDA"


def test_write_file_failure_not_break_sqlite(tmp_path):
    sf = _db(tmp_path)
    svc = CloseSnapshotService(sf)
    svc.scoreboard.build_scoreboard = lambda source, api_key: _fake_snapshot()
    svc.scoreboard.data_service._provider = lambda source, api_key: type("P", (), {"get_market_status": lambda self: {"market": "closed"}})()
    svc._write_files = lambda exchange_date, payload: {"json_ok": False, "txt_ok": False, "errors": ["x"]}

    r = svc.capture("finnhub", "k", force=True)
    assert r["ok"] is True
    assert r["file_status"]["json_ok"] is False
    latest = svc.get_latest()
    assert latest is not None
    assert latest["snapshot_type"] == "official_close_snapshot"
    assert latest["score_basis"] == "official_close"


def test_market_time_shanghai_display_and_exchange_date():
    from app.services.market_time_service import MarketTimeService
    mts = MarketTimeService()
    sh = mts.now_shanghai()
    ny = mts.now_ny()
    assert "-" in mts.to_shanghai_display(sh)
    assert "-" in mts.to_newyork_display(ny)
    assert len(mts.get_exchange_date()) == 10
