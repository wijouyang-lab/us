# 盘中机械止损（Intraday Mechanical Stop-Loss）设计文档

> 状态：**设计稿（只读诊断 + 方案设计）**，未写实现代码，未改任何 `.py` / workflow，未 push。

## 0. 用户已确认的决策

| 项 | 决策 |
|---|---|
| 监控频率 | 盘中每 15 分钟（挂 `dashboard-data`） |
| 执行价 | 触发时的实时价 |
| AI 原因 | 下次 scan / review 补（**不在触发时调 AI**） |
| 时段 | 只监控常规时段 09:30–16:00 ET，不碰盘前盘后 |

---

## 1. 现状诊断

### 1.1 现有止损机制真相（意外发现）

> ⚠️ **关键发现**：`portfolio_50000.py` 的 `process_sells`（:278-332）**根本不实现"价格跌穿止损就卖"**。它只消费 Review 已在 `trade_history.csv` 里写好的**终态裁决**。

`process_sells` 逻辑（逐条）：
- 只处理 `Status == "OPEN"` 的持仓；
- 读对应推荐 `rec = recs.get(rid)`，要求 `rec["Status"] in TERMINAL_STATUSES`（如 `Stop_Loss_Hit`）；
- 卖出价 = `rec["Exit_Price"]`，卖出日 = `rec["Exit_Date"]`；
- 写入 `transactions` 的 `Reason = f"Review exit: {rec['Status']}"`（**模板串，无 AI 调用**）；
- fail-safe：若 `Exit_Price` / `Exit_Date` 缺失 → 不卖，等 Review 补齐（绝不猜测价格）。

也就是说，真正的"止损决策 + 执行价"发生在 **Review 盘后**（review.py:1825-1848），而不是 portfolio 模块。

### 1.2 Review 的止损触发逻辑

- 触发位置：review.py:1825-1848（`evaluate_stop_trigger` 在 :763-784）。
- 数据源：**当日完整 OHLC**（同一交易日真实 Low/Open/Close，来自 `df_hist_all`），不是实时价。
- 判定规则（`evaluate_stop_trigger`）：
  - `Low <= exec_stop` → `STOP_TRIGGERED`，执行价 `exit = Open`（若跳空低开 `Open < stop`）否则 `stop`；
  - `Low` 缺失但 `Close <= stop` → 确认触发，执行价取 `stop`；
  - `Stop_Loss` 无效 → 不触发，仅 warning；无可靠 OHLC → `DATA_MISSING` 不触发（**绝不猜价**）。
- AI 调用：触发本身**纯技术**（MA20/MA50 + ATR + MACD/KDJ），无 AI；`item["盈利/亏损原因"]`（:2036）是模板串 `"移动止损触发…"`，也非 AI。

### 1.3 现状汇总表

| 项 | 现在 |
|---|---|
| 触发时机 | Review 盘后（约 21:00 ET）**每日一次**，用当日完整 OHLC |
| 判断价 | 当日 **Low**（缺 Low 用 Close；跳空低开 `Open<stop` 取 Open） |
| 执行价 | Review 计算的 `Exit_Price`（= stop，或跳空取 Open） |
| AI 原因 | **无**（触发是技术判定；transaction `Reason` 是模板串，无 AI 调用） |
| 实现位置 | `process_sells` 只消费裁决；决策在 `review.py` |

> 一句话：**当前止损是"盘后日级、用当日 Low、技术判定、无 AI"**；用户要的是"盘中 15 分钟、用实时价、技术判定、AI 原因延后"。这是**新增一条独立触发链路**，不是改现有 Review 链路。

### 1.4 并发 / 写入机制（现状）

- `portfolio_50000.run()` 写文件：
  - 全量模式：写 `portfolio_50000_positions.csv` + `portfolio_50000_transactions.csv` + `portfolio_50000_history.csv` + `meta`；
  - `--price-only` 模式（:492-521，刚加）：**只写 `portfolio_50000_positions.csv`**（含 `Extended_Price`/`Extended_Time`），不碰交易/历史。
