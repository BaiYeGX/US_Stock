from __future__ import annotations

import json
import sqlite3
from datetime import date

from app.db.session import make_session_factory
from app.services.local_position_store import LocalPositionStore
from app.services.score_engine import ScoreConfig
from app.services.scoreboard_service import RefreshConfig, ScoreBoardService
from app.services.close_snapshot_service import CloseSnapshotService
from app.services.after_hours_review_service import AfterHoursReviewService
from app.services.market_time_service import MarketTimeService


def _safe_text(v) -> str:
    if v is None:
        return "数据不足"
    s = str(v)
    if s.lower() in {"nan", "none", "null", "undefined", "infinity", "-infinity"}:
        return "数据不足"
    return s


def create_app(db_url: str):
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import HTMLResponse, JSONResponse
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("FastAPI/uvicorn 未安装") from exc

    db_path = db_url.replace("sqlite:///", "")
    session_factory = make_session_factory(db_url)
    scoreboard_service = ScoreBoardService(session_factory)
    position_store = LocalPositionStore(session_factory)
    close_snapshot_service = CloseSnapshotService(session_factory)
    after_hours_service = AfterHoursReviewService()
    time_service = MarketTimeService()

    app = FastAPI(title="2-5日多头波段评分与执行监控")

    def _api_key(request: Request, query_key: str = "") -> str:
        header_key = request.headers.get("X-API-Key", "").strip()
        if header_key:
            return header_key
        return (query_key or "").strip()

    @app.get("/health")
    def health():
        return {"ok": True}


    @app.get("/api/market-status")
    def api_market_status(request: Request, source: str = "finnhub", api_key: str = ""):
        api_key = _api_key(request, api_key)
        if not api_key:
            return JSONResponse({"ok": False, "detail": "缺少 API 密钥"}, status_code=400)
        provider = scoreboard_service.data_service._provider(source, api_key)
        payload = provider.get_market_status() if hasattr(provider, "get_market_status") else {"market": "unknown"}
        state = time_service.classify_from_status(payload)
        return JSONResponse({
            "ok": True,
            "market_status": state.market_status,
            "ny_time": time_service.to_newyork_display(state.exchange_tz_now),
            "shanghai_time": time_service.to_shanghai_display(state.exchange_tz_now),
            "exchange_date": time_service.get_exchange_date(),
            "has_regular_closed": time_service.has_regular_session_closed_today(payload),
            "in_close_window": time_service.get_today_close_trigger_window(payload),
        })

    @app.get("/api/official-close-snapshot/latest")
    def api_official_latest():
        payload = close_snapshot_service.get_latest()
        if not payload:
            return JSONResponse({"ok": False, "detail": "暂无正式收盘快照"}, status_code=404)
        return JSONResponse({"ok": True, "payload": payload})

    @app.get("/api/official-close-snapshot/{exchange_date}")
    def api_official_by_date(exchange_date: str):
        payload = close_snapshot_service.get_by_date(exchange_date)
        if not payload:
            return JSONResponse({"ok": False, "detail": "指定日期快照不存在"}, status_code=404)
        return JSONResponse({"ok": True, "payload": payload})

    @app.post("/api/official-close-snapshot/capture")
    def api_official_capture(request: Request, source: str = "finnhub", api_key: str = ""):
        api_key = _api_key(request, api_key)
        if not api_key:
            return JSONResponse({"ok": False, "detail": "缺少 API 密钥"}, status_code=400)
        result = close_snapshot_service.capture(source=source, api_key=api_key)
        return JSONResponse({"ok": True, **result})

    @app.post("/api/official-close-snapshot/backfill-latest")
    def api_official_backfill(request: Request, source: str = "finnhub", api_key: str = ""):
        api_key = _api_key(request, api_key)
        if not api_key:
            return JSONResponse({"ok": False, "detail": "缺少 API 密钥"}, status_code=400)
        result = close_snapshot_service.backfill_latest(source=source, api_key=api_key)
        return JSONResponse({"ok": True, **result})

    @app.get("/api/after-hours-review/latest")
    def api_after_hours_latest(request: Request, source: str = "finnhub", api_key: str = ""):
        api_key = _api_key(request, api_key)
        if not api_key:
            return JSONResponse({"ok": False, "detail": "缺少 API 密钥"}, status_code=400)
        latest = close_snapshot_service.get_latest()
        if not latest:
            return JSONResponse({"ok": False, "detail": "暂无正式快照"}, status_code=404)
        review = after_hours_service.build(source=source, api_key=api_key, official_snapshot=latest)
        return JSONResponse({"ok": True, "payload": review})
    @app.get("/api/scoreboard")
    def api_scoreboard(request: Request, source: str = "finnhub", api_key: str = ""):
        api_key = _api_key(request, api_key)
        if not api_key:
            return JSONResponse({"ok": False, "detail": "缺少 API 密钥"}, status_code=400)
        try:
            data = scoreboard_service.build_scoreboard(source=source, api_key=api_key)
            return JSONResponse({"ok": True, **data})
        except Exception as exc:
            detail = str(exc)
            if "429" in detail:
                detail = "请求频率过高，已触发节流保护"
            return JSONResponse({"ok": False, "detail": detail}, status_code=400)

    @app.get("/api/position-state")
    def api_position_state():
        return JSONResponse({"ok": True, "items": position_store.get_all()})

    @app.post("/api/position-state/{symbol}")
    async def api_upsert_position(symbol: str, payload: dict):
        try:
            position_store.upsert(symbol.upper(), payload)
            return JSONResponse({"ok": True})
        except Exception as exc:
            return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.get("/")
    def index(scan_date: str | None = None):
        d = scan_date or date.today().isoformat()
        html = f"""
<html><head><meta charset='utf-8'><title>波段评分与执行监控系统</title>
<style>
:root {{ --bg:#f3f6fb; --card:#fff; --line:#e5e7eb; --txt:#111827; --muted:#6b7280; --blue:#2563eb; --green:#16a34a; --red:#dc2626; --amber:#d97706; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--txt); font-family:'Segoe UI',Arial; }}
.wrap {{ max-width:1600px; margin:0 auto; padding:24px; }}
.header {{ display:flex; justify-content:space-between; align-items:end; margin-bottom:14px; }}
.header h1 {{ margin:0; font-size:28px; }} .sub {{ color:var(--muted); font-size:12px; }}
.badge {{ padding:6px 10px; border-radius:999px; background:#e0ecff; color:#1d4ed8; font-size:12px; }}
.grid-top {{ display:grid; grid-template-columns:repeat(5,1fr); gap:10px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:16px; box-shadow:0 10px 30px rgba(15,23,42,.08); }}
.metric {{ padding:12px; }} .k {{ color:var(--muted); font-size:12px; }} .v {{ font-size:24px; font-weight:700; margin-top:5px; }}
.main {{ display:grid; grid-template-columns:360px 1fr; gap:12px; margin-top:12px; }}
.panel {{ padding:14px; }} h3 {{ margin:0 0 10px 0; font-size:16px; }}
.field {{ margin-bottom:10px; }} label {{ display:block; color:var(--muted); font-size:12px; margin-bottom:4px; }}
input,select,textarea {{ width:100%; border:1px solid var(--line); border-radius:8px; padding:8px 10px; font-size:13px; background:#fff; }} textarea {{ min-height:64px; }}
.row {{ display:flex; gap:8px; }}
button {{ border:none; border-radius:8px; padding:8px 10px; font-size:12px; cursor:pointer; }}
.pri {{ background:var(--blue); color:#fff; }} .subbtn {{ background:#e8efff; color:#1d4ed8; }} .plain {{ background:#f3f4f6; }}
.state {{ font-size:12px; margin-top:8px; }} .ok {{ color:var(--green); }} .err {{ color:var(--red); }} .warn {{ color:var(--amber); }}
.section {{ margin-top:10px; }}
table {{ width:100%; border-collapse:collapse; }} th,td {{ border-bottom:1px solid var(--line); padding:7px; font-size:12px; text-align:left; }} th {{ background:#f8fafc; color:#334155; position:sticky; top:0; backdrop-filter: blur(2px); }}
.tag {{ padding:2px 6px; border-radius:6px; font-size:11px; color:#fff; display:inline-block; }}
.a5,.s5 {{ background:#16a34a; }} .a4,.s4 {{ background:#2563eb; }} .a3,.s3 {{ background:#0ea5e9; }} .a2,.s2 {{ background:#d97706; }} .a1,.s1 {{ background:#ef4444; }} .a0,.s0 {{ background:#6b7280; }}
.details {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }}
.list li {{ margin-bottom:4px; }}
@media (max-width:1200px) {{ .main{{grid-template-columns:1fr;}} .grid-top{{grid-template-columns:repeat(2,1fr);}} .details{{grid-template-columns:1fr;}} }}
</style></head>
<body><div class='wrap'>
  <div class='header'>
    <div><h1>12只固定股票池 · 2~5交易日多头波段评分系统</h1><div class='sub'>交易日：{d}｜时区：America/New_York｜仅多头，不做空</div></div>
    <div class='badge'>数据源：Finnhub Free（免费模式）</div>
  </div>

  <div class='card panel' style='margin-bottom:12px;background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff;'>
    <div style='display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;'>
      <div>
        <div style='font-size:14px;opacity:.8;'>实时电子时钟</div>
        <div style='font-size:26px;font-weight:700;margin-top:6px;'>北京时间 <span id='bj-clock' style='font-size:34px;letter-spacing:1px;'>--:--:--</span></div>
      </div>
      <div style='text-align:right;'>
        <div style='font-size:14px;opacity:.8;'>纽约时间（America/New_York）</div>
        <div id='ny-clock' style='font-size:34px;font-weight:700;letter-spacing:1px;'>--:--:--</div>
      </div>
    </div>
  </div>

  <div class='card panel' id='official-banner' style='margin-bottom:12px;'>
    <h3>主评分依据：前一交易日正式收盘快照（上海时间主显示）</h3>
    <div id='official-banner-content' class='state warn'>加载中...</div>
  </div>

  <div class='card panel' id='afterhours-card' style='margin-bottom:12px;'>
    <h3>盘后/盘前补充状态（不改写正式评分）</h3>
    <div id='afterhours-content' class='state warn'>加载中...</div>
  </div>

  <div class='grid-top'>
    <div class='card metric'><div class='k'>市场状态</div><div class='v' id='m-status'>--</div></div>
    <div class='card metric'><div class='k'>固定池数量</div><div class='v'>12</div></div>
    <div class='card metric'><div class='k'>候选数量</div><div class='v' id='m-cand'>--</div></div>
    <div class='card metric'><div class='k'>持仓数量</div><div class='v' id='m-held'>--</div></div>
    <div class='card metric'><div class='k'>次日重点监控</div><div class='v' id='m-next'>--</div></div>
  </div>

  <div class='main'>
    <aside class='card panel'>
      <h3>数据源设置</h3>
      <div class='field'><label>数据源</label><select id='source'><option value='finnhub'>Finnhub</option></select></div>
      <div class='field'><label>API 密钥</label><div class='row'><input id='api-key' type='password' placeholder='请输入 Finnhub API 密钥' /><button class='plain' id='toggle-key'>显示</button></div></div>
      <div class='field'><label>固定股票池（只读）</label><textarea id='symbols'>NVDA,AMD,QQQ,SMH,AVGO,TSM,AMZN,META,MSFT,GOOGL,SPY,SOXX</textarea></div>
      <h3>刷新频率设置</h3>
      <div class='field'><label>收盘前报价刷新（秒）</label><input id='rf-preclose' value='180' type='number' /></div>
      <div class='field'><label>最后10分钟刷新（秒）</label><input id='rf-last10' value='60' type='number' /></div>
      <div class='field'><label>30分钟K线刷新（秒）</label><input id='rf-30m' value='900' type='number' /></div>
      <div class='field'><label>候选股本地重算（秒）</label><input id='rf-local' value='2' type='number' /></div>

      <h3>风险参数设置</h3>
      <div class='field'><label>MaxRiskUSD</label><input id='p-risk' value='12' type='number' step='0.1' /></div>
      <div class='field'><label>BuyThreshold</label><input id='p-buy' value='80' type='number' /></div>
      <div class='field'><label>HalfBuyThreshold</label><input id='p-half' value='70' type='number' /></div>
      <div class='field'><label>SellThreshold</label><input id='p-sell' value='80' type='number' /></div>
      <div class='field'><label>HardSellThreshold</label><input id='p-hard' value='90' type='number' /></div>
      <div class='field'><label>Target1R</label><input id='p-t1r' value='2.0' type='number' step='0.1' /></div>
      <div class='field'><label>Target2R</label><input id='p-t2r' value='3.0' type='number' step='0.1' /></div>
      <div class='field'><label>TrailATR</label><input id='p-trail' value='1.5' type='number' step='0.1' /></div>
      <div class='field'><label>MaxHoldingDays</label><input id='p-maxhd' value='5' type='number' /></div>
      <div class='field'><label>Target1SellFraction</label><input id='p-f1' value='0.5' type='number' step='0.05' /></div>
      <div class='field'><label>Target2SellFraction</label><input id='p-f2' value='0.25' type='number' step='0.05' /></div>
      <div class='field'><label>MaxRealtimeCandidates</label><input id='p-maxrt' value='3' type='number' /></div>
      <div class='field'><label><input id='enable-exec' type='checkbox' checked /> 启用盘中触发监控</label></div>
      <div class='field'><label><input id='enable-fallback' type='checkbox' checked /> WebSocket断开启用20秒轮询兜底</label></div>

      <div class='row'>
        <button class='pri' id='btn-save'>保存设置</button>
        <button class='subbtn' id='btn-test'>测试连接</button>
        <button class='plain' id='btn-clear'>清空密钥</button>
      </div>
      <div class='state warn' id='conn-state'>连接状态：未配置</div>
      <div class='state warn' id='budget-state'>节流状态：--</div>
      <div class='state warn' id='last-update'>最近更新时间：--</div>
      <div class='state warn'>说明：WebSocket 消息不计入 REST 请求预算。</div>
    </aside>

    <main>
      <div class='card panel section'>
        <h3>候选股 / 持仓监控（点击查看详情）</h3>
        <table id='tbl-main'><tr><th>排名</th><th>代码</th><th>是否持仓</th><th>买入评分</th><th>卖出评分</th><th>候选动作</th><th>持仓动作</th><th>总动作</th><th>买入档位</th><th>卖出档位</th></tr></table>
      </div>

      <div class='card panel section'>
        <h3>股票详情（评分解释）</h3>
        <div id='empty-detail' class='state warn'>请选择上方任一股票，查看“为什么能买 / 为什么该卖”。</div>
        <div id='detail' style='display:none'>
          <div class='details'>
            <div class='card panel'><h3>总结果</h3><div id='d-total'></div></div>
            <div class='card panel'><h3>硬过滤状态</h3><ul id='d-filters' class='list'></ul></div>
            <div class='card panel'><h3>关键执行价</h3><div id='d-prices'></div></div>
            <div class='card panel'><h3>买入子分数</h3><div id='d-buy'></div></div>
            <div class='card panel'><h3>卖出子分数</h3><div id='d-sell'></div></div>
            <div class='card panel'><h3>风险与结构字段</h3><div id='d-fields'></div></div>
          </div>
          <div class='card panel section'>
            <h3>本地持仓维护</h3>
            <div class='row'><input id='pos-symbol' placeholder='代码' /><label><input id='pos-held' type='checkbox' />已持仓</label></div>
            <div class='row'><input id='pos-entry' placeholder='EntryFilled' /><input id='pos-date' placeholder='EntryDate (YYYY-MM-DD)' /></div>
            <div class='row'><input id='pos-shares' placeholder='HeldPositionSizeShares' /><input id='pos-rinit' placeholder='R_init' /></div>
            <div class='row'><input id='pos-highclose' placeholder='HighestCloseSinceEntry' /><input id='pos-stop0' placeholder='Stop0_t' /><input id='pos-trail' placeholder='TrailStop_t' /><input id='pos-hd' placeholder='HoldingDays' /></div>
            <div class='row'><button class='pri' id='btn-pos-save'>保存持仓记录</button></div>
            <div id='pos-state' class='state warn'>提示：当前持仓来自本地手动维护，不来自 Finnhub。</div>
          </div>
        </div>
      </div>
    </main>
  </div>
</div>
<script>
const LS='swing.cn.settings.v2';
let rows=[];
const officialBannerContent=document.getElementById('official-banner-content');
const afterhoursContent=document.getElementById('afterhours-content');
function fmt(v, digits=3){{
  if(v===null||v===undefined) return '数据不足';
  const s=String(v);
  if(['NaN','undefined','null','Infinity','-Infinity','None'].includes(s)) return '数据不足';
  const n=Number(v); if(!Number.isFinite(n)) return s; return Number.isInteger(n)? String(n) : n.toFixed(digits);
}}
function actCN(code){{
  const m={{
    MUST_WATCH_BUY:'次日重点买入监控', STRONG_WATCH_BUY:'次日强监控', BUY_SMALL_IF_TRIGGERED:'触发后小仓试买', NO_BUY:'不买',
    HOLD:'持有', REDUCE:'减仓', REDUCE_HARD:'明确减仓', STRONG_SELL:'强卖', MUST_SELL:'立刻清仓'
  }}; return m[code]||'--';
}}
function clsGrade(g){{ return (g||'').toLowerCase(); }}
function saveSettings(){{
  const s={{source:source.value, apiKey:apiKey.value.trim(), refresh:{{pre:rfPre.value,last10:rfLast10.value,m30:rf30.value,local:rfLocal.value}},
  risk:{{maxRisk:pRisk.value,buy:pBuy.value,half:pHalf.value,sell:pSell.value,hard:pHard.value,t1:pT1r.value,t2:pT2r.value,trail:pTrail.value,maxHd:pMaxhd.value,f1:pF1.value,f2:pF2.value,maxrt:pMaxrt.value}},
  flags:{{exec:enableExec.checked,fallback:enableFallback.checked}} }};
  localStorage.setItem(LS, JSON.stringify(s));
  connState.textContent='连接状态：已配置，未测试'; connState.className='state warn';
}}
function loadSettings(){{
  const raw=localStorage.getItem(LS); if(!raw) return;
  try{{const s=JSON.parse(raw); source.value=s.source||'finnhub'; apiKey.value=s.apiKey||'';
    if(s.refresh){{rfPre.value=s.refresh.pre||180; rfLast10.value=s.refresh.last10||60; rf30.value=s.refresh.m30||900; rfLocal.value=s.refresh.local||2;}}
    if(s.risk){{pRisk.value=s.risk.maxRisk||12; pBuy.value=s.risk.buy||80; pHalf.value=s.risk.half||70; pSell.value=s.risk.sell||80; pHard.value=s.risk.hard||90; pT1r.value=s.risk.t1||2.0; pT2r.value=s.risk.t2||3.0; pTrail.value=s.risk.trail||1.5; pMaxhd.value=s.risk.maxHd||5; pF1.value=s.risk.f1||0.5; pF2.value=s.risk.f2||0.25; pMaxrt.value=s.risk.maxrt||3;}}
    if(s.flags){{enableExec.checked=!!s.flags.exec; enableFallback.checked=!!s.flags.fallback;}}
    connState.textContent=apiKey.value?'连接状态：已配置，未测试':'连接状态：未配置';
  }}catch(e){{}}
}}
async function testConn(){{
  if(!apiKey.value.trim()){{connState.textContent='连接状态：缺少 API 密钥';connState.className='state err';return;}}
  connState.textContent='连接状态：测试中...';connState.className='state warn';
  const r=await fetch(`/api/scoreboard?source=${{encodeURIComponent(source.value)}}`, {{headers:{{'X-API-Key':apiKey.value.trim()}}}});
  const d=await r.json();
  if(d.ok){{connState.textContent='连接状态：连接成功';connState.className='state ok';}} else {{connState.textContent='连接状态：连接失败 - '+(d.detail||'未知错误');connState.className='state err';}}
}}
function renderMain(data){{
  rows=data.rows||[];
  mStatus.textContent=data.overview.market_status||'--';
  mCand.textContent=data.overview.candidate_count||0;
  mHeld.textContent=data.overview.held_count||0;
  mNext.textContent=data.overview.nextday_watch_count||0;
  lastUpdate.textContent='最近更新时间：'+(new Date(data.overview.updated_at).toLocaleString('zh-CN'));
  const b=data.overview.rest_budget||{{}};
  budgetState.textContent=`节流状态：REST ${{b.rest_per_min||0}}/分钟，${{b.rest_per_sec||0}}/秒，${{b.throttled?'已进入节流保护':'正常'}}，WS连接=${{b.ws_connected?'是':'否'}}`;
  budgetState.className='state '+(b.throttled?'err':'ok');

  let html='<tr><th>排名</th><th>代码</th><th>是否持仓</th><th>买入评分</th><th>卖出评分</th><th>候选动作</th><th>持仓动作</th><th>总动作</th><th>买入档位</th><th>卖出档位</th></tr>';
  rows.forEach(r=>{{
    html+=`<tr data-s='${{r.Symbol}}'><td>${{r.Rank}}</td><td>${{r.Symbol}}</td><td>${{r.isHeld?'是':'否'}}</td><td>${{fmt(r.BuyScore,2)}}</td><td>${{fmt(r.SellScore,2)}}</td><td>${{r.CandidateAction}} / ${{actCN(r.CandidateAction)}}</td><td>${{r.PositionAction||'--'}}${{r.PositionAction?(' / '+actCN(r.PositionAction)):''}}</td><td>${{r.Action}} / ${{actCN(r.Action)}}</td><td><span class='tag ${{clsGrade(r.grade_buy)}}'>${{r.grade_buy}}</span></td><td>${{r.grade_sell?`<span class='tag ${{clsGrade(r.grade_sell)}}'>${{r.grade_sell}}</span>`:'--'}}</td></tr>`;
  }});
  tblMain.innerHTML=html;
  [...tblMain.querySelectorAll('tr[data-s]')].forEach(tr=>tr.onclick=()=>showDetail(tr.dataset.s));
}}
function showDetail(sym){{
  const r=rows.find(x=>x.Symbol===sym); if(!r) return;
  emptyDetail.style.display='none'; detail.style.display='block';
  dTotal.innerHTML=`<div>代码：${{r.Symbol}}</div><div>是否持仓：${{r.isHeld?'是':'否'}}</div><div>BuyEligible：${{r.BuyEligible?'是':'否'}}</div><div>BuyScore：${{fmt(r.BuyScore,2)}}（${{r.grade_buy}}）</div><div>SellScore：${{fmt(r.SellScore,2)}}（${{r.grade_sell||'--'}}）</div><div>CandidateAction：${{r.CandidateAction}} / ${{actCN(r.CandidateAction)}}</div><div>PositionAction：${{r.PositionAction||'--'}}${{r.PositionAction?(' / '+actCN(r.PositionAction)):''}}</div><div>Action：${{r.Action}} / ${{actCN(r.Action)}}</div>`;
  let f=''; Object.entries(r.hard_filters||{{}}).forEach(([k,v])=>f+=`<li>${{k}}：${{v===true?'✅ PASS':v===false?'❌ FAIL':_safe(v)}}</li>`); dFilters.innerHTML=f||'<li>暂无数据</li>';
  dPrices.innerHTML=`<div>Entry：${{fmt(r.Entry,4)}}</div><div>Stop0（硬止损，盘中可触发）：${{fmt(r.Stop0,4)}}</div><div>TrailStop（趋势止损，默认收盘确认）：${{fmt(r.TrailStop,4)}}</div><div>Target1：${{fmt(r.Target1,4)}}</div><div>Target2：${{fmt(r.Target2,4)}}</div>`;
  dBuy.innerHTML=Object.entries(r.buy_breakdown||{{}}).map(([k,v])=>`<div>${{k}}：${{fmt(v,2)}}</div>`).join('')||'暂无足够数据';
  dSell.innerHTML=Object.entries(r.sell_breakdown||{{}}).map(([k,v])=>`<div>${{k}}：${{fmt(v,2)}}</div>`).join('')||'暂无足够数据';
  dFields.innerHTML=`<div>R_t：${{fmt((r.Entry&&r.Stop0)?(Number(r.Entry)-Number(r.Stop0)):null,4)}}</div><div>Risk_Reward_Ratio：${{fmt(r.Risk_Reward_Ratio,3)}}</div><div>SuggestedPositionSizeShares：${{fmt(r.SuggestedPositionSizeShares,0)}}</div><div>HeldPositionSizeShares：${{fmt(r.HeldPositionSizeShares,0)}}</div><div>HoldingDays：${{fmt(r.HoldingDays,0)}}</div><div>DaysToEarnings：${{fmt(r.DaysToEarnings,0)}}</div><hr/><div>PBDepthATR_t：${{fmt(r.fields?.PBDepthATR_t,3)}}</div><div>PullbackDays（日）：${{fmt(r.fields?.PullbackDays,0)}}</div><div>PBVolRatio_t：${{fmt(r.fields?.PBVolRatio_t,3)}}</div><div>ER3_t：${{fmt(r.fields?.ER3_t,4)}}</div><div>ER5_t：${{fmt(r.fields?.ER5_t,4)}}</div><div>RVOL20_t：${{fmt(r.fields?.RVOL20_t,3)}}</div><div>AvgDollarVol20_t：${{fmt(r.fields?.AvgDollarVol20_t,0)}}</div>`;
  posSymbol.value=r.Symbol;
}}
function _safe(v){{return v===undefined||v===null?'数据不足':v;}}
async function loadScoreboard(){{
  if(!apiKey.value.trim()){{connState.textContent='连接状态：缺少 API 密钥';connState.className='state err';return;}}
  // 1) 先读正式快照
  let snapRes = await fetch(`/api/official-close-snapshot/latest`);
  let snap = await snapRes.json();
  if(!snap.ok){{
    const backfill = await fetch(`/api/official-close-snapshot/backfill-latest?source=${{encodeURIComponent(source.value)}}`, {{method:'POST', headers:{{'X-API-Key':apiKey.value.trim()}}}});
    const backfillData = await backfill.json();
    if(!backfillData.ok){{connState.textContent='快照补录失败：'+(backfillData.detail||'未知错误');connState.className='state err';return;}}
    snapRes = await fetch(`/api/official-close-snapshot/latest`);
    snap = await snapRes.json();
  }}
  if(!snap.ok){{connState.textContent='读取正式快照失败';connState.className='state err';return;}}
  const payload = snap.payload;
  renderMain(payload);
  const m = payload.meta||{{}};
  officialBannerContent.textContent = `交易所日期(纽约)：${{m.exchange_date||payload.exchange_date||'--'}}｜快照生成(上海)：${{payload.snapshot_generated_timestamp_shanghai||'--'}}｜是否补录：${{m.is_backfilled?'是':'否'}}｜来源：${{m.snapshot_generated_by||payload.snapshot_generated_by||'auto'}}`;

  // 2) 再读市场状态
  const ms = await fetch(`/api/market-status?source=${{encodeURIComponent(source.value)}}`, {{headers:{{'X-API-Key':apiKey.value.trim()}}}});
  const msd = await ms.json();
  if(msd.ok){{
    mStatus.textContent=msd.market_status;
    lastUpdate.textContent='最近更新时间（上海）：'+(msd.shanghai_time||'--');
  }}

  // 3) 盘后/盘前补充状态
  const ah = await fetch(`/api/after-hours-review/latest?source=${{encodeURIComponent(source.value)}}`, {{headers:{{'X-API-Key':apiKey.value.trim()}}}});
  const ahd = await ah.json();
  if(ahd.ok){{
    const first = (ahd.payload.items||[]).slice(0,3).map(x=>`${{x.symbol}} ${{fmt(x.afterHoursChangePctVsClose,2)}}%(${{x.afterHoursRiskFlag}})`).join(' | ');
    afterhoursContent.textContent = `状态：${{ahd.payload.market_status_label_cn}}｜复核时间(上海)：${{ahd.payload.review_timestamp_shanghai}}｜示例：${{first||'暂无'}}`;
  }}
}}
async function savePos(){{
  const symbol=posSymbol.value.trim().toUpperCase(); if(!symbol) return;
  const payload={{
    isHeld: posHeld.checked,
    EntryFilled: posEntry.value?Number(posEntry.value):null,
    EntryDate: posDate.value||null,
    HeldPositionSizeShares: posShares.value?Number(posShares.value):0,
    R_init: posRinit.value?Number(posRinit.value):null,
    HighestCloseSinceEntry: posHighclose.value?Number(posHighclose.value):null,
    Stop0_t: posStop0.value?Number(posStop0.value):null,
    TrailStop_t: posTrail.value?Number(posTrail.value):null,
    HoldingDays: posHd.value?Number(posHd.value):0,
  }};
  const r=await fetch(`/api/position-state/${{symbol}}`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}});
  const d=await r.json();
  posState.textContent=d.ok?'持仓记录保存成功':'持仓记录保存失败：'+(d.detail||'未知错误');
  posState.className='state '+(d.ok?'ok':'err');
  if(d.ok) loadScoreboard();
}}
btnSave.onclick=()=>{{saveSettings(); loadScoreboard();}};
btnTest.onclick=testConn;
btnClear.onclick=()=>{{apiKey.value=''; saveSettings(); connState.textContent='连接状态：未配置'; connState.className='state err';}};
toggleKey.onclick=()=>{{apiKey.type=(apiKey.type==='password'?'text':'password'); toggleKey.textContent=(apiKey.type==='password'?'显示':'隐藏');}};
btnPosSave.onclick=savePos;
const bjClock=document.getElementById('bj-clock');
const nyClock=document.getElementById('ny-clock');

function updateClocks(){{
  const now = new Date();
  const bj = now.toLocaleString('zh-CN', {{hour12:false,timeZone:'Asia/Shanghai'}});
  const ny = now.toLocaleString('zh-CN', {{hour12:false,timeZone:'America/New_York'}});
  bjClock.textContent = bj;
  nyClock.textContent = ny;
}}

updateClocks();
setInterval(updateClocks,1000);
loadSettings();
if(apiKey.value) loadScoreboard();
setInterval(()=>{{ if(apiKey.value) loadScoreboard(); }}, 60000);
</script>
</body></html>
        """
        return HTMLResponse(html)

    return app
