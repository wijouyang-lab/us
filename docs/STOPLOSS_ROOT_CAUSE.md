# 止损三值不一致 —— 根因报告（只读调查）

> ⚠️ **结论已于 2026-10-13 被推翻 —— 本文仅存历史调查价值**
>
> 本文 `:182-183` 的根因结论（「ANET 现价 ~216 远高于 197.69 → 路径 B 事实上永远不会触发」）**是错的**。
> 实测根因：`dec()` 只剥逗号、**不剥 `$`**，故 `dec("$197.69") is None`，而 `_run_intraday_stop` 是
> `stop = dec(...)` → `if stop is None: continue` → **整条逻辑被跳过，与价格无关，任何价格都不会触发**。
> 正确结论见 `HANDOVER.md:176-179`。**处置止损问题请以 `HANDOVER.md` 为准，勿引用本文 `:182-183` 的结论。**

> 调查对象：ANET（Unit U002）在三个界面出现的不同止损价
> - 持仓卡片：`$197.69`
> - 详情页：`209.36`
> - review 日志：`210.24`
>
> 调查方式：纯只读（Read / grep）。**未改任何代码、未 push、未触碰监控。**
> 本机 `C:\dev\us` @ `3077040e`（main）。
>
> ⚠️ 仓库内已存在一份 `docs/ANET_STOPLOSS_TRIPLE.md`（上一工具产出）。本报告**逐条复核**了它，结论方向一致，但其**行号已漂移**（例如它写 `portfolio_50000.py:552`，实际为 `:555`；`:684` 实际为 `:687`）。下文行号均为**当前 HEAD 实测**。

---

## 0. 一分钟结论

**同一个止损，被存在两个不同的文件里；而界面各读了其中一个。**

| 位置 | 值 | 读的文件 | 谁在维护它 |
|---|---|---|---|
| 持仓卡片 | `$197.69` | `portfolio_50000_positions.csv` 的 `Stop_Loss` | **建仓时写入一次，之后永不更新** |
| 详情页 | `209.36` | `trade_history.csv` 的 `Stop_Loss` | review 的移动止损，**会抬高并落盘** |
| review 日志 | `210.24` | 运行时实时重算（`exec_stop`） | review 每次现算，**只在非触发时回写** |

**根因一句话：移动止损确实落盘了，但落到了 `trade_history.csv`；而卡片读的是 `portfolio_50000_positions.csv`——后者的 `Stop_Loss` 全仓库唯一写入点是建仓那一行，持仓期间没有任何代码路径更新它。**

---

## 1. 三个数字各自的来源（文件 + 行号）

### 1.1 卡片 `$197.69` —— 账本原始止损，**冻结态**

| 环节 | 位置 |
|---|---|
| 数据文件 | `portfolio_50000_positions.csv` → `Stop_Loss` 列 |
| **唯一写入点** | `portfolio_50000.py:555` → `"Stop_Loss": rec["Stop_Loss"]`（在 `process_buys()` 建仓分支内） |
| 值的来源 | `portfolio_50000.py:372` `load_recommendations()` 从 `trade_history.csv` 读 `Stop_Loss`（建仓那一刻的值） |
| 列定义 | `portfolio_50000.py:57-62` `POSITION_COLUMNS`（含 `Stop_Loss`，**不含** `Trail_Stop`） |
| 导出层 | `dashboard_export.py:2645`（`build_portfolio()`，函数始于 `:2589`）：`"stop_loss": clean_text(r.get("Stop_Loss")) or None` —— **纯透传，不重算** |
| 前端 | `app.js:441` 卡片渲染 `esc(p.stop_loss \|\| NA)`；`p` = `portfolio.positions[]`（`app.js:357/391` 说明 positions 是主表） |

**验算**：入场价 `211.30`，`ATR% ≈ 3.22%` → `211.30 − 2×ATR ≈ 197.70`，即「入场价 − 2×ATR」的初始 ATR 保护线。

**关键证据（本次新验证）**：`mark_to_market()`（`portfolio_50000.py:566-603`）只更新
`Current_Price / Extended_Price / Extended_Time / Market_Value / Unrealized_PnL / Unrealized_PnL_Pct / Last_Update`
—— **完全不碰 `Stop_Loss`**。

并且对 `portfolio_50000.py` 全文 grep `Stop_Loss`，只有 7 处：

