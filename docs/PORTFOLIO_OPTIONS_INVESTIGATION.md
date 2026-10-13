# $50,000 持仓期权涉入调查（Options Involvement Investigation）

> 生成时间：2026-10-08 10:50 GMT+8（早于 13:07 scan 判决）
> 性质：**只读调查，不改代码、不实施、不 push、不 rebase、不 fetch、不碰监控 PID 536931、不手工改任何 portfolio 文件**。
> 问题：Dashboard 显示 `$50,000 Long-Term Portfolio`，当前 4 持仓（ADSK/ANET/ISRG/KR）全是股票——这个组合会不会涉及期权？
> 数据源：`portfolio_50000.py`（全 535 行）、`portfolio_50000_positions/transactions/history.csv` 列头、`scan.py`（期权引擎引用）、`review.yml`、`trade_history.csv`（组合输入源）。

---

## 1. 数据结构（字段清单）

### 1.1 `portfolio_50000.py` 持仓/交易/历史字段（`POSITION_COLUMNS` L57-71）

**持仓字段（15 列，全部为股票属性，零期权字段）：**
```
Portfolio_ID, Unit_ID, Ticker, Shares, Entry_Price, Entry_Date,
Cost_Basis, Current_Price, Market_Value, Unrealized_PnL,
Unrealized_PnL_Pct, Weight_Pct, Status, Stop_Loss,
Recommendation_ID, Last_Update
```
→ 无任何 `Option / Strike / Expiry / Call / Put / Contract / Premium / Side / Underlying / DTE` 字段。

**交易字段（14 列，`TRANSACTION_COLUMNS` L63-67）：**
```
Txn_ID, Date, Ticker, Action, Shares, Price, Amount,
Realized_PnL, Cash_After, Reason, Recommendation_ID, Scan_Date,
Portfolio_ID, Unit_ID
```
→ `Action` 仅 `BUY` / `SELL` 两值（见 §2），无期权动作。

**历史快照字段（10 列，`HISTORY_COLUMNS` L68-71）：**
```
Date, Cash, Stock_Value, Total_Equity, Realized_PnL,
Unrealized_PnL, Total_PnL, Return_Pct, Open_Positions, Portfolio_ID
```
→ 维度是 `Stock_Value`（股票市值），非含期权的 `Derivative_Value`。

### 1.2 CSV 列头实测（本地 checkout）
- `portfolio_50000_positions.csv`：仅表头，与 §1.1 一致，**无期权列**。
- `portfolio_50000_transactions.csv`：仅表头，一致。
- `portfolio_50000_history.csv`：含 `2026-10-06` 创立日一行（0 持仓），字段与 §1.1 一致。

### 1.3 常量（`portfolio_50000.py` L39-43）
```
MAX_OPEN_POSITIONS = 4   # 注释明确写 "最多 4 个同时存在的 Long Stock Unit"
UNIT_DOLLARS = 10000.00  # 1 Unit 目标资金（股票份额预算）
UNIT_IDS = ["U001".."U004"]
```
→ 常量语义是 **"Long Stock Unit"（多头股票单位）**，非期权合约单位。

---

## 2. 逻辑路径（buy / sell 全部可能动作）

### 2.1 开仓 `process_buys`（L292-378）—— **只有买股票，无买期权路径**
- 候选筛选（L303-308）：仅 `Tag == Core_Dragon` 且 `Status == "Active"` 的**股票推荐**。
- 份额计算（L322）：`shares = int((UNIT_DOLLARS / price).to_integral_value(ROUND_DOWN))` —— **买整数股**，典型股票 Long 逻辑。
- 预算双保险（L327-331）：`if amount > UNIT_DOLLARS: shares -= 1` —— 约束的是股票金额，非权利金。
- 写入 `Action: "BUY"`（L343）、`Reason: "Core recommendation -> 1 Unit long"`（L349）—— **明确 "long"**。
- **无任何 `buy_call / buy_put / sell_put / open_contract` 分支**。

