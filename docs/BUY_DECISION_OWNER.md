# $50k 组合买入决策归属调查（只读）

> 调查目标：确认 $50,000 模拟组合的「买不买」决策发生在 scan 还是 review，以及是否用到
> 「推荐之后的信息」（美股开盘/收盘后的价格变动），从而构成后见之明（look-ahead bias）。
> 铁律：只读，未改代码、未 push、未碰监控。

---

## 1. process_buys 的调用链（谁调、何时调）

| 环节 | 证据 | 结论 |
|---|---|---|
| `scan.py` 是否执行买入 | `scan.py` 仅 `grep` 到 `POSITIONS_CSV_PATH` 常量（L67）与 `from portfolio_target import ...`（L3855）；**不 import / 不调用 `portfolio_50000` 的 `run`/`process_buys`** | scan **不执行账本买入** |
| scan 做的 portfolio 相关事 | `portfolio_target.py` 头部注释明确：ENABLE_TARGET_FILE=1 时落盘 `portfolio_50000_target.csv`，**纯展示用的「目标持仓」卡片**，不写 positions/transactions、不执行买入 | scan 只产出"打算买"的**展示**，不落地成交 |
| `review.yml` 步骤 | L57-58：`运行美股盘后复盘` → `python review.py`；随后 `python portfolio_50000.py --data-dir .`（**不带 `--price-only`**） | 账本买入在 **review** 阶段执行 |
| `scan.yml` | 仅 `python scan.py`（L47），无 portfolio 步骤 | scan 不碰账本 |
| 内部调用 | `portfolio_50000.py` `run()` L799：`for line in process_buys(positions, transactions, recs, meta, today)` | 买入逻辑在 `run()` 内，`run()` 由 review 的 CLI 调用触发 |

**调用链结论：**
```
scan.py  → 生成推荐 → pending CSV + (flag) portfolio_50000_target.csv【展示，不成交】
review.py → 首次吃 pending → trade_history.csv 写 "Active" + scan 时价格
review.yml → python portfolio_50000.py --data-dir . → run() → process_buys()  ← 真正的买入决策/成交在这里
```
**买入决策的执行发生在 review，不在 scan。** 这与"scan 决定买不买、review 只回填"的理想架构**不符**——scan 只给了一个展示用的 target，真实账本买入由 review 的 `process_buys` 决定。

---

## 2. 决策输入字段清单（逐字段）

`process_buys`（L443-560）读取两类数据：`recs`（来自 `trade_history.csv`）与 `positions/transactions/meta`。

### 2.1 来自 `recs`（=`load_recommendations` 从 trade_history.csv 加载，L350-372）
| 字段 | 用途 | 是否"推荐后/实时"信息 |
|---|---|---|
| `Tag` | 必须 `== "Core_Dragon"` 才买（L470） | 否，scan 时打的标签 |
| `Status` | 必须 `== "Active"` 才买（L471） | 否——见 §3 说明 |
| `Rec_Date` | ≥ start_date 才买（L472）；**并作为 BUY 成交 `Date`**（L523） | 否，scan 时日期 |
| `Price` | >0 校验（L473）；**并作为成交 `Entry_Price`/执行价**（L502-527） | 否，**scan 时记录价** |
| `Ticker` | 未持仓才买（L481）；写入持仓 | 否 |
| `Stop_Loss` | **仅写入持仓的止损线**（L552），**不是买入过滤条件** | 否，scan 时止损线 |
| `AI_Score` | 被 `unit_dollars_for` 读取（L194），但当前恒为 None → 退化为固定 1 Unit（L199-200），**不构成买/不买闸门** | 否（且当前未落地） |

### 2.2 来自 `positions` / `transactions` / `meta`（组合状态）
| 字段 | 用途 | 性质 |
|---|---|---|
| `open_tickers` / `open_count` | 已持有则跳过（L481, L451） | 组合状态 |
| `Market_Value`（OPEN 持仓） | 算 `equity`、做 `_within_alloc` 占比预审（L454, L212-219） | 组合状态（上一次盯市价） |
| `Cooldown_Until` | 止损后 7 天冷却闸门（L465, L486-489） | 组合状态 |
| `transactions` → `stopped_recent` | 近 1-2 日刚止损则暂不复买（L466, L491-493） | 组合状态 |
| `transactions` → `_had_stop_today` | 全清仓当日停手（L460-462） | 组合状态 |
| `cash` = `derive_cash(transactions)` | 现金不足则跳过（L452, L514） | 组合状态 |
| `Unit_ID`（空闲 unit） | 无空闲 Unit 则跳过（L517-520） | 组合状态 |
| `meta.start_date` | 推荐日期下限（L447, L472） | 配置 |

### 2.3 明确**未读取**的字段（关键）
- ❌ 不读任何"当前价 / 实时价 / review 时点价格"——候选股的成交价固定用 `rec["Price"]`（scan 时价）。
- ❌ 不读"推荐后涨跌 / 未来收益率 / 收盘表现"来决定买不买。
- ❌ `mark_to_market`（L563）与 `fetch_last_closes`（L820）只用于**已有 OPEN 持仓的盯市**，不参与买入候选的筛选。

---

## 3. "Active" 状态怎么来——是否用到推荐后信息

- `Status="Active"` 是推荐被 ingest 时的**默认初始态**：`review.py` `supplement_us_stocks_from_pending()` 吃 pending 时写入（L641），同时写入 **scan 时 OHLC 价**作为 `Price`。
- Core（`Core_Dragon`）推荐离开 `Active` 的**唯一途径**是 `Stop_Loss_Hit`：`review.py` 检测到真实击穿止损线后调用 `update_trade_history_status(..., "Stop_Loss_Hit", ...)`（L1848，经 `update_trade_history_status` L1450-1467）。
  - 这是**推荐自带的退出规则被真实价格事件触发**，不是"它跌了所以主观不买"。
