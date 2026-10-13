# Scan 角色重定义设计（只读调查 + 方案）

> **状态**：只读调查 + 设计方案。**未写任何代码，未改 scan.py / dashboard_export.py / evolve.yml / scan_us_option_engine.py / review.py / portfolio_50000.py，未 push/rebase/fetch，未碰监控 PID 536931。**
> **生效前提**：10-08 判决通过 + 用户最终确认。
> 调查基准时间：2026-10-08。代码引用均来自 `/tmp/us`（仓库真实路径）。

---

## 0. 决策记录（最终拍板 · 确认日期 2026-10-08）

> **判决状态**：全部决策已拍板，待 10-08 13:07 UTC 判决。本文件为**判决前文档最终确认**，**未写任何代码**，未改 scan.py / evolve.yml / portfolio_50000.py / dashboard_export.py / review.py。判决后按本文件实施。

### 0.1 核心架构

| 维度 | 旧（全市场推荐） | 新（持仓 + 严筛候选） |
|---|---|---|
| 行情扫描 | get_scan_pool → Core_Dragon + Observation（全市场 ~262 只） | get_scan_pool → **全市场行情硬筛（零 token）** → 持仓(浮动 3-5 只，见 0.8) + 严筛候选(≤3) |
| AI 分析范围 | generate_ai_report 对**全池**做 LLM 分析（token 主消耗点） | generate_ai_report 仅对**这 ≤7 只**（持仓 + 严筛候选）做 LLM 分析（token 主节省点） |
| Observation | 生成 + 调 AI 分析 | **代码保留、不生成、不调用 AI（零 token）** |
| 候选定义 | 无 | Candidate（严筛后 ≤3），默认 status="建议"（冷启动期不执行） |

### 0.2 严格筛选标准（严筛层，纯程序计算、零 token）

| 项 | 阈值 |
|---|---|
| 评分下限 | **≥ 90** |
| R/R 下限 | **≥ 2.0**（与期权引擎 `MIN_REWARD_RISK` 一致，scan_us_option_engine.py:42） |
| 目标价公式 | **前 20 日高点 `max(high[-20:])`** |
| R/R 计算 | `(目标价 - 现价) / (现价 - 止损价)` |
| 止损距离区间 | **2% ≤ 止损距离 ≤ 5%** |
| 板块集中度 | **≤ 1 只/板块** |
| 每日候选上限 | **≤ 3 只** |

### 0.3 交易触发规则

| 触发 | 规则 |
|---|---|
| 买入 | 有空间（仓位<80%）：候选评分 **≥ 90** 直接加仓；满仓（=80%）：候选评分 ≥ 现有最差 **+ 20** 换股（见 0.8） |
| 卖出（止损） | 跌破止损价，随时生效，**不受频率限制** |
| 卖出（评分崩塌） | 评分跌至 **< 60** |
| 卖出（被挤出） | 新候选评分**显著更高** |
| 换股频率上限 | **每周最多 1 次** |
| 冷启动期 | 前 3 个月只记录"建议换股"，**不执行** |

### 0.4 Observation 处理

- 代码保留，**不生成、不调用 AI（零 token）**。

### 0.5 evolve 调度变更

- cron 由 `37 2 * * 6` 改为 **`0 2 1 * *`**（每月 1 号 02:00 UTC）。
- **同步删除周六门控**：evolve.yml:30-37 的 `BJ_DOW=="6"` 判断删除（详见 §5.3）。

### 0.6 持仓每日重评分

- 持仓**强制纳入 AI 分析**（每天多分析 3-5 只持仓，约 +1 万 token），确保"评分崩塌 < 60"规则可执行。
- AI 分析范围 = 持仓(浮动 3-5 只) + 严筛候选(≤3)，**不含其他股票**。
- ✅ 已解决（方案 B，见 §0.9）：`AI_INPUT_MAX=7` 保持不变，候选数 = `min(3, 7 - 持仓数)`，持仓优先。

### 0.7 待确认项状态

- §8 全部 6 项已确认 ✅（见 §8 状态列）。

