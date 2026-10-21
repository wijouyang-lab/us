# 盘中机械止损 实施报告

> **当前状态更新（2026-10-20；以本段为准）**
>
> 原报告记录的是最初版本。低频量化集成 PR #186 中的待审版本进一步收紧报价逻辑：
> - `portfolio_50000.py` 的盘中路径单独请求 Yahoo/yfinance 的 `5m` 常规时段 K 线（`prepost=False`），不再把默认日线 `Close` 当作盘中实时价。
> - 报价必须带时区、属于当天常规交易时段、时间不在未来超过 2 分钟、并且时间戳不旧于 15 分钟；不满足就 fail closed，不写模拟卖出。
> - 触发卖出时，`Quote_As_Of` 会作为最后一列追加到模拟交易流水，记录用于比较止损线的 K 线时间戳；`Pending_Reason` 原列继续保留，原 14 列顺序不变。
> - PR 分支把 `dashboard-data.yml` 的 cron 改为 `*/15 * * * 1-5`（工作日每 15 分钟）；GitHub 的计划任务仍可能延迟或漏跑，因此这不是券商级保护性止损。
>
> **部署边界：**以上是 Draft PR #186 的待审变更，尚未合并到 `main`。生产主分支目前仍是每小时调度和旧取价路径。在审查/合并前，不要据此声称生产已具备可靠盘中止损。
>
> 当前全量测试在前一代码提交 `1966df10342ae315f87f6ac5d8aa598efef2f6bb` 上通过：**948 passed, 1 skipped**；PR #186 正在当前 main 基线重新集成；旧分支 948 passed 的结果不是当前验收结果，必须以 PR #186 最新提交的全量 CI 为准。

> 已 commit + push。约束全部遵守：未改 `process_buys`/`process_sells`/`run()` 默认行为、未改 `review.yml`、未改 `scan.py` 主逻辑、未激活 `ENABLE_TARGET_FILE`、未碰监控、未调 AI（触发不调 AI，AI 回填本期延后）。

## 1. --intraday-stop 实现摘要

新增参数 `--intraday-stop`（`portfolio_50000.py`）：

- **入口**：`run()` 新增 `intraday_stop=False` 参数与早退分支 `if intraday_stop: return _run_intraday_stop(...)`。默认（无 flag，即 Review 路径）**完全不进入此分支**，函数体其余逻辑一字未改。
- **`_run_intraday_stop()`**（新增纯函数）：
  - **时段守卫**：仅 `09:30 ≤ ET < 16:00` 执行，其他时间（含盘前/盘后/周末）**静默退出 exit 0**，不读价、不写文件。
  - **取价（历史实现，已被上方当前状态更新取代）**：最初版本复用 `fetch_last_closes`；当前 PR 分支改为独立的 `fetch_intraday_last_prices`，只接受新鲜的 5 分钟常规时段 bar。
  - **触发**：`最近有效 5 分钟 bar Close ≤ Stop_Loss` → 模拟卖出；`Status=CLOSED`、`Current_Price=bar Close`、写 `transactions`（Action=SELL, Reason=`Intraday Stop Loss`, **Pending_Reason=True** 待 AI 补原因）并保存 `Quote_As_Of`。
  - **不调用 `process_buys`/`process_sells`**——只做"检查 + 卖"。
  - **守卫**：单日最多 2 只（`MAX_INTRADAY_STOPS_PER_DAY`）；全部 CLOSED 不再触发；已今日止损幂等不重复；取不到/过期报价不猜价（与 Review `DATA_MISSING` 一致）。
- **Txn_ID** 用 `INTRADAY|{TICKER}|{today}`，与 Review 的 `{rid}|SELL|{date}` 区分，避免幂等冲突。
- **`TRANSACTION_COLUMNS`** 在原 14 列之后追加 `Pending_Reason`，再追加 `Quote_As_Of`；原 14 列顺序不变，老行读取时新字段为空，不要求历史账本迁移。

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
| ⑥ 交易结构只追加字段 | `test_transaction_columns_append_only`（原 14 列顺序不变，最后两列为 `Pending_Reason`、`Quote_As_Of`） |
| 附加 | 离线不触发 / 幂等已止损 / 全平仓不触发 |

**全量**：`pytest tests/` → **281 passed**（基线 267 + 14），≥270 达标。
**语法/格式**：`py_compile portfolio_50000.py` OK；`node --check app.js` OK；`yaml.safe_load` 校验 dashboard-data.yml OK。

## 4. Commit SHA + push 结果

分 2 个 commit（rebase 到 `origin/main` 之上后）：

- `83152b7` feat(portfolio): add --intraday-stop mechanical stop-loss check（portfolio_50000.py + tests）
- `edba8e7` feat(dashboard): wire intraday-stop step + frontend badge（dashboard-data.yml + app.js + app.css）

远端基线 `bb18597` → 推送 `bb18597..edba8e7 main -> main` ✅。改动文件仅 5 个（portfolio_50000.py / dashboard-data.yml / app.js / app.css / tests/test_intraday_stop.py），未触碰 review.yml / scan.py / dashboard_export.py（前端徽章经交易流水展示，无需改导出层）。

## 5. 下周一首次真实验证预期行为

- **触发**（PR 合并且计划任务正常运行后）：读 OPEN 持仓 → 请求 5 分钟常规时段 K 线 → 时间戳有效且不旧于 15 分钟时，比较最后一根有效 bar 的 Close 与 `Stop_Loss` → 条件满足则写模拟 SELL，流水保存 `Quote_As_Of`。
- **前端**：dashboard_export 下一轮刷新后，持仓区下方出现 `🔴 盘中止损` 横幅（ticker + 触发价 + 原因）。
- **不触发**：所有持仓价 > 止损 → 静默，仅 `--price-only` 已更新的价格被提交；时段外 → 静默退出。
- **上限/幂等**：单日最多 2 只；同一 ticker 当日只止损一次；全 CLOSED 后不再触发。
- **盘后 Review**：跑完整 `run()`（无 `--intraday-stop`）→ 见 CLOSED 仓位跳过卖出、回填 `Cash_After`，与改前完全一致。
- **风险点**：报价取自 yfinance，而不是券商/交易所直连实时报价。若 Yahoo 限流、bar 时间戳无效/过旧或 GitHub 调度延迟 → fail closed、不触发模拟卖出。每 15 分钟的设计仍可能错过两次检查间的快速下跌；这套账本不下券商订单，不能作为真实资金止损保证。

## 6. 本期明确延后（待后续）

1. **AI 原因回填（第三件）**：按用户"复杂则本次不做，只标记"的许可，**本期未实现**。`Pending_Reason=True` 已落库，后续由 scan/review 新增函数批量读 `Pending_Reason=True` 的记录、调 AI 写 `Reason` 并清标志。在此之前，前端展示的原因恒为 `Intraday Stop Loss`。
2. **决策 1 / 决策 3 的买入侧冷却**：`--intraday-stop` 自身从不买入，故"同日不重买同一只""全部止损后当天不再买"的**买入侧**执行需改 `process_buys`（被本任务禁止），本期未做；当前仅保证"卖出侧"守卫与幂等。如需严格买入侧冷却，需在 `process_buys` 增加"跳过近 N 日盘中止损过的 ticker"（独立小任务）。
