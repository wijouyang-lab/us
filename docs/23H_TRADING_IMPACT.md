# 23 小时交易 + 买入价时点：现有代码影响面（只读调查）

> 生成时间：2026-10-11（只读调查，未改代码、未 push）
> 假设前提：NYSE 的 23 小时 / Overnight Session（夜盘）于 **12-06** 起生效，覆盖 **美东 20:00–04:00 ET**（周日~周四夜）。
> 本文只做「影响面 + 改动半径」定位，不评估该假设本身是否正确（以官方公告为准）。

---

## 0. 现状速览（先给结论）

现有代码对美股的时区假设是**两套硬阈值**，全部基于「常规交易日 09:30–16:00 ET、16:00 后为收盘、盘前 04:00–09:30」：

| 假设 | 代码位置 | 23 小时交易后是否失效 |
|---|---|---|
| 交易时段状态机（周末/盘前/常规/盘后） | `scan.py:164-176` `get_market_session_state` | ⚠️ 失效：夜盘 20:00–04:00 会被误判为 AFTER_HOURS / PREMARKET_NOT_STARTED |
| 「已完成交易日」边界 = 16:00 ET | `scan.py:750-755` `_last_completed_regular_date_us` | ⚠️ 失效：16:00 后夜盘仍在交易，当日并未结束 |
| 日线 K 棒完成过滤（按 16:00 截止日期） | `scan.py:758-774` `_filter_completed_daily_bars` | ⚠️ 失效：夜盘产生的 K 棒归属日期错乱 |
| 盘前快照窗口 = 04:00–09:29 ET | `scan.py:793-847` `get_premarket_snapshot_batch` | ⚠️ 需扩展：夜盘 20:00–04:00 未被覆盖/标注 |
| 盘中止损时段守卫 = 09:30–16:00 ET | `portfolio_50000.py:624-625, 638-656` | ⚠️ 失效：夜盘时段不触发机械止损 |
| 股指实时更新门控 = 09:30–16:00 ET | `dashboard_export.py:284-294` | ⚠️ 需扩展：夜盘时段股指也应实时 |
| 复盘评估「已完成交易日」= 16:00 后 | `review.py:78-92` `review_session_date` | ⚠️ 失效：16:00 后夜盘仍在交易 |
| 价格历史回填的「交易日」边界 = 16:00 | `quant_factor_price.py:60` | ⚠️ 失效：同上 |

> **一句话**：所有把「16:00 ET = 一天结束」「09:30–16:00 = 唯一交易时段」写死的代码，都会在 12-06 后产生**数据归属错误**（夜盘成交被当成盘后/盘前、日期切错、止损漏触发）。这些是**必须改**的。
> **买入价改成「完成时价」** 与 23 小时交易**无必然耦合**，是独立的设计决策，**可选**。

---

# 任务 1：23 小时交易影响面（逐文件列）

## 1.1 盘中止损时段守卫 — `portfolio_50000.py`

```python
# L624-625
INTRADAY_SESSION_OPEN  = (9, 30)    # 09:30 ET
INTRADAY_SESSION_CLOSE = (16, 0)    # 16:00 ET（不含）

# L638-656 _run_intraday_stop 时段守卫
if not (_dtime(oh, om) <= now.time() < _dtime(ch, cm)):
    print("[intraday-stop] 非交易时段（09:30-16:00 ET），静默退出")
    return ...
```

- **现状**：机械止损**只在 09:30 ≤ ET < 16:00** 触发；执行价 = 触发时实时价（`fetch_last_closes` 的 current，`prepost=False`）。
- **12-06 后要改成什么**：夜盘 20:00–04:00 ET 也是真实交易时段，若仍只在常规时段止损，则夜盘跌破止损线不会被机械卖出（只能等次日 09:30）。应把守卫扩展为「**只要处于可交易时段（含夜盘）就允许机械止损**」，或显式定义新的 `INTRADAY_SESSION_*` 常量覆盖 20:00–04:00 + 09:30–16:00（中间 04:00–09:30 是盘前，是否纳入需决策）。
- **影响半径**：守卫本身 1 处（`_run_intraday_stop`）+ 2 个常量；但 `prepost=False` 在夜盘需用 `prepost=True` 才能取到夜盘价（见 1.3 `dashboard_export` 同类逻辑 `L587-620` 已用 `prepost=True` 覆盖盘前/盘后，可作为样板）。