- **无 file lock**：所有写都是"读全量 → 改内存 → 整体覆盖写回"。靠 CI 的 `concurrency` 组（每个 workflow 一个 group + `cancel-in-progress:false`）保证同一时刻只有一个 run 操作文件。
- 现有 concurrency 组：
  - `dashboard-data.yml` → `dashboard-data-refresh`（每 15 分钟，工作日 24h，含 `--price-only` 步骤）；
  - `review.yml` → `us-stock-review`（盘后）；
  - `scan.yml` → `us-stock-scan`（盘中）。
- **冲突点**：`dashboard-data`（含 `--price-only` 写 positions）与 `review`（盘后写 positions/transactions/history）**时段不重叠**，目前无真并发。但若把盘中止损挂到 `dashboard-data` 并写入 `transactions.csv`，则与现有 `dashboard-data` 提交守卫（`git add` 仅含 `dashboard_data.json`、`last_run.*`、`portfolio_50000_positions.csv`，:145/:178）冲突——**守卫不会提交 transactions.csv**，需扩展。

### 1.5 `--price-only` 现状（可否扩展出 `--intraday-stop`）

- 取时价：`fetch_last_closes(open_tickers)`（:499，已存在），返回 `{TICKER: {current, extended, extended_time}}`；失败回退上一快照价（不编造）。
- 写字段：仅 positions（含 `Extended_Price`/`Extended_Time`）。
- **可扩展**：`fetch_last_closes` 已能提供实时 `current` 价；新增 `--intraday-stop` 只需在 `run()` 内复用它做"实时价 ≤ Stop_Loss"判定 + 写 SELL 流水。判定函数可复用 `evaluate_stop_trigger` 的"缺口取 Open"思想（但盘中实时无当日 Low，直接比 last price）。

### 1.6 trade_history / transactions 结构

`TRANSACTION_COLUMNS`（portfolio_50000.py:63-67）：
`Txn_ID, Date, Ticker, Action, Shares, Price, Amount, Realized_PnL, Cash_After, Reason, Recommendation_ID, Scan_Date, Portfolio_ID, Unit_ID`

- 止损卖出后写：`Action="SELL"`, `Price=执行价`, `Reason="Review exit: Stop_Loss_Hit"`, `Txn_ID=f"{rid}|SELL|{exit_date}"`（幂等去重）。
- **可加字段**：`Pending_Reason`（bool，触发时写 `True`，AI 补完原因后清 `False`）+ `Stop_Trigger_Time`（盘中触发时刻）+ `Stop_Method="Intraday"`。需在 `TRANSACTION_COLUMNS` 追加列（向后兼容：旧行缺列读为空串）。

### 1.7 前端现有止损显示

- 持仓卡片（app.js:1398-1400）：已显示 `止损价`(`s.stop`)、`距止损`(`stopPct`)、`止损方式`(`s.stopMethod`)。
- **无** `Stop_Touched` / "已盘中止损 / 等待 AI 原因" 类字段或徽章。需在 positions 或 dashboard_export 注入点补充。

---

## 2. 新方案设计

### 2.1 监控层（挂 `dashboard-data`，时段限制）

- 在 `dashboard-data.yml` 新增一步（与现有 `--price-only` 并列，`continue-on-error: true`）：
  `python portfolio_50000.py --intraday-stop --data-dir .`
- **时段守卫写在代码内**：`--intraday-stop` 启动时先算 ET 当前时间，若不在 09:30–16:00 ET 直接 `return`（不读价、不写文件）。这样复用 `dashboard-data` 的 24h/15min 触发，无需单独 workflow。
- DST 注意：GitHub runner 为 UTC，需用 `zoneinfo` 转 ET 并正确处理夏令时。

### 2.2 执行层（触发 + 写流水）