```
:48   TERMINAL_STATUSES 常量
:60   POSITION_COLUMNS 列定义
:372  load_recommendations 读 trade_history
:440  if rec["Status"] == "Stop_Loss_Hit"（冷却判断）
:555  process_buys 写入 positions   ← 唯一的写
:643  docstring
:687  _run_intraday_stop 读取 positions
```

→ **确认：建仓后 `positions.csv` 的 `Stop_Loss` 永远不变。**

### 1.2 详情页 `209.36` —— `trade_history.csv` 里的**存储态移动止损**

| 环节 | 位置 |
|---|---|
| 数据文件 | `trade_history.csv` → `Stop_Loss` 列（另配套 `Trail_Stop` / `Stop_Method` / `MA20` / `MA50` / `ATR_Pct`） |
| 维护者 | `review.py:1426-1448` `update_trade_history_trailing_stop()` → **`:1446 d.to_csv(TRADE_HISTORY, ...)` 真落盘** |
| 调用点 | `review.py:1878-1882`（仅当 `next_stop` 存在且非当日新仓） |
| 导出层 | `dashboard_export.py:2100`（`build_events()`，函数始于 `:2005`）：`"stop_loss": parse_num(r.get("Stop_Loss"))`，`"source": "trade_history"` |
| 前端 | `app.js:198` `STOCKS = (data.stocks \|\| []).map(...)`；`app.js:238` `stop: num(s.stop_loss)`；详情页按 ticker 从 STOCKS 取 `s`（`app.js:1625` / `:1964`）；`app.js:1793` `mx('止损价', nv(s.stop, 2))` |

→ **详情页读的是 `trade_history`，不是账本 positions。** 所以它显示 209.36 而非 197.69。

### 1.3 review 日志 `210.24` —— 当次**实时重算**的执行止损

| 环节 | 位置 |
|---|---|
| 计算函数 | `review.py:1374-1423` `get_trailing_stop_context()` |
| 取值 | `review.py:1819` `exec_stop = old_stop if is_same_day_entry and old_stop>0 else (ctx.get("exec_stop") if ctx else old_stop)` |
| 判定 | `review.py:1826` `evaluate_stop_trigger(low, closep, openp, exec_stop)`（定义在 `:763`） |
| 日志 | `review.py:1871-1873` `[风控诊断] ... Stop_Loss={exec_stop} Trigger={trigger_result} Exit={exitp} ...` |
| 触发后写回 | `review.py:1848` `update_trade_history_status(ticker, rec_date_str, "Stop_Loss_Hit", exitp)` |

---

## 2. 移动止损的公式与落盘位置

### 2.1 公式（`review.py:1388-1421`）

```python
# 1388-1391: 取近 6 个月日线，算 MA20 / MA50 / ATR14；close / atr 取最后一根
pct       = max(atr_floor_pct(3), min(atr_ceiling_pct(12), atr_multiplier(2) * atr / close))   # :1393
candidate = max(close*(1-pct/100), ma20 - atr, ma50 - 1.5*atr)                                   # :1394

# :1398-1399  前 3 个日历日快速试错：-5%
if entry_price and days_held <= early_days(3):
    candidate = max(candidate, entry_price * (1 + early_stop_pct(-5)/100))

# :1401-1406  浮盈保护（50% / 30% / 15% 三档，命中一档即 break）
if pnl_pct >= profit_lock_N_pct:
    candidate = max(candidate, close * (1 - profit_lock_N_drawdown_pct/100))

# :1407-1409  MACD 死叉 且 KDJ_J 下行 → 收紧到 close - 1.5*ATR
if macd_bear and kdj_falling:
    candidate = max(candidate, close - 1.5*atr)

candidate = min(candidate, close * 0.98)        # :1410 封顶：不高于现价 98%

# :1411-1418  trailing：只升不降（用历史止损做 floor，但要做合理性校验）
if old_stop 有效 and is_valid_existing_stop(old_stop, entry_price):
    candidate = max(old_stop, candidate)
else:
    print("[STOP_FLOOR_REJECT] ...")

return {"exec_stop": round(candidate,2), "ma20":..., "ma50":..., "atr_pct":..., ...}   # :1419
```

参数来自 `strategy_params.json` → `EXIT_PARAMS`（`review.py:53-64`，默认 `atr_multiplier=2.0`、`atr_floor_pct=3.0`、`atr_ceiling_pct=12.0`、`profit_lock_1/2/3 = 15/30/50%`、回撤 `10/8/12%`）。

