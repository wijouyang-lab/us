# 盘中 Sparkline 设计文档（Intraday Sparkline Design）

> 生成于 2026-10-13 · 只读 / 设计阶段 · **今天不动代码**
> 目标：在不改动现有日线 K 线（已确认见下）的前提下，新增一个独立的"当日盘中 sparkline"。

---

## 1. 目标

在持仓卡片上**保留现有日线 K 线**，新增一个独立的"当日盘中 sparkline"——让用户一眼分清：

- **日线趋势**（现有 `stock.ohlcv` → `sparkHtml` / `drawSpark`，每日 `close` 序列）
- **今日盘中走势**（新方案，15 分钟粒度累积）

> 背景事实（来自只读审计 `dashboard_export.py` + `app.js`）：
> - 现有 K 线 = `daily_bars()` 拉取的 **1d 日线**，经 `_filter_completed` 剔除未完成当日棒，最后一根通常是**昨日收盘**（`provider.daily_bars` L1306/L1308，`last_completed_regular_date_us` L276-281）。
> - 盘中实时价走的是**另一通道** `provider.quote()` 的 `realtime`（`current_price`/`price_source`，build_stocks L1323-1344），与日线 sparkline 不混用。
> - 新 sparkline 正是要补上"盘中"这一缺失视角。

---

## 2. 数据源（关键决策）

三个选项，各列代价：

| 选项 | 数据源 | 代价 |
|------|--------|------|
| **A** | `yfinance` 1m：`yf.Ticker(t).history(period="1d", interval="1m", prepost=True)` | 每只股票 × 每 15 分钟一次 yfinance 调用；**可能限流**（沙箱已实测 yfinance / stooq 网络被阻断，CI 出口才稳）；prepost 逻辑复杂；分钟数据噪声大 |
| **B** | 累积实时价：每 15 分钟 `dashboard-data` 跑时，把 `current_price` 追加到 `intraday_prices.json` | 需**新存储文件**；需**跨天清理**旧数据；需新步骤保证顺序写盘 |
| **C** | 简化：只显示"较昨收涨跌"：用现有字段 `current_price` vs `ohlcv[-1].close` | **零新数据、零新调用**；但**不是走势图**（无形态，只一个数字/箭头），不满足"让用户看盘中走势"的目标 |

**推荐：B** —— 理由：

- 不依赖 yfinance 分钟数据（避免限流与网络不确定性）；
- 数据完全可控（全部来自已抓取的 `current_price`，与现有实时价口径一致）；
- 每天清理，无历史包袱；
- 15 分钟粒度对"盘中走势"够用（一天约 26 个点，足够看出方向）。

---

## 3. 数据流（方案 B 具体）

```
dashboard-data 每 15 分钟跑
   ↓
fetch_last_closes 已拿到 current_price（现成，无需新抓）
   ↓
新增步骤：追加到 dashboard/data/intraday_prices.json
   结构：
   {
     "date": "2026-10-13",
     "prices": {
       "ADSK": [[ "09:45", 233.77 ], [ "10:00", 234.10 ], ...]
     }
   }
   ↓
跨天时清空昨日数据（保留当日）
   ↓
dashboard_export 读入，注入 stocks[].day_prices
   ↓
前端 positionCard 新增 renderIntradaySpark() 画小图
```

要点：
- **累加而非覆盖**：每次 `dashboard-data` 运行追加当根 `[time, price]`，不重写全量。
- **跨天切换**：写入前比对 `date` 字段；若 `date != 今天` → 重置为 `{"date": 今天, "prices": {}}`，丢弃昨日。
- **幂等**：同一 15 分钟窗口若重复运行（CI 重试），按时间键去重（同 `time` 覆盖而非追加两条）。

---

## 4. 前端展示

- **位置**：卡片顶部"当前价"**下方**（与日线 K 线区分开，避免混淆）。
- **尺寸**：小图，约 **60px 高 × 200px 宽**。
- **配色**（与全站涨跌惯例一致）：
  - 当日累计涨 → **红**
  - 当日累计跌 → **绿**
  - 平 → **灰**
- **hover**：显示"最高 / 最低 / 当前"。

> 累计涨跌基准 = 当日第一根 `day_prices` 价格（非昨收；若需与昨收对比，可额外取 `ohlcv[-1].close` 作参考线，但默认以当日开盘序列起点为基准）。

---

## 5. 边界

- **无当日数据**（刚开盘 / 第一根尚未写入）→ 显示"盘中数据积累中"。
- **`intraday_prices.json` 缺文件** → 隐藏该小图，**不崩**（前端 `day_prices` 缺失即 `style.display='none'` 或跳过渲染，对齐现有 `market_indicators` 哨兵式隐藏做法）。
- **跨日** → 自动清空昨日（见 §3 跨天切换）。

---

## 6. 改动半径

| 文件 | 改动 |
|------|------|
| `dashboard_export.py` | 追加 `intraday_prices` 读取并注入 `stocks[].day_prices` |
| `dashboard-data.yml` | 新增"追加实时价"步骤（或并入现有 price-only 步骤） |
| `app.js` | 新增 `renderIntradaySpark()` + 在 `positionCard` 调用 |
| `app.css` | 新增 `.pos-intraday` 样式 |
| `tests/` | 新增 3-5 个测试（缺文件→隐藏 / 当日累积中 / 涨红跌绿 / 跨天清空 / 注入字段存在） |

---

## 7. 时机

**验证后（明天 21:30 后）再动手** —— 今天不动代码。
（理由：明天 06:23 review 双跑 + 21:00 scan/macro 首次跑为优先事项；本功能属于新增展示，不阻塞任何现有流程，等主线稳定后再实施。）

---

## 8. 待确认问题

1. 数据源选 **A / B / C**？（本设计推荐 **B**）
2. 盘中 sparkline 位置：**当前价下方** / **日线 K 线下方**？（本设计默认"当前价下方"）
3. 15 分钟粒度够吗？（本设计认为够；若需更细可改 5 分钟，但调用次数 ×3）

---

## 铁律

- ✅ 只写文档
- ❌ 不碰仓库（未改任何 `.py` / `.yml` / `.js` / `.css`）
- ❌ 不 push
