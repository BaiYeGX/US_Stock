# intraday-stock-scanner

美股盘中手动交易扫描助手（MVP）。目标是盘中扫描并输出可人工执行的结构化交易计划，不自动下单、不做投资建议。

## 0. 现在是实时还是预设？
- `premarket-scan` 当前默认用 `MockProvider`，属于**预设/模拟数据流程**，用于本地调试。
- `market-loop`：
  - `--mock` 时是模拟。
  - 不加 `--mock` 且提供 `POLYGON_API_KEY` 时，走 `PolygonProvider` WebSocket + REST 回补，属于**真实实时行情接入**。

## 1. 项目目标
- 盘前构建候选池（watchlist）。
- 盘中持续更新状态并识别 3 个 setup：ORB / VWAP_RECLAIM / HOD_BREAKOUT。
- 仅输出少量 A/B 级机会，包含 entry/stop/tp/invalidate/score/reason。
- 记录全部 alerts 与过滤拒绝原因，收盘后复盘评估。

## 2. 范围边界（MVP）
### 包含
- Provider 抽象（默认 Polygon，保留 Alpaca 接口）
- PreMarketScore + IntradayActionScore
- Hard filters（可追踪拒绝原因）
- SQLite 持久化
- CLI 工作流：premarket-scan / market-loop / review / replay-alerts / seed-universe
- 可视化 UI（FastAPI）：watchlist + latest alerts 面板
- 真实 WebSocket（Polygon）接入、自动重连与分钟线回补机制

### 不包含
- 自动下单
- 期权/杠杆 ETF 专项
- 模型训练或 LLM 决策
- 复杂 GUI / 高频 tick 级

## 3. 安装

### 方案 A（推荐）：Poetry
```bash
cd intraday-stock-scanner
poetry install
cp .env.example .env
```

如果提示 `poetry` 不存在（你现在遇到的就是这个）：

**Windows PowerShell**
```powershell
python -m pip install -U poetry
# 重新打开 PowerShell 后验证
poetry --version
```

若仍找不到命令，可用：
```powershell
python -m poetry install
```

### 方案 B（无需 Poetry）：venv + pip
```powershell
cd intraday-stock-scanner
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

## 4. 配置
- 主配置：`config/default.yaml`
- Provider 配置：`config/providers.yaml`
- DB：`DATABASE_URL`（默认 sqlite）

## 5. 运行方式
### 盘前扫描
```bash
python -m app.cli premarket-scan --scan-date 2026-03-11
```

### 盘中循环（Mock）
```bash
python -m app.cli market-loop --mock --symbols NVDA,AAPL,TSLA
```

### 盘中循环（真实 Polygon）
Linux/macOS:
```bash
export POLYGON_API_KEY=xxx
python -m app.cli market-loop --symbols SPY,QQQ,NVDA,AAPL,TSLA
```

Windows PowerShell:
```powershell
$env:POLYGON_API_KEY="xxx"
python -m app.cli market-loop --symbols SPY,QQQ,NVDA,AAPL,TSLA
```

### 启动 UI
```bash
python -m app.cli serve-ui --host 127.0.0.1 --port 8000
# 打开 http://127.0.0.1:8000
# 若 fastapi/uvicorn 不可用，会自动降级到内置 simple server
```

### 收盘复盘
```bash
python -m app.cli review --scan-date 2026-03-11
```

## 6. API/UI
- `GET /health`
- `GET /api/watchlist?scan_date=YYYY-MM-DD`
- `GET /api/alerts/latest?limit=20`
- `GET /api/interval-snapshots?scan_date=YYYY-MM-DD`
- `GET /` 仪表盘页面（watchlist + alerts + interval snapshots）

## 7. 数据模型
核心 schema 在 `app/providers/base.py`（AssetMeta/Bar/Quote/Trade/Snapshot/NewsItem），状态模型在 `app/state/symbol_state.py`，告警 schema 在 `app/alerts/schemas.py`。

## 8. setup 规则（摘要）
- **ORB**：09:35~10:15 突破开盘区间并站上 VWAP。
- **VWAP_RECLAIM**：09:45~13:30 两根 1m 重新站回 VWAP。
- **HOD_BREAKOUT**：10:00~11:30 与 14:00~15:30 贴近日高并突破。

## 9. 评分体系（股票评选给分原则）
### 9.1 盘前评分 PMS（决定重点盯谁）
`PMS = 0.30*Gap + 0.25*PMDollarVol + 0.20*ATR + 0.15*PrevDayTrend + 0.10*Catalyst`
- Gap：隔夜/盘前跳空幅度越大（按横截面分位）分越高。
- PMDollarVol：盘前成交额越大分越高。
- ATR：20日 ATR% 越高分越高。
- PrevDayTrend：前日趋势位置强分更高。
- Catalyst：有财报/评级/新闻催化可加分。

### 9.2 盘中评分 IAS（决定是否发出手动计划）
`IAS = 0.25*Setup + 0.20*RS + 0.20*Activity + 0.15*Liquidity + 0.10*MarketAlign + 0.10*Room`
- Setup：setup 条件满足度。
- RS：相对基准/板块强度。
- Activity：RVOL 与 ATR 活跃度。
- Liquidity：点差与成交额质量。
- MarketAlign：与大盘环境一致性。
- Room：目标空间与风险距离比。

### 9.3 评级
- A：IAS >= 80
- B：70 <= IAS < 80
- C：IAS < 70（记录，不提示）

## 10. 当前可达到的程度（你最关心）
- ✅ 可做：盘前 watchlist、规则驱动 setup 扫描、评分、告警结构化输出、数据库落地、基础复盘、UI 浏览。
- ✅ 可做：真实 Polygon WebSocket 接入与自动重连；断线后按最近时间戳做分钟线回补，尽量补齐状态。
- ✅ 新增：从开盘 0 分钟（09:30）开始，每 30 分钟记录一次生成信息（slot#0~13），直到 16:00 收盘。
- ⚠️ 暂未做满：回补目前以分钟线为主（非逐笔 tick 全量回放）；多源一致性、复杂风控与生产级监控告警需要下一版强化。

## 11. 测试
```bash
pytest
```

## 12. 风险提示
- 本工具不构成投资建议。
- 本工具不自动下单。
- 本工具不保证收益。

## 13. 路线图 / TODO
- **V2**：加入更完整 market-loop orchestrator（regime + setups + alerts + dedupe 全链路实时落库）。
- **V2**：增强回补策略（按 symbol/窗口分片拉取、防重复、防漏洞）。
- **V3**：加入 LLM 解释层（解释信号，不替代策略判定）。
