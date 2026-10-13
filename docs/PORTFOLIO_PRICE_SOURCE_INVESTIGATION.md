# 50k 持仓价格数据来源调查（只读）

> 调查日期：2026-10-09
> 结论一句话：**50k 组合的 `Current_Price` 是纯 EOD 常规收盘价，收盘后不会自动更新为盘前 / 盘后 / 夜盘价。**
> 铁律：只读调查，未改任何代码、未 push / rebase、未触碰监控。

---

## 1. 50k `Current_Price` 的来源（文件 + 行号）

写入方与读取方是**两个不同文件**，必须分开看：

### 1.1 唯一定价写入方：`portfolio_50000.py`

| 环节 | 位置 | 代码 / 行为 |
|------|------|-------------|
| 取价函数 `fetch_last_closes` | `portfolio_50000.py:140-162` | `hist = yf.Ticker(t).history(period="5d", auto_adjust=False)` → 取 `hist["Close"].dropna().iloc[-1]`（最近一个完整交易日收盘价） |
| 盯市写回 `mark_to_market` | `portfolio_50000.py:381-406`（关键行 399） | `p["Current_Price"] = str(money(px))` —— 把取到的价写入 OPEN 仓位的 `Current_Price` |
| 主流程 `run` | `portfolio_50000.py:465` | `prices = {} if offline else fetch_last_closes(open_tickers)` |
| 取价失败回退 | `portfolio_50000.py:392-395` | 取不到 → 沿用上一快照 `Current_Price`；再缺失 → 用成本价（**绝不编造**） |

要点：
- `yf.Ticker(t).history(period="5d", ...)` **未传 `prepost` 参数** → 走 yfinance 默认 `prepost=False` → 只返回**常规时段（09:30–16:00 ET）日线**。`.iloc[-1]` 是最近一个完整常规交易日的 `Close`。
- 这是**日线收盘价**，不是 `fast_info["last_price"]`，也不是 `info` 里的实时快照。

### 1.2 前端展示的读取方：`dashboard_export.py::build_portfolio`

| 环节 | 位置 | 代码 / 行为 |
|------|------|-------------|
| 导出函数 `build_portfolio` | `dashboard_export.py:2445` | docstring 明确：「只读消费 portfolio_50000_*.csv —— 本导出层**绝不写回、绝不重算盈亏**」 |
| 价格透传 | `dashboard_export.py:2493` | `"current_price": round_num(parse_num(r.get("Current_Price")), 2)` —— **直接读 CSV 里的 `Current_Price` 字段**，不发起任何行情请求 |
| 调用检查 | `dashboard_export.py` 全文 grep | 无 `import portfolio_50000`、无 `portfolio_50000.run()` 调用 —— 导出层不会触发重新取价 |

> 注意：`dashboard_export.py:572-619` 那段**盘前/盘后实时价逻辑**（`postMarketPrice` / `preMarketPrice` / `prepost=True` 1m / `fast_info.last_price`）是给 **scan 股票池（事件池）的 `current_price`** 用的，**与 50k 组合无关**。50k 组合走的是上面第 2493 行的纯 CSV 透传。

---

## 2. 分类：是 EOD / 盘前盘后 / 夜盘？

**结论：A. 纯 EOD（只用常规收盘价）。**

| 类别 | 含义 | 50k 是否符合 |
|------|------|--------------|
| A. 纯 EOD | 只用常规时段收盘价 | ✅ **符合**（`history(period="5d").Close.iloc[-1]`，`prepost=False` 默认） |
| B. 含盘前盘后 | 用 `last_price` / `fast_info` / `prepost=True` 分钟线 | ❌ 不符合（50k 没用这些） |
| C. 含夜盘 | 用其他盘后/夜盘源 | ❌ 不符合（无任何夜盘数据源） |

