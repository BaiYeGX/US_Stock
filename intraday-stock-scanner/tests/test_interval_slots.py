from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.market_loop import half_hour_slot_index, slot_time_label

NY = ZoneInfo("America/New_York")


def test_half_hour_slot_index():
    assert half_hour_slot_index(datetime(2026, 3, 11, 9, 30, tzinfo=NY)) == 0
    assert half_hour_slot_index(datetime(2026, 3, 11, 10, 0, tzinfo=NY)) == 1
    assert half_hour_slot_index(datetime(2026, 3, 11, 15, 59, tzinfo=NY)) == 12
    assert half_hour_slot_index(datetime(2026, 3, 11, 16, 0, tzinfo=NY)) == 13
    assert half_hour_slot_index(datetime(2026, 3, 11, 8, 59, tzinfo=NY)) is None


def test_slot_label():
    assert slot_time_label(0) == "09:30"
    assert slot_time_label(13) == "16:00"
