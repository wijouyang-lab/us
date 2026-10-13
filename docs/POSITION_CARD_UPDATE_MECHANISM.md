# 50k 持仓卡片详细内容更新机制（只读静态分析）

> 方法：只读源码与已提交的线上数据文件；未运行任何 `.py`、未调用任何 API、未消耗 AI token。
> 仓库 HEAD：`7e3bda5`（2026-10-09）
> 调查时间：2026-10-09 17:35 (北京)

## 结论速览

**用户的直觉只对了一半。**

- **A 类（持仓专属字段）不是"买入时一次"**——价格和盈亏类字段现在是**每 15 分钟刷新**（挂了 dashboard-data 的 `--price-only`）；但 **`Entry_Price` / `Entry_Date` / `Stop_Loss` 确实买入后永久冻结**，其中 `Stop_Loss` 冻结是需要注意的一点。
- **B 类（评分/技术面）也不是"买入时一次"**——它**完全不由 50k 组合维护**，而是由 scan 的当日股票池"借给"卡片的。评分每日随 scan 重算；K 线/MA/MACD/KDJ 每次 dashboard-data 都重算，但**只有出现新的完整收盘日才实质变化**。
- **最大的隐藏风险**：B 类字段**依赖该 ticker 仍未掉出当日扫描池**。一旦掉出，评分环/技术面/K 线会从卡片上**整体消失**（降级为 `poscard-na`），而 A 类字段照常显示。

---

## 1. 卡片字段清单（分类 A / B）

来源：`app.js:390-445` `positionCard(p, s)`，其中 `p` = `DATA.portfolio.positions[]`，`s` = 按 ticker join 到的 `STOCKS[]` 条目（`app.js:520-525`）。

### A 类 —— 来自 `positions.csv`（50k 账本自持）

| 卡片显示 | 前端字段 | 来源列 |
|---|---|---|
| 股票代码 | `p.ticker` | Ticker |
| 当前价 | `p.current_price` | Current_Price |
| 盘前/盘后价（本次新增） | `p.extended_price` / `p.extended_time` | Extended_Price / Extended_Time |
| 股数 | `p.shares` | Shares |
| Entry | `p.entry_price` | Entry_Price |
| 市值 | `p.market_value` | Market_Value |
| 浮盈（$ / %） | `p.unrealized_pnl` / `p.unrealized_pnl_pct` | Unrealized_PnL / Unrealized_PnL_Pct |
| 权重 | `p.weight_pct` | Weight_Pct |
| 持有 N 天 | `p.holding_days` | **不在 CSV**，由 `build_portfolio` 派生 |
| 止损 | `p.stop_loss` | Stop_Loss |

### B 类 —— 来自 `stocks[]`（scan 产出，借给卡片）

| 卡片显示 | 前端字段 | 来源 |
|---|---|---|
| 公司名 | `s.n` | pending CSV `Name` |
| Final 评分环 | `s.s.final` | `final_score` ← pending CSV `Final_Score`（兜底 `Score`）|
| Quant / AI 徽章 | `s.s.quant` / `s.s.ai` | pending CSV `Quant_Score` / `AI_Score` |
| 板块标签 | `s.bucketLabel` | pending CSV `Tag` 映射 |
| 五条评分钟 | Quant / AI / Fundamental / Technical / Risk | pending CSV 同名五列 |
| K 线 | `sparkHtml(s)` | `ohlcv` ← **实时 `provider.daily_bars()`** |
| 技术底栏 MA20/MA50/MACD/KDJ | `s.m.*` | `technical` ← 实时 bars 计算 |
| 技术底栏 **RSI** | `s.m.rsi` | `technical.rsi` ← **优先 pending CSV `RSI` 列** ⚠️ |
| 技术底栏 **ATR%** | `s.m.atrPct` | **顶层 `s.atr_pct`** ← pending CSV `ATR_Pct` ⚠️ |

> ⚠️ 两个容易误判的点：卡片上的 **RSI 和 ATR% 都不是实时算的**，它们优先取 pending CSV 的列（`dashboard_export.py:1409` 与 `app.js:232`）。只有 MA20/MA50/KDJ/MACD/K 线是真每次从实时 K 线重算。

---

## 2. 每个字段的更新机制

### A 类（positions.csv）

`POSITION_COLUMNS`（`portfolio_50000.py:57-62`）：Portfolio_ID / Unit_ID / Ticker / Shares / Entry_Price / Entry_Date / Cost_Basis / Current_Price / Extended_Price / Extended_Time / Market_Value / Unrealized_PnL / Unrealized_PnL_Pct / Weight_Pct / Status / Stop_Loss / Recommendation_ID / Last_Update