### 0.8 持仓只数：浮动 3-5 只取代固定 4 只（2026-10-08 补拍板）

> **状态**：代码未改，判决后实施。本小节**取代** 0.1 / 0.3 / 0.6 中"持仓(~4)"的固定只数表述。

**决策**：固定 4 只 → **浮动 3-5 只**（无固定只数）。

**背景**：固定 4 只会导致"满仓时被迫卖不错的中等仓位，换进差不多强的新股票"——纯折腾 + 换股成本。

**仓位约束**（与 OPTIONS_WHEEL_DESIGN.md §1.3 百分比制一致）：

| 约束 | 值 |
|---|---|
| 单只上限 | **25%** |
| 总股票 | **80%** |
| 总期权 | **15%** |
| 现金下限 | **5%** |
| 固定只数 | **无（浮动 3-5 只）** |

**换股触发**：

| 场景 | 规则 |
|---|---|
| 有空间时（仓位 < 80%） | 新候选评分 **≥ 90 → 直接加仓**（不用卖） |
| 满仓时（仓位 = 80%） | 新候选评分 **≥ 现有最差 + 20 → 换股** |

**实施要点（判决后）**：

- 删 `portfolio_50000.py:42` 的 `MAX_OPEN_POSITIONS=4` 逻辑守卫；常量本身可保留作历史参考。
- `dashboard_export.py` 的 "Open Units 4/4" 显示改为**百分比或浮动只数**。

### 0.9 AI 输入上限的动态分配（方案 B · 2026-10-08 补拍板）

> **状态**：代码未改，判决后实施。解决 §0.6 曾标注的"8 只 vs `AI_INPUT_MAX=7`"硬顶冲突。

**决策**：候选数随持仓数动态调整，`AI_INPUT_MAX = 7` 保持不变。

**规则**：`候选数 = min(3, AI_INPUT_MAX - 持仓数)`

| 持仓数 | 候选上限 | 合计 |
|---|---|---|
| 5 只 | ≤ 2 | 7 |
| 4 只 | ≤ 3 | 7 |
| 3 只 | ≤ 3 | 6 |

**约束**：
- `AI_INPUT_MAX = 7` **保持不变**（不调 8）。
- **持仓优先**：持仓必须全部纳入每日重评分（不因候选数压缩而牺牲持仓）。
- 候选数动态、但不超上限（≤3，且受 `7 - 持仓数` 钳制）。

---

## 1. 新旧架构对比

### 1.1 旧架构（全市场推荐）

```
get_scan_pool()                      [scan.py:565]
   S&P500+Nasdaq100+Dow 按量取 Top300（实际 ~262 只）
        │
        ▼
build_stock_pool → 技术/基本面/新闻 enrich → apply_entry_quality_gate()
   全池过"程序硬门槛" → Gate_Status = PASS_PRE_AI   [scan.py:1212 / :1271]
   eligible = 全闸口候选池（数十~数百只，随市场 regime 波动）
        │
        ▼  ★ AI 调用 #1：generate_ai_report(eligible 全池)   [scan.py:2572 / :3777]
        对全闸口池逐只产出 AI评分 + 核心卡片 + 观察池 + 诱多对照组
        │  （token 主消耗点：输入 = 全池 + 宏观/新闻，输出 ≤30000 token）
        ▼
match_pool_to_report()               [scan.py:2756]
   全候选统一赋 AI_Score → Final = 0.7×Quant + 0.3×AI
   Core_Dragon: Quant≥65 & Final≥65 & 技术≥2   [scan.py:2940 / :2594]
   Observation: Quant≥58 & Final≥58 & 技术≥1   [scan.py:2947]
   core = 前5 / obs = 前7                        [scan.py:3019 / :3021]
        │
        ▼  ★ AI 调用 #2：enrich_verified_items_with_ai_details(chosen)  [scan.py:3031 / :3805]
   Core 生成六段中文（industry_logic/news_cn/premarket/catalysts/risks/invalidation）
   Observation 生成三字段（industry_logic/catalysts/risks）
        │
        ▼
写入 trade_history.csv（Tag∈{Core_Dragon, Observation}）+ ai_snapshot.csv（全闸口池快照）
        │
        ▼
组合挑选：portfolio_50000.py 读 trade_history 的 Core 推荐开仓
```

