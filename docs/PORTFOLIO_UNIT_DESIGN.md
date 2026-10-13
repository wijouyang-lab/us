# $50,000 模拟账户 Unit 制设计调查报告

> 调查时间：2026-10-08（GMT+8）
> 性质：**只读调查，未修改任何代码、未 push、未 rebase、未碰监控 PID 536931、未改持仓/交易记录。**
> 代码源：`/tmp/us/portfolio_50000.py`、`/tmp/us/portfolio_50000_meta.json`、展示层 `/tmp/us/dashboard_export.py`

---

## 1. Unit 常量与规则（文件 + 行号）

| 常量 | 值 | 位置 | 说明 |
|---|---|---|---|
| `INITIAL_CAPITAL` | `Decimal("50000.00")` | `portfolio_50000.py:40` | 初始本金 |
| `UNIT_DOLLARS` | `Decimal("10000.00")` | `portfolio_50000.py:41` | **1 Unit 目标资金（固定值，v1 不复利）** |
| `MAX_OPEN_POSITIONS` | `4` | `portfolio_50000.py:42` | **最多 4 个同时存在的 Long Stock Unit** |

`portfolio_50000_meta.json`（运行时配置，与代码常量一致）：

```json
{ "initial_capital": "50000.00", "start_date": "2026-10-06",
  "unit_dollars": "10000.00", "max_open_positions": 4, "currency": "USD" }
```

> **结论（问题 1）**：unit 与上限均**硬编码为 4 个 unit、每 unit $10,000（= 初始本金的 20%）**。
> `UNIT_DOLLARS` 是字面常量，`MAX_OPEN_POSITIONS` 是字面整数，无外部配置开关、无环境变量覆盖。

---

## 2. 开仓逻辑（最多 / 必须 / 排序）

入口 `process_buys()`（`portfolio_50000.py:292-378`），docstring 明确：

> **"BUY：新 Core 推荐、未持有、有空闲 Unit、现金足够 → 买 1 Unit。"**（`portfolio_50000.py:293`）

逐条对应三个子问题：

**(a) 是"最多 4 units、按信号数决定"，还是"必须满仓 4 units"？**

→ **最多 4 units、按信号数决定。不存在"必须满仓"规则。** 证据：
- `portfolio_50000.py:318` `if open_count >= MAX_OPEN_POSITIONS:` → 跳过并记日志 `"⏸ {Ticker} 无空闲 Unit（{open_count}/4）→ 仅保留为推荐"`。
- 没有"补仓到 4"的 rebalance 循环；每天只对**新出现的 Core 推荐**开仓，已持仓的跳过（`L315-316` HOLD 不重复买）。
- 因此某日若只有 2 个 Core 信号 → 只开 2 units；若 0 个信号 → 0 units（仅全现金）。

**(b) 今天只有 2 个信号，会不会只开 2 units？**

→ **会。** 每个信号最多买 1 unit（L349 `Reason: "Core recommendation -> 1 Unit long"`），信号耗尽即止。无强制填满。

**(c) 信号数超过 4 时如何选择（排序规则）？**

→ **按推荐日期升序、Ticker 升序的确定性先到先得**，填满 4 个空闲 unit 后其余跳过：
- `portfolio_50000.py:303-308`：候选 = `Tag==CORE_TAG` 且 `Status==Active` 且 `Rec_Date >= start_date` 且价格有效的推荐；`candidates.sort(key=lambda r: (r["Rec_Date"], r["Ticker"]))`。
- 注释明确："按推荐日期升序处理，保证先来的推荐先占用 Unit（确定性，不受 dict 顺序影响）"。
- 第 5 个及以后的信号被 `L318-320` 跳过（"仅保留为推荐"），不会排队到次日自动补（无待开仓队列持久化）。

> **每 unit 份额**：`shares = floor(UNIT_DOLLARS / price)`（`L322`），并用 `L327-331` 双保险确保 `amount` 绝不超 `UNIT_DOLLARS`。单一持仓恒为 1 unit（约 $10,000），**不存在 5+ units 或更高单只仓位**（硬上限 `MAX_OPEN_POSITIONS=4` + 每信号 1 unit）。

---

## 3. 现金规则（有 / 无）

| 现金相关约束 | 是否存在 | 位置 / 证据 |
|---|---|---|
| 购买时现金不足则跳过 | **有** | `portfolio_50000.py:332-334` `if amount > cash:` → 跳过 |
| `min_cash` / 最低现金保留 | **无** | 全文件 grep `min_cash\|cash_buffer\|reserve\|buffer\|MAX_EXPOSURE\|rebalance` → **零命中** |
| `cash_buffer` / 现金缓冲 | **无** | 同上 |
| `max_exposure` / 最大敞口 | **无** | 同上 |
| 每日 rebalance / 再平衡 | **无** | 无补仓逻辑（见 §2） |

> 现金的**唯一**约束是"买不起就不买"（`L332`）。**没有任何主动保留现金/敞口上限的规则。**

---

## 4. 历史上的 unit 使用趋势

**本地可核查的事实：**
- `portfolio_50000_history.csv` 仅有 **1 行**：`2026-10-06, Cash=50000.00, Stock_Value=0.00, Open_Positions=0`（创立日，全现金、0 持仓）。
- `portfolio_50000_positions.csv`：**仅表头，无数据行**（当前无落地持仓）。
- `dashboard/data/dashboard_data.json` 的 `portfolio` 段：`asof=2026-10-06, cash=50000.0, open_positions=0, positions=[]`（同样停留在创立日快照）。

