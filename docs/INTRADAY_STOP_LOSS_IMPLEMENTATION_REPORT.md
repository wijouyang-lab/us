# 盘中机械止损 实施报告

> 已 commit + push。约束全部遵守：未改 `process_buys`/`process_sells`/`run()` 默认行为、未改 `review.yml`、未改 `scan.py` 主逻辑、未激活 `ENABLE_TARGET_FILE`、未碰监控、未调 AI（触发不调 AI，AI 回填本期延后）。

## 1. --intraday-stop 实现摘要

新增参数 `--intraday-stop`（`portfolio_50000.py`）：

- **入口**：`run()` 新增 `intraday_stop=False` 参数与早退分支 `if intraday_stop: return _run_intraday_stop(...)`。默认（无 flag，即 Review 路径）**完全不进入此分支**，函数体其余逻辑一字未改。
- **`_run_intraday_stop()`**（新增纯函数）：
  - **时段守卫**：仅 `09:30 ≤ ET < 16:00` 执行，其他时间（含盘前/盘后/周末）**静默退出 exit 0**，不读价、不写文件。
  - **取价**：`fetch_last_closes`（其 `current` 为 `prepost=False`，决策 5 满足），实时价即执行价。
  - **触发**：`实时价 ≤ Stop_Loss` → 机械卖出；`Status=CLOSED`、`Current_Price=执行价`、写 `transactions`（Action=SELL, Reason=`Intraday Stop Loss`, **Pending_Reason=True** 待 AI 补原因）。
  - **不调用 `process_buys`/`process_sells`**——只做"检查 + 卖"。
  - **守卫**：单日最多 2 只（`MAX_INTRADAY_STOPS_PER_DAY`）；全部 CLOSED 不再触发；已今日止损幂等不重复；取不到价不猜价（与 Review `DATA_MISSING` 一致）。
- **Txn_ID** 用 `INTRADAY|{TICKER}|{today}`，与 Review 的 `{rid}|SELL|{date}` 区分，避免幂等冲突。
- **`TRANSACTION_COLUMNS`** 仅追加 `Pending_Reason`（原 14 列顺序不变）。

## 2. Review 路径安全性验证（无 flag 时行为一致的证据）

Review 的命令是 `python portfolio_50000.py --data-dir .`（**不带 `--intraday-stop`**），因此 `intraday_stop` 默认为 `False`，早退分支永远不会进入。证据：

- **单元测试 `test_default_run_does_not_invoke_intraday`**：monkeypatch `_run_intraday_stop` 为记录器，跑 `run(d, offline=True)`，断言记录器**从未被调用**，且仓位 `Status` 仍为 `OPEN`、无 `Intraday Stop Loss` 交易。
- **`test_default_run_review_path_unchanged`**：默认 `run()` 返回完整字段（`history`/`meta`/`transactions`），证明走的是完整 `run()` 而非早退分支。
- **Code diff 比对**：`run()` 仅签名多一个默认参数 + 早退 `if` + 注释；`process_buys`/`process_sells`/`ensure_meta`/`load_recommendations` 等**零改动**。`git diff --stat` 显示 `portfolio_50000.py` 仅 +136/−3（新增函数 + 早退分支），无对既有函数的修改。
- **结论**：今晚（北京周六 06:23 ≈ ET 周五晚间）Review 跑的是完整 `run()`，与改前逐字节一致；即便 dashboard-data 在该时刻触发 `--intraday-stop` 步骤，也会因时段守卫（`≥16:00 ET` 外）静默退出，不影响任何输出。

## 3. 新测试 + 全量测试结果

新增 `tests/test_intraday_stop.py`（**14 个**，覆盖用户 6 项必验 + 幂等/离线/全平仓）：