- 触发条件：`fetch_last_closes` 取到的实时 `current` 价 ≤ 持仓 `Stop_Loss`（仅 `Status=OPEN` 且 `Stop_Loss>0`）。
- 执行价：**触发时的实时价**（= 该次 `current`）。
- 缺口保护（沿用 Review 的稳健哲学）：取不到实时价 → 沿用上一快照、**不触发**（绝不猜价）。
- 写盘（复用 `process_sells` 的 SELL 落盘逻辑，但 Reason 占位）：
  - `transactions` 追加 `SELL` 行：`Price=实时价`, `Reason="Intraday stop (pending AI)"`, `Pending_Reason=True`, `Stop_Trigger_Time=<UTC>`, `Stop_Method="Intraday"`；
  - `positions` 对应行：`Status=CLOSED`, `Shares=0`, `Current_Price=实时价`, `Last_Update=今日`；
  - `Txn_ID` 用 `f"{rid}|SELL|INTRADAY|{today}"` 与 Review 的 `{rid}|SELL|{exit_date}` 区分，避免幂等冲突。

### 2.3 AI 原因层（延后，不在触发时调 AI）

- 触发时**绝不调 AI**（满足用户决策 + 与现有"触发无 AI"哲学一致）。
- 后续某次 scan（盘中）或 review（盘后）跑时，扫描 `transactions` 中 `Pending_Reason=True` 的 SELL 行：
  - 调 AI 分析"为什么跌"（结合当日行情/新闻/技术面）；
  - 将结论写入 `Reason`，并置 `Pending_Reason=False`。
- 幂等：已填 `Reason` 且 `Pending_Reason=False` 的行跳过。

### 2.4 并发处理（与 review 抢写 CSV 的风险 + 解法）

| 风险 | 分析 | 解法 |
|---|---|---|
| `dashboard-data` 提交守卫不含 `transactions.csv` | 盘中止损写的 SELL 流水**不会被提交**，丢失 | 扩展 `dashboard-data.yml` 的 `git add` 与 `grep -vE` 守卫，纳入 `portfolio_50000_transactions.csv` |
| 与 `review`（盘后写同批文件）真并发 | 时段不重叠（盘中 vs 盘后），无真并发 | 维持现状；如担心，可在 `intraday-stop` 内对 positions/transactions 整文件覆盖写（与现有"读全改内存写回"一致），不引入 file lock |
| `intraday-stop` 与同 job 的 `--price-only` 都写 positions | 同 job 顺序执行，无并发进程 | 顺序即可；建议 `intraday-stop` 放在 `--price-only` 之后、`dashboard_export` 之前 |
| review 盘后重跑覆盖盘中 SELL | review 读最新文件，见 `Status=CLOSED` 会跳过该持仓的卖出处理（幂等） | 确认 `process_sells` 对 `Status != OPEN` 直接 `continue`（:283），已天然安全 |

### 2.5 前端

- 新增徽章："🛑 已盘中止损 · 等待 AI 原因"（当 positions/transactions 有 `Pending_Reason=True` 且当日触发）。
- 显示 AI 原因：卡片补充 `AI 原因` 行（读 `Reason`，`Pending_Reason=False` 时展示；`True` 时显示"分析中…"）。
- 改动点：dashboard_export 注入 `pending_reason`/`stop_trigger_time`；app.js `positionCard` 渲染；app.css 增加徽章样式。

---

## 3. 改动半径

| 文件 | 改动 |
|---|---|
| `portfolio_50000.py` | 新增 `--intraday-stop` 模式：复用时价 + `Stop_Loss` 判定，写 SELL 流水（`Pending_Reason=True`）+ 关仓；`TRANSACTION_COLUMNS` 追加 `Pending_Reason`/`Stop_Trigger_Time`/`Stop_Method`；ET 时段守卫 |
| `dashboard-data.yml` | 新增 `--intraday-stop` 步骤（`continue-on-error`）；扩展提交守卫纳入 `portfolio_50000_transactions.csv` |
| `scan.py` / `review.py` | AI 原因回填：扫描 `Pending_Reason=True` 行，调 AI 写 `Reason` 并清标志（scan 盘中 / review 盘后均可） |
| 前端（`app.js`/`app.css`/`index.html`/`dashboard_export.py`） | 注入并展示"盘中止损"徽章 + AI 原因；positions 卡片补充 `Stop_Touched`/`Pending_Reason` 展示 |

