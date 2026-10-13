# $50,000 Portfolio Ledger · 只读审计 + 最小改造方案（第一阶段）

> 状态：**只读审计完成，尚未修改任何代码**。等待确认后再实施。
> 审计时间：2026-10-06

---

## A. 当前架构（基于实际代码，非文件名猜测）

### 数据流

```
scan.py (盘中 13:07 UTC)
  ├─ 生成 us_stocks_pending_YYYYMMDD.csv      Tag ∈ {Core_Dragon, Observation}
  │                                            Status=pending, Scan_Ref_Price, Stop_Loss
  ├─ 写入 ai_text_cache.csv / ai_snapshot.csv
  └─ scan.yml 提交推送（fetch + rebase，无 force）

review.py (盘后 22:00 UTC)
  ├─ supplement_us_stocks_from_pending()  消费 pending → trade_history.csv
  │    · Price = 推荐日真实 Open（op），拿不到则留空，绝不拿实时价冒充
  │    · Close_Price = 推荐日 Close、Status=Active、Stop_Loss 由 pending 继承
  ├─ 每日盯市、止损/到期/Dropped 判定 → 写 Exit_Date / Exit_Price / Status
  ├─ 写 review_history.csv（Rec_Date / Cur_Price / PnL_Pct / Status）
  └─ review.yml 提交推送（fetch + rebase，冲突即停止，无 force）

dashboard_export.py (每 15 分钟)
  └─ 只读读取 trade_history / review_history / option_strategies / runtimes.json
     → dashboard/data/dashboard_data.json → Pages → app.js 渲染
```

### 关键事实（实测）

| 项 | 实测结果 |
|---|---|
| trade_history 总行数 | **401** |
| Status 分布 | Stop_Loss_Hit 126 / Observation_Closed 98 / **Active 60** / Dropped 59 / Period_Matured 49 / 空 9 |
| 终态记录（283 条）有 Exit_Price + Exit_Date | **283 / 283（100%）** |
| Active（60 条） | Core_Dragon **24**、Observation 34、Trap_Warning 2 |
| Active 中有 Price（Rec_Price） | **60 / 60** |
| Active 中有 Stop_Loss | **60 / 60** |
| 是否已存在 portfolio 文件 | **无**（工作区与 git 中均不存在） |
| 正式买入价定义 | `trade_history.Price` = **推荐日真实 Open**（review.py:602-621，`op`） |
| 退出价定义 | `trade_history.Exit_Price`（review.py:1636，收盘价 round 4 位） |
| 前端图表能力 | app.js 已有 canvas sparkline（`drawSpark` / `drawDetailCharts`），可复用 |
| dashboard payload 组装 | `dashboard_export.py:2690`（`payload = {...}`） |

### 可复用而不改动的资产

- **买入价**：直接用 `trade_history.Price`，无需重算
- **退出信号**：直接用 `trade_history.Status` 终态 + `Exit_Price`，**不新增止损逻辑**
- **Core/Observation 区分**：`Tag` 字段已明确
- **持久化通道**：review.yml 已有成熟的 fetch + rebase + push（无 force、冲突即停）

---

## B. 最小修改方案

### 核心思路：**Portfolio 是一个"镜像层"，不发明任何新的买卖逻辑**

```
trade_history（推荐 + Review 退出裁决）
        ↓ 只读
Portfolio Decision Layer（确定性规则，无 AI 写账）
        ↓
Portfolio Ledger（3 个 CSV + 1 个 meta）
        ↓ 只读
dashboard_export → dashboard_data.json → app.js
```

### 1. 新增独立模块（不动 scan.py / review.py 业务逻辑）

`portfolio_50000.py`：`python portfolio_50000.py --data-dir .`

执行顺序（幂等）：

1. 读 `portfolio_50000_meta.json` → 不存在则**初始化**：`initial_capital=50000.00`、`start_date=今天(US)`
2. 读 positions / transactions / history（不存在即空）
3. **SELL 先于 BUY**（先释放现金，避免资金误判）
4. BUY：扫描 `trade_history` 中 `Tag=Core_Dragon` 且 `Status=Active` 且 `Rec_Date >= start_date`
5. 盯市 + 写当日 snapshot（upsert 同一天）
6. 写回 4 个文件

