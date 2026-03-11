from __future__ import annotations

import json
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from app.data.provider_service import MarketDataService
from app.ui.server import _render_html, query_interval_snapshots, query_latest_alerts, query_today_watchlist

_DATA_SERVICE = MarketDataService()


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
            if parsed.path == "/api/interval-snapshots":
                scan_date = qs.get("scan_date", [date.today().isoformat()])[0]
                data = query_interval_snapshots(db_path, scan_date)
                self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                return
            if parsed.path == "/api/data/health":
                source = qs.get("source", ["finnhub"])[0]
                api_key = qs.get("api_key", [""])[0]
                if not api_key:
                    self._send(400, b'{"ok":false,"detail":"\u7f3a\u5c11 API \u5bc6\u94a5"}', "application/json; charset=utf-8")
                    return
                data = _DATA_SERVICE.health_check(source=source, api_key=api_key)
                self._send(200 if data.get("ok") else 400, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                return
            if parsed.path == "/api/data/quotes":
                source = qs.get("source", ["finnhub"])[0]
                api_key = qs.get("api_key", [""])[0]
                symbols = qs.get("symbols", [""])[0]
                pool = []
                for s in [x.strip().upper() for x in symbols.split(",") if x.strip()]:
                    if s not in pool and len(s) <= 10 and s.replace(".", "").replace("-", "").isalnum():
                        pool.append(s)
                pool = pool[:200]
                if not api_key:
                    self._send(400, b'{"ok":false,"detail":"\u7f3a\u5c11 API \u5bc6\u94a5"}', "application/json; charset=utf-8")
                    return
                try:
                    items = []
                    for symbol in pool:
                        q = _DATA_SERVICE.get_quote(source=source, api_key=api_key, symbol=symbol, ttl=30)
                        items.append({"symbol": symbol, "price": round(float(q.get("c", 0.0)), 4), "change_pct": round(float(q.get("dp", 0.0)), 3)})
                    payload = {"ok": True, "items": items, "updated_at": time.time()}
                    self._send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                except Exception as exc:
                    self._send(400, json.dumps({"ok": False, "detail": str(exc)}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                return
            if parsed.path == "/api/data/news":
                source = qs.get("source", ["finnhub"])[0]
                api_key = qs.get("api_key", [""])[0]
                symbol = qs.get("symbol", [""])[0]
                if not api_key:
                    self._send(400, b'{"ok":false,"detail":"\u7f3a\u5c11 API \u5bc6\u94a5"}', "application/json; charset=utf-8")
                    return
                try:
                    items = _DATA_SERVICE.get_news(source=source, api_key=api_key, symbol=(symbol or None), ttl=120)
                    self._send(200, json.dumps({"ok": True, "items": items}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                except Exception as exc:
                    self._send(400, json.dumps({"ok": False, "detail": str(exc)}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                return
            if parsed.path == "/":
                scan_date = qs.get("scan_date", [date.today().isoformat()])[0]
                alerts = query_latest_alerts(db_path, 20)
                watchlist = query_today_watchlist(db_path, scan_date)
                intervals = query_interval_snapshots(db_path, scan_date)
                self._send(200, _render_html(scan_date, alerts, watchlist, intervals).encode("utf-8"), "text/html; charset=utf-8")
                return
            self._send(404, b"not found")

    return Handler


def run_simple_ui_server(db_path: str, host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(db_path))
    print(f"simple ui serving at http://{host}:{port}")
    server.serve_forever()
