# $50,000 Long-Term Portfolio Ledger · 实施报告

> 完成时间：2026-10-06
> 前置：只读审计（`PORTFOLIO_50000_AUDIT_PLAN.md`）→ 参数确认 → 实施 → 测试 → Code Review → 部署

---

## 1. 修改文件（5 个）

| 文件 | 改动 | 为什么必需 |
|---|---|---|
| `dashboard_export.py` | **+118 行，0 删除** | 新增 `build_portfolio()` 只读消费 Portfolio CSV → `payload["portfolio"]`。纯新增函数 + 1 行调用 + 1 行 payload 键 |
| `app.js` | **+152 行，0 删除** | 新增 `renderPortfolio()` + `drawPortfolioCurve()`（canvas 复用现有绘图风格），并在 `renderDashboard()` 中调用 |
| `index.html` | **+12 行** | 新增 `$50,000 Long-Term Portfolio` section（概览 / 曲线 / 持仓表 / 交易表） |
| `app.css` | **+10 行** | Portfolio 表格样式（`.pf-tbl` / `.pf-hd`） |
| `.github/workflows/review.yml` | **+17 行** | 新增 1 个 step 运行引擎；artifact 清单与 git add 清单加入 4 个 Portfolio 文件 |

## 2. 新增文件（2 个 + 4 个运行时数据文件）

| 文件 | 说明 |
|---|---|
| `portfolio_50000.py` | **Portfolio 引擎**（唯一写账入口，确定性，无 AI 参与） |
| `tests/test_portfolio_50000.py` | 38 项回归测试 |
| `portfolio_50000_meta.json` | 运行时生成：`initial_capital` / `start_date` / `unit_dollars` / `max_open_positions` |
| `portfolio_50000_positions.csv` | 运行时生成：当前持仓状态 |
| `portfolio_50000_transactions.csv` | 运行时生成：不可丢失的交易流水（现金与 Realized PnL 的唯一真相源） |
| `portfolio_50000_history.csv` | 运行时生成：每日净值快照（Equity Curve 数据源） |

> 运行时文件由 review.yml 首次运行时自动创建，不在此次提交内。

## 3. Portfolio 数据结构

```
Portfolio_ID = US-50000-001
Unit_ID      = U001 / U002 / U003 / U004（每个持仓占用一个 Unit，释放后可复用）
```

**positions.csv**：`Portfolio_ID, Unit_ID, Ticker, Shares, Entry_Price, Entry_Date, Cost_Basis, Current_Price, Market_Value, Unrealized_PnL, Unrealized_PnL_Pct, Weight_Pct, Status, Stop_Loss, Recommendation_ID, Last_Update`

**transactions.csv**：`Txn_ID, Date, Ticker, Action, Shares, Price, Amount, Realized_PnL, Cash_After, Reason, Recommendation_ID, Scan_Date, Portfolio_ID, Unit_ID`

**history.csv**：`Date, Cash, Stock_Value, Total_Equity, Realized_PnL, Unrealized_PnL, Total_PnL, Return_Pct, Open_Positions, Portfolio_ID`

**Dashboard JSON**（新增顶层 `portfolio`，未初始化时为 `null`）：
`portfolio_id / initial_capital / start_date / unit_dollars / max_open_positions / asof / cash / stock_value / total_equity / realized_pnl / unrealized_pnl / total_pnl / return_pct / open_positions / positions[] / transactions[] / equity_curve[]`

## 4. $50,000 如何初始化 / 如何保证不重置

**初始化**：仅当 `portfolio_50000_meta.json` **不存在**时写入一次：
```json
{"portfolio_id":"US-50000-001","initial_capital":"50000.00","start_date":"<当日美东日期>",
 "unit_dollars":"10000.00","max_open_positions":4,"currency":"USD"}
```
文件存在 → `ensure_meta()` 直接返回，**永不重写**。

**三重防重置**：
1. `initial_capital` 是常量 `Decimal("50000.00")`，只在 meta 缺失时落盘
2. **现金不作为状态保存** —— `Cash = 50000 − Σ买入 + Σ卖出`，每次运行从交易流水重新推导 → 物理上无法重置
3. `start_date` 闸门：`Rec_Date < start_date` 的推荐永不建仓（不回溯历史、不虚构收益）

## 5. BUY 如何发生

全部为确定性规则（无 AI 写账）：

| 条件 | 判定 |
|---|---|
| Tag | 必须 `Core_Dragon`（**Observation / Trap_Warning 一律不进 Portfolio**） |
| Status | 必须 `Active` |
| 买入价 | 取 `trade_history.Price` = **推荐日真实 Open**；缺失则不买（绝不猜测） |
| Rec_Date | ≥ `start_date` |
| 已持仓 | 同 Ticker 有 OPEN → **HOLD，不重复买入**（不因新票评分高而换仓） |
| 空闲 Unit | 无空闲 → 仅保留为推荐，不动现有持仓 |
| 现金 | 不足则跳过 |

**Position Sizing（1 Unit）**：
```
Shares = floor(10000.00 / Entry_Price)     # 实测 AMD@630.48 → 15 股 = $9,457.20
Amount = Shares × Entry_Price ≤ 10000.00   # 绝不超预算，余数留在 Cash
```

**Unit 释放**：只有 Review 产生正式退出事件后才释放，**不会因新推荐而卖出旧持仓**。

## 6. SELL 如何发生 / Stop Loss 如何联动

**完全沿用 Review 裁决，未实现第二套止损**：

```
持仓对应的 trade_history 行 Status ∈ {Stop_Loss_Hit, Dropped, Period_Matured,
                                      Observation_Closed, Target_Reached, ...}
且 Exit_Date 与 Exit_Price 均非空
   → SELL 全部股数 @ Exit_Price，成交日 = Exit_Date
```