区分依据（代码事实）：
- `portfolio_50000.py:151` 调用 `yf.Ticker(t).history(period="5d", auto_adjust=False)`，**没有** `prepost=True` → yfinance 默认 `prepost=False`，只含 09:30–16:00 ET 常规时段。
- 没有任何 `fast_info` / `last_price` / `preMarketPrice` / `postMarketPrice` 调用出现在 `portfolio_50000.py` 中（grep 全仓库仅在 `review.py` / `dashboard_export.py` 股票池逻辑 / `scan.py` 出现 `fast_info`，与 50k 无关）。
- 全仓库 grep `overnight` 在 `portfolio_50000.py` 中无命中（仅 `scan.py` 的「昨收后新消息」统计用字面量，与价格无关）。

---

## 3. 刷新频率（谁写、什么时候写）

| 问题 | 答案 | 证据 |
|------|------|------|
| 谁写 `Current_Price`？ | **只有** `portfolio_50000.py` 的 `run()`（写回 `portfolio_50000_positions.csv`） | `portfolio_50000.py:399`、`write_csv_rows(... POSITIONS_FILE ...)`（第 477 行） |
| 谁触发它？ | **只有** `.github/workflows/review.yml`（美股盘后复盘） | `review.yml:57`：`python portfolio_50000.py --data-dir .` |
| 什么时候跑？ | 周一到周五 `cron: '23 22 * * 1-5'` = **22:00 UTC = 北京次日 06:00**（盘后） | `review.yml:8` 注释：「Review: Tue–Sat 06:00 Beijing = Mon–Fri 22:00 UTC」 |
| scan.yml 会更新 50k 定价吗？ | ❌ 不会 | `scan.yml` 中 grep `portfolio_50000` 无命中 |
| dashboard-data（每 15 分钟）会更新 50k 定价吗？ | ❌ 不会 | `dashboard-data.yml` 只调 `dashboard_export.py`（只读 CSV 透传，第 92 行）+ `fetch_runtimes.py`；不调 `portfolio_50000.py`（grep 确认无命中）。它每 15 分钟刷新时读的是 CSV 里**上次 review 落盘的**那份 `Current_Price` |

更新节奏总结：
- 50k 持仓的 `Current_Price` **每天只在盘后复盘（review.yml）跑一次时刷新一次**，取当日常规收盘价。
- 之后无论 dashboard 每 15 分钟刷新多少次（`dashboard-data.yml`），`build_portfolio` 都只是把 CSV 里那一份已落盘的 EOD 收盘价读出来展示，**价格不再变化**。
- 若某天 review 未跑（周末 / 失败 / 手动跳过），`mark_to_market` 的回退逻辑（第 392-395 行）会沿用上一快照价或成本价，同样**不会**去抓盘前/盘后/夜盘。

---

## 4. 与 scan 盘前数据的对比

| 维度 | 50k 组合 `Current_Price` | scan `Premarket_Price` |
|------|--------------------------|------------------------|
| 来源函数 | `portfolio_50000.py::fetch_last_closes`（`history(period="5d").Close`） | `scan.py::get_premarket_snapshot_batch`（第 793-807 行） |
| 数据源 / 参数 | `yf.Ticker.history`，`prepost` 默认 `False` | `yf.download(..., prepost=True, auto_adjust=False)` |
| 价格性质 | **常规时段收盘价（EOD）** | **盘前实时成交价**（04:00–09:30 ET） |
| 写入位置 | `portfolio_50000_positions.csv`（`Current_Price`） | `us_stocks_pending_*.csv` 等（`Premarket_Price` / `Premarket_AsOf_ET` / `Price_Reference`） |
| 触发时机 | 盘后复盘（review.yml，22:00 UTC） | 盘前扫描（scan，SCAN_RUN_MODE=="PREMARKET"，见 `scan.py:852/879`） |
| 时间戳 | `Last_Update`（日期粒度，如 `2026-10-08`） | `Premarket_AsOf_ET`（精确到分钟）+ `Price_Reference` 标记 |
| 是否同一时点 | ❌ 否 | 与 50k 不同日/不同时段 |

