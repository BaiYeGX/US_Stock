from __future__ import annotations

import json
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from app.ui.server import query_latest_alerts, query_today_watchlist


def make_handler(db_path: str):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, content_type: str = "text/plain; charset=utf-8") -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            if parsed.path == "/health":
                self._send(200, b'{"ok": true}', "application/json; charset=utf-8")
                return
            if parsed.path == "/api/alerts/latest":
                limit = int(qs.get("limit", ["20"])[0])
                data = query_latest_alerts(db_path, limit)
                self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                return
            if parsed.path == "/api/watchlist":
                scan_date = qs.get("scan_date", [date.today().isoformat()])[0]
                data = query_today_watchlist(db_path, scan_date)
                self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                return
            if parsed.path == "/":
                scan_date = qs.get("scan_date", [date.today().isoformat()])[0]
                alerts = query_latest_alerts(db_path, 20)
                watchlist = query_today_watchlist(db_path, scan_date)
                rows_alert = "".join(
                    f"<tr><td>{a['ts']}</td><td>{a['symbol']}</td><td>{a['setup']}</td><td>{a['grade']}</td><td>{a['score']}</td><td>{a['entry_low']}~{a['entry_high']}</td><td>{a['stop']}</td><td>{a['tp1']}/{a['tp2']}</td><td>{a['reason']}</td></tr>"
                    for a in alerts
                )
                rows_watch = "".join(
                    f"<tr><td>{w['pms_rank']}</td><td>{w['symbol']}</td><td>{round(w['pms_score'],2)}</td><td>{w['gap_pct']}</td><td>{int(w['pm_dollar_vol'])}</td></tr>"
                    for w in watchlist
                )
                html = f"""
                <html><head><meta charset='utf-8'><title>Intraday Scanner (Simple)</title>
                <style>body {{ font-family: Arial; margin: 24px; }} table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }} td,th {{ border: 1px solid #ddd; padding: 6px; font-size: 12px; }} th {{ background: #f4f4f4; }}</style>
                </head><body>
                <h2>Intraday Stock Scanner Dashboard (Simple Server)</h2>
                <p>Scan date: {scan_date}</p>
                <h3>Latest Alerts</h3>
                <table><tr><th>TS</th><th>Symbol</th><th>Setup</th><th>Grade</th><th>Score</th><th>Entry</th><th>Stop</th><th>TP</th><th>Reason</th></tr>{rows_alert}</table>
                <h3>Watchlist</h3>
                <table><tr><th>Rank</th><th>Symbol</th><th>PMS</th><th>Gap%</th><th>PM$Vol</th></tr>{rows_watch}</table>
                </body></html>
                """
                self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
                return
            self._send(404, b"not found")

    return Handler


def run_simple_ui_server(db_path: str, host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(db_path))
    print(f"simple ui serving at http://{host}:{port}")
    server.serve_forever()