合理性校验 `is_valid_existing_stop()`（`review.py:734`）用 `MAX_TRAILING_RATIO=2.0` 拦截异常旧止损（跨 ticker 污染 / 高于入场价）——**被拒时 `[STOP_FLOOR_REJECT]` 会打日志**。

### 2.2 落盘位置 —— **有落盘，但只落到 `trade_history.csv`**

**是**，review 算完的移动止损**会落盘**，通过 `update_trade_history_trailing_stop()`（`review.py:1426-1448`）：

```python
d.loc[mask,"Stop_Loss"]   = str(stop_price)        # :1440
d.loc[mask,"Trail_Stop"]  = str(stop_price)        # :1441
d.loc[mask,"Stop_Method"] = "MA20/MA50 + ATR + MACD/KDJ"   # :1442
d.loc[mask,"MA20"/"MA50"/"ATR_Pct"] = ...          # :1443-1445
d.to_csv(TRADE_HISTORY, index=False, encoding="utf-8")     # :1446  ← 真正写文件
```

调用点 `review.py:1878-1882`：

```python
next_ctx  = get_trailing_stop_context(ticker, exec_stop, None, ...)     # :1878  before_date=None
next_stop = exec_stop if is_same_day_entry and exec_stop else (next_ctx.get("exec_stop") if next_ctx else exec_stop)
if next_stop and not is_same_day_entry:
    update_trade_history_trailing_stop(ticker, rec_date_str, next_stop, next_ctx or ctx or {})   # :1882
```

**落盘文件：`trade_history.csv`。`portfolio_50000_positions.csv` 从头到尾没有被 review 写过一个字节。**

### 2.3 为什么日志的 210.24 比落盘的 209.36 还高（本次查清）

两个原因，都是**代码结构决定的**，不是 bug：

1. **两次计算用的窗口/floot 不同**：
   - `:1814` `ctx` → `before_date=REVIEW_SESSION_DATE`，floor 用 `old_stop`（= 已落盘的 209.36）
   - `:1878` `next_ctx` → `before_date=None`，floor 用 `exec_stop`（= 210.24）
   由于 `next_stop = max(floor, candidate)`，`next_stop ≥ exec_stop`。
2. **触发时根本不回写** —— `review.py:1875-1876`：

   ```python
   if trigger_result in ("STOP_TRIGGERED", "DATA_MISSING"):
       continue                      # ← 直接跳过 :1882 的回写
   ```
   所以一旦本次判定为 `STOP_TRIGGERED`，抬高的 210.24 **不会**被写进 `trade_history`；写进去的是 `update_trade_history_status(..., "Stop_Loss_Hit", exitp)`（`:1848`）。落盘的 209.36 是**更早某次未触发时**回写的值。

3. 另一个收窄点：`update_trade_history_trailing_stop` 的 mask（`:1434-1438`）要求 **`Status == "Active"`**，一旦转成 `Stop_Loss_Hit` 就再也不会被更新。

→ **结论：210.24 是"当次执行态"，209.36 是"上一次成功回写的存储态"，197.69 是"建仓冻结态"。三者不一致是三个不同数据源 + 回写条件限制的必然结果。**

---

## 3. 账本实际用哪个止损？（重要：提示 UI 之外的行为分叉）

账本里有**两套互不相关的退出路径**：

| 路径 | 触发源 | 读哪个止损 | 位置 |
|---|---|---|---|
| **A. review 终态驱动**（权威） | `trade_history.csv` 的 `Status ∈ TERMINAL_STATUSES`（`:47-50`）+ `Exit_Price` | **完全不读 `Stop_Loss`** | `process_sells()` `:386-443`，判断在 `:398`，卖出价在 `:400`/`:413` |
| **B. 盘中机械止损**（并行） | 实时价 ≤ 止损 | 读 **`positions.csv` 的 `Stop_Loss`（= 197.69 冻结值）** | `_run_intraday_stop()` `:641`，取值 `:687` `stop = dec(p.get("Stop_Loss"))` |

⚠️ **路径 B 与 `portfolio_50000.py` 自己的设计声明相矛盾**——模块 docstring（`:5-11`）写明：

> 2. **只做镜像，不发明交易逻辑** … 卖出：完全沿用 Review 已裁决的终态 Status + Exit_Price，**本模块不实现第二套止损**

但 `_run_intraday_stop` 就是那"第二套止损"，且它挂在一个**永不更新**的止损值上。