### 2. 现金恒定由流水推导（杜绝"每日重置"）

```
Cash = 50000.00 − Σ(BUY.amount) + Σ(SELL.amount)
```

**不保存现金余额快照** → 现金不可能被重置，因为它只是交易流水的函数。
`initial_capital` 只在 meta 文件不存在时写入一次。

### 3. Position Sizing（1 Unit = 固定美元，可审计）

```
UNIT_DOLLARS      = 10000.00     # = 初始本金 20%，固定值，不随权益复利（v1 不复利）
MAX_OPEN_POSITIONS = 4           # 4 × 10000 = 40000，至少保留 10000 现金

target = min(UNIT_DOLLARS, available_cash * CASH_USAGE_CAP)   # CASH_USAGE_CAP = 0.95
shares = floor(target / price)                                 # 整数股
if shares < 1: skip（不买入）
amount = shares * price
```

> 与你举例的差异需确认：AMD @630.48 → 本规则 `floor(10000/630.48)` = **15 股**（你示例写 20 股 ≈ $12,610）。
> 若要贴近示例，把 `UNIT_DOLLARS` 调到 **13000** 即可得 20 股（$12,609.60）。**该常量由你定，我不擅自决定。**

### 4. BUY 规则（全部确定性）

| 条件 | 要求 |
|---|---|
| Tag | 必须 `Core_Dragon`（Observation / Trap_Warning **一律不进 Portfolio**） |
| Status | 必须 `Active` |
| Rec_Price | 存在且 > 0（拿不到就不买，绝不猜测） |
| Rec_Date | ≥ `portfolio_start_date`（**不回溯历史推荐**） |
| 已持仓 | 同 Ticker 有 OPEN 仓位 → **HOLD，不重复买** |
| 幂等 | `Recommendation_ID = Ticker|Rec_Date|Tag` 已存在于 transactions → 跳过 |
| 仓位上限 | OPEN 数 ≥ MAX_OPEN_POSITIONS → 跳过 |
| 现金 | `cash < price` → 跳过 |

### 5. SELL 规则（同步 Review 裁决，不另发明）

对每个 OPEN 仓位，回查其 `Recommendation_ID` 对应的 trade_history 行：

```
Status ∈ {Stop_Loss_Hit, Dropped, Period_Matured, Observation_Closed, ...终态}
且 Exit_Date 与 Exit_Price 均非空
   → SELL 全部股数 @ Exit_Price，成交日 = Exit_Date
   → Realized_PnL = (Exit_Price − Entry_Price) × Shares
   → 仓位 Shares=0、Status=Closed
```

- 幂等键：`Ticker|Rec_Date|Tag|SELL|Exit_Date`
- **不自己判断止损** —— 止损判定完全沿用 Review 已有结论，避免两套止损打架
- Exit_Price 缺失 → **不卖**（fail-safe），等 Review 补齐

### 6. PnL 定义

```
Unrealized = Σ (Current_Price − Entry_Price) × Shares        （仅 OPEN）
Realized   = Σ transactions 中 SELL 的 Realized_PnL
Total_PnL  = Realized + Unrealized
Return_%   = Total_PnL / 50000.00 × 100        （分母恒为初始本金）
Total_Equity = Cash + Σ Market_Value
```

### 7. 幂等性矩阵

| 场景 | 行为 |
|---|---|
| positions.csv 已存在 | **不重新初始化 50000** |
| history.csv 已有今天 | **同一天 upsert，不新增重复行** |
| transaction 已存在同键 | **跳过** |
| 首次运行 | 写 meta + 写首条 snapshot（equity=50000.00，即曲线起点） |

---

## C. 预计修改 / 新增文件