**关键说明：** 用户所描述的 live 状态（Open Units = 4/4、4 只各约 $10,000、现金 $10,438.80）**不存在于本 checkout 的落盘文件**，它来自云端运行管线实时写入的快照（positions / history / dashboard 缓存），本地工作副本尚未同步该数据。

因此：
- **无法从本地文件验证"过去几天 open_units 是否总在 4"**，也**无法确认是否存在 1/4、2/4、3/4 的日期**。
- 已知事实：账户 `start_date = 2026-10-06`，调查日 2026-10-08，**组合仅运行 2 天**，本地仅捕捉到创立日 0 持仓快照，尚无任何多日趋势样本。
- 依据设计（§2），open_units 应为**信号驱动、浮动于 0–4**：出现 1/4、2/4、3/4 完全正常，仅在当日 Core 信号数 < 4 时发生。

> 若需确证历史逐日 unit 使用，应读取云端最新 `portfolio_50000_history.csv`（含每日 `Open_Positions` 列）或最新 `dashboard_data.json` 的 `equity_curve`——本只读调查未改动、亦未拉取该远端数据。

---

## 5. 设计意图判定

| 用户疑问 | 判定 |
|---|---|
| 20% 现金是"主动风控留 20%"吗？ | **否。** 代码**无任何 min_cash / cash_buffer / max_exposure / rebalance**（§3 grep 零命中）。现金唯一约束是"买不起才不买"。 |
| 20% 现金是"4 units 用满后自然剩余"吗？ | **是。** 4 × ~$10,000 = ~$40,000 投入，剩余 ~$10,000 ≈ 初始本金的 20%。这是上限填满后的**算术余数**，非刻意预留。 |
| "用满 4 units"是强制满仓吗？ | **否，是信号驱动。** 当天 Core 信号 ≥ 4 才填满 4；信号少则少开（§2）。 |

> **综合判定：用户当前的 4/4 + ~20% 现金 = "恰好当日有 ≥4 个 Core 信号 → 填满 4 unit 上限 → 自然剩余约 20% 现金"。这是"信号用满到上限"的副产品，不是"主动风控预留 20%"。**

> 推演：若某日只有 2 个 Core 信号，则开 2 units（~$20,000），现金约 **~60%**；此时 dashboard 会显示 `Open Units = 2/4`、现金占比骤升。可见 20% 并非固定不变的风控位。

---

## 6. 每 unit 金额：固定还是随 equity 动态调整？

→ **固定 $10,000，v1 不复利，不随 equity 调整。**

证据：
- `portfolio_50000.py:41` 注释明示："1 Unit 目标资金（**固定值，v1 不复利**）"。
- `UNIT_DOLLARS` 为模块级常量；`process_buys` 内 `shares = floor(UNIT_DOLLARS / price)`（`L322`）只依赖单价，不读 `total_equity`。
- 无任何按 `total_equity` 重算 unit 的逻辑（grep `rebalance\|equity` 在买入路径无命中）。

> **推演：若账户 equity 涨到 $60,000，unit 仍为 $10,000（不会变 $12,000）。** 4 units 仍投 ~$40,000，现金随浮盈增长到 ~$20,000+。unit 规模只在改 `UNIT_DOLLARS` 常量（或未来 v2 引入复利/再平衡）时变化。

---

## 7. 用户疑虑是否成立（总结）

| 用户原问 | 是否成立 | 依据 |
|---|---|---|
| 为什么用满 4 units？ | 因**当日 Core 信号 ≥ 4**，每信号 1 unit 填满上限 4 | §2（L318 上限、L308 排序、L349 每信号 1 unit） |
| 是否有"必须满仓"规则？ | **不成立**（无 must-fill / 无补仓 rebalance） | §2（仅"新信号→开 1 unit"，信号少则少开） |
| 20% 现金是设计还是巧合？ | **设计上无现金缓冲；20% 是 4 unit 用满后的自然余数（巧合/算术结果），非主动风控** | §3（无 buffer）、§5 |
| 是否允许 5+ units / 更高单只仓位？ | **否**（硬上限 4 + 每信号 1 unit） | §2（L318、L322、L327-331） |
| unit 是否随 equity 变 $12,000？ | **否**（固定 $10,000，v1 不复利） | §6（L41 注释、L322） |

**一句话结论：** 该账户是"**上限 4 units + 每信号 1 unit + 固定 $10,000/unit + 无现金缓冲**"的朴素等权 Long 设计。当前 4/4 与 ~20% 现金是"信号恰好填满上限"的**涌现结果**，并非一套主动风控（无 min_cash / max_exposure / rebalance）。若担忧"被动满仓"，真正可调的旋钮只有 `MAX_OPEN_POSITIONS`、`UNIT_DOLLARS` 两个常量，以及是否引入显式现金缓冲——这些均为设计层改动，本次只读调查未做任何修改。

---

## 附：核查命令与范围（可复现）

- 常量：`Read portfolio_50000.py:39-55`、`:180-181`；`Read portfolio_50000_meta.json`
- 开仓：`Read portfolio_50000.py:292-378`（候选筛选 L303-308、上限 L318、份额 L322、双保险 L327-331、现金 L332）
- 现金约束：grep `min_cash\|cash_buffer\|reserve\|buffer\|MAX_EXPOSURE\|rebalance` in `portfolio_50000.py` → 零命中
- 展示层：`Read dashboard_export.py:2475-2529`（`last.get("Cash")`、`last.get("Open_Positions")`、`max_open_positions` 均来自 history CSV 末行 + meta，无额外现金规则）
- 历史：`Read portfolio_50000_history.csv`（仅 10-06 一行）、`Read portfolio_50000_positions.csv`（空）、`Read dashboard_data.json:73939-73964`（asof 10-06, 0 持仓）
