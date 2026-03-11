# intraday-stock-scanner

美股盘中手动交易扫描助手（MVP）。目标是盘中扫描并输出可人工执行的结构化交易计划，不自动下单、不做投资建议。

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

### 不包含
- 自动下单
- 期权/杠杆 ETF 专项
- 模型训练或 LLM 决策
- 复杂 GUI / 高频 tick 级

## 3. 安装
```bash
cd intraday-stock-scanner
poetry install
cp .env.example .env
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

### 盘中循环（MVP skeleton）
```bash
python -m app.cli market-loop
```

### 收盘复盘
```bash
python -m app.cli review --scan-date 2026-03-11
```

### 回放告警
```bash
python -m app.cli replay-alerts --scan-date 2026-03-11
```

### 种子标的
```bash
python -m app.cli seed-universe
```

## 6. 数据模型
核心 schema 在 `app/providers/base.py`（AssetMeta/Bar/Quote/Trade/Snapshot/NewsItem），状态模型在 `app/state/symbol_state.py`，告警 schema 在 `app/alerts/schemas.py`。

## 7. setup 规则（摘要）
- **ORB**：09:35~10:15 突破开盘区间并站上 VWAP。
- **VWAP_RECLAIM**：09:45~13:30 两根 1m 重新站回 VWAP。
- **HOD_BREAKOUT**：10:00~11:30 与 14:00~15:30 贴近日高并突破。

> 详细阈值全部通过 config 管理，避免魔法数字散落。

## 8. 评分体系
- **PMS**（盘前评分）：Gap / PMDollarVol / ATR / PrevDayTrend / Catalyst 加权。
- **IAS**（盘中评分）：Setup / RS / Activity / Liquidity / MarketAlignment / Room 加权。
- 评级：A(>=80) / B(70~79.99) / C(<70,仅记录不提示)

## 9. 数据库
SQLAlchemy 表：
- assets
- daily_stats
- watchlist_snapshots
- alerts
- alert_outcomes
- filter_rejections

## 10. 测试
```bash
pytest
```
覆盖：特征、三类 setup、过滤、评分、alert 生成、regime、时间窗口与容错。

## 11. 风险提示
- 本工具不构成投资建议。
- 本工具不自动下单。
- 本工具不保证收益。

## 12. 路线图 / TODO
- **V2**：加入表格模型排序（仍以规则引擎为主）。
- **V3**：加入 LLM 解释层（解释信号，不替代策略判定）。
- 加强 websocket 重连后状态回补。
- 增加 FastAPI 只读接口与更完整复盘图表。