- 幂等键 `Ticker|Rec_Date|Tag|SELL|Exit_Date`
- **fail-safe**：Exit_Price 或 Exit_Date 缺失 → **不卖**，等 Review 补齐（现有数据 283/283 均有）
- 卖出后 `Shares=0`、`Status=CLOSED`、Realized PnL 入账、Cash 增加、Unit 释放

## 7. PnL / Equity 计算

```
Unrealized = Σ (Current_Price − Entry_Price) × Shares     （仅 OPEN）
Realized   = Σ transactions 中 SELL 的 Realized_PnL
Total PnL  = Realized + Unrealized
Return_%   = Total_PnL / 50000.00 × 100        （分母恒为初始本金）
Total_Equity = Cash + Σ Market_Value
```

**金额全程 `Decimal`，落盘 `quantize(0.01)`**；股数为整数。测试实测无浮点毛刺（如 `50000.00`、`9457.20`，非 `50000.00000000001`）。

## 8. Dashboard 增加了什么

- **概览**：Initial Capital / Total Equity / Total PnL / Return % / Cash / Stock Value / Realized / Unrealized / Open Units / Start Date
- **Equity Curve**：canvas 折线，含 $50,000 基准虚线；**起点强制为 $50,000**（起始日全现金状态，避免首日盯市覆盖原点）
- **持仓表**：Unit / Ticker / Shares / Entry / Current / Market Value / Unrealized / Return % / Weight % / Stop / Days
- **最近交易表**：Date / Action / Ticker / Shares / Price / Amount / Realized PnL / Reason
- 未初始化时显示「尚未初始化」，**不报错、不白屏**
- 全部价格 `nv(v, 2)` 两位小数（如 `630.48`）

## 9. Transaction Ledger 如何防重复

| 层 | 机制 |
|---|---|
| BUY | `Txn_ID = Ticker|Rec_Date|Tag|BUY` 已存在 → 跳过 |
| SELL | `Txn_ID = Ticker|Rec_Date|Tag|SELL|Exit_Date` 已存在 → 跳过 |
| Snapshot | History 按 `Date` upsert，同一交易日只保留一行 |
| 初始化 | meta 存在即不重写 |

实测：连续运行 5 次，transaction 数与 history 行数均不增长。

---

## 10. 测试结果

| 项 | 结果 |
|---|---|
| **Portfolio 新增测试** | **38 / 38 PASS** |
| **全量项目测试** | **309 / 309 PASS** |
| `py_compile`（portfolio_50000.py / dashboard_export.py） | ✅ PASS |
| `node --check app.js` | ✅ PASS |
| YAML 语法（review.yml） | ✅ PASS（cron `0 22 * * 1-5`、concurrency 均未变） |
| `git diff --check` | ✅ PASS |

测试覆盖：初始化幂等、Entry Price 固定、Unrealized 正负、SELL 与 Realized、Cash/Equity/PnL/Return、快照与流水防重复、永不重置、Stop Loss 同步、Observation 隔离、历史闸门、Unit 上限 4、预算不超 10000、空仓、全卖、金额 2 位小数、Dashboard 字段与曲线原点。

## 11. Git

| 项 | 值 |
|---|---|
| commit SHA | `4389977`（本地）→ rebase 后 **`99d14d1075b31d3ad19b013b18c77267f41a13cd`** |
| push | ✅ 成功（`1d2f212..99d14d1`，无 force） |
| **HEAD == origin/main** | ✅ **TRUE**（`99d14d1`） |
| 工作区 | clean（modified = 0） |

## 12. 线上验证

| 项 | 结果 |
|---|---|
| 线上 `app.js` 含 `renderPortfolio` / `drawPortfolioCurve` | ✅ 4 处命中，Pages `built` |
| 远端 `dashboard_data.json` 新增 `portfolio` 顶层键 | ✅ 存在（当前值 `null`，尚未初始化） |
| stocks / rec_price | ✅ 30 / 30 覆盖，无回归 |
| Options Active / Rejected | ✅ 0 / 12 |
| runtimes | ✅ scan / review / evolve 三键完整 |

## 13. 未解决问题 / 后续观察

1. **Portfolio 当前尚未初始化** —— 将在**下一次 review.yml 自然运行**（今日 22:00 UTC）时创建。未手动 dispatch。
2. **首日预计空仓后建仓**：现有 18 条 Active Core_Dragon 的推荐日期均早于 start_date（最新为 2026-10-02），**全部被闸门拦住**；今晚 Scan（13:07 UTC）产生的新 Core 推荐经 Review 入账后，Portfolio 才会首次建仓（最多 4 Unit）。
3. **取价依赖 yfinance**：若某次取价失败，沿用上一快照价格并打印告警，**绝不编造价格**。
4. **后续建议（未做）**：若希望更快看到持仓，可考虑放宽 start_date 闸门（但这会把历史推荐变成持仓，等于虚构历史收益 —— 按你的要求未做）。

---

## 红线遵守确认

| 禁止项 | 状态 |
|---|---|
| 修改 scan.py | ✅ 未改 |
| 修改 review.py | ✅ 未改 |
| 修改 scan.yml | ✅ 未改 |
| 修改 dashboard-data.yml（并发稳定性架构） | ✅ 未改 |
| 修改 Runtime | ✅ 未改 |
| 修改 Options / RR | ✅ 未改 |
| 恢复 Email | ✅ 未恢复 |
| 改变 Buy Price 定义 | ✅ 未变（仍取 trade_history.Price = 推荐日 Open） |
| 回溯历史推荐 | ✅ 未回溯（start_date 闸门） |
| 删除任何现有功能 | ✅ **0 deletions，全部为新增** |
| force push / reset --hard | ✅ 未使用 |