## 1.2 「开盘价 / 09:30 / 盘前」的使用点 — 全仓 grep 结果

| 文件:行 | 用途 | 23h 后是否需要改 |
|---|---|---|
| `scan.py:784` | 注释：09:30–16:00 ET 当日未收盘日线被 `_filter_completed_daily_bars` 剔除 | 是（剔除逻辑见 1.4） |
| `scan.py:806,843` | `get_premarket_snapshot_batch`：`prepost=True` 1m，标注 `Yahoo/yfinance 1m prepost` | 是（窗口/标注见 1.3） |
| `scan.py:994,1005,1031` | 读取 `Open` 作为 `Open_Price` / 推荐参考价 | 否（Open 字段仍有效，仅语义不变） |
| `review.py:264,304,310` | 必需 `Open/High/Low/Close`，止损/缺口判定用 `Open` | 否（日线 Open 仍可用） |
| `review.py:438,617-619` | `safe_record_price`：**正式买入价 = Rec_Date 真实 Open**；盘前新仓 Open 未产生则 `None`，等回补 | 否（这是买入价语义，见任务 2） |
| `review.py:772-773,1834,1902-1903` | 止损 `exit_price`：Gap Down 时取 `Open`；「今日开盘→收盘%」展示 | 否（日线 Open 仍可用） |
| `dashboard_export.py:285,294` | `us_regular_session_open`：股指实时更新门控（周末/09:30–16:00） | 是（见 1.5） |
| `dashboard_export.py:587-620` | `prepost=True` 1m 取盘前/盘后（04:00–09:30、16:00–20:00）真实价 | 是（需覆盖夜盘 20:00–04:00） |
| `quant_factor_price.py:24,42,44,60,112,117,121,157` | OHLCV 补采；**L60：`now.time() < 16:00 → 昨天；否则 → 今天`** | 是（交易日边界见 1.6） |
| `review.py:82-83,89` | `review_session_date`：16:00 ET 后才把当天当已完成交易日 | 是（见 1.7） |

> **关键**：`Open`/`09:30` 作为「日线开盘价」「常规时段起点」在 23h 后**仍然成立**（常规 09:30 open 依然存在）；真正失效的是把 **16:00 当成「一天结束」** 的所有边界判断（夜盘让「一天」延伸到 04:00 次日或 20:00 次日）。

## 1.3 yfinance 的 `prepost` 能否覆盖 21:00–04:00 ET 夜盘 — `scan.py:805` / `dashboard_export.py:592`

- 现有 `yf.download(..., interval="1m", prepost=True)` 覆盖 **盘前 04:00–09:30 + 盘后 16:00–20:00**（`dashboard_export.py:587-589` 注释明确）。
- **21:00–04:00 ET 夜盘**：取决于 Yahoo 是否在 `prepost=True` 的 1m 数据里提供 NYSE Overnight Session 的成交。这是一个**外部数据源事实**，无法从代码静态判定——需实测（用 1m + prepost=True 拉一只大票如 SPY，看 20:00–04:00 是否有 bar）。
- 当前 `get_premarket_snapshot_batch`（`scan.py:793-796`）**硬门控** `get_market_session_state(...) == "PREMARKET"`（即 04:00–09:29），夜盘窗口（20:00–04:00）**不会被读取/标注**。即使 Yahoo 提供夜盘 1m 数据，代码也不会取。
- **结论**：`prepost=True` 参数层面可能够用，但**窗口筛选与标注逻辑必须改**（新增 NIGHT_SESSION 状态 + 对应 20:00–04:00 的 1m 抓取分支）。