> 不碰：`process_sells` 现有 Review 链路、`evaluate_stop_trigger`、`--price-only` 既有行为、监控 PID。

---

## 4. 实施顺序（每步可独立验证）

1. **`portfolio_50000.py`：`--intraday-stop` 核心**
   - 离线可测：注入 `prices`（实时价），断言"价 > stop 不卖 / 价 ≤ stop 卖且 `Pending_Reason=True` / 取不到价不触发"；
   - 单测覆盖 ET 时段守卫（09:30 前 / 16:00 后直接 return）。
2. **`dashboard-data.yml`：新步骤 + 提交守卫扩展**
   - 手动 `workflow_dispatch` 验证：`continue-on-error` 不拖垮整体；transactions.csv 被提交。
3. **scan/review：AI 原因回填**
   - 用 mock AI 测"读 Pending_Reason → 写 Reason → 清标志"幂等；确认不重复调 AI。
4. **前端徽章 + 原因显示**
   - 本地页面渲染验证（注入模拟 `pending_reason` 数据）。

---

## 5. 待用户确认的问题

1. **防"卖-买"循环**：盘中止损关仓后，当天（或未来 N 天）scan 是否会用新 Core 推荐**重新买入同一只**？现状 `process_buys` 只查 `open_tickers` 与 `{rid}|BUY` 幂等，关仓后该 ticker 不在 `open_tickers`，新推荐可再买。建议加**冷却期**（如 intraday 止损后 N 日禁止同 ticker 重买）。
2. **单日最多止损几只？** 是否设上限（如单日 ≤2 只）避免"一天清仓"。
3. **全部止损后当天是否停手？** 若 4 只同日全触，是否停止当日后续买入。
4. **执行价口径**：取"触发检查那一刻的 `current`"为执行价；但 15 分钟窗口内可能已跌更深——是否接受"执行价 ≠ 真实最低"，还是改为取窗口内最低（需缓存）。
5. **实时价来源**：`fetch_last_closes` 的 `current` 在 09:30–16:00 是否返回**常规时段实时 last price**（非上一收盘/盘前价）？需核对 `dashboard_export` 的 `_quote_*` 实现，确保盘中取的是活价。

---

## 6. 风险与限制

- **15 分钟延迟**：两次检查间价格可已远跌破 stop，执行价仅是该次检查时刻的价，实际浮亏可能大于 stop。模拟账户可接受；真实交易需承担滑点 + 时延敞口。
- **模拟 vs 真实**：`portfolio_50000` 是 **$50k 模拟账本**，SELL 仅为 CSV 流水，无券商下单。生产化需接入下单 API + 成交回执 + 滑点处理。
- **极端行情**：
  - 跳空低开（Open < stop）：09:30 首次检查即可捕获，执行价取 Open（沿用 Review 缺口逻辑）；
  - 熔断（Circuit Breaker）：交易暂停、实时价冻结，账本只记录最后价，无法成交——模拟层仅记账，需人工复核。
- **数据可靠性**：sandbox/CI 的 yfinance 常被 Yahoo 429 限流；取不到价时 `intraday-stop` **不触发**（与 Review `DATA_MISSING` 一致，安全优先）。
- **DST/时区**：ET 时段守卫必须正确处理夏令时，否则可能漏检（夏/冬令偏移 1h）或多检（盘前误触发）。
- **提交冲突**：扩展 `dashboard-data` 提交守卫后，务必同步改首次提交（:145）与重试提交（:178）两处 `git add` 与 `grep -vE`，否则非预期文件会被守卫拒绝、导致 push 失败。