- `TERMINAL_STATUSES`（L47-50）含 `Stop_Loss_Hit/Dropped/Period_Matured/Observation_Closed/Target_Reached/Closed/Exited`，但其中 `Observation_Closed`（L1643，阈值 `OBS_TARGET_PCT=10%` / `OBS_INVALIDATION_PCT=-6%` / `OBS_MAX_TRADING_SESSIONS=10`，L1505-1507）**仅作用于 `Observation` 标签**，与 `process_buys` 只看的 `Core_Dragon` 无关。
- **没有任何代码依据"推荐后涨/跌"把 Core 推荐从 Active 改成 Passed/Expired 来阻止买入。**

> 结论：`Active` 是一个"未被终止即默认有效"的被动态，不携带推荐后涨跌判断。

---

## 4. 决策时点

- `process_buys` **只在 `run()` 内被调用**，而 `run()` 只由 `python portfolio_50000.py --data-dir .`（review.yml）触发 → 决策**代码运行于 review 时点**。
- `today = us_today_str()`（L105-113）= 美东当前日期。该 `today` 用于：冷却比较（L487）、近 1-2 日止损窗口（L466）、全清仓停手（L460）、`Last_Update` 与 history 快照日（L834）。
- **但 BUY 成交的 `Date` = `rec["Rec_Date"]`（scan 日），`Entry_Price` = `rec["Price"]`（scan 价）**（L523-527, L543-544）。即**记录的交易被锚定到推荐日/推荐价，而非 review 当日**。
- 它**不区分"今天是 scan 日还是 review 日"**，只对当前 Active 的 rec 生效。
- 同一 `trade_history` 记录，scan 时点跑 vs review 时点跑：`Tag/Status/Rec_Date/Price/Ticker/分配/现金` 这些买否判据**与运行时刻无关**；唯一受 `today` 影响的是冷却/近期止损/全清仓闸门（都用组合状态）。
- **已知架构缺口（非后见之明，但需注意）**：若某 Core 推荐在 ingest 当天 review 因无空闲 Unit/现金而未买，后续某天 review 腾出额度时会**仍以旧 scan 价、旧 scan 日**买入（成交价锚定旧价，不是当时实时价）。属"延迟以旧价成交"，不构成看未来收益决策，但时点不直观。

---

## 5. 关键判断与结论

1. **决策在 scan 还是 review？** → 在 **review**（`process_buys` 由 review 的 CLI 调用执行）。scan 只生成推荐 + 一个**展示用** target 文件，不执行账本买入。这与"scan 决定买不买"的理想不符。
2. **如果决策在 review，它用了"推荐后的信息"吗？** → **没有**。`process_buys` 不读任何实时价/推荐后涨跌；成交价与成交日都锚定 scan 时推荐（`rec["Price"]` / `rec["Rec_Date"]`）。唯一会改 `Active` 的是真实击穿止损（推荐自带退出规则）。
3. **是后见之明吗？** → **严格意义上不是**：买不买的判据与"推荐之后价格怎么走"无关，且成交锚定推荐时价格/日期。

### 结论

> **决策在 review，但只用推荐时信息 → ✅ 无后见之明（但架构不直观）。**

- ✅ 无 look-ahead：买入价=scan 记录价、成交日=scan 日；决策不用推荐后/实时价格。
- ⚠️ 架构不直观：① 执行入口在 review 而非 scan（与"scan 决定、review 回填"的预期相反）；② `today`（review 日）参与冷却/分配闸门；③ 可能"延迟多日仍以旧价买入"。

### 若要彻底对齐"scan 决定、review 只回填"的理想架构（可选，未执行）
- 把 `process_buys` 的执行从 review.yml 的 `portfolio_50000.py --data-dir .` 迁移到 scan 之后（scan.yml 或 scan 末尾），使"买不买"在 scan 时点定下；
- review 侧 `portfolio_50000.py` 改为仅 `--price-only`（盯市/复盘）+ `process_sells`（沿用 Review 终态裁决）；
- 当前 scan 已有的 `portfolio_50000_target.csv`（展示用）可保留，但需明确它不是成交依据，成交仍以账本为准。

---

## 附：证据索引（文件:行）
- `portfolio_50000.py:443-560` — `process_buys` 完整逻辑（字段使用）
- `portfolio_50000.py:502, 523, 527, 543-544` — 成交价/日锚定 `rec["Price"]` / `rec["Rec_Date"]`
- `portfolio_50000.py:350-372` — `load_recommendations` 加载字段
- `portfolio_50000.py:799` — `run()` 调用 `process_buys`
- `portfolio_50000.py:745-893` — `run()` / `main()`（CLI，`--price-only` 分支）
- `portfolio_50000.py:105-113` — `us_today_str`（决策用 today）
- `portfolio_target.py:1-12` — scan 的 target 为展示用，不执行买入
- `review.yml:57-58` — `python portfolio_50000.py --data-dir .`（非 price-only）
- `scan.yml:47` — scan 仅 `python scan.py`
- `review.py:641` — ingest 时写 `Status="Active"` + scan 价
- `review.py:1450-1467, 1848` — `Stop_Loss_Hit` 真实击穿才改终态
- `review.py:1505-1507, 1643` — Observation 阈值，仅作用于 Observation 标签
- `portfolio_50000.py:47-50` — `TERMINAL_STATUSES`（Core 离开 Active 仅 `Stop_Loss_Hit` 等真实事件）
