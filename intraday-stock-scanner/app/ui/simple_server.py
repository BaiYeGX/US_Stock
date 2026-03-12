from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


_SIMPLE_HTML = """<!doctype html>
<html lang='zh-CN'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>波段评分与执行监控系统</title>
  <style>
    body { font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif; background:#f3f6fb; margin:0; }
    .wrap { max-width: 860px; margin: 40px auto; padding: 20px; }
    .card { background:#fff; border:1px solid #e5e7eb; border-radius:14px; padding:18px; box-shadow:0 6px 18px rgba(15,23,42,.06); }
    h1 { margin:0 0 10px; font-size:24px; }
    p { color:#475569; line-height:1.7; }
    code { background:#f1f5f9; padding:2px 6px; border-radius:6px; }
  </style>
</head>
<body>
  <div class='wrap'>
    <div class='card'>
      <h1>简易模式已启动</h1>
      <p>当前环境未加载 FastAPI/Uvicorn，已切换到内置简易页面。</p>
      <p>如需完整中文控制台（评分、动作分解、持仓设置、数据源设置），请安装依赖后重新运行：</p>
      <p><code>pip install fastapi uvicorn</code></p>
      <p>然后执行：<code>python -m app.cli serve-ui --host 127.0.0.1 --port 8000</code></p>
    </div>
  </div>
</body>
</html>"""


def make_handler():
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, content_type: str = "text/plain; charset=utf-8") -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            if self.path.startswith("/health"):
                self._send(200, b'{"ok": true}', "application/json; charset=utf-8")
                return
            if self.path == "/" or self.path.startswith("/?"):
                self._send(200, _SIMPLE_HTML.encode("utf-8"), "text/html; charset=utf-8")
                return
            self._send(404, b"not found")

    return Handler


def run_simple_ui_server(db_path: str, host: str, port: int) -> None:  # noqa: ARG001
    server = ThreadingHTTPServer((host, port), make_handler())
    print(f"simple ui serving at http://{host}:{port}")
    server.serve_forever()
