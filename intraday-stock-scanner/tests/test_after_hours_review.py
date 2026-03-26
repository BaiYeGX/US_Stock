from __future__ import annotations

from app.services.after_hours_review_service import AfterHoursReviewService


def test_after_hours_uses_official_close(monkeypatch):
    svc = AfterHoursReviewService()
    monkeypatch.setattr(svc.data, "get_quote", lambda source, api_key, symbol, ttl=20: {"c": 102.0})

    snapshot = {
        "rows": [
            {"Symbol": "NVDA", "Entry": 90.0, "fields": {"close": 100.0}},
            {"Symbol": "AMD", "Entry": 80.0, "fields": {}},  # no official close -> skip
        ],
        "overview": {"market_status": "盘后"},
    }

    out = svc.build("finnhub", "k", snapshot)
    assert len(out["items"]) == 2
    nvda = [x for x in out["items"] if x["symbol"] == "NVDA"][0]
    assert round(nvda["afterHoursChangePctVsClose"], 2) == 2.0