| 字段 | 谁写 | 代码位置 | 频率 | 性质 |
|---|---|---|---|---|
| Entry_Price | `process_buys` | `:361` | **买入时一次，此后永不更新**（`Shares` 用 ROUND_DOWN 按推荐日 Open 算） | 🔒 冻结 |
| Entry_Date / Cost_Basis | `process_buys` | `:362-363` | 买入时一次 | 🔒 冻结 |
| Unit_ID / Recommendation_ID | `process_buys` | `:353,371` | 买入时一次 | 🔒 冻结 |
| **Stop_Loss** | `process_buys` | `:413`（值来自 `trade_history`） | **买入时一次，全文件再无第二个写入点** | 🔒 **冻结** ⚠️ |
| Shares / Status | `process_buys` → `process_sells` | `:363-369` / `:323-324` | 买卖时 | 事件驱动 |
| **Current_Price** | `process_buys`(初始化) → `mark_to_market` | `:399` | **每次 run**（review 全量 + `--price-only` 每 15 分钟）| ♻️ 活跃 |
| **Extended_Price / Extended_Time** | `mark_to_market` | `:406-407` | **每次 run**（同上） | ♻️ 活跃 |
| Market_Value | → `mark_to_market` | `:404` | 每次 run | ♻️ 活跃 |
| Unrealized_PnL / _Pct | → `mark_to_market` | `:400-401` | 每次 run | ♻️ 活跃 |
| Weight_Pct | `fill_weights` | `:409-416` | 每次 run | ♻️ 活跃 |
| Last_Update | `mark_to_market` | `:403` | 每次 run | ♻️ 活跃 |
| **Holding_Days** | `dashboard_export._days()` | `dashboard_export.py:2469,2502` | 每次 dashboard-data 重算 | ♻️ 派生 |

**Holding_Days 的特殊性**：它是 `max((asof − Entry_Date).days, 0)`，其中 **`asof` = `portfolio_50000_history.csv` 最后一行的 Date**。而 `--price-only` **不写 history**（只写 positions）→ 所以 `asof` 只由 **review 的每日全量 run** 推进 → **持有天数每天 +1，不是每 15 分钟 +1**。这是正确的。

**`--price-only` 到底改哪些列**（本次新增，`run()` `:442-478`）：
写入列 = `Current_Price`、`Extended_Price`、`Extended_Time`、`Market_Value`、`Unrealized_PnL`、`Unrealized_PnL_Pct`、`Weight_Pct`、`Last_Update`。
**不碰** Entry_* / Cost_Basis / Stop_Loss / Shares / Status / Unit_ID / Recommendation_ID，也**不写** transactions / history / meta。
✅ **实测验证**：price-only 前后 `transactions.csv` / `history.csv` 的 md5 完全一致。

### B 类（stocks[]）

`build_stocks(pending_rows, ...)`（`dashboard_export.py:1186`），`pending_rows` = **当前最新 pending CSV 的行**（scan 每日产出；无新 pending 时按既有逻辑复用上一版名单）。

| 字段 | 谁写 | 频率 |
|---|---|---|
| final / quant / ai / fund / tech / risk 六项评分 | **scan**（写入 pending CSV 同名列）| **每 scan 一次（每日）** |
| Name / Tag / Status / AI 六段 / Rec_Price | scan | 每 scan 一次 |
| **RSI**（`technical.rsi`） | pending CSV `RSI` 列优先 | **每 scan 一次**（非实时） |
| **ATR%** | pending CSV `ATR_Pct` | 每 scan 一次 |
| ohlcv（K 线） | `provider.daily_bars()` 实时拉取 | **每 dashboard-data（每 15 分钟）** |
| MA20 / MA50 / KDJ / MACD | 由上面的 bars 实时计算（`:1399-1407`）| 每 15 分钟；**仅当出现新的完整收盘日才实质变化** |
| price（卡片当前价走 `s.px`）| `provider.quote()` 实时 | 每 15 分钟 |

---

## 3. 数据流完整链路