## 1.4 scan 触发时间（21:00 北京）— `tencent_scf_review_trigger.py:35`

```
Scan Timer: 0 0 21 * * 1-5 = 工作日 21:00 北京 = 美东 09:00 盘前（夏令时）/ 08:00（冬令时）
```
- 现状：21:00 北京 = **08:00–09:00 ET**，落在 PREMARKET 窗口（04:00–09:30）内，scan 以「盘前模式」跑（`scan.py:184-195`）。
- 12-06 后：夜盘 20:00–04:00 ET 已先于 scan 交易（20:00 ET = 冬令时 09:00 北京 / 夏令时 08:00 北京）。也就是说 scan 在 21:00 北京跑时，**夜盘已经交易了约 12 小时**（09:00 北京起的夜盘）。
  - 若仍想「在夜盘开始前扫一遍」：触发应前移到 **~09:00 北京（=20:00 ET 夜盘开盘）**。
  - 若保持 21:00 北京：scan 读取的是「夜盘已交易大半」的盘面，且 `get_market_session_state` 会把 08/09 ET 判为 PREMARKET（常规 09:30 前）——这与夜盘并存的语义需在 `get_market_session_state` 里新增 NIGHT_SESSION 才能正确表达。
- **是否必须改**：**不强制**。scan 仍能跑（PREMARKET 模式仍可工作），只是「夜盘已先行交易」这个事实会改变盘前快照的语义。属于**可选优化**。

## 1.5 交易日定义 — 现状与维护窗口

**现状（「已完成交易日」的判定）**：
- `scan.py:750-755` `_last_completed_regular_date_us`：`now.time() < 16:00 → 昨天；否则今天`。
- `review.py:78-92` `review_session_date`：16:00 ET 之后才把当天视为已完成常规交易日。
- `quant_factor_price.py:60`：`now.time() < 16:00 → 昨天`。
- `scan.py:758-774` `_filter_completed_daily_bars`：用上面 cutoff 日期过滤日线 K 棒。

**维护窗口 20:00–21:00 ET 会不会影响日期判断？**
- 仓库代码里**没有**任何「20:00–21:00 ET 维护窗口」的定义（全局 grep `20:00`/`维护`/`maintenance` 无代码引用；该表述只出现在你本次提问里）。所以**不存在维护窗口干扰日期判断**的问题——反而是 12-06 后的夜盘（20:00–04:00）让 16:00 这个边界本身失效。
- 12-06 后「已完成交易日」的边界应从 **16:00** 改为夜盘结束点（04:00 ET，或按券商结算口径）。否则：`_last_completed_regular_date_us` 会在 16:00–04:00 之间把「当天」算成已完成（实际夜盘还在交易），`_filter_completed_daily_bars` 可能把夜盘 K 棒错误归属/剔除。

---

# 任务 2：买入价时点调查

## 2.1 现状

**`trade_history.Price` 现在写什么？**
- scan 落盘推荐时，`Price` 初始 = `0`（占位），见 `scan.py:2633-2642`（`Price` 列置 0/空）。
- **正式买入价 = 推荐日（Rec_Date）真实 Open**，由 review 的 `backfill_rec_price`（`review.py:2488-2573`）幂等回填：`Rec_Price = Rec_Date Open`。
- `safe_record_price`（`review.py:437-444`）明确定义：**正式买入价 = trade_history 的 Price 字段 = 推荐日真实 Open**；盘前新仓（Open 未产生）→ `None`，由后续 Review 回补。**绝不** fallback 到实时 quote / Close / Prev_Close。

