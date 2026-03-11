from __future__ import annotations

import sqlite3
import time
from datetime import date

from app.data.provider_service import MarketDataService

_DATA_SERVICE = MarketDataService()


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
        f"<tr><td>{r['slot_index']}</td><td>{r['slot_time']}</td><td>{r['generated_at']}</td><td>{r['symbol_count']}</td><td>{r['active_symbol_count']}</td><td>{r['avg_last_price']}</td><td>{r['alert_count']}</td><td>{r.get('top_symbols','')}</td></tr>"
        for r in intervals
    )
    default_symbols = ",".join(w["symbol"] for w in watchlist[:20])
    return f"""
    <html><head><meta charset='utf-8'><title>盘中交易扫描控制台</title>
    <style>
      :root {{ --bg:#f5f7fb; --card:#ffffff; --muted:#6b7280; --text:#111827; --line:#e5e7eb; --pri:#2563eb; --ok:#16a34a; --err:#dc2626; }}
      * {{ box-sizing: border-box; }}
      body {{ margin:0; font-family: 'Segoe UI', Arial, sans-serif; background:var(--bg); color:var(--text); }}
      .wrap {{ max-width: 1520px; margin: 0 auto; padding: 20px; }}
      .top {{ display:flex; justify-content:space-between; align-items:end; gap:16px; margin-bottom:14px; }}
      .title h1 {{ margin:0; font-size:28px; }} .title p {{ margin:4px 0 0 0; color:var(--muted); }}
      .badge {{ font-size:12px; color:#1d4ed8; background:#dbeafe; padding:6px 10px; border-radius:999px; }}
      .grid3 {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
      .panel {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:14px; box-shadow:0 6px 24px rgba(17,24,39,.06); }}
      .metric .k {{ font-size:12px; color:var(--muted); }} .metric .v {{ font-size:26px; font-weight:700; margin-top:4px; }}
      .layout {{ display:grid; grid-template-columns: 370px 1fr; gap:14px; margin-top:14px; }}
      .field {{ margin-bottom:10px; }} .field label {{ display:block; font-size:12px; color:var(--muted); margin-bottom:4px; }}
      input,select,textarea {{ width:100%; border:1px solid var(--line); border-radius:8px; padding:8px 10px; font-size:13px; background:#fff; }}
      textarea {{ min-height:64px; resize:vertical; }}
      .row {{ display:flex; gap:8px; }}
      button {{ border:none; border-radius:8px; padding:8px 10px; font-size:12px; cursor:pointer; }}
      .btn-pri {{ background:var(--pri); color:#fff; }} .btn-sub {{ background:#eef2ff; color:#1e40af; }} .btn-plain {{ background:#f3f4f6; }}
      .status {{ font-size:12px; margin-top:8px; }} .ok {{ color:var(--ok); }} .err {{ color:var(--err); }} .warn {{ color:#92400e; }}
      table {{ width:100%; border-collapse:collapse; }} th,td {{ border-bottom:1px solid var(--line); padding:8px; font-size:12px; text-align:left; }}
      th {{ color:#334155; background:#f8fafc; position:sticky; top:0; }}
      .section {{ margin-top:12px; }} .section h3 {{ margin:0 0 10px 0; font-size:16px; }}
      .small {{ color:var(--muted); font-size:12px; }}
      @media (max-width: 1100px) {{ .layout {{ grid-template-columns:1fr; }} .grid3 {{ grid-template-columns:1fr; }} }}
    </style></head>
    <body><div class='wrap'>
      <div class='top'>
        <div class='title'>
          <h1>盘中交易扫描控制台</h1>
          <p>交易日：{scan_date} ｜ 最新更新时间：<span id="last-update">{time.strftime('%Y-%m-%d %H:%M:%S')}</span></p>
        </div>
        <div class='badge'>免费模式：仅建议监控 50~200 只自选股票</div>
      </div>

      <div class='grid3'>
        <div class='panel metric'><div class='k'>自选股数量</div><div class='v'>{len(watchlist)}</div></div>
        <div class='panel metric'><div class='k'>最新提醒数量</div><div class='v'>{len(alerts)}</div></div>
        <div class='panel metric'><div class='k'>30分钟快照数量</div><div class='v'>{len(intervals)}</div></div>
      </div>

      <div class='layout'>
        <aside class='panel'>
          <h3>数据源设置</h3>
          <div class='field'><label>数据源</label><select id='source'><option value='finnhub'>Finnhub（默认）</option></select></div>
          <div class='field'><label>Finnhub API 密钥</label><div class='row'><input id='api-key' type='password' placeholder='请输入 API 密钥' /><button class='btn-plain' id='toggle-key'>显示</button></div></div>
          <div class='field'><label>自选股票池（逗号分隔，自动大写去重）</label><textarea id='symbols'>{default_symbols}</textarea></div>
          <div class='field'><label>列表刷新频率（秒，建议 60）</label><input id='refresh-list' type='number' min='30' max='600' value='60' /></div>
          <div class='field'><label>详情刷新频率（秒，建议 15~30）</label><input id='refresh-detail' type='number' min='10' max='120' value='20' /></div>
          <div class='field'><label>新闻刷新频率（秒，建议 60~180）</label><input id='refresh-news' type='number' min='30' max='600' value='120' /></div>
          <div class='field'><label><input id='enable-news' type='checkbox' checked /> 启用新闻</label></div>
          <div class='field'><label><input id='enable-realtime' type='checkbox' /> 启用实时推送（仅重点股票）</label></div>
          <div class='row'>
            <button class='btn-pri' id='btn-save'>保存设置</button>
            <button class='btn-sub' id='btn-test'>测试连接</button>
            <button class='btn-plain' id='btn-clear'>清空密钥</button>
          </div>
          <div class='status warn' id='conn-status'>连接状态：未配置</div>
          <div class='small'>说明：页面不会直连第三方地址，所有请求都经过统一数据服务层。</div>
        </aside>

        <main>
          <div class='panel section'><h3>最新提醒</h3><table><tr><th>时间</th><th>代码</th><th>形态</th><th>评级</th><th>分数</th><th>入场区间</th><th>止损</th><th>止盈</th><th>理由</th></tr>{rows_alert}</table></div>
          <div class='panel section'><h3>自选股（盘前评分）</h3><table><tr><th>排名</th><th>代码</th><th>PMS</th><th>Gap%</th><th>盘前成交额</th></tr>{rows_watch}</table></div>
          <div class='panel section'><h3>每30分钟生成信息（09:30~16:00）</h3><table><tr><th>时段编号</th><th>时段</th><th>生成时间</th><th>股票总数</th><th>活跃数</th><th>平均最新价</th><th>提醒数</th><th>成交额Top</th></tr>{rows_intervals}</table></div>
          <div class='panel section'>
            <h3>行情预览（基于数据源服务）</h3>
            <div class='row'><button class='btn-sub' id='btn-load-quotes'>刷新报价</button><button class='btn-sub' id='btn-load-news'>刷新新闻</button></div>
            <div id='data-hint' class='status warn'>提示：未请求数据</div>
            <div id='quote-box' class='small'>暂无报价</div>
            <div id='news-box' class='small' style='margin-top:10px'>暂无新闻</div>
          </div>
        </main>
      </div>
    </div>
    <script>
      const LS_KEY='scanner.data.settings.v1';
      const $=(id)=>document.getElementById(id);
      function normalizeSymbols(raw) {{
        const arr = raw.split(',').map(s=>s.trim().toUpperCase()).filter(Boolean);
        const valid = arr.filter(s=>/^[A-Z][A-Z0-9\.\-]{{0,9}}$/.test(s));
        return [...new Set(valid)].slice(0,200);
      }}
      function saveSettings() {{
        const settings = {{
          source:$('source').value,
          apiKey:$('api-key').value.trim(),
          symbols:normalizeSymbols($('symbols').value),
          refreshList:parseInt($('refresh-list').value||'60',10),
          refreshDetail:parseInt($('refresh-detail').value||'20',10),
          refreshNews:parseInt($('refresh-news').value||'120',10),
          enableNews:$('enable-news').checked,
          enableRealtime:$('enable-realtime').checked,
        }};
        localStorage.setItem(LS_KEY, JSON.stringify(settings));
        $('symbols').value = settings.symbols.join(',');
        $('conn-status').textContent='连接状态：已配置，未测试';
        $('conn-status').className='status warn';
        alert('设置已保存');
      }}
      function loadSettings() {{
        const raw = localStorage.getItem(LS_KEY);
        if(!raw) return;
        try {{
          const s = JSON.parse(raw);
          $('source').value=s.source||'finnhub';
          $('api-key').value=s.apiKey||'';
          if(Array.isArray(s.symbols) && s.symbols.length) $('symbols').value=s.symbols.join(',');
          if(s.refreshList) $('refresh-list').value=s.refreshList;
          if(s.refreshDetail) $('refresh-detail').value=s.refreshDetail;
          if(s.refreshNews) $('refresh-news').value=s.refreshNews;
          $('enable-news').checked=!!s.enableNews;
          $('enable-realtime').checked=!!s.enableRealtime;
          $('conn-status').textContent=s.apiKey ? '连接状态：已配置，未测试' : '连接状态：未配置';
          $('conn-status').className=s.apiKey ? 'status warn' : 'status err';
        }} catch(e) {{}}
      }}
      async function testConnection() {{
        const source=$('source').value; const apiKey=$('api-key').value.trim();
        if(!apiKey) {{ $('conn-status').textContent='连接状态：缺少 API 密钥'; $('conn-status').className='status err'; return; }}
        $('conn-status').textContent='连接状态：测试中...'; $('conn-status').className='status warn';
        try {{
          const res = await fetch(`/api/data/health?source=${{encodeURIComponent(source)}}&api_key=${{encodeURIComponent(apiKey)}}`);
          const data = await res.json();
          if(data.ok) {{ $('conn-status').textContent='连接状态：连接成功'; $('conn-status').className='status ok'; }}
          else {{ $('conn-status').textContent='连接状态：连接失败 - '+(data.detail||'未知错误'); $('conn-status').className='status err'; }}
        }} catch(e) {{
          $('conn-status').textContent='连接状态：网络错误，请稍后重试';
          $('conn-status').className='status err';
        }}
      }}
      async function loadQuotes() {{
        const source=$('source').value; const apiKey=$('api-key').value.trim();
        const symbols = normalizeSymbols($('symbols').value);
        if(!apiKey) {{ $('data-hint').textContent='请求失败：请先配置 API 密钥'; $('data-hint').className='status err'; return; }}
        $('data-hint').textContent='加载中...'; $('data-hint').className='status warn';
        try {{
          const res=await fetch(`/api/data/quotes?source=${{encodeURIComponent(source)}}&api_key=${{encodeURIComponent(apiKey)}}&symbols=${{encodeURIComponent(symbols.join(','))}}`);
          const data=await res.json();
          if(!data.ok) {{ $('data-hint').textContent='请求失败：'+(data.detail||'未知错误'); $('data-hint').className='status err'; return; }}
          const rows=(data.items||[]).map(x=>`<div>${{x.symbol}}：最新价 ${{x.price}}，涨跌幅 ${{x.change_pct}}%</div>`).join('');
          $('quote-box').innerHTML=rows || '暂无数据';
          $('data-hint').textContent='报价更新成功'; $('data-hint').className='status ok';
          $('last-update').textContent=new Date().toLocaleString('zh-CN');
        }} catch(e) {{ $('data-hint').textContent='网络错误，请重试'; $('data-hint').className='status err'; }}
      }}
      async function loadNews() {{
        if(!$('enable-news').checked) {{ $('news-box').textContent='新闻开关已关闭'; return; }}
        const source=$('source').value; const apiKey=$('api-key').value.trim();
        const first = normalizeSymbols($('symbols').value)[0] || '';
        if(!apiKey) {{ $('news-box').textContent='请先配置 API 密钥'; return; }}
        try {{
          const res=await fetch(`/api/data/news?source=${{encodeURIComponent(source)}}&api_key=${{encodeURIComponent(apiKey)}}&symbol=${{encodeURIComponent(first)}}`);
          const data=await res.json();
          if(!data.ok) {{ $('news-box').textContent='新闻请求失败：'+(data.detail||'未知错误'); return; }}
          const rows=(data.items||[]).slice(0,8).map(n=>`<div>• ${{n.headline}}</div>`).join('');
          $('news-box').innerHTML=rows || '暂无数据';
        }} catch(e) {{ $('news-box').textContent='网络错误，请稍后重试'; }}
      }}
      $('btn-save').onclick=saveSettings;
      $('btn-test').onclick=testConnection;
      $('btn-load-quotes').onclick=loadQuotes;
      $('btn-load-news').onclick=loadNews;
      $('btn-clear').onclick=()=>{{ $('api-key').value=''; saveSettings(); $('conn-status').textContent='连接状态：未配置'; $('conn-status').className='status err'; }};
      $('toggle-key').onclick=()=>{{ const k=$('api-key'); k.type = (k.type==='password'?'text':'password'); $('toggle-key').textContent = (k.type==='password'?'显示':'隐藏'); }};
      loadSettings();
    </script>
    </body></html>
    """


