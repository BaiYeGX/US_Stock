# intraday-stock-scanner

面向 **2~5 个交易日多头波段** 的中文评分与执行监控系统（固定 12 只股票池）。

## 核心定位
- 只做多头，不做空。
- 不扫描全市场，只对固定股票池评分：
  `NVDA, AMD, QQQ, SMH, AVGO, TSM, AMZN, META, MSFT, GOOGL, SPY, SOXX`
- 日线为主、周线过滤、30分钟线只做辅助观察与执行监控。
- 数据源默认 Finnhub Free，优先免费可用。

## 当前是否实时？
- `market-loop`（非 `--mock`）+ 配置 `FINNHUB_API_KEY`：使用真实行情。
- `premarket-scan` 仍可用于本地模拟流程（用于开发验证）。

## 股票评选给分原则（摘要）
系统会先过 **硬过滤**，再计算 BuyScore / SellScore。

### 一、硬过滤（未通过则 BuyScore=0）
1. `C_t > SMA20_t`
2. `SMA5_t > SMA10_t > SMA20_t`
3. `WeeklyUpFlag=1`
4. `DaysToEarnings >= 4`
5. `AvgDollarVol20_t >= 100,000,000`
6. `Entry_t > Stop0_t`
7. `SuggestedPositionSizeShares >= 1`

### 二、BuyScore（0~100）
由 5 个子分数与惩罚项组成：
- MR 市场环境分
- TQ 趋势质量分
- PQ 回踩质量分
- TG 触发质量分
- TF 交易可行性分
- Penalty 惩罚项

阈值：
- `>=80` 才允许正式开仓（次日触发后执行）
- `70~79` 只允许最强一只且减半仓
- `<70` 不开仓

### 三、SellScore（0~100）
先检查硬退出：
- `L_t <= Stop0_t`（硬止损，盘中可触发）
- `C_t <= TrailStop_t`（趋势止损，默认收盘确认）
- 财报/持有天数相关强退规则

未命中硬退出时，计算：
- `SF_Trend / SF_RS / SF_Dist / SF_Exhaust / SF_Time / SF_Event`

## 动作语义
### 未持仓（CandidateAction）
- `MUST_WATCH_BUY` 次日重点买入监控
- `STRONG_WATCH_BUY` 次日强监控
- `BUY_SMALL_IF_TRIGGERED` 触发后小仓试买
- `NO_BUY` 不买

### 已持仓（PositionAction）
- `HOLD` 持有
- `REDUCE` 减仓
- `REDUCE_HARD` 明确减仓
- `STRONG_SELL` 强卖
- `MUST_SELL` 立刻清仓

## 数据与预算控制
- 去重后 symbol 仅 12 个，不重复请求。
- 缓存策略：
  - quote：20 秒
  - 30m candles：10 分钟
  - 日线：日内复用，收盘后刷新
  - 周线：日内一次
  - 财报：每日一次
- REST 与 WebSocket 分开统计，WS 消息不计入 REST 预算。

## 安装
```bash
cd intraday-stock-scanner
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

## 运行
```bash
# UI
python -m app.cli serve-ui --host 127.0.0.1 --port 8000

# 盘中循环（真实）
export FINNHUB_API_KEY=xxx
python -m app.cli market-loop --symbols NVDA,AMD,QQQ,SMH
```

## 测试
```bash
pytest -q
```