```
[scan] 每天 21:00 北京（外部 cron 触发）────────────────────────────
   ├─ 写 us_stocks_pending_*.csv
   │     ├─ 评分：Final_Score / Quant_Score / AI_Score /
   │     │        Fundamental_Score / Technical_Score_25 / Risk_Liquidity_Score
   │     ├─ 技术快照：RSI / ATR_Pct / Stop_Loss / Status
   │     └─ AI 六段文本（透传，导出层不改写）
   ├─ 写 trade_history.csv（推荐事件 + Rec_Price + Stop_Loss 源头）
   └─ 写 quant_factor_snapshot.csv

      ↓ (needs: scan，scan 成功后自动触发)

[news-fetch] 每天 1 次 ──► dashboard/data/dashboard_news.json

      ↓

[review] 每天 22:23 UTC（= 次日 06:23 北京）─────────────────────
   ├─ review.py  更新 trade_history.csv 的终态裁决（Status/Exit_Date/Exit_Price）
   └─ portfolio_50000.py 全量 run()
        ├─ process_sells / process_buys（买卖、建仓、平仓）
        ├─ mark_to_market（盯市，含 Extended_Price）
        └─ 写完 4 个文件：positions / transactions / history / meta
           ⇒ **推进 asof ⇒ Holding_Days +1**

      ↓

[dashboard-data] 工作日每 15 分钟（*/15 * * * 1-5）───────────────
   ├─ Step「Refresh portfolio prices」
   │     python portfolio_50000.py --price-only --data-dir .
   │     ⇒ 只改 positions.csv 的 8 个价格/盈亏/权重列
   │     （continue-on-error: true — 失败不拖垮整体）
   └─ dashboard_export.py
        ├─ build_portfolio()  ← 读 positions/transactions/history/meta
        │     ⇒ portfolio.positions[]（含 extended_price/extended_time/holding_days）
        └─ build_stocks()     ← 读 pending CSV + 实时 daily_bars/quote
              ⇒ stocks[]（评分冻结于 scan，K线/MA/MACD/KDJ 实时）
   ⇒ 写 dashboard/data/dashboard_data.json

      ↓

[前端] index.html + app.js（每次打开/刷新）
   renderPortfolio() → positions[] 主表
                     → 按 ticker join STOCKS[]（有则全渲染，无则降级 poscard-na）
```

---

## 4. 直接回答

### A 类（持仓专属字段）

| 类别 | 字段 |
|---|---|
| 🔒 **真正冻结**（买入后永不变）| Entry_Price、Entry_Date、Cost_Basis、Unit_ID、Recommendation_ID、**Stop_Loss** |
| ♻️ **活跃**（每 15 分钟影子刷新）| Current_Price、**Extended_Price**、Extended_Time、Market_Value、Unrealized_PnL(_Pct)、Weight_Pct、Last_Update |
| ♻️ **每日 +1**（由 review 推进）| Holding_Days |
| ⚡ **事件驱动** | Shares、Status（仅在买卖时变）|

→ **A 类既不是"一次"，也不是"全部持续更新"**：价格盈亏类已做到 15 分钟级，**但 Entry 三件套与 Stop_Loss 是死的**。

### B 类（评分 / 技术面 / K 线）

| 类别 | 字段 | 何时变 |
|---|---|---|
| ♻️ **每 scan 重算（每日）** | Final / Quant / AI / Fundamental / Technical / Risk 六项评分、板块标签、AI 六段、Stop_Loss 展示值、**RSI**、**ATR%** | 每天 21:00 后 |
| ♻️ **每 15 分钟重算，但每日才实质变化** | K 线、MA20、MA50、KDJ、MACD | 新完整收盘日出现时（收盘后）|
| 🔒 **事件驱动** | recommendation_date（本次实测恒为买入日 2026-10-07）| 换推荐事件才变 |

→ **B 类不是"买入时一次"，是持续借用的外部数据**；但它有一个 A 类没有的脆弱性：**取决于 ticker 是否仍在当日扫描池**。

---

## 5. 线上实测对比（Risk of 实测：读已提交数据）

### positions.csv（`origin/main`，4 只 OPEN）

| Ticker | Entry_Date | Entry_Price | Current_Price | Extended_Price | Extended_Time | Last_Update |
|---|---|---|---|---|---|---|
| ADSK | 2026-10-07 | 231.42 | 233.60 | （空）| （空）| 2026-10-09 |
| ANET | 2026-10-07 | 211.30 | 210.97 | **215.00** | **10-09 04:20 ET** | 2026-10-09 |
| ISRG | 2026-10-07 | 405.07 | 415.41 | **415.52** | **10-09 04:01 ET** | 2026-10-09 |
| KR | 2026-10-07 | 59.27 | 61.41 | **61.26** | **10-09 04:01 ET** | 2026-10-09 |

- ✅ 四只 `Last_Update` 全部 **2026-10-09**（是本轮 dashboard-data 的 `--price-only` 写的）
- ✅ 四只 `Entry_Date` 全部 **2026-10-07**（买入日，永不更新，符合预期）
- ⚠️ ADSK 的 Extended_Price 为空 —— 该时点无盘前成交 bar，卡片那一行自动隐藏（兜底生效）