- 当前 ANET 现价 ~216 远高于 197.69 → 路径 B 事实上**永远不会触发**（惰性/失效）。 —— ⚠️ **此结论已作废（2026-10-13）**：真实根因是 `dec("$197.69") is None` 导致整条被跳过，**与价格无关**；见 `HANDOVER.md:176-179`。
- 但一旦价格回落，路径 B 会在 197.69 卖出，**比 review 认定的 ~209 线低 11 美元**，等于多亏约 5.6%。这才是这个 bug 真正的**资金风险**，卡片显示不一致只是它的表征。

---

## 4. 最小修复方案

### 方案 A —— review 算完回写 `positions.csv`（碰主链路，**不推荐**）

- **改哪里**：`review.py:1882` 之后（或塞进 `update_trade_history_trailing_stop`），再写一次 `portfolio_50000_positions.csv` 的 `Stop_Loss`。
- **改动半径**：`review.py` 约 +15 行；**引入 `positions.csv` 的第二个写入者**（原本唯一写入者是 `portfolio_50000.py`）。
- **风险**：
  - review.py 会用 pandas 重写整个 CSV，**列顺序/引号/空值表示可能与 `portfolio_50000.py` 的 `write_csv_rows(..., POSITION_COLUMNS, ...)` 不一致** → 账本 diff 噪声甚至 schema 漂移。
  - 违反两个模块的既定职责边界（review 不拥有账本）。
  - `review.yml` 里 review.py 先跑、`portfolio_50000.py` 后跑；后者开头会 `read_csv_rows` 再写回，**恰好能保住改过的 Stop_Loss**——但这种"靠执行顺序侥幸成立"的耦合很脆。
- **对 06:23 review 的影响：⚠️ 有，且直接。**

### 方案 B —— `dashboard_export` 注入移动止损（碰展示层，**最小**）

- **改哪里**：`dashboard_export.py:2645`（`build_portfolio()`）。把
  ```python
  "stop_loss": clean_text(r.get("Stop_Loss")) or None,
  ```
  改成：按 ticker join `build_events()` 的 `stop_loss`（即 `trade_history` 的移动止损），取不到再回退 positions 的值。
- **改动半径**：`dashboard_export.py` 一个函数，约 +10~20 行（`build_portfolio` 里已经能拿到 `data_dir`，也可直接读 `trade_history.csv`）。
- **风险 / 代价**：
  - ✅ 不动 review.py / portfolio_50000.py，**零主链路风险**。
  - ⚠️ **会制造一个新的"显示 vs 行为"分叉**：卡片从此显示 ~209 的移动止损，但账本 `_run_intraday_stop` 实际仍按 197.69 卖。**UI 会宣称一条账户并不执行的保护线**——在这个场景里可能比现状更危险。
  - 只治表征，不治"两套止损"的病根。
- **对 06:23 review 的影响：✅ 无。** `dashboard_export.py` 只在 `dashboard-data.yml`（每 15 分钟）里跑，`review.yml` 完全不经过它。

### 方案 C —— `portfolio_50000.py` 自己把 `Stop_Loss` 同步成 trade_history 的值（**结构性正确，推荐方向**）

- **改哪里**：
  1. `mark_to_market()`（`:566`）增加把 `p["Stop_Loss"]` 从 `recs[rid]["Stop_Loss"]` 同步过来（`load_recommendations()` 已经在 `:372` 读好了这个字段）。
  2. `mark_to_market(positions, prices, today)` 签名需要加 `recs`，并改 `run()` 里的调用点。
- **改动半径**：`portfolio_50000.py` 约 +15~25 行（一个文件、单一写入者、不新增跨模块耦合）。
- **收益**：
  - 消除 197.69 vs 209.36 的分叉 —— **卡片、`_run_intraday_stop` 机械止损、review 三者对齐到同一个数**。
  - `positions.csv` 仍只有一个写入者，符合模块既有设计。
- **风险（**必须正视**）**：这会把**盘中机械止损线从 197.69 抬到 ~209**，意味着**原本不会触发的机械卖出现在会触发** → 可能产生真实 SELL 记录。
  - 反过来说，这正是**应该**发生的行为（197.69 已失效），但它是一次真实的行为变更，需要你确认。
  - 建议配合"先只同步、不启用机械止损"或"同步 + 明确移除机械止损"一起决策。
- **对 06:23 review 的影响：⚠️ 部分有。** review.py 自身的止损判定**完全不受影响**；但 `portfolio_50000.py` 就是 `review.yml` 里的第二步（`更新 $50,000 Portfolio Ledger`），**该 step 会在 06:23 跑**，届时 `positions.csv` 的 `Stop_Loss` 会被改写。

