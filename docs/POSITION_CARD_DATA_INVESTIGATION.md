# $50k 持仓能否渲染成 Core 式详细卡片 —— 数据调查报告

> 调查日期：2026-10-09（只读，未改代码）
> 结论一句话：**能**。4 只持仓在 `stocks`（旧 pool）里都有完整详细数据（评分/技术面/量化拆解/AI/OHLCV），前端按 ticker 合并即可。

---

## 1. pool（`stocks`）里是否有 4 只持仓的详细数据

`dashboard_data.json` 顶层键里没有叫 `pool` 的字段，旧 core/obs 卡片的数据源是 **`stocks`**（数组，46 只）。

| 持仓 ticker | 在 stocks 里？ | bucket | tag_raw | final_score |
|---|---|---|---|---|
| ADSK | ✅ 有 | Core | Core_Dragon | 69.9 |
| ANET | ✅ 有 | Core | Core_Dragon | 73.9 |
| ISRG | ✅ 有 | Core | Core_Dragon | 71.9 |
| KR | ✅ 有 | Core | Core_Dragon | 72.5 |

**结论**：4 只持仓全部在 `stocks` 里，且都是 `bucket=Core`，带完整评分/技术面/AI/K线数据。

---

## 2. 字段清单对比

### `stocks[]` 单条字段（以 ADSK 为例，完整）

```
ticker, name, bucket, tag_raw, recommendation_id, recommendation_date,
rec_price, recommendation_tag, ai_snapshot_id, ai_snapshot_date,
price, price_source, current_price, current_price_updated_at,
pending_price, pending_price_source, prev_close,
change_1d, change_1d_source, pending_change_1d, pending_change_1d_source,
final_score, quant_score, ai_score, fundamental_score, technical_score, risk_liquidity_score,   ← 评分
rsi, atr_pct, stop_loss, stop_method,
pe_ttm, pe_forward, pb, eps_ttm, roe, revenue_growth, earnings_growth, profit_margin, market_cap,   ← 基本面
market_regime, vix, status, technical_date, scan_date, avg_dollar_volume_20d,
sector_rs_20d_pct, bias, event_score, technical_confirmations, technical_confirmation_signals,
ai: {industry_logic, news_cn, premarket_conclusion, catalysts, risks, invalidation},               ← AI 六段
technical: {ma20, ma50, kdj_j, kdj_k, kdj_d, macd_hist, macd, macd_signal, atr_abs, atr_pct_computed, rsi, ...},  ← 技术面
ohlcv: [ {date, open, high, low, close, volume}, ... ],                                              ← K线
ohlcv_status
```

### `portfolio.positions[]` 单条字段（14 个）

```
portfolio_id, unit_id, ticker, shares, entry_price, entry_date,
cost_basis, current_price, market_value, unrealized_pnl,
unrealized_pnl_pct, weight_pct, stop_loss, holding_days
```

### 对比结论

| 维度 | stocks[] | portfolio.positions[] |
|---|---|---|
| 评分（final/quant/ai/fund/tech/risk） | ✅ | ❌ 缺 |
| 技术面（MA20/MA50/KDJ/MACD/ATR/RSI） | ✅（`technical` 子对象 + 顶层 rsi/atr_pct） | ❌ 缺 |
| AI 六段 | ✅（`ai` 子对象） | ❌ 缺 |
| K线 OHLCV | ✅（`ohlcv`） | ❌ 缺 |
| 基本面（PE/PB/ROE/增速…） | ✅ | ❌ 缺 |
| 持仓专属（shares/entry_price/cost_basis/市值/盈亏/权重/持有天数） | ❌ 缺 | ✅ |
| ticker / current_price / stop_loss | ✅（stop_loss=228.0 是 scan 时点止损） | ✅（stop_loss=$214.76 是当前移动止损，**两者不同**） |

**共享键**只有 `ticker` 和 `current_price`（数值一致）。`stop_loss` 两边都有但**值不同**——positions 里是**当前生效的移动止损**（$214.76），stocks 里是 scan 时点止损（228.0）。做卡片时**应优先取 positions 的 stop_loss**。

---

## 3. 能否合并成「详细卡片」—— ✅ 能

合并方式：**以 `portfolio.positions[]` 为主表，按 `ticker` 去 `stocks[]` 里查详细数据**。

```js
positions.forEach(function (pos) {
  var detail = STOCKS_BY_TICKER[pos.ticker];   // stocks[] 建索引
  // 卡片 = 持仓专属字段(pos.shares/entry_price/pnl/weight/holding_days)
  //      + 详细字段(detail.final_score/quant_score/ai_score/technical/ai/ohlcv)
});
```

这是纯前端 join，**后端（dashboard_export.py）已经同时输出了 `stocks` 和 `portfolio.positions`，无需改后端**。

---

## 4. 缺什么、从哪来

| 缺口 | 来源 | 说明 |
|---|---|---|
| 评分/技术/AI/K线 | `stocks[]`（已存在） | 按 ticker join 即可 |
| 持仓专属字段 | `portfolio.positions[]`（已存在） | 卡片主数据 |
| （无） | — | **没有任何数据缺口**，全部现成 |

唯一需注意的小差异：`stop_loss` 两边值不同，卡片应显示 positions 的（当前移动止损），而非 stocks 的（scan 时点止损）。

---

## 5. 前端改动方向（只列，不实施）

1. **复用旧 `coreCard` 的渲染结构**（评分环形图 `ring()` + 量化拆解进度条 `scoreRow()` + 技术面 foot + K线 spark）。
2. 数据源从「`STOCKS.filter(bucket)`」改为「`portfolio.positions[]` 逐条 join `STOCKS`」。
3. 卡片顶部/底部**追加持仓专属行**：股数、Entry_Price、市值、未实现盈亏（红涨绿跌）、权重、持有天数。
4. `stop_loss` 用 positions 的值。
5. 可选：点击卡片仍走 `openDetail(ticker)`（该函数与 `stocks[]` 数据仍在，天然可用，只是之前我删了 `.pcard,.ocard` 的 click 绑定）。

**关键前提（已验证）**：`stocks[]` 里 4 只持仓都还是 `bucket=Core`、带 `Core_Dragon` tag，详细字段完整——旧卡片要的字段一样不缺，只是换了个「按持仓 ticker 取」的入口。

---

## 附：速查

| 文件/字段 | 位置 |
|---|---|
| `stocks[]`（旧 pool，46 只，含 4 持仓） | dashboard_data.json 顶层 `stocks` |
| `portfolio.positions[]`（14 字段） | dashboard_data.json 顶层 `portfolio.positions` |
| 旧 coreCard/obsCard（已删） | 原 app.js `coreCard()` / `renderPools()`，字段用 `s.s.*` `s.m.*` `s.ohlcv` |
| `STOCKS` 前端归一化 | app.js `normalize()`（把 `stocks[]` 映射成 `s.t/s.n/s.s/s.m/s.ohlcv` 等） |