### 交叉印证：`stocks[]` 的实时价 == 我们写入的 Extended_Price

最新 `dashboard_data.json`（`7e3bda5`）中 `stocks[]` 共 46 只，4 只持仓**全部在池且 `status=Active`**：

| Ticker | final | quant | ai | price | price_source | ohlcv |
|---|---|---|---|---|---|---|
| ADSK | 69.9 | 81.0 | 44.0 | 233.60 | realtime_unverified | 180 |
| ANET | 73.9 | 85.0 | 48.0 | **215.00** | realtime | 180 |
| ISRG | 71.9 | 77.0 | 60.0 | **415.52** | realtime | 180 |
| KR | 72.5 | 74.0 | 69.0 | **61.26** | realtime | 180 |

ANET/ISRG/KR 的 `price` 与我们新写入的 Extended_Price **完全一致** —— 两条独立路径（dashboard_export 的 prepost 实时报价 vs 我们新增的 `--price-only`）互相印证成功。

### 昨日 vs 今日：评分没变，MA20 变了

对比 `67076ad`（10-08）与 `7e3bda5`（10-09）：

| Ticker | final | quant | ai | RSI | MA20 | last_bar_date |
|---|---|---|---|---|---|---|
| ADSK | 69.9 → **69.9** | 81→81 | 44→44 | 60.1 → **60.1** | 217.114 → **218.2135** ✅变 | 10-07 → **10-08** ✅变 |
| ANET | 73.9 → 73.9 | 85→85 | 48→48 | 67.3 → 67.3 | 202.666 → **203.765** ✅变 | 10-07 → 10-08 ✅变 |
| ISRG | 71.9 → 71.9 | 77→77 | 60→60 | 61.9 → 61.9 | 395.158 → **397.9055** ✅变 | 10-07 → 10-08 ✅变 |
| KR | 72.5 → 72.5 | 74→74 | 69→69 | 53.2 → 53.2 | 59.4045 → **59.6275** ✅变 | 10-07 → 10-08 ✅变 |

**这张表就是答案的证据**：
- 评分六项 + RSI **跨日完全没变** → 印证 RSI 走 pending CSV（`:1409` 优先取 CSV），而评分本身取决于上游 quant 因子与当日新闻。
- MA20 与最后一棒日期**每天都变** → 印证 K 线/均线是真的按新收盘日滚动重算。
- 同一天内（03 小时内两次 dashboard-data `3bcdeaf`→`7e3bda5`）**所有值都不变** → 印证"15 分钟重算"只是重跑，**没有新完整日线时结果一致**。

---

## 6. 用户的直觉是否正确？

| 直觉 | 判定 | 说明 |
|---|---|---|
| "卡片详细内容是买入时获取一次" | ❌ **不对** | 评分/技术/K 线来自 scan 池，每日重算；技术面甚至每 15 分钟重算 |
| "50k 自身字段只在买卖时更新" | ⚠️ **半对** | 价格盈亏类已改为 15 分钟刷新；但 **Entry 三件套 + Stop_Loss** 确实买入后冻结 |
| 隐含期待"持仓卡应与当日 scan 同步" | ✅ **基本成立** | 只要 ticker 还在池，评分/技术就是当日数据 |

**一句话**：卡片是「**A 类低价/高频 + B 类借来的当日快照**」的混合体。A 类里唯一"名不副实"的冻结项是 **Stop_Loss**——它在 `portfolio_50000.py` 里只有 `process_buys:413` 一个写入点，买入之后即便 review 调整了移动止损，卡片上的止损值也不会跟着动。这可能不符合"移动止损"的直觉，建议留意（如需修复属改动，本次未做）。

---

## 7. 需要注意的三个脆弱点（只列，未改）

1. **ticker 掉出扫描池 → 卡片整块降级**：`app.js:404-443` 中所有 B 类渲染都以 `s` 是否存在为条件。一旦某只持仓不再出现在当日 pending CSV，`s=null` → 评分环/五条评分钟/K 线/技术底栏**全部消失**，只剩 A 类七行。目前 4 只都在池，暂无此现象。
2. **Stop_Loss 永久冻结**（见上）。
3. **Holding_Days 依赖 history 的最后 Date**：若 review 某天没跑成功（无新 history 行），`asof` 不推进，持有天数会**停滞**；而 `--price-only` 明确不写 history，所以这个依赖是安全的但也不可逆地绑死了 review。