### 1.2 新架构（持仓 + 严筛候选）

```
get_scan_pool()                         [不变，Top300 行情源]
        │
        ▼
扫描层（不花 token）：build_stock_pool → 技术/基本面 enrich
   → apply_entry_quality_gate() 程序硬门槛（不变）
   → 严筛层（新）：评分≥90 & R/R≥2.0 & 2%≤止损距离≤5% & ≤1只/板块 → 候选池 ≤3 只
        │
        ▼  ★ AI 调用 #1（输入骤减）：generate_ai_report(持仓 + ≤3 候选)   [≤7 只]
   仅对"当前持仓 + 严筛后的 ≤3 候选"做 LLM 分析
   （宏观/新闻上下文保留；不再逐只扫描全市场）
        │
        ▼
match_pool_to_report() → 候选赋分；不再有 Observation 标签
   Tag 仅剩：Core_Dragon（持仓内已持有的）+ Candidate（严筛候选）
        │
        ▼  ★ AI 调用 #2（更小）：仅对"持仓 + ≤3 候选"生成中文详情
   （取消 Observation → 省掉原 obs≤7×3 字段集）
        │
        ▼
写入 trade_history.csv（Tag∈{Core_Dragon, Candidate}）
   Candidate 默认 status="建议"（冷启动期不执行）
        │
        ▼
组合挑选：portfolio_50000.py 按"换股触发规则"决定是否把 Candidate 纳入持仓
```

### 1.3 对比要点

| 维度 | 旧 | 新 |
|---|---|---|
| AI 输入规模 | 全闸口池（数十~数百只） | 持仓(~4) + 候选(≤3) = ≤7 只 |
| Observation | 生成 + AI 分析（≤7） | **保留代码、不生成、不调 AI** |
| Core/Observation 双栏 | 有 | 改为 Core + Candidate |
| 候选筛选 | 程序硬门槛（Quant≥65） | 严筛（评分≥90 / R/R≥2.0 / 2%≤止损≤5% / ≤1板块 / ≤3日） |
| 执行时机 | 信号即开仓 | 换股触发（评分差≥20 / 挤出 / 止损），每周≤1 次，冷启动 3 月观察 |

---

## 2. 严格筛选标准（完整规则）

> 严筛层位于"程序硬门槛"之后、"AI 分析"之前，是**纯程序计算、零 token**的行情/量化过滤。

| 项 | 阈值 | 说明 | 现有对照 |
|---|---|---|---|
| 评分下限 | **≥ 90** | Final/Quant 评分（0~100） | 旧 Core 仅 ≥65；**大幅收紧** |
| R/R 下限 | **≥ 2.0** | 收益风险比（(目标-入场)/(入场-止损)） | 旧股票 scan **无此字段**；期权引擎有 `MIN_REWARD_RISK=2.0`（scan_us_option_engine.py:42）——与期权引擎口径一致；需为股票新增 R/R 计算 |
| 止损距离区间 | **2% ≤ 距离 ≤ 5%** | 入场价到止损价的距离（下限防噪声触发、上限控单笔风险） | 旧无此区间（仅 ATR 动态止损）；新增强制区间约束 |
| 板块集中度 | **≤ 1 只/板块** | 同一 Sector 至多 1 只候选 | 旧无板块去重（仅总板块上限 40%） |
| 每日候选上限 | **≤ 3 只** | 单日严筛候选硬顶 | 旧 obs≤7 / core≤5，无"候选"概念 |

**严筛伪代码（设计，非实现）**：
```
candidates = [x for x in eligible
              if x.score >= 90
              and x.rr_ratio >= 2.0
              and x.stop_distance_pct <= 5
              and x not in used_sectors]   # 每板块首只后剔除同板块
candidates = candidates[:3]                # 每日上限
```
- 若严筛后为空 → 当日无候选，仅保持持仓（不凑数，沿用旧"不凑数"铁律，scan.py:3770/:3802）。
- 板块去重：按 `Sector` 字段，命中首只即标记该板块已占用。

