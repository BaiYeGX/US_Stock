from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.services.market_time_service import MarketTimeService
from app.settings import load_settings


def test_load_settings_from_yaml(tmp_path):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        """
provider:
  name: polygon
  rest_base_url: https://example.com
universe:
  watchlist_size: 12
filters:
  min_rvol_20: 2.0
""".strip(),
        encoding="utf-8",
    )
    s = load_settings(str(cfg))
    assert s.provider.name == "polygon"
    assert s.provider.rest_base_url == "https://example.com"
    assert s.universe.watchlist_size == 12
    assert s.filters.min_rvol_20 == 2.0


def test_latest_completed_exchange_date_weekend_fallback(monkeypatch):
    mts = MarketTimeService()
    fake_now = datetime(2026, 1, 5, 10, 0, tzinfo=ZoneInfo("America/New_York"))  # Monday pre-close
    monkeypatch.setattr(mts, "now_ny", lambda: fake_now)
    out = mts.get_latest_completed_exchange_date(payload={"market": "open"})
    assert out == date(2026, 1, 2).isoformat()  # Friday


def test_ny_close_timestamp_uses_zone_offset():
    mts = MarketTimeService()
    # July should be DST -04:00, Jan should be -05:00
    assert mts.ny_close_timestamp("2026-07-10").endswith("-04:00")
    assert mts.ny_close_timestamp("2026-01-10").endswith("-05:00")


def test_latest_completed_exchange_date_holiday_fallback(monkeypatch):
    mts = MarketTimeService()
    # 2026-01-20 Tue pre-close, previous day is MLK holiday, should fallback to 2026-01-16 Fri
    fake_now = datetime(2026, 1, 20, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    monkeypatch.setattr(mts, "now_ny", lambda: fake_now)
    out = mts.get_latest_completed_exchange_date(payload={"market": "open"})
    assert out == date(2026, 1, 16).isoformat()