def create_app(db_url: str):
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("FastAPI/uvicorn 未安装") from exc

    db_path = db_url.replace("sqlite:///", "")
    app = FastAPI(title="盘中交易扫描")

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

    @app.get("/api/data/health")
    def api_data_health(source: str = "finnhub", api_key: str = ""):
        if not api_key:
            return JSONResponse({"ok": False, "detail": "缺少 API 密钥"}, status_code=400)
        data = _DATA_SERVICE.health_check(source=source, api_key=api_key)
        code = 200 if data.get("ok") else 400
        return JSONResponse(data, status_code=code)

    @app.get("/api/data/quotes")
    def api_data_quotes(source: str = "finnhub", api_key: str = "", symbols: str = ""):
        if not api_key:
            return JSONResponse({"ok": False, "detail": "缺少 API 密钥"}, status_code=400)
        raw = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        pool = []
        for s in raw:
            if s not in pool and len(s) <= 10 and s.replace(".", "").replace("-", "").isalnum():
                pool.append(s)
        pool = pool[:200]
        if not pool:
            return JSONResponse({"ok": False, "detail": "自选股票池为空"}, status_code=400)
        items = []
        try:
            for symbol in pool:
                q = _DATA_SERVICE.get_quote(source=source, api_key=api_key, symbol=symbol, ttl=30)
                items.append({"symbol": symbol, "price": round(float(q.get("c", 0.0)), 4), "change_pct": round(float(q.get("dp", 0.0)), 3)})
        except Exception as exc:
            detail = str(exc)
            if "429" in detail:
                detail = "请求过于频繁，已触发限频/额度限制"
            return JSONResponse({"ok": False, "detail": detail}, status_code=400)
        return JSONResponse({"ok": True, "items": items, "updated_at": time.time()})

    @app.get("/api/data/news")
    def api_data_news(source: str = "finnhub", api_key: str = "", symbol: str = ""):
        if not api_key:
            return JSONResponse({"ok": False, "detail": "缺少 API 密钥"}, status_code=400)
        try:
            items = _DATA_SERVICE.get_news(source=source, api_key=api_key, symbol=(symbol or None), ttl=120)
            return JSONResponse({"ok": True, "items": items})
        except Exception as exc:
            detail = str(exc)
            if "429" in detail:
                detail = "新闻请求过于频繁，请稍后重试"
            return JSONResponse({"ok": False, "detail": detail}, status_code=400)

    @app.get("/", response_class=HTMLResponse)
    def index(scan_date: str | None = None):
        d = scan_date or date.today().isoformat()
        alerts = query_latest_alerts(db_path, 20)
        watchlist = query_today_watchlist(db_path, d)
        intervals = query_interval_snapshots(db_path, d)
        return HTMLResponse(_render_html(d, alerts, watchlist, intervals))

    return app