| 文件 | 类型 | 原因 |
|---|---|---|
| `portfolio_50000.py` | **新增** | Portfolio 引擎（唯一写账入口，确定性、无 AI） |
| `portfolio_50000_positions.csv` | **新增数据** | 当前持仓状态 |
| `portfolio_50000_transactions.csv` | **新增数据** | 不可丢失的交易流水（现金与 Realized PnL 的唯一真相源） |
| `portfolio_50000_history.csv` | **新增数据** | 每日净值快照（Equity Curve 数据源） |
| `portfolio_50000_meta.json` | **新增数据** | `initial_capital` / `start_date` / `unit_dollars` —— 初始化一次，之后只读 |
| `dashboard_export.py` | 修改（**只读消费**） | 新增 `payload["portfolio"]`，约 60 行，**不改任何现有字段** |
| `app.js` | 修改 | `renderPortfolio()` + equity curve canvas，约 70 行，**不改现有渲染** |
| `index.html` | 修改 | 新增一个 `<section>` 区块，约 10 行 |
| `.github/workflows/review.yml` | 修改 | 加 1 个 step + git add 3 个 CSV，约 10 行 |
| `tests/test_portfolio_50000.py` | **新增** | 25+ 项回归测试 |

### 明确不动

`scan.py` / `review.py` / `scan.yml` / `dashboard-data.yml` / `dashboard/fetch_runtimes.py` / `scan_us_option_engine.py` / 任何 Schedule / Runtime / Options / Email —— **全部零改动**。

> 特别说明：**不需要改 dashboard-data.yml**，因此上一轮已生产验证的并发稳定性架构（concurrency false + reset --soft retry + 提交范围守卫）**完全不受影响**。Portfolio CSV 只由 review.yml 写入，与 dashboard-data 的 15 分钟提交互不冲突。

---

## D. 数据 Schema

### `portfolio_50000_meta.json`
```json
{
  "initial_capital": "50000.00",
  "start_date": "2026-10-06",
  "unit_dollars": "10000.00",
  "max_open_positions": 4,
  "currency": "USD"
}
```

### `portfolio_50000_positions.csv`
```
Ticker, Shares, Entry_Price, Entry_Date, Cost_Basis,
Current_Price, Market_Value, Unrealized_PnL, Unrealized_PnL_Pct,
Weight_Pct, Status, Stop_Loss, Recommendation_ID, Last_Update
```
- `Shares` 整数；`Entry_Price` **永久固定**（只在 BUY 时写入，之后永不更新）
- `Status` ∈ `OPEN` / `CLOSED`
- 金额字段一律 2 位小数

### `portfolio_50000_transactions.csv`
```
Txn_ID, Date, Ticker, Action, Shares, Price, Amount,
Realized_PnL, Cash_After, Reason, Recommendation_ID, Scan_Date
```
- `Txn_ID = Ticker|Rec_Date|Tag|BUY`（或 `...|SELL|Exit_Date`）→ **天然幂等键**
- `Realized_PnL`：BUY 为 0，SELL 为实际已实现盈亏
- `Cash_After`：审计用，便于人工核对

### `portfolio_50000_history.csv`
```
Date, Cash, Stock_Value, Total_Equity,
Realized_PnL, Unrealized_PnL, Total_PnL, Return_Pct, Open_Positions
```
- **每天一行，同一天 upsert**（幂等）
- 首行 = 初始化日，`Total_Equity = 50000.00` → 曲线起点恒为 $50,000

### Dashboard JSON（新增顶层键）
```json
"portfolio": {
  "initial_capital": 50000.00,
  "start_date": "2026-10-06",
  "cash": 10000.00,
  "stock_value": 40000.00,
  "total_equity": 50000.00,
  "realized_pnl": 0.00,
  "unrealized_pnl": 0.00,
  "total_pnl": 0.00,
  "return_pct": 0.00,
  "positions": [ { ticker, shares, entry_price, current_price,
                   market_value, unrealized_pnl, return_pct,
                   weight_pct, stop_loss, holding_days } ],
  "transactions": [ {date, ticker, action, shares, price, amount, realized_pnl, reason} ],
  "equity_curve": [ {date, total_equity} ]
}
```
- 文件不存在时输出 `null`，前端显示"尚未初始化"，**不报错、不白屏**

---

## E. 风险点

