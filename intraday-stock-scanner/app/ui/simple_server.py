from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


_SIMPLE_HTML = """<!doctype html>
<html lang='zh-CN'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>波段评分与执行监控系统</title>
  <style>
    :root{--bg:#f1f5f9;--card:#fff;--line:#e2e8f0;--txt:#0f172a;--muted:#475569;--blue:#2563eb}
    *{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at top,#dbeafe,#f8fafc 38%,#f1f5f9);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;color:var(--txt)}
    .wrap{max-width:1100px;margin:28px auto;padding:18px}
    .hero{background:linear-gradient(135deg,#0f172a,#1e293b);color:#fff;border-radius:20px;padding:26px;box-shadow:0 16px 42px rgba(15,23,42,.25)}
    .hero h1{margin:0;font-size:34px}
    .sub{margin-top:8px;opacity:.84}
    .clock-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:18px}
    .clock{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.18);border-radius:14px;padding:14px 16px}
    .clock .k{opacity:.8;font-size:13px}.clock .v{font-size:44px;font-weight:800;letter-spacing:1px;margin-top:4px}
    .card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;margin-top:14px;box-shadow:0 8px 20px rgba(15,23,42,.06)}
    .btn{display:inline-block;background:var(--blue);color:#fff;text-decoration:none;padding:10px 14px;border-radius:10px;font-weight:600}
    @media(max-width:900px){.clock-grid{grid-template-columns:1fr}.clock .v{font-size:32px}.hero h1{font-size:26px}}
  </style>
</head>
<body>
  <div class='wrap'>
    <section class='hero'>
      <h1>2~5日多头波段评分系统</h1>
      <div class='sub'>当前为降级展示模式（缺少 FastAPI/Uvicorn），已保留核心视觉与实时双时区电子时钟。</div>
      <div class='clock-grid'>
        <div class='clock'><div class='k'>北京时间（Asia/Shanghai）</div><div class='v' id='bj-clock'>--:--:--</div></div>
        <div class='clock'><div class='k'>纽约时间（America/New_York）</div><div class='v' id='ny-clock'>--:--:--</div></div>
      </div>
    </section>

    <section class='card'>
      <h3 style='margin:0 0 8px'>如何启用完整版 UI</h3>
      <p style='color:var(--muted);line-height:1.75'>请在可联网 pip 环境安装依赖后启动：<code>pip install fastapi uvicorn</code>，再运行 <code>python -m app.cli serve-ui --host 127.0.0.1 --port 8000</code>。</p>
      <p><a class='btn' href='/health'>检查服务健康状态</a></p>
    </section>
  </div>

<script>
function tick(){
  const now = new Date();
  const bj = now.toLocaleString('zh-CN',{hour12:false,timeZone:'Asia/Shanghai'});
  const ny = now.toLocaleString('zh-CN',{hour12:false,timeZone:'America/New_York'});
  document.getElementById('bj-clock').textContent = bj;
  document.getElementById('ny-clock').textContent = ny;
}
tick();
setInterval(tick,1000);
</script>
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