---

## 3. 交易触发规则（含止损优先）

| 触发 | 规则 | 频率限制 | 现有对照 |
|---|---|---|---|
| **买入** | 候选评分 ≥ 现有最差持仓评分 **+ 20** | 受"换股频率"约束 | 旧：Core 信号即开仓（process_buys 见 OPTIONS 调查 L322） |
| **卖出（止损）** | 价格跌破止损价 | **随时生效，不受频率限制** | 旧：ATR 动态止损 + Review 终态价 |
| **卖出（评分崩塌）** | 评分跌至 **< 60** | 随时 | 新引入（旧无持仓评分实时跌落退市规则） |
| **卖出（被挤出）** | 新候选评分**显著更高**（> 当前持仓 + 阈值） | 受频率约束 | 新引入 |
| **换股频率上限** | **每周最多 1 次** | 硬顶 | 旧：无（每日可调） |
| **冷启动期** | 前 3 个月只记录"建议换股"，**不执行** | — | 新引入 |

**优先级（设计）**：
1. **止损 / 评分崩塌 = 最高优先**，随时触发、不受每周 1 次限制（保护本金）。
2. 买入 / 被挤出 = 受"每周≤1 次换股"约束，且需满足评分差 ≥20。
3. 冷启动期：所有卖出/买入建议照常生成并写入 `trade_history`（status="建议"），但 `review.py` / `portfolio_50000.py` **不执行**实际调仓。

**评分实时性**：评分崩塌（<60）依赖持仓股每日重新打分——需在 scan 或 review 中对现有持仓股重算 Quant/AI 分（旧系统仅对全池候选打分，不对已持仓股持续评分；这是新增数据流）。

### 3.1 R/R 计算口径（前 20 日高点 + 止损距离区间）

> 判决明确：R/R 计算与"前 20 日高点"目标价、"止损距离 2%–5%"区间绑定，为严筛层的纯程序计算（零 token）。

- **目标价（target）** = 前 20 日高点 = `max(high[-20:])`：
  - 数据源：`get_kline_data(ticker)` → `_filter_completed_daily_bars` 过滤后的日线 OHLC（yf.download `period="6mo"`，含 `High` 列，scan.py:957 `highs = df["High"].values.astype(float)`）。
  - 计算：`target = max(df["High"].tail(20))`（20 个**已完成**交易日高点，已剔除当日未收盘 K 棒）。
  - **只读核查结论**：`_filter_completed_daily_bars` 已提供前 20 日高点所需的日线 `High` 序列（6 月窗口 ≥ 20 根），**无需新增数据源**，只需在严筛层新增 `max(high[-20:])` 计算。
- **R/R** = `(target - 现价) / (现价 - 止损价)`，下限 **≥ 2.0**（与期权引擎 `MIN_REWARD_RISK` 一致）。
- **止损距离** = `(现价 - 止损价) / 现价`，**区间 2% ≤ 距离 ≤ 5%**（下限避免噪声误触发，上限控单笔风险）。
- 伪代码（设计，非实现）：
  ```python
  target   = max(df["High"].tail(20))            # 前 20 日高点
  stop     = entry * (1 - stop_pct)              # stop_pct ∈ [0.02, 0.05]
  rr       = (target - price) / (price - stop)
  passed   = (score >= 90) and (rr >= 2.0) and (0.02 <= (price-stop)/price <= 0.05)
  ```

---

## 4. 冷启动期设计（前 3 个月只观察）

- **窗口**：自首份"候选"生成起算 3 个月（约 13 周）。
- **行为**：
  - scan 照常产出 Candidate（严筛 ≤3），AI 照常分析（持仓 + 候选）。
  - 所有换股建议写入 `trade_history.csv`，但 `Status` 标记为 **"建议"/"OBSERVE"**（非 Active）。
  - `review.py` 的调仓执行逻辑进入"只读"模式：生成建议、记录 KPI，但**不调用 `portfolio_50000.py` 实际买卖**。
  - 监控/邮件照常推送"建议换股"列表，标注"冷启动·未执行"。
