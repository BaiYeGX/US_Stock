from __future__ import annotations

from datetime import date

from app.journal.reports import make_daily_report


def run_review(session_factory, day: date) -> dict:
    with session_factory() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM alerts WHERE ts >= ? AND ts < ?", (day.isoformat(), day.fromordinal(day.toordinal() + 1).isoformat()))
        total = cur.fetchone()[0]
    summary = {"total_alerts": total, "hit_tp1_rate": 0.0, "hit_tp2_rate": 0.0, "stop_first_rate": 0.0}
    summary["markdown"] = make_daily_report(summary)
    return summary
