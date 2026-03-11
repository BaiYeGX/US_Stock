from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.journal.models import Alert


def replay_alerts(session_factory, day: date) -> list[Alert]:
    with session_factory() as s:
        q = select(Alert).where(Alert.ts >= day, Alert.ts < day.fromordinal(day.toordinal() + 1))
        return list(s.scalars(q))