关键差异：
- **时点不一致**：50k 的 `Current_Price` 是上一个**完整常规交易日收盘（16:00 ET）**；scan 的 `Premarket_Price` 是盘前窗口（04:00–09:30 ET）的实时价。两者天然不是同一时刻。
- **盘前跳空时差距明显**：例如隔夜重大利好，盘前价已大涨，但 50k 的 `Current_Price` 仍显示上一交易日收盘，直到当晚 review 跑完才更新为当天收盘（注意：当天收盘仍不含盘前涨幅的"实时"——收盘价是当天 16:00 的成交，而非盘前价）。
- **21:00 北京 = 13:00 UTC = 09:00 ET（盘前）**：此时 scan 触发会写 `Premarket_Price`（`SCAN_RUN_MODE=="PREMARKET"`），但 scan **不调用** `portfolio_50000.py`，所以 50k 的 `Current_Price` **不会**被 scan 的盘前数据刷新，仍停留在上次 review 的 EOD 收盘价。
- `Price_Reference` 字段（`scan.py`）会在盘前会话把参考价标记为 `PREMARKET`、否则 `REGULAR_CLOSE`；50k 组合**没有**这个字段，永远指向 EOD 收盘。

---

## 5. 用户的答案：收盘后是否爬取盘前 / 盘后 / 夜盘？

**答：不会。**

逐项回答：

| 时段 | 50k `Current_Price` 是否会自动更新为该时段价？ |
|------|-----------------------------------------------|
| 盘后（16:00–20:00 ET / 盘后交易） | ❌ 不会。`portfolio_50000.py` 用 `history(prepost=False)` 取常规收盘价，不含盘后；且 review 只在 22:00 UTC（已接近盘后末端）跑一次，取的是当日常规收盘。 |
| 夜盘（overnight，如 futures/24h 源） | ❌ 不会。仓库内无任何夜盘数据源接 50k。 |
| 次日盘前（04:00–09:30 ET） | ❌ 不会。此时只有 scan 写 `Premarket_Price`；scan 不触发 `portfolio_50000.py`，dashboard 每 15 分钟刷新也只是透传 CSV 旧值。 |

准确机制：
- 50k 的 `Current_Price` **仅在盘后复盘（review.yml，周一到周五 ~06:00 北京）由 `fetch_last_closes` 抓取一次常规收盘价并落盘**。
- 之后无论 dashboard 多少次刷新（每 15 分钟）、无论是否处于盘后/夜盘/盘前时段，它读的都是 CSV 里那份**已落盘的 EOD 收盘价**——不会变，也**不会**去抓盘前/盘后/夜盘。
- 因此「收盘后自动更新为盘前/盘后/夜盘价」这一预期**不成立**：50k 组合展示的始终是最近一次盘后复盘的常规收盘价快照。

---

## 附：关键代码定位速查

- `portfolio_50000.py:140-162` — `fetch_last_closes`（取价，EOD Close，`prepost` 默认 False）
- `portfolio_50000.py:381-406` / `:399` — `mark_to_market`（写 `Current_Price`）
- `portfolio_50000.py:465` — `run` 调用取价
- `portfolio_50000.py:392-395` — 取价失败回退（沿用快照 / 成本价）
- `dashboard_export.py:2445` — `build_portfolio`（只读 CSV）
- `dashboard_export.py:2493` — `current_price` 透传 `r.get("Current_Price")`
- `dashboard_export.py:572-619` — 股票池实时价（含盘前/盘后，**非 50k 组合**）
- `.github/workflows/review.yml:8,57` — 50k 定价唯一触发方（盘后）
- `.github/workflows/dashboard-data.yml:16,92` — 每 15 分钟只调导出层，不刷新 50k 定价
- `scan.py:793-807,852-879,861` — scan `Premarket_Price`（盘前价，独立于 50k）
