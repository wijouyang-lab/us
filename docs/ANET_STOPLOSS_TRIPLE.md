# ANET 三个止损价溯源报告（只读调查）

> 调查对象：同一仓位 ANET（Unit U002）在三个界面出现的不同止损价
> - 持仓卡片：`$197.69`
> - 详情页：`209.36`
> - review 日志：`210.24`（且 `Trigger=STOP_TRIGGERED`）
>
> 调查方式：纯只读（grep / Read / `git show` 历史比对），未改动任何代码、未 push、未碰监控。

---

## 0. 结论速览

| 数字 | 出处文件 | 性质 | 谁"用它" |
|------|----------|------|----------|
| **197.69** | `portfolio_50000_positions.csv` 的 `Stop_Loss` 列 | 建仓时的**原始扫描止损**（"ATR初始保护"），建仓后**从未再调整** | 50k 账本的**盘中机械止损**（`≤197.69` 才卖）；详情页/推荐系统都不读它 |
| **209.36** | `trade_history.csv` 的 `Stop_Loss` 列（被 review 移动止损**抬高后落库**的值） | review 跟踪系统的**存储态移动止损** | 详情页（读 `trade_history`）展示它 |
| **210.24** | `review.py` 当次会话**实时重算**的 `exec_stop` | review 跟踪系统**当次判定用的移动止损**（比落库的 209.36 又高了一点） | review 用它判定 `STOP_TRIGGERED`，并据其写出 `Exit_Price` 驱动账本实际卖出 |

**"实际执行用的"止损价 = 210.24 这条链路（派生出的 `Exit_Price`）**，不是卡片上的 197.69。
理由见第 2 节。卡片的 197.69 是一个**已被 review 移动止损逻辑架空、自建仓后从未跟随抬升的陈旧值**。

---

## 1. 三个数字各自的来源（文件 + 行号）

### 1.1 卡片的 197.69 — 账本原始止损，冻结态

- **落库位置**：`portfolio_50000_positions.csv` → ANET 行 `Stop_Loss` 列（第 16 列），值 `$197.69`。
- **写入逻辑**：`portfolio_50000.py` 建仓时（BUY）把推荐记录的止损原样写入：
  - `portfolio_50000.py:552` → `"Stop_Loss": rec["Stop_Loss"]`
  - `rec["Stop_Loss"]` 来自推荐（trade_history）在建仓那一刻的取值。
- **前端渲染**：`dashboard_export.py:2645` 仅**透传**该列（`"stop_loss": clean_text(r.get("Stop_Loss"))`），不重算；`app.js:441` 持仓卡片 `'<span class="pmk">止损</span><b>' + esc(p.stop_loss || NA)` 直接读它。
- **历史佐证**：`git show` 比对多个历史 `portfolio_50000_positions.csv`，ANET 的 `Stop_Loss` **始终是 197.69**，从未变更 → 账本止损自建仓（2026-10-07）起冻结。
- **原始含义**：commit `82d1cc7`（ANET 入表时）`trade_history.csv` 中 ANET 的 `Stop_Loss=$197.69`，`Stop_Method="ATR初始保护"`。验算：入场价 `211.30`，`ATR%≈3.22%`，`211.30 − 2×ATR ≈ 211.30 − 13.6 ≈ 197.70` → 即"入场价 − 2×ATR"的初始保护线。

### 1.2 详情页的 209.36 — trade_history 落库的移动止损

- **落库位置**：`trade_history.csv` → ANET 行 `Stop_Loss` 列（第 10 列），值 `209.36`（`Stop_Method` 已变为 `MA20/MA50 + ATR + MACD/KDJ`）。
- **前端渲染**：`dashboard_export.py:2100` `build_events()` 读 `r.get("Stop_Loss")` → `data.stocks[].stop_loss`；`app.js:238` `stop: num(s.stop_loss)`；`app.js:1793` 详情页 `'止损价', nv(s.stop, 2)`。
- **关键**：详情页的 `s` 来自 `STOCKS`（= `data.stocks`，由 `trade_history` 构建，`app.js:1625/1964` 按 ticker 取），**不读账本 positions**。所以详情页显示的是 trade_history 的值 209.36，而非账本的 197.69。

### 1.3 review 日志的 210.24 — 当次会话实时重算的移动止损