| 验证项 | 测试 |
|---|---|
| ① 非交易时段静默退出 | `test_out_of_session_silent_exit`（08:00/16:30/00:00/20:00）+ `test_weekend_silent_exit`（周六） |
| ② 实时价 > 止损 → 不触发 | `test_price_above_stop_no_trigger` |
| ③ 实时价 ≤ 止损 → 触发 + 写 transactions | `test_price_below_stop_triggers`（断言 Action/Price/Reason/Pending_Reason/Txn_ID/Status） |
| ④ 单日 ≥ 2 → 不再触发 | `test_max_two_stops_per_day`（3 只全破 → 只触发 2） |
| ⑤ 默认 run() 行为不变 | `test_default_run_does_not_invoke_intraday` + `test_default_run_review_path_unchanged` |
| ⑥ 交易结构只追加字段 | `test_transaction_columns_append_only`（原 14 列顺序不变，仅追加 `Pending_Reason`） |
| 附加 | 离线不触发 / 幂等已止损 / 全平仓不触发 |

**全量**：`pytest tests/` → **281 passed**（基线 267 + 14），≥270 达标。
**语法/格式**：`py_compile portfolio_50000.py` OK；`node --check app.js` OK；`yaml.safe_load` 校验 dashboard-data.yml OK。

## 4. Commit SHA + push 结果

分 2 个 commit（rebase 到 `origin/main` 之上后）：

- `83152b7` feat(portfolio): add --intraday-stop mechanical stop-loss check（portfolio_50000.py + tests）
- `edba8e7` feat(dashboard): wire intraday-stop step + frontend badge（dashboard-data.yml + app.js + app.css）

远端基线 `bb18597` → 推送 `bb18597..edba8e7 main -> main` ✅。改动文件仅 5 个（portfolio_50000.py / dashboard-data.yml / app.js / app.css / tests/test_intraday_stop.py），未触碰 review.yml / scan.py / dashboard_export.py（前端徽章经交易流水展示，无需改导出层）。

## 5. 下周一首次真实验证预期行为

- **触发**（09:30–16:00 ET 内某次 15 分钟运行）：读 OPEN 持仓 → `fetch_last_closes` 取实时价 → 若某仓 `实时价 ≤ Stop_Loss` → 机械 SELL（执行价=触发实时价），`positions.csv` 该仓 `Status=CLOSED`，`transactions.csv` 追加 SELL 行（Reason=`Intraday Stop Loss`, Pending_Reason=`True`）。
- **前端**：dashboard_export 下一轮刷新后，持仓区下方出现 `🔴 盘中止损` 横幅（ticker + 触发价 + 原因）。
- **不触发**：所有持仓价 > 止损 → 静默，仅 `--price-only` 已更新的价格被提交；时段外 → 静默退出。
- **上限/幂等**：单日最多 2 只；同一 ticker 当日只止损一次；全 CLOSED 后不再触发。
- **盘后 Review**：跑完整 `run()`（无 `--intraday-stop`）→ 见 CLOSED 仓位跳过卖出、回填 `Cash_After`，与改前完全一致。
- **风险点**：实时价取自 yfinance `prepost=False`；若沙箱被 Yahoo 429 限流取不到价 → 按"不猜价"原则**不触发**（安全优先）。15 分钟间隔内价格可能已跌更深，执行价为检查时刻价（模拟账户可接受）。

## 6. 本期明确延后（待后续）

1. **AI 原因回填（第三件）**：按用户"复杂则本次不做，只标记"的许可，**本期未实现**。`Pending_Reason=True` 已落库，后续由 scan/review 新增函数批量读 `Pending_Reason=True` 的记录、调 AI 写 `Reason` 并清标志。在此之前，前端展示的原因恒为 `Intraday Stop Loss`。
2. **决策 1 / 决策 3 的买入侧冷却**：`--intraday-stop` 自身从不买入，故"同日不重买同一只""全部止损后当天不再买"的**买入侧**执行需改 `process_buys`（被本任务禁止），本期未做；当前仅保证"卖出侧"守卫与幂等。如需严格买入侧冷却，需在 `process_buys` 增加"跳过近 N 日盘中止损过的 ticker"（独立小任务）。