### 2.2 平仓 `process_sells`（L235-289）—— **只平多头股票，无做空/无期权平仓**
- 触发：对应 `trade_history` 推荐进入 `TERMINAL_STATUSES`（Stop_Loss_Hit / Target_Reached / Closed 等，L47-50）。
- 动作：`Action: "SELL"`（L267），`Reason: "Review exit: {Status}"`（L273），按 `Exit_Price` 平仓（L248-262）。
- **无 `short / sell_short / open_short` 任何做空逻辑**；SELL 永远对应已持有的多头平仓。

### 2.3 全局关键词搜索（`portfolio_50000.py` 全文 grep）
```
pattern: option|call|put|strike|expiry|contract|premium|short|sell_short|exercise|assign
结果：No matches found  ← 整个模块零命中
```
→ **模块内既无期权字段、也无期权/做空逻辑**。

### 2.4 动作全集（穷举）
| 动作 | 代码位置 | 性质 |
|---|---|---|
| BUY | L339-354 | 买整数股 Long（1 Unit） |
| SELL | L263-278 | 平多头（Review 终态裁决价） |
| （其余） | — | 不存在 |

---

## 3. 信号源（从 scan 到 portfolio 的数据流）

### 3.1 组合的**唯一输入** = `trade_history.csv`
`portfolio_50000.py: load_recommendations()`（L201-223）**只读取 `trade_history.csv`**，字段 `Ticker/Date/Tag/Price/Status/Exit_*`。
- 实测 `trade_history.csv` 列头：`Date,Ticker,Name,Tag,Score,Price,...` —— `Ticker` 为**普通股票代码**（样本：AMZN、BBAI…），**无期权符号格式**（如 `AAPL 250919 230 C`）。
- `Tag` 仅 `Core_Dragon` / `Observation`；组合只认 `Core_Dragon`（L45, L304）。**没有任何期权 Tag**。

### 3.2 review.yml 喂给组合的数据（L53-56）
```yaml
- name: 更新 $50,000 Portfolio Ledger
  run: python portfolio_50000.py --data-dir .
```
→ 组合运行**只依赖 `trade_history.csv`**，不接收 `option_strategies.csv`、不接收任何期权信号。

### 3.3 ⚠️ 关键区分：仓库**另有一套期权子系统，但与 $50k 组合不连通**
- `scan.py:44` 导入 `from scan_us_option_engine import append_option_strategy, get_recent_option_recommendations`
- `scan.py:3314` `generate_option_recommendations()` → 生成 **Short Put / Call Debit Spread**（L3336-3404），写入 **`option_strategies.csv`**（独立账本）。
- `review.yml:89-92`：注释明确"`review.py` 平仓时会改写**期权账本**"，单独 `git add option_strategies.csv` —— 这是**与 $50k 组合平行的另一个 ledger**。
- `portfolio_50000.py` 全模块**从不引用 `option_strategies.csv`**（grep 零命中），也不读任何期权推荐。

> 结论：**期权能力存在于项目，但落在 `option_strategies.csv` 这本独立账里，从未流入 `$50,000 portfolio`**。两者在代码与数据流上完全隔离。

---

## 4. 结论：纯股票 / 预留 / 支持 / 其他

| 候选情况 | 是否成立 | 证据 |
|---|---|---|
| **完全无期权字段/逻辑** | ✅ **成立（针对 $50k 组合）** | §1 字段全为股票；§2.3 grep 零命中；§2.1-2.2 仅 BUY 股 / SELL 平多 |
| 有字段但未启用（预留接口） | ❌ 不成立 | 模块内连"期权字段骨架"都没有，非"预留未激活" |
| 有逻辑但当前无信号（支持期权） | ❌ 不成立（针对 $50k） | $50k 模块无任何期权逻辑；期权逻辑在**另一本账** `option_strategies.csv` |
| 其他 | ⚠️ 部分成立 | "项目整体有期权子系统"成立，但**与本组合无关**——属"其他"里的边界说明 |

