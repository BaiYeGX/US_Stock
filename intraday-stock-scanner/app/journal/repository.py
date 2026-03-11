from __future__ import annotations

import json
from datetime import date

from app.alerts.schemas import AlertPlan


class JournalRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def save_watchlist(self, scan_date: date, rows: list[dict]) -> None:
        with self.session_factory() as conn:
            cur = conn.cursor()
            for row in rows:
                cur.execute(
                    """INSERT INTO watchlist_snapshots
                    (scan_date,symbol,pms_score,pms_rank,gap_pct,pm_dollar_vol,catalyst_score,selected_flag)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (scan_date.isoformat(), row["symbol"], row["pms_score"], row["pms_rank"], row["gap_pct"], row["pm_dollar_vol"], row["catalyst_score"], int(row["selected_flag"])),
                )
            conn.commit()

    def load_watchlist(self, scan_date: date) -> list[str]:
        with self.session_factory() as conn:
            cur = conn.cursor()
            cur.execute("SELECT symbol FROM watchlist_snapshots WHERE scan_date=? AND selected_flag=1", (scan_date.isoformat(),))
            return [r[0] for r in cur.fetchall()]

    def save_alert(self, plan: AlertPlan, market_regime: str | None = None) -> None:
        with self.session_factory() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO alerts (ts,symbol,side,setup,score,grade,entry_low,entry_high,stop,tp1,tp2,risk_pct,rr_tp1,rr_tp2,invalidate_if,reason,market_regime,raw_metrics_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (plan.ts.isoformat(), plan.symbol, plan.side, plan.setup, plan.score, plan.grade, plan.entry_low, plan.entry_high, plan.stop, plan.tp1, plan.tp2, plan.risk_pct, plan.rr_tp1, plan.rr_tp2, plan.invalidate_if, plan.reason, market_regime, json.dumps(plan.metrics, ensure_ascii=False)),
            )
            conn.commit()

    def save_rejection(self, ts, symbol: str, setup: str, reason: str, metrics: dict) -> None:
        with self.session_factory() as conn:
            conn.execute(
                "INSERT INTO filter_rejections (ts,symbol,setup,reason,metrics_json) VALUES (?,?,?,?,?)",
                (ts.isoformat(), symbol, setup, reason, json.dumps(metrics, ensure_ascii=False)),
            )
            conn.commit()
