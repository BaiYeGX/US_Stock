from __future__ import annotations

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


def query_interval_snapshots(db_path: str, trade_date: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT slot_index,slot_time,generated_at,symbol_count,active_symbol_count,avg_last_price,alert_count,top_symbols_json FROM interval_snapshots WHERE trade_date=? ORDER BY slot_index ASC LIMIT 50",
            (trade_date,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        import json
        for row in rows:
            raw = row.get("top_symbols_json", "[]")
            try:
                row["top_symbols"] = ", ".join(json.loads(raw))
            except Exception:
                row["top_symbols"] = raw
        return rows
    finally:
        conn.close()


def _render_html(scan_date: str, alerts: list[dict], watchlist: list[dict], intervals: list[dict]) -> str:
    rows_alert = "".join(
        f"<tr><td>{a['ts']}</td><td>{a['symbol']}</td><td>{a['setup']}</td><td>{a['grade']}</td><td>{a['score']}</td><td>{a['entry_low']} ~ {a['entry_high']}</td><td>{a['stop']}</td><td>{a['tp1']} / {a['tp2']}</td><td>{a['reason']}</td></tr>"
        for a in alerts
    )
    rows_watch = "".join(
        f"<tr><td>{w['pms_rank']}</td><td>{w['symbol']}</td><td>{round(w['pms_score'],2)}</td><td>{w['gap_pct']}</td><td>{int(w['pm_dollar_vol'])}</td></tr>"
        for w in watchlist
    )
    rows_intervals = "".join(
        f"<tr><td>{r['slot_index']}</td><td>{r['slot_time']}</td><td>{r['generated_at']}</td><td>{r['symbol_count']}</td><td>{r['active_symbol_count']}</td><td>{r['avg_last_price']}</td><td>{r['alert_count']}</td><td>{r.get('top_symbols','[]')}</td></tr>"
        for r in intervals
    )
    return f"""
    <html><head><meta charset='utf-8'><title>Intraday Scanner</title>
    <style>
      :root {{ --bg:#0b1220; --card:#121a2b; --muted:#8ea3c0; --text:#ecf2ff; --accent:#4f8cff; --line:#2a3650; }}
      body {{ margin:0; font-family: Inter,Segoe UI,Arial; background:linear-gradient(135deg,#0a1020,#0c1a35); color:var(--text); }}
      .wrap {{ max-width: 1440px; margin: 0 auto; padding: 24px; }}
      h1 {{ margin: 0 0 8px 0; font-size: 30px; }}
      .sub {{ color: var(--muted); margin-bottom: 16px; }}
      .cards {{ display:grid; grid-template-columns: repeat(3,1fr); gap:12px; margin-bottom:16px; }}
      .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px; }}
      .k {{ color:var(--muted); font-size:12px; }}
      .v {{ font-size:22px; font-weight:700; margin-top:6px; }}
      .sec {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px; margin-top:14px; }}
      table {{ width:100%; border-collapse: collapse; }}
      th,td {{ border-bottom:1px solid var(--line); padding:8px; font-size:12px; }}
      th {{ color:#bcd0ef; text-align:left; position:sticky; top:0; background:var(--card); }}
    </style></head>
    <body><div class='wrap'>
      <h1>Intraday Stock Scanner Dashboard</h1>
      <div class='sub'>Scan date: {scan_date}</div>
      <div class='cards'>
        <div class='card'><div class='k'>Watchlist Size</div><div class='v'>{len(watchlist)}</div></div>
        <div class='card'><div class='k'>Latest Alerts</div><div class='v'>{len(alerts)}</div></div>
        <div class='card'><div class='k'>30m Snapshots</div><div class='v'>{len(intervals)}</div></div>
      </div>
      <div class='sec'><h3>Latest Alerts</h3><table><tr><th>TS</th><th>Symbol</th><th>Setup</th><th>Grade</th><th>Score</th><th>Entry</th><th>Stop</th><th>TP</th><th>Reason</th></tr>{rows_alert}</table></div>
      <div class='sec'><h3>Watchlist</h3><table><tr><th>Rank</th><th>Symbol</th><th>PMS</th><th>Gap%</th><th>PM$Vol</th></tr>{rows_watch}</table></div>
      <div class='sec'><h3>30-Min Generated Snapshots (09:30 ~ 16:00)</h3><table><tr><th>Slot#</th><th>Slot Time</th><th>Generated At</th><th>Symbols</th><th>Active</th><th>Avg Last Px</th><th>Alerts</th><th>Top Symbols</th></tr>{rows_intervals}</table></div>
    </div></body></html>
    """


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

    @app.get("/api/interval-snapshots")
    def api_interval_snapshots(scan_date: str | None = None):
        d = scan_date or date.today().isoformat()
        return JSONResponse(query_interval_snapshots(db_path, d))

    @app.get("/", response_class=HTMLResponse)
    def index(scan_date: str | None = None):
        d = scan_date or date.today().isoformat()
        alerts = query_latest_alerts(db_path, 20)
        watchlist = query_today_watchlist(db_path, d)
        intervals = query_interval_snapshots(db_path, d)
        return HTMLResponse(_render_html(d, alerts, watchlist, intervals))

    return app