- **退出条件**：满 3 个月且系统无异常 → 切换为执行模式（按 §3 规则真实换股）。
- **数据价值**：3 个月纸面记录用于验证"严筛候选"的历史胜率/接货质量，为期权 wheel 的 CSP 标的源（§6）提供样本。

---

## 5. 与现有系统的影响面

### 5.1 取消 Observation 生成

| 文件 | 影响 | 改动性质 |
|---|---|---|
| `scan.py` | `match_pool_to_report` 不再产 Observation（:2962 分支删除）；`enrich_verified_items_with_ai_details` 去掉 obs 三字段分支（:3109）；prompt 删观察池/诱多对照组（:2710-2724） | 改逻辑 |
| `scan.py` | `LIMIT_PARAMS.max_observation`（:113）保留为兼容占位或删除 | 小改 |
| `dashboard_export.py` | `BUCKET_MAP` 的 Observation 映射（:754）、`obs_count`（:2860）、`build_current_event_rows` obs 分支（:2270）— Observation 桶变空，payload 结构**不变**（仅无 obs 项） | 兼容即可 |
| `review.py` / `review_kpi_tracking_fix.py` | "持仓 + Observation 均纳入"的 KPI 跟踪（review_kpi_tracking_fix.py:6-7,146,155,199）需改为"持仓 + Candidate" | 改逻辑 |
| `ai_snapshot.csv` | 不再有 Observation 行（仅 Core/Candidate） | 自动 |

> **payload 结构结论**：`dashboard_export.py` 的 payload **无需改 schema**（stocks[] 的 bucket 字段保留，Observation 仅为空集合）；但 `review` 段 KPI 文案与 `obs_count` 展示需同步。

### 5.2 全市场 AI → 持仓 + ≤3 候选

| 文件 | 影响 |
|---|---|
| `scan.py:2572 generate_ai_report` | **输入从 `eligible`（全闸口池）改为 `持仓 + ≤3 候选`**——这是 token 节省的核心改动点 |
| `scan.py:3777` 主流程 | `ai_html = generate_ai_report(positions + candidates, ...)` |
| `scan.py:2543 eligible` | 保留用于"扫描层"统计，但不再整体喂 AI |
| `trade_history.csv` | 新增 `Candidate` Tag + "建议/OBSERVE" 状态；需 widen schema 或新增状态枚举 |
| `portfolio_50000.py` | 买入规则改为"候选评分 ≥ 最差持仓 +20" + 每周≤1 换股（process_buys 逻辑变更） |
| `review.py` | 调仓执行新增"换股频率""冷启动只读""评分崩塌退市"判断 |

### 5.3 evolve 确认（只读）

- **当前 cron**：`evolve.yml:7` = `'37 2 * * 6'`（每月第一个星期六 02:00 UTC = 10:00 北京）。
- **门控逻辑**：`:22-23` 注释 + `:30-37` `check-date` 步骤 + `:44-48` 跳过判断，强依赖 `BJ_DOW=="6"`（星期六）且 `BJ_DAY<=7`。
- **改为 `0 2 1 * *` 的影响面**：
  - cron 本身：每月 1 号 02:00 UTC 触发（无需 Saturday 判断，因为 cron 已限定 day=1）。
  - **必须同步改门控**：删除 `:30-37` 的 `BJ_DOW=="6"` 周六判断，改为"day==1 即运行"或直接 `SHOULD_RUN=true`（cron 已保证每月仅 1 号触发）；否则原周六门控会**拦截绝大多数月份**（仅当 1 号恰为周六才放行）。
  - 注释 `:22-23` "First Saturday" 需更新为 "Monthly on the 1st"。
  - 时间等价：02:00 UTC = 10:00 北京，与现"首周六 10:00"时段一致，无展示冲突。