**scan.py 有没有记录「scan 完成时刻」？**
- **没有**。`RUN_ASOF_US`（`scan.py:152`）= 进程**开始**时的固定快照（`RUN_ASOF_UTC.astimezone(US_TZ)`），用作整次 scan 的统一时间戳（`get_scan_asof_us`，`scan.py:157-159`）。
- scan **不写任何「完成时间戳」/「完成价」**（`grep complete/finished/end_time` 仅命中 premarket 快照函数内部的局部变量 `end_time`，非落盘字段）。`News_AsOf_ET`（`scan.py:554`）记录的是开始快照时刻，不是完成时刻。

**review.py 怎么用这个 Price？**
- `process_buys` / 账本以 `rec["Price"]`（= Rec_Date Open）为成交价、以 `rec["Rec_Date"]` 为成交日（此前 buy-decision-migration 中已确认）。
- 即便买入决策迁到 scan（`ENABLE_SCAN_BUY_DECISION`），`process_buys` 仍读 `rec["Price"]` = Rec_Date Open，**买入价语义未变**。

## 2.2 你的提议（「盘中完成按完成时价」）的可行性 + 改动半径

> 注意：当前买入价是 **Rec_Date 的 09:30 Open**，不是 scan 完成时刻价。所以「改成完成时价」是**改变买入价口径**——不是小改，是语义变更 + 历史数据重算。

**需要改的文件（改动半径）：**

| 文件 | 改动点 | 说明 |
|---|---|---|
| `scan.py` | 新增「完成时刻 + 完成时价」记录 | 进程结束处 `datetime.now(US_TZ)` 取完成时刻，并抓当时实时价；写入 `trade_history.csv` 新字段（如 `Fill_Price` / `Scan_Done_ET`）。**当前无任何完成时刻字段，需新增。** |
| `portfolio_50000.py` | `process_buys` 读新字段 | 把成交价来源从 `rec["Price"]`（=Rec_Date Open）改为新字段 `Fill_Price`；缺失时回退策略要明确（仍回退 Open？还是 fail-closed？）。 |
| `review.py` | `backfill_rec_price` / `safe_record_price` | 历史推荐已用 Rec_Date Open 回填，**改口径意味着历史 PnL / Stage 全部重算**（影响 review_history.csv 全量行）。`safe_record_price` 的语义文档需重写。 |
| `dashboard_export.py` | 若前端展示「买入价」来源 | 检查 `portfolio.transactions[].price` 是否直接透传，是否需标注「Fill vs Open」。 |
| 测试 | `tests/test_buy_decision_flag.py` 等 | 需新增「买入价 = 完成时价」路径测试 + 历史回填回归。 |

**scan.py 怎么知道「我是什么时候完成的」？**
- 现在不知道（只有开始快照 `RUN_ASOF_US`）。需在 `main()`/scan 末段加 `SCAN_DONE_ET = datetime.now(US_TZ)`，并据此时点抓实时价（可复用 `fetch_last_closes` / `yf.download 1m prepost`）。
- 难点：**完成时价 ≠ 任何已有字段**——必须现场取实时价，而现有「取价」都带 `prepost=False`（常规时段）或限定 04:00–09:29 窗口。夜盘情景下（任务 1.3）还需 `prepost=True`。

**改动半径评估：大。**
- 属于**买入价口径的核心变更**，牵连 scan 落盘 schema（新字段）、portfolio 决策读取、review 全量历史回填与 PnL 重算、前端展示语义、测试。
- 与「23 小时交易」**无强耦合**：即使不改变 23h 处理，也能单独决定「用完成时价」。建议作为**独立设计决策**，不要塞进 23h 应急改造里。

---

# 明确区分：12-06 前必须改 vs 12-06 后可选

## 🔴 12-06 前必须改（否则数据/逻辑错误）
> 根因：23h 夜盘让「16:00=收盘」「09:30–16:00=唯一交易时段」的硬假设失效。