- **计算函数**：`review.py:1374` `get_trailing_stop_context(...)` 用 ANET 近 6 月日线实时算移动止损：
  - `review.py:1393-1394` 候选价公式：
    ```
    pct = max(atr_floor_pct=3, min(atr_ceiling_pct=12, atr_multiplier=2 * atr/close))
    candidate = max(close*(1-pct/100), ma20-atr, ma50-1.5*atr)
    ```
  - 再叠加浮盈保护、`is_valid_existing_stop` 作为 floor（`review.py:1411-1417`），最终 `exec_stop = round(candidate,2)`。
  - 因为 ANET 已涨到 ~216，MA20/MA50 抬高，算出 `candidate=210.24` > 落库旧值 209.36，故 `exec_stop=210.24`。
- **取值位置**：`review.py:1819` `exec_stop = ... (ctx.get("exec_stop") if ctx else old_stop)`。
- **判定触发**：`review.py:1826` `evaluate_stop_trigger(low, closep, openp, exec_stop)` → 当日 `Low ≤ 210.24` ⇒ 返回 `("STOP_TRIGGERED", exitp)`（`review.py:763-781`，`exitp = open if open<210.24 else 210.24`）。
- **日志打印**：`review.py:1871-1873` 风控诊断行输出 `Stop_Loss={exec_stop}`（即 210.24）、`Trigger={trigger_result}`（即 STOP_TRIGGERED）。
- **写回**：`review.py:1848` `update_trade_history_status(ticker, rec_date_str, "Stop_Loss_Hit", exitp)` → 把 trade_history 的 `Status` 置 `Stop_Loss_Hit` 并写入 `Exit_Price=exitp`。

---

## 2. 哪个是"实际触发用的"止损价

**结论：210.24 这条链路（及其派生的 `Exit_Price`）才是实际驱动卖出的止损价；197.69 是已被架空的陈旧值。**

### 2.1 账本为什么不会用 197.69 实际止损

- 账本的盘中机械止损确实读 197.69：`portfolio_50000.py:684` `stop = dec(p.get("Stop_Loss"))`，实时价 `≤ stop` 才卖。
- 但当前 ANET 实时价 `216.74`，**远高于 197.69**，该机械止损线永远不会被触及 → 197.69 在现在的价格区间里是**惰性/失效**的。
- 更关键：账本的真实卖出路径不是这条机械止损，而是 **review 状态驱动的退出**：

### 2.2 实际卖出由 review 的 Stop_Loss_Hit 驱动

- `portfolio_50000.py:47-48` `TERMINAL_STATUSES` 含 `"Stop_Loss_Hit"`。
- `portfolio_50000.py:395` `if rec["Status"] not in TERMINAL_STATUSES: continue` → 当 trade_history 状态为 `Stop_Loss_Hit` 且 `Exit_Price` 存在时：
  - `portfolio_50000.py:422` 以 `rec["Exit_Price"]`（= review 写回的 `exitp`，围绕 210.24）**实际卖出**（`Reason="Review exit: Stop_Loss_Hit"`）。
- 即：review 在 210.24 判定触发 → 把 trade_history 标 `Stop_Loss_Hit` + `Exit_Price` → 账本下次运行**按 Exit_Price（≈210.24 一带）卖出**。

### 2.3 当前为何账本仍显示 OPEN

- 最新 `portfolio_50000_positions.csv`（含多次 `refresh market data` 提交）ANET 仍为 `Status=OPEN`、`Stop_Loss=$197.69`。
- 说明：产生 `210.24 / STOP_TRIGGERED` 日志的 review 运行**尚未被账本消费**，可能原因（只读无法 100% 判定，列为待核）：
  1. 该 review 是 dry-run / 临时 / 非生产环境运行（例如 `_temp-*` 调试或本地跑），并未把 `Stop_Loss_Hit` 真正写回生产 `trade_history.csv`；
  2. 或 review 已写回，但 `portfolio_50000.py` 尚未在之后运行；
  3. 或账本读取的 `trade_history.csv` 与 review 写入的不是同一份。
- **风险提示**：无论哪种，当前界面呈现"卡片 197.69（OPEN）、详情页 209.36、review 说 210.24 已触发"三者并存，用户极易误判——以为 210.24 已实亏卖出（实际账本仍持 OPEN），或以为 197.69 是有效保护线（实际已被移动止损架空）。

---

## 3. 为什么三个数字不一致（根因）

同一仓位被**三套相互独立的止损值**描述，且其中两套会随时间漂移、一套冻结：