- **★ 判决要求：同步删除周六门控（零歧义）**：
  - 删除 `evolve.yml:30-37` 的 `if [ "$BJ_DOW" = "6" ] && [ "$BJ_DAY" -le 7 ]` 周六判断分支，改为 `SHOULD_RUN=true`（cron `0 2 1 * *` 已保证每月仅 1 号触发）。
  - 依赖字段：`BJ_DOW`（`evolve.yml:31` `TZ=Asia/Shanghai date '+%u'`）、`BJ_DAY`（`evolve.yml:32` `TZ=Asia/Shanghai date '+%d'`）随门控一并移除。
  - 保留 `if: steps.check-date.outputs.should_run == 'true'` 守卫（:51/:57/:61/:72）仍成立，因 `SHOULD_RUN` 恒为 true；注释 `:21-24` "First Saturday" 更新为 "Monthly on the 1st"。
  - **只读核查定位**：cron `evolve.yml:7`；周六门控核心 `evolve.yml:33`（`BJ_DOW=="6"`），门控步骤 `evolve.yml:25-48`。

### 5.4 持仓每日重评分（强制纳入 AI 分析）

> 判决明确：持仓**强制纳入 AI 分析**，确保"评分崩塌 < 60"规则可执行。

- **行为**：每日 scan 的 `generate_ai_report` 输入 = **持仓(~4) + 严筛候选(≤3)**（≤7 只），持仓股不参与"严筛"，但**强制进入 AI 分析池**。
- **token 成本**：每天多分析 ~4 只持仓，约 **+1 万 token**（AI 调用 #1 输入增量），属设计内可接受成本。
- **数据流（新增）**：scan.py 当前**不读取** `portfolio_50000_positions.csv`（只读核查确认：scan.py 无 `portfolio_50000_positions` / `POSITIONS_FILE` 引用），需新增"读持仓 CSV → 取 `Ticker` 列 → 并入 AI 输入"的数据流。
  - 持仓 CSV 路径：`portfolio_50000_positions.csv`（仓库根 `/tmp/us/portfolio_50000_positions.csv`），定义于 `portfolio_50000.py:53 POSITIONS_FILE`、`dashboard_export.py:2425 data_dir/"portfolio_50000_positions.csv"`。
  - 列：`Ticker`（持仓标的）、`Stop_Loss`（止损价，直接服务于 §3 止损规则）、`Status`（OPEN 过滤）等。
- **评分崩塌**：持仓股每日重算 Quant/AI 分，跌至 < 60 即触发卖出（§3），不依赖候选筛选。

---

## 6. 与期权 Wheel 的联动（CSP 标的来源依赖严筛候选）

> 关键依赖：期权 Wheel（CSP）的**标的来源**依赖 scan 输出的候选集。

- **现状**：`scan_us_option_engine.py` 读 `trade_history.csv` 的 **Core_Dragon** 事件生成期权策略（SHORT_PUT / CALL_DEBIT_SPREAD / LONG_CALL）——即 CSP 候选来自 Core 推荐（详见 OPTIONS_WHEEL_DESIGN.md §2.1）。
- **新架构影响**：
  - Core_Dragon 不再"全市场推荐"，而是"持仓 + 严筛候选（≤3）"。
  - 因此 **CSP 标的范围收窄**：只有被严筛（评分≥90 / R/R≥2.0 / 2%≤止损≤5% / ≤1板块）的标的才会进入期权引擎候选——**与 Wheel 设计"CSP 标的范围=全池筛选、高价跳过"一致且更严**。
  - 联动点：`scan_us_option_engine.py` 的 `build_option_recommendation` 输入若依赖 `trade_history` 的 Core 标签，则**自动继承**新严筛结果，**无需额外改**（前提是 trade_history 仍保留 Core_Dragon 标签用于已持仓股）。
  - 风险：若新架构将"候选"与"持仓"分离（Candidate 不写 Core_Dragon），期权引擎需改为读 `Candidate` 标签——需在实施时确认 `scan_us_option_engine` 的读取键（见 §8 待确认 4）。

---

## 7. 实施顺序建议（判决后）