| # | 文件:行 | 必须改的内容 |
|---|---|---|
| 1 | `scan.py:164-176` `get_market_session_state` | 新增 `NIGHT_SESSION`（20:00–04:00）状态，重新划分周末/夜盘/盘前/常规/盘后 |
| 2 | `scan.py:750-755` `_last_completed_regular_date_us` | 「已完成交易日」边界从 16:00 改为夜盘结束点（04:00 ET 或券商口径） |
| 3 | `scan.py:758-774` `_filter_completed_daily_bars` | 配合 #2 修正 K 棒日期归属（避免夜盘 bar 被错剔/错归） |
| 4 | `scan.py:793-847` `get_premarket_snapshot_batch` | 扩展窗口覆盖 20:00–04:00 夜盘；新增 NIGHT 标注（先实测 Yahoo 是否提供 1m） |
| 5 | `portfolio_50000.py:624-656` 盘中止损守卫 | 守卫扩展至夜盘可交易时段；`fetch_last_closes` 在夜盘用 `prepost=True` |
| 6 | `dashboard_export.py:284-294` `us_regular_session_open` | 股指实时更新门控扩展至夜盘时段 |
| 7 | `dashboard_export.py:587-620` prepost 取价 | 确认并扩展覆盖 20:00–04:00 |
| 8 | `review.py:78-92` `review_session_date` | 「已完成交易日」边界从 16:00 改为夜盘结束点（与 #2 一致） |
| 9 | `quant_factor_price.py:60` | 「交易日」边界从 16:00 改为夜盘结束点（与 #2 一致） |

## 🟢 12-06 后可选（独立决策 / 优化，不阻塞）
| # | 内容 | 理由 |
|---|---|---|
| A | 买入价改成「完成时价」 | 语义变更 + 全量历史重算，与 23h 无强耦合，可独立排期（任务 2.2） |
| B | scan 触发时间 21:00→09:00 北京 | 仅影响「是否在夜盘前扫一遍」，scan 仍能跑；属优化 |
| C | 夜盘 1m 数据实测 | `prepost=True` 能否覆盖 21:00–04:00 取决于 Yahoo，需实测后再定 #4 实现细节 |
| D | 中间时段（04:00–09:30 盘前）是否纳入机械止损 | 设计选择，非必须 |

---

# 建议（仅调研结论，未实施）

1. **先做一个「时区边界统一」改造**：把散落在 4 个文件里的「16:00=收盘」「09:30–16:00=常规」硬阈值，抽成一个统一的 session/日历模块（例如 `_us_session.py`），集中定义 `REGULAR_OPEN/CLOSE`、`NIGHT_OPEN/CLOSE`、`completed_day_cutoff`。这样 12-06 只改一处常量 + 状态机，避免 9 处散落改动各自漂移。
2. **实测 Yahoo 夜盘 1m 数据**（`prepost=True`，拉 SPY 看 20:00–04:00 是否有 bar）再定 #4 实现细节——这是 #4 的硬前置，纯静态无法判定。
3. **买入价「完成时价」作为独立议题**排期，不要并入 23h 应急；它牵动 schema 新增 + 全量 PnL 重算，应单独评估与灰度。
4. **扫描触发时刻**：若要在夜盘前扫盘，把 `tencent_scf_review_trigger.py:35` 的 `0 0 21` 前移到 `0 9`（=20:00 ET）或新增一条夜盘前触发；若维持 21:00 北京，则需在 #1 状态机里让「08/09 ET」正确表达为「夜盘已交易中的盘前」。

---

## 铁律确认
- 本文为**只读调查**：仅读取 `portfolio_50000.py` / `scan.py` / `review.py` / `dashboard_export.py` / `quant_factor_price.py` / `tencent_scf_review_trigger.py` 与全局 grep，未改任何代码。
- 未执行 `git push` / `git rebase`。
- 未触碰任何监控/运行中的 job。
- 未调用任何 AI。
- 「NYSE 12-06 起 23h 夜盘」为本次调研的**输入假设**，其真实性需以官方公告为准，本文未验证该假设本身。