1. **账本止损冻结（197.69）**：`portfolio_50000.py` 建仓写入 197.69 后，没有任何代码路径在持仓期间**回写/抬高** `positions.csv` 的 `Stop_Loss`（`mark_to_market` 只更新价格与浮盈，不碰止损）。所以账本止损永远是原始 ATR 线。
2. **trade_history 移动止损抬高（→209.36）**：review 的 `update_trade_history_trailing_stop` 把推荐止损从 197.69 逐步抬高到 209.36 并落库；详情页读 trade_history，故显示 209.36。
3. **review 当次实时重算（210.24）**：`get_trailing_stop_context` 每次 review **重新算**一条移动止损，因价格继续上涨，算得 210.24，高于落库的 209.36，并被用作当次触发判定线。
4. **数据源分叉**：卡片读 `portfolio.positions`（197.69），详情页读 `stocks`/`trade_history`（209.36），review 日志读自己实时算的 `exec_stop`（210.24）——三个界面读三个不同来源，无人对齐。

一句话：**197.69 是历史遗留的"初始止损"且被冻结；209.36 是 review 抬高后落库、详情页展示的"存储态移动止损"；210.24 是 review 当次实时重算、真正用于判定触发并驱动账本卖出的"执行态移动止损"。**

---

## 4. 修复方向（仅列出，不实施）

1. **统一账本与 review 的止损线**
   - 让 `portfolio_50000.py` 在 `mark_to_market` 或独立步骤中，**同步 trade_history 的当前移动止损**到 `positions.csv` 的 `Stop_Loss`（197.69 → 209.36 → …），使账本机械止损线随 review 抬高，避免 197.69 成为失效/误导值。
   - 或反向：明确"账本用固定初始止损、review 仅做跟踪预警"的职责分离，并在 UI 标注两套系统的差异。

2. **统一卡片与详情页的数据源**
   - 卡片（197.69）与详情页（209.36）应读**同一份**止损：要么都读 `portfolio.positions.stop_loss`，要么都读 `trade_history` 当前移动止损，消除同一仓位两种止损价并存的困惑。

3. **明确"STOP_TRIGGERED"语义，区分"跟踪触发"与"账户实际止损"**
   - UI/日志应清楚区分：review 的 `STOP_TRIGGERED`（推荐跟踪触发，在 210.24）≠ 账本已实际卖出（当前仍 OPEN）。
   - 避免用户把 210.24 误读为"已成交亏损价"。

4. **核对 review→账本的 propagation 是否生效**
   - 确认产生 210.24/STOP_TRIGGERED 的 review 是否生产环境运行、是否真正写回 `trade_history.csv` 的 `Stop_Loss_Hit`+`Exit_Price`；确认 `portfolio_50000.py` 会在下一运行周期消费该终态并以 `Exit_Price` 卖出。
   - 当前 `positions.csv` 仍 OPEN，需排查是 dry-run、时序未到、还是读写不同文件。

5. **（可选）止损口径收敛**
   - 评估是否应让"初始 ATR 止损（197.69）""存储态移动止损（209.36）""执行态实时重算（210.24）"合并为单一权威止损源，杜绝三值漂移。

---

## 附：关键代码/数据定位清单

| 关注点 | 位置 |
|--------|------|
| 卡片渲染读 `p.stop_loss` | `app.js:441` |
| 详情页 `s.stop = num(s.stop_loss)` | `app.js:238` |
| 详情页展示 `nv(s.stop, 2)` | `app.js:1793` |
| STOCKS 由 `trade_history` 构建 | `app.js:198`、`dashboard_export.py:2100` |
| 账本透传 positions `Stop_Loss` | `dashboard_export.py:2645` |
| 账本建仓写入止损 | `portfolio_50000.py:552` |
| 账本盘中机械止损（读 197.69） | `portfolio_50000.py:684` |
| 账本消费 `Stop_Loss_Hit` 实际卖出 | `portfolio_50000.py:395,422` |
| review 移动止损计算 | `review.py:1374-1421` |
| review `exec_stop` 取值 | `review.py:1819` |
| review 触发判定 | `review.py:1826`、`763-781` |
| review 风控诊断日志 | `review.py:1871-1873` |
| review 写回 `Stop_Loss_Hit`+`Exit_Price` | `review.py:1848` |
| trade_history ANET `Stop_Loss=209.36` | `trade_history.csv` 第 10 列 |
| positions ANET `Stop_Loss=$197.69` | `portfolio_50000_positions.csv` 第 16 列 |
| 原始入表止损（197.69, ATR初始保护） | commit `82d1cc7` 的 `trade_history.csv` |
