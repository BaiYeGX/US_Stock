from __future__ import annotations

from datetime import date, timedelta


def replay_alerts(session_factory, day: date) -> list[dict]:
    start = day.isoformat()
    end = (day + timedelta(days=1)).isoformat()
    with session_factory() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, ts, symbol, side, setup, score, grade, entry_low, entry_high, stop, tp1, tp2, reason
            FROM alerts WHERE ts >= ? AND ts < ? ORDER BY ts ASC""",
            (start, end),
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