1. **扫描层严筛（零 token）**：在 `apply_entry_quality_gate` 后新增严筛函数（评分≥90/R/R≥2.0/2%≤止损≤5%/板块去重/≤3）——纯程序，先独立可测。
2. **AI 输入收缩（token 核心）**：`generate_ai_report` 输入改为 `持仓 + ≤3 候选`；删 Observation 分支；call#2 同步缩小。
3. **trade_history schema 扩展**：新增 `Candidate` Tag + "建议/OBSERVE" 状态；`review.py` KPI 文案改"持仓+Candidate"。
4. **组合换股规则**：`portfolio_50000.py` 买入改"评分差≥20"+每周≤1；`review.py` 加止损优先/评分崩塌/冷启动只读。
5. **冷启动开关**：3 月观察期标志（配置/状态文件），到期切执行。
6. **dashboard 兼容**：`obs_count` 展示与 Observation 桶置空；可选新增 Candidate 展示位。
7. **evolve cron**：`37 2 * * 6` → `0 2 1 * *` + 删周六门控。
8. **回填/迁移**：旧 Observation 历史事件保留（不删），新数据起用 Candidate；回归测试确保现有 191 passed 0 regression。

---

## 8. 需要用户确认的补充事项（全部已确认 ✅ · 2026-10-08）

| # | 事项 | 拍板结论 | 状态 |
|---|---|---|---|
| 1 | 股票 **R/R 指标**定义与计算 | 口径 `(目标-入场)/(入场-止损)`，目标=**前 20 日高点 `max(high[-20:])`**，下限 **≥ 2.0**（与期权引擎 `MIN_REWARD_RISK` 一致） | 已确认 ✅ |
| 2 | 持仓股**每日重新评分**数据流 | 持仓**强制纳入 AI 分析**（scan.py 新增读 `portfolio_50000_positions.csv` 的 `Ticker` 列），约 +1 万 token/日 | 已确认 ✅ |
| 3 | Candidate 与 Core_Dragon 标签关系 | Candidate 独立 Tag；已持仓股仍保留 Core_Dragon（期权引擎读取键不变） | 已确认 ✅ |
| 4 | 期权引擎读取键是否改 | 因已持仓股保留 Core_Dragon 且 Candidate 独立，引擎读取键**无需改**；实施时复验 | 已确认 ✅ |
| 5 | 冷启动 3 月"未执行"落点 | `review.py` 加只读开关，建议仍写 `trade_history`（status="建议"），不计入执行胜率 | 已确认 ✅ |
| 6 | "评分≥90"过严致常日 0 候选 | 保留"0 候选即保持持仓"兜底（沿用旧"不凑数"铁律） | 已确认 ✅ |

---

## 附：调查证据索引

| 事实 | 文件:行 |
|---|---|
| 标的池 Top300（S&P500+Nasdaq100+Dow 按量） | `scan.py:565-618` |
| 程序硬门槛 PASS_PRE_AI | `scan.py:1212` `:1271` |
| eligible = 全闸口池 | `scan.py:2543` |
| AI 调用 #1：全池分析 | `scan.py:2572` `generate_ai_report` / `:3777` 主流程调用 |
| AI prompt 要求覆盖全池每只 Ticker | `scan.py:2702-2708` `:2726-2729` |
| 评分阈值 Core≥65 / Obs≥58 | `scan.py:2594` `:2940` `:2947` |
| core≤5 / obs≤7 | `scan.py:3019` `:3021` / `LIMIT_PARAMS` `:113` |
| AI 调用 #2：入账详情 | `scan.py:3031` `enrich_verified_items_with_ai_details` / `:3805` |
| Observation 三字段（不调 AI 六段） | `scan.py:3109` |
| ai_snapshot 写全闸口池 | `scan.py:3731` `:3898` `upsert_ai_snapshot` |
| dashboard Observation 桶/计数 | `dashboard_export.py:754` `:2860` `:2270` |
| 期权引擎读 Core 生成策略 | `scan_us_option_engine.py`（OPTIONS 调查 §2.1） |
| evolve 当前 cron + 首周六门控 | `evolve.yml:7` `:22-23` `:30-37` `:44-48` |
