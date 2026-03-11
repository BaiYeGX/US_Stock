from __future__ import annotations

import os
import sqlite3
from datetime import date


def query_latest_alerts(db_path: str, limit: int = 20) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT ts,symbol,side,setup,score,grade,entry_low,entry_high,stop,tp1,tp2,reason FROM alerts ORDER BY ts DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def query_today_watchlist(db_path: str, scan_date: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT symbol,pms_score,pms_rank,gap_pct,pm_dollar_vol FROM watchlist_snapshots WHERE scan_date=? ORDER BY pms_rank ASC LIMIT 200",
            (scan_date,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def create_app(db_url: str):
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("FastAPI/uvicorn not installed. Install dependencies to run UI.") from exc

    db_path = db_url.replace("sqlite:///", "")
    app = FastAPI(title="Intraday Stock Scanner UI")

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/api/alerts/latest")
    def api_latest_alerts(limit: int = 20):
        return JSONResponse(query_latest_alerts(db_path, limit))

    @app.get("/api/watchlist")
    def api_watchlist(scan_date: str | None = None):
        d = scan_date or date.today().isoformat()
        return JSONResponse(query_today_watchlist(db_path, d))

    @app.get("/", response_class=HTMLResponse)
    def index(scan_date: str | None = None):
        d = scan_date or date.today().isoformat()
        alerts = query_latest_alerts(db_path, 20)
        watchlist = query_today_watchlist(db_path, d)
        rows_alert = "".join(
            f"<tr><td>{a['ts']}</td><td>{a['symbol']}</td><td>{a['setup']}</td><td>{a['grade']}</td><td>{a['score']}</td><td>{a['entry_low']}~{a['entry_high']}</td><td>{a['stop']}</td><td>{a['tp1']}/{a['tp2']}</td><td>{a['reason']}</td></tr>"
            for a in alerts
        )
        rows_watch = "".join(
            f"<tr><td>{w['pms_rank']}</td><td>{w['symbol']}</td><td>{round(w['pms_score'],2)}</td><td>{w['gap_pct']}</td><td>{int(w['pm_dollar_vol'])}</td></tr>"
            for w in watchlist
        )
        return HTMLResponse(
            f"""
            <html><head><meta charset='utf-8'><title>Intraday Scanner</title>
            <style>
            body {{ font-family: Arial; margin: 24px; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
            td,th {{ border: 1px solid #ddd; padding: 6px; font-size: 12px; }}
            th {{ background: #f4f4f4; }}
            .grid {{ display: grid; grid-template-columns: 1fr; gap: 20px; }}
            </style></head><body>
            <h2>Intraday Stock Scanner Dashboard</h2>
            <p>Scan date: {d}</p>
            <div class='grid'>
            <section><h3>Latest Alerts</h3><table><tr><th>TS</th><th>Symbol</th><th>Setup</th><th>Grade</th><th>Score</th><th>Entry</th><th>Stop</th><th>TP</th><th>Reason</th></tr>{rows_alert}</table></section>
            <section><h3>Watchlist</h3><table><tr><th>Rank</th><th>Symbol</th><th>PMS</th><th>Gap%</th><th>PM$Vol</th></tr>{rows_watch}</table></section>
            </div>
            </body></html>
            """
        )

    return app