---

## 7. 结论

现有系统**没有盘中实时止损**——止损是 Review 盘后一次性、用当日 Low、技术判定、无 AI 的链路。`portfolio_50000` 只消费裁决。用户要的盘中机械止损是**一条独立新增链路**，技术上可低风险落地：复用已有 `fetch_last_closes` 取实时价、`process_sells` 的落盘范式、`dashboard-data` 的 15 分钟触发，并把 AI 原因延后到 scan/review 回填。主要工作量在 **`dashboard-data.yml` 提交守卫扩展**与**防卖-买循环冷却期**（待用户定夺）。

---

## 已知缺口（本期未实现）

> 记录时间：2026-10-09 晚
> 原因：本期铁律禁止改 `process_buys`，故买入侧守卫未做。

### 缺口 1：决策 1 买入侧（同日不重买）

**决策**：止损后同日不重买同一只（冷却 1 天）。
**现状**：只实现了卖出侧（`_run_intraday_stop` 正确卖出并关仓），但买入侧未做。
**后果**：09:45 止损卖出的股票，如果 21:00 scan 重新推荐 → 22:00 review 会重新买入，形成"卖-买循环"。
**修复方案**：
- `portfolio_50000_positions.csv` 的 CLOSED 行加字段 `Cooldown_Until`（= 止损日 +1 天）
- `process_buys` 里加检查：`if ticker in cooldown_tickers and today <= cooldown_until: skip`
- 改动约 10 行
**实施时机**：周末

### 缺口 2：决策 3 买入侧（全清仓停手）

**决策**：全部止损后当天不再买。
**现状**：同缺口 1，只做卖出侧。
**后果**：全部止损后，如果 scan 有推荐，review 仍会买入。
**修复方案**：`process_buys` 里加：`if all_positions_closed_today: skip`
**实施时机**：周末

### 缺口 3：AI 原因回填

**决策**：止损时写 `Pending_Reason=True`，由 scan/review 补 AI 分析。
**现状**：`Pending_Reason=True` 已落库，但回填逻辑未做。
**后果**：前端显示的 Reason 是固定文案 "Intraday Stop Loss"，无 AI 解释。
**修复方案**：
- `scan.py` 或 `review.py` 加：读 `transactions.csv` 里 `Pending_Reason=True` 的记录
- 批量调 AI 分析"为什么跌"（一次调用，不逐条）
- 写入 `Reason` 字段 + 清 `Pending_Reason`
**实施时机**：周末

### 缺口 4：7 天冷却期（决策 B）

**决策**：止损后 7 天内，该 Ticker 不买、不进 AI 输入、不进候选。
**实现要点**：
- 止损时写 `Cooldown_Until = 止损日 + 7 天`
- `process_buys` 冷却期内跳过
- `build_ai_input` 冷却期内不进入（零 token）
- `scan.py` 严筛排除冷却期内的 Ticker
**实施时机**：周末（依赖缺口 1/2 的买入侧守卫）

---

## 周末实施顺序（建议）

按优先级：

| # | 任务 | 风险 | 理由 |
|---|---|---|---|
| 1 | quant-research 挂 `needs: scan` | 低 | 不做白等 70 天 |
| 2 | 激活 flag（`ENABLE_TARGET_FILE=1`） | 低 | AI 目标持仓上线 |
| 3 | 缺口 1 + 2 + 4（买入侧冷却：同日不重买 + 全清仓停手 + 7 天冷却期） | 中 | 堵"卖-买循环" |
| 4 | 缺口 3（AI 原因回填） | 中 | 止损说明完整 |
| 5 | 持仓强制进池（防降级） | 中 | 前次调查发现 |

**执行顺序**：1 → 2 → 3 → 4 → 5。每项独立 commit + push，逐项验证。