| # | 风险 | 影响 | 应对 |
|---|---|---|---|
| 1 | **Sizing 常量与你的示例不一致** | AMD 得 15 股而非 20 股 | 需你确认 `UNIT_DOLLARS`（10000 → 15 股；13000 → 20 股） |
| 2 | **历史 24 条 Active Core_Dragon 会被误当新建仓** | 凭空产生虚假历史收益 | **已用 `Rec_Date >= start_date` 闸门阻断**；但副作用是 Portfolio 在下次 Scan 产生新 Core 之前会保持空仓 |
| 3 | Review 的 Exit_Price 缺失 | 该仓位不会卖出，浮亏持续 | fail-safe：**不卖**，等 Review 补齐（现有数据 283/283 都有 Exit_Price，风险低） |
| 4 | yfinance 在 review 环境取价失败 | 当日快照价格陈旧 | 回退用上一快照价格并标记，绝不写 NaN；不影响已成交记录 |
| 5 | 浮点累积误差 | 金额出现 50000.00000001 | 金额全程 `Decimal`，落盘 `quantize(0.01)`；股数为 int |
| 6 | 首次运行 Portfolio 长期空仓 | 用户觉得"没反应" | 报告明确说明：Portfolio 从 start_date 之后**新产生的 Core 推荐**才开始建仓 |
| 7 | review.yml 新增文件进 commit | 与远端 dashboard-data 提交冲突 | 沿用 review.yml 已有 fetch+rebase（无 force）；portfolio CSV 只此一处写入 |
| 8 | Dashboard JSON 体积增加 | pages 加载略增 | 仅 3 个 CSV，体量极小（KB 级） |

**无 P0 级风险**；无需要修改现有核心逻辑的地方 —— 所有买卖输入均来自现有 trade_history，Portfolio 只是"确定性镜像"。

---

## F. 测试计划

新增 `tests/test_portfolio_50000.py`，至少覆盖你要求的 25 项：

| # | 用例 | # | 用例 |
|---|---|---|---|
| 1 | Initial Capital = 50000 | 14 | Total Equity 正确 |
| 2 | 第二次运行不重新初始化 | 15 | Total PnL 正确 |
| 3 | BUY 创建 Position | 16 | Return % 正确（分母恒 50000） |
| 4 | Entry Price 固定 | 17 | History Snapshot 正确 |
| 5 | 当前价变化不改 Entry Price | 18 | 重复运行不重复 transaction |
| 6 | Unrealized PnL 为正正确 | 19 | 重复运行不重复 snapshot |
| 7 | Unrealized PnL 为负正确 | 20 | 50000 永不每日重置 |
| 8 | SELL 产生 Realized PnL | 21 | Stop Loss 退出正确同步 |
| 9 | SELL 后 Cash 正确 | 22 | Dashboard 字段正确 |
| 10 | SELL 后 Position 清零 | 23 | 价格两位小数 |
| 11 | 已持有再 BUY 不重复买入 | 24 | 空 Portfolio 正确处理 |
| 12 | Observation 不进入 Portfolio | 25 | 全卖出后 Cash / Equity 正确 |
| 13 | Cash 正确计算 | 26 | 金额无浮点误差（Decimal） |

同时运行：

- 新增 Portfolio 测试
- 原有全部测试（含 Options RR 80、Review 字段 38、Dashboard 稳定性 30 等）
- 完整 project test suite
- `py_compile`（相关 py）
- `node --check app.js`
- `git diff --check`

集成/生产验证（实施后）：

1. 本地跑 `portfolio_50000.py` 两次 → 验证幂等与无重置
2. push → 等 review.yml 自然运行（**不手动 dispatch**）
3. 验证 3 个 CSV 已入库、Dashboard 出现 Portfolio 区块、Equity Curve 起点 = 50000

---

## 需要你拍板的 3 件事

1. **`UNIT_DOLLARS`**：默认 10000（AMD→15 股），还是 13000（→20 股，贴近你示例）？
2. **`MAX_OPEN_POSITIONS`**：默认 4（留 $10,000 现金，贴合你示例）？
3. **是否接受"Portfolio 从 start_date 之后的新 Core 推荐才开始建仓"**（即不回溯现有 24 条 Active Core）？

确认后我立即实施；在此之前**不修改任何代码**。