### 方案 D —— 拆掉并行的"第二套止损"（架构清理，非最小改动）

- 依据模块 docstring 的自我声明，`_run_intraday_stop` 本就不该存在（review 终态是唯一权威退出）。
- 做法：让 `_run_intraday_stop` 改读 `trade_history` 的移动止损，或直接下线该步骤（`dashboard-data.yml:93-97`）。
- **对 06:23 review 的影响：✅ 无**（只动 `dashboard_export`/`dashboard-data.yml` 一侧）。

### 推荐

| 目标 | 选择 |
|---|---|
| **只求今晚/明天别再看到两个数字打架，且绝不碰主链路** | **方案 B**（承认它与机械止损仍不一致） |
| **真正消除分叉（含资金风险）** | **方案 C**，但**必须由你确认"机械止损线抬到 ~209 是可接受的"** |
| **最干净** | **C + D**（同步 + 移除并行机械止损，让 review 成为唯一退出权威） |

---

## 5. 这个改动会不会影响明早 06:23 的 review？

| 方案 | 影响 06:23 review？ | 说明 |
|---|---|---|
| **A**（review 回写 positions） | ❌ **会** | 直接改 review.py 运行时逻辑；且引入第二写入者 |
| **B**（dashboard_export 注入） | ✅ **不会** | `review.py` / `review.yml` / `portfolio_50000.py` 全不动；`dashboard_export.py` 只在 `dashboard-data.yml` 跑 |
| **C**（portfolio 同步） | ⚠️ **部分会** | review.py 的止损判定不变；但 `portfolio_50000.py` 是 `review.yml` 的第二个 step，会在 06:23 执行并改写 `positions.csv` 的 `Stop_Loss` |
| **D**（移除并行机械止损） | ✅ **不会** | 只动 dashboard 侧 |

**若今晚要做改动，只有 B 和 D 是"对 06:23 review 零影响"的。**

---

## 附：行号索引（当前 HEAD = `3077040e`）

| 关注点 | 位置 |
|---|---|
| 卡片渲染止损 | `app.js:441`（`p.stop_loss`） |
| 卡片主表 = positions | `app.js:357`、`app.js:391` |
| STOCKS 由 `data.stocks` 构建 | `app.js:198` |
| 详情页 `stop` 取值 | `app.js:238` |
| 详情页按 ticker 从 STOCKS 取 | `app.js:1625`、`app.js:1964` |
| 详情页展示"止损价" | `app.js:1793` |
| positions 导出（卡片源） | `dashboard_export.py:2589`(`build_portfolio`) → `:2645` |
| trade_history 导出（详情页源） | `dashboard_export.py:2005`(`build_events`) → `:2100` |
| 账本建仓写入止损（唯一写点） | `portfolio_50000.py:555` |
| 账本 `POSITION_COLUMNS`（无 Trail_Stop） | `portfolio_50000.py:57-62` |
| 账本读取 trade_history 止损 | `portfolio_50000.py:352-374`（`:372`） |
| `mark_to_market` 不动 Stop_Loss | `portfolio_50000.py:566-603` |
| 账本盘中机械止损（读冻结值） | `portfolio_50000.py:641`（`:687`） |
| 账本 SELL 用 rec 终态 + Exit_Price（不读 Stop_Loss） | `portfolio_50000.py:386-443`（`:398`/`:400`/`:413`） |
| `TERMINAL_STATUSES` | `portfolio_50000.py:47-50` |
| review 移动止损计算 | `review.py:1374-1423` |
| review 移动止损落盘（trade_history.csv） | `review.py:1426-1448`（写文件 `:1446`） |
| review 落盘调用点 | `review.py:1878-1882` |
| 触发时跳过回写 | `review.py:1875-1876` |
| review `exec_stop` | `review.py:1819` |
| review 触发判定 | `review.py:1826`、定义 `:763` |
| review 写回 `Stop_Loss_Hit`+`Exit_Price` | `review.py:1848` |
| review 风控诊断日志 | `review.py:1871-1873` |
| 止损合理性校验 | `review.py:734`（`is_valid_existing_stop`） |
| `portfolio_50000.py` 在 review.yml 中执行 | `review.yml` step `更新 $50,000 Portfolio Ledger` |
| 机械止损在 dashboard-data 中执行 | `dashboard-data.yml:93-97`（`--intraday-stop`） |

---

*本报告为只读调查产物，未提交、未 push。*