**最终判定：`$50,000 Long-Term Portfolio` = 纯多头股票组合（Pure Long-Stock Portfolio），不涉及任何期权。**

- 4 个当前持仓（ADSK/ANET/ISRG/KR）均为普通股票代码（来自 `trade_history.csv` 的 `Core_Dragon`），无期权合约。
- 项目虽有独立期权引擎（`scan_us_option_engine` → `option_strategies.csv`），但那是**平行账本**，与本组合代码/数据流零交集。
- 用户看到的"4 持仓全是股票"与代码完全一致，不是巧合、也不是展示遗漏。

---

## 5. 若未来要加期权 —— 改动半径评估（只列方向，不实施）

> 以下为"把期权纳入 $50k 组合"所需的改造范围，**仅方向，不写代码、不实施**。

**A. 数据模型层（必改）**
- `POSITION_COLUMNS` 增期权字段：`Instrument_Type`(STOCK/OPTION)、`Side`(CALL/PUT/SHORT_PUT)、`Strike`、`Expiry`、`DTE`、`Contract_ID`、`Premium`、`Underlying`。
- `TRANSACTION_COLUMNS` 增 `Action` 取值：`BUY_CALL` / `BUY_PUT` / `SELL_PUT`（权利金现金流方向不同于股票）。

**B. 开仓逻辑层（必改）**
- `process_buys` 当前按 `UNIT_DOLLARS/price` 算股数（L322）——期权需改为"按权利金预算买 N 张合约"，且需识别 `option_strategies.csv` 的推荐（当前 `load_recommendations` 只认 `trade_history.csv`，L201）。
- 需新增期权候选源：让组合消费 `option_strategies.csv`（或让 scan/review 把期权推荐并入 `trade_history` 的某 Tag）。

**C. 盯市/盈亏层（必改）**
- `mark_to_market`（L381-406）当前按 `shares × price` 算市值——期权需按合约乘数（×100）× 期权中间价，且浮盈依赖 **期权报价 + 可能 Greek**（IV/Delta），需新接入期权行情源（yfinance options chain 等）。
- `derive_cash` 需区分"买股付全额"vs"卖 Put 收权利金/保证金占用"。

**D. 风控/语义层（必改）**
- `MAX_OPEN_POSITIONS=4` 语义是"4 个股票 Unit"；若混入期权需重定义敞口口径（如按 Delta 等效、或按合约数）。
- `Stop_Loss` 字段当前是股票止损价；期权需加入"被指派(Put Assignment)/到期归零"处理。

**E. 流水线层（可能改）**
- `review.yml` 当前组合步骤只跑 `portfolio_50000.py`；若要期权进组合，需决定期权账本是"并入 $50k"还是"保持 `option_strategies.csv` 独立"——后者改动半径小，前者是中大型重构。

**改造半径总评**：从"纯股票"到"含期权"是**中大型重构**（新增 Instrument 类 + 期权行情 + 新开仓/盯市/风控路径），非一两行。但**好消息**：期权引擎与独立账本（`option_strategies.csv`）已存在，若选择"期权保持独立账本、不在 $50k 组合内"的方向，则**本组合模块零改动**，只是 Dashboard 展示上把两本账并列即可（最小半径）。

---

## 6. 本调查未做的事（限制遵守确认）

- ✅ 未改 `portfolio_50000.py` / `scan.py` / `review.yml` / 任何 CSV / 任何 workflow。
- ✅ 未 push / rebase / fetch；未碰监控 PID 536931；未手工改任何 portfolio / option 文件。
- ✅ 仅做只读字段核查、关键词搜索、数据流追踪与判定。
- 注：本地 `trade_history.csv` 为真实 374 行数据（仅读取，未改）；`option_strategies.csv` 仅作"独立账本存在性"证据引用，未读取其内容。
