# 期权 Wheel（CSP → CC）设计文档

> **状态**：只读调查 + 设计方案。**未写任何代码，未改 portfolio_50000.py / scan_us_option_engine.py / review.py，未 push/rebase/fetch，未碰监控 PID 536931。**
> **生效前提**：10-08 判决通过 + 用户最终确认。
> 调查基准时间：2026-10-08。代码引用均来自 `/tmp/us`（仓库真实路径）。

---

## 0. 决策记录（2026-10-08 确认）

> 以下 5 项于 **2026-10-08**（判决前文档更新轮次）由用户拍板固化；原 §8.4「待用户确认事项」同步转为「已确认」。文档其余章节（设计规则、复用评估、改动半径、白名单、测试）维持不变。

| # | 事项 | 决策 | 确认日期 |
|---|---|---|---|
| 1 | 改动半径 L2 还是 L3 | **L2**：扩展组合模型 + 担保现金 + `run()` 内 `process_options`；L3 废 unit 留待后续独立 PR | 2026-10-08 |
| 2 | CC 启动时机 | **CSP 跑通 3 个月后**再启动，给 CSP 足够验证时间 | 2026-10-08 |
| 3 | 被迫调仓减仓优先级 | **表现最差 + 与当前信号冲突**的持仓优先减仓（并列按市值小者先减） | 2026-10-08 |
| 4 | 账本新建还是复用 | **新建执行账本 `option_positions.csv`**，复用信号层（`option_strategies.csv` = 推荐，组合需要的是持仓——两个不同概念） | 2026-10-08 |
| 5 | 回测窗口 | **先纸上记录 6 个月**（不引入前视偏差）；现有系统无回测，强行造回测会引入前视偏差 | 2026-10-08 |
| 6 | 持仓只数 | **浮动 3-5 只取代固定 4 只**（详见 SCAN_ROLE_REDEFINITION_DESIGN.md §0.8）；仓位<80% 时候选评分≥90 直接加仓、=80% 时候选≥现有最差+20 换股 | 2026-10-08 |

### 决策要点说明
- **L2 而非 L3**：单 PR 改动面可控，担保现金与指派转股票在 L2 即可落地；unit→百分比彻底废除留独立 PR（见 §3 L3）。
- **CC 延后**：避免 CSP 未验证就叠加第二腿；3 个月观察期用于验证接货率 / 资金占用 / 组合扩容行为。
- **被迫调仓**：被行权后若触发板块 / 总股票硬顶，按「表现最差 + 信号冲突」减仓，与 §1.5 一致。
- **两张账本分离**：`option_strategies.csv` = 信号层（推荐/复盘），`option_positions.csv` = 执行层（组合实际持仓/担保现金/指派），职责清晰。
- **回测保守**：纸上记录优先，待真实样本 ≥6 个月再考虑历史链回放（测试 14），避免前视偏差污染结论。

---

## 1. 完整设计（已确认规则）

### 1.1 阶段顺序
| 阶段 | 触发 | 说明 |
|---|---|---|
| **CSP**（Cash-Secured Put，现金担保卖 Put） | 先 | 减股票仓位腾现金 → 卖 OTM Put 收权利金 → 未行权等下次信号；被行权则组合扩容、纳入股票持仓 |
| **CC**（Covered Call，备兑看涨） | 后 | 待 CSP 跑通、已有被行权股票池后启动；对持仓股卖 OTM Call |

### 1.2 CSP 核心规则

| 项 | 规则 |
|---|---|
| 现金来源 | 减股票仓位腾出现金（非新增本金） |
| 被行权处理 | 组合扩容，按执行价纳入 100 股/张股票持仓（等价建仓） |
| 标的范围 | 全池筛选；高价股跳过、改选其他可负担标的 |
| 仓位金额 | 信号强度四层结构（见 1.4） |
| 减仓触发 | 按表现 + 信号（弱信号/破位主动平仓或不再续卖） |
| 未行权 | 等下次信号（低频，不每天强开） |
| 行权价 | OTM **5–10%**（正股下方 5%–10%） |
| 到期日 | **30–45 天**（DTE 30–45） |
| 多信号优先级 | 按评分降序；同分按止损距离升序 |

### 1.3 仓位约束（百分比制，废除 unit 模型）

| 约束 | 默认值 | 硬顶 | $50,000 基准金额 |
|---|---|---|---|
| 单只标的上限 | 25% | 30% | $12,500 / 硬顶 $15,000 |
| 单一板块上限 | 40% | 45% | $20,000 / 硬顶 $22,500 |
| 总股票仓位 | 80% | 85% | $40,000 / 硬顶 $42,500 |
| 总期权暴露 | 15% | 20% | $7,500 / 硬顶 $10,000 |
| 单张 CSP 上限 | 10% | 10% | $5,000 / 硬顶 $5,000 |
| 现金下限 | 5% | 5% | $2,500（不可破） |

### 1.4 信号强度四层结构（金额计算公式）

```
金额 = 基础 × 评分系数 × 止损系数 × 技术系数
约束：金额 ≤ 单张上限($5,000) AND 金额 ≤ 可用现金 × 0.8
```

| 层 | 取值 | 系数 |
|---|---|---|
| **基础** | Core $12,000 / Observation $6,000 | — |
| **评分** | ≥90 / 75–89 / 60–74 / <60 | ×1.3 / ×1.0 / ×0.8 / ×0.6 |
| **止损距离** | ≤5% / 5–10% / >10% | ×1.2 / ×1.0 / ×0.7 |
| **技术** | RSI>80 减半 / MACD 死叉且 MA20 下方减半 | ×0.5（叠加） |

### 1.5 CC 规则（第二阶段）
- 行权价 **≥ 成本价（含权利金）**（保证不"倒贴"平仓）
- 接受"浮亏时卖不出 CC"的后果（正股深跌时不强制卖 Call，仅收不到额外权利金）
- 被行权后：接受被迫调仓（可能需先卖掉一个现有持仓才能合规，触发 1.3 上限检查）

---

## 2. 现有期权系统复用评估

### 2.1 现有系统事实（只读确认）
- **引擎** `scan_us_option_engine.py`：
  - 产出 3 类策略：`SHORT_PUT`（L682 `OptionType="PUT"`）、`CALL_DEBIT_SPREAD`、`LONG_CALL`（L650-661）
  - 完整风控：**长期价值门槛** `_long_term_value_gate`（L365-396，仅 Quant≥70 且 基本面≥24 的 Core 才允许卖 Put）、**最终交易资格门** `MIN_REWARD_RISK=2.0`（L42）、BS 推导 Delta/IV（L160-241）、Wall 分析（L318-347）
  - 期权链读取：Layer1 yfinance `option_chain()`（L600-609），Layer2 直连 Yahoo `query2.finance.yahoo.com/v7/finance/options`（L566-594）
  - 默认 DTE 窗 **45–90 天、目标 60**（L24-26），Short Put 行权价折扣 3–15%（L52-53），目标 Delta 0.25（L49）—— **与本次 wheel 设计（DTE 30–45、OTM 5–10%）不一致**
- **账本** `option_strategies.csv`：git 跟踪，当前 14 行（10 Active / 4 Rejected；CALL_DEBIT_SPREAD 7 + SHORT_PUT 7）
- **Review** `review.py`：`load_option_positions`（L923，按 `Status=='Active'` 严格过滤）、`process_options`（L979，到期/指派结算）、`build_active_option_reviews`（L1087，盘后复盘 + 指派风险预警）
- **测试** `tests/test_options_reward_risk.py`：15 组资格门槛回归测试（Reward/Risk≥2.0、NaN/inf、rounded gating 防护）——**无回测引擎、无实盘执行路径**

### 2.2 隔离现状（关键边界）
> **现有期权账本（`option_strategies.csv`）与 `$50,000` 组合（`portfolio_50000.py`）在代码与数据流上完全隔离**：`portfolio_50000.py` 从不引用 `option_strategies.csv`，`review.py` 的 `process_options` 只更新期权账本状态与 PnL，不向股票组合写入任何持仓。

### 2.3 复用结论
| 组件 | 可复用度 | 说明 |
|---|---|---|
| 期权链读取（yfinance + Yahoo 直连） | ✅ 直接复用 | 免费拿 strike/expiry/premium/IV/OI/volume，无需付费源 |
| BS Greeks（Delta/IV 推导） | ✅ 直接复用 | 技术系数（RSI/MACD）需另接 quant 因子 |
| 长期价值门槛 / R/R 门 | ✅ 复用 + 扩展 | 作为"信号层白名单"基础 |
| 账本 CSV schema（50+ 列） | ⚠️ 部分复用 | 字段够用；但需新增"是否接入 $50k 组合 / 担保现金 / 指派后股票 Unit_ID"映射 |
| DTE / 行权价参数 | ❌ 需改 | 现有 45–90/3–15% 与 wheel 30–45/5–10% 不符，需新增参数或分支 |
| 实盘执行 / 指派转股票 / 现金担保 | ❌ 无 | 现有系统**只有推荐与复盘，没有把期权落地进组合**——这是本次最大新增面 |

**一句话**：期权**数据获取与风控内核可复用**；但"CSP 现金担保、被行权转股票、CC 覆盖卖"的**执行与组合集成层为全新模块**，现有系统不提供。

---

## 3. portfolio_50000.py 改动半径（L1 / L2 / L3）

### 3.0 现状约束（只读确认）
- 持仓为 `list[dict]`（**无 Instrument 类**，grep `class ` 在文件中零命中）
- `positions.csv` 列（15 字段，纯股票）：`Portfolio_ID, Unit_ID, Ticker, Shares, Entry_Price, Entry_Date, Cost_Basis, Current_Price, Market_Value, Unrealized_PnL, Unrealized_PnL_Pct, Weight_Pct, Status, Stop_Loss, Recommendation_ID, Last_Update`
- 现金由流水推导 `derive_cash`（L189，BUY 减 / SELL 加）—— **无"冻结/担保现金"概念**
- 常量 `UNIT_DOLLARS=10000`(L41) / `MAX_OPEN_POSITIONS=4`(L42) 硬编码；`process_buys` 按 `floor(UNIT_DOLLARS/price)` 买股（L322）

### L1 — 最小（仅扩展字段，独立子账本）
- 不改现金/持仓模型；期权仍走 `option_strategies.csv`
- 仅给 `portfolio_50000.py` 的 position 加可选 `OptionType/Strike/Expiry` 字段（默认空）
- **不满足设计**：CSP 现金担保、被行权转股票、CC 覆盖卖均无法落地（现金与持仓模型不动）
- **评估**：❌ 不采用（与"组合扩容、纳入股票持仓"直接冲突）

### L2 — 中等（扩展组合模型 + 新增担保现金 + run() 内期权阶段）✅ 推荐基线
- position schema 扩展：新增 `Instrument_Type`(STOCK/OPTION)、`OptionType`、`Strike`、`Expiry`、`Qty_Contracts`、`Collateral_Unit_ID`（CSP 担保指向股票 Unit）
- 新增**担保现金**概念：`derive_cash` 改为 `可用现金 = 本金 − Σ股票市值占用 − Σ期权担保现金`；CSP 卖出时冻结 `Strike×100×张数` 作为担保，不计入可花现金
- `run()` 新增 `process_options` 阶段：
  - CSP 卖出（SELL_TO_OPEN PUT，现金担保）→ 冻结现金、写期权子持仓
  - 到期指派 → 解冻担保、按执行价建股票 Unit（复用现有 `positions.append` 股票结构）
  - CC 卖出（SELL_TO_OPEN CALL，覆盖持仓股）→ 校验"持仓股 ≥ 100×张数"
- 保留 `UNIT_DOLLARS/MAX_OPEN_POSITIONS` 作为**兼容默认值**，新增百分比上限常量并行生效
- **评估**：✅ 满足设计核心（现金担保、指派转股票、CC 覆盖），改动面集中于 `portfolio_50000.py` + `review.yml` 调用

### L2.1 详细实施路径（设计稿，非代码）

> 以下为 L2 的设计细化，**本轮不写代码**；判决后实施严格照此执行。所有函数名指向既有模块，仅描述行为与字段，不含可执行实现。

#### (a) 数据结构扩展（portfolio_50000.py）
- **持仓记录**：保留 `list[dict]` 形态（不引入新 class，最小改动），每条记录新增 `Instrument_Type` 字段（默认 `STOCK`）。
  - 股票持仓：沿用现有 15 字段 + `Instrument_Type=STOCK`。
  - 期权持仓新增字段：`OptionType`(PUT/CALL)、`Strike`、`Expiry`、`Qty_Contracts`、`Collateral_Amount`(= `Strike×100×张数`)、`Collateral_Unit_ID`(担保现金标识)、`Underlying_Ticker`、`Status`(OPEN/ASSIGNED/EXPIRED/CLOSED)、`Recommendation_ID`。
- **担保现金概念（核心新增）**：
  - 账户本金不变；在既有 `derive_cash`（流水推导）之外新增 **`reserved_cash`** 运行时变量 = Σ期权 `Collateral_Amount`。
  - 新增 **`derive_available_cash`**：`可用现金 = 本金 − Σ股票市值占用 − reserved_cash`。
  - 担保现金**不计入可花现金**，仅 CSP 指派解冻后转为股票建仓成本；任何下单前的「可用现金×0.8 / 单张≤$5,000」校验均基于 `derive_available_cash`。

#### (b) run() 内接入 process_options（调用顺序）
既有 `run()`：`加载推荐 → 计算现金 → process_sells → process_buys → 写账本`。
L2 在 **`process_buys` 之后、`写账本` 之前**插入 `process_options(signals, ...)`：
1. 输入来源：读 `option_strategies.csv`，仅筛 `Strategy∈{CSP,CC}` 且 `Status==Active` 且 `RR≥2.0` 的条目——**信号由 `scan_us_option_engine` 生成，本函数不生成**。
2. 逐条执行层白名单校验（§6）：策略∈{CSP,CC} / 担保现金≤`可用现金×0.8` / 单张≤$5,000 / 单只·板块·总股票·总期权·现金下限（§1.3）逐项 / CC 持仓≥`100×张数` 且 `行权价≥成本+权利金`。
3. **CSP**：SELL_TO_OPEN PUT → 冻结 `Collateral_Amount`（`reserved_cash` 增加）、追加 OPTION 持仓、`可用现金` 不变（本金不变，仅占用担保）。
4. **到期指派**（由 `review.py` 的 `process_options` 判定后回写）：解冻担保 + 按执行价建 STOCK Unit（复用现有 `positions.append` 股票结构），形成 CSP→股票 闭环。
5. **CC（第二阶段，延后 3 个月）**：SELL_TO_OPEN CALL，覆盖持仓股，校验权证数量与行权价。
6. **R1 原则**：无信号 / 无可用现金 → 不追加 OPTION 持仓、不冻结现金、不写账本。

#### (c) 新建执行账本 option_positions.csv（字段设计）
- **文件名**：`option_positions.csv`（执行层，与信号层 `option_strategies.csv` 并存，不混用）。
- **核心字段（草案）**：`Option_ID, Portfolio_ID, Underlying_Ticker, OptionType, Strike, Expiry, Qty_Contracts, Entry_Premium, Collateral_Amount, Collateral_Unit_ID, Status, Recommendation_ID, Open_Date, Assigned_Unit_ID, Last_Update`
- **与 `option_strategies.csv` 的关系**（两张账本分离）：
  - `option_strategies.csv` = **信号层**：`scan_us_option_engine` 产出，含 Delta/IV/Wall 等多列风控证据，用于推荐与复盘。
  - `option_positions.csv` = **执行层**：组合实际持仓、担保现金、指派结果，字段精简聚焦「持仓状态」。
  - 映射键：`option_positions.Recommendation_ID → option_strategies.Strategy_ID`（执行来自哪条推荐）。
  - **单向引用**：执行层读信号层，信号层不反向写；被行权转股票后 `Assigned_Unit_ID` 写回 `positions.csv`（股票 Unit）。
- **Git 跟踪**：`option_positions.csv` 纳入版本控制（仿 `portfolio_50000_positions.csv` 模式，由 `review.yml` 追加 `git add` + commit + push）。

#### (d) L2 实施影响面（铁律兼容）
- 改动文件：`portfolio_50000.py`（schema + 担保现金 + `process_options`）、`review.yml`（追加调用 + 提交 `option_positions.csv`）。
- 不碰：`scan.py` / `review.py` 股票逻辑（仅复用其期权结算 `process_options`）、`scan_us_option_engine.py`（判决前不碰）、新闻模块。
- 测试：新增 `tests/test_options_wheel.py`（§7 清单 1–13），预期全量 **191 → ≥204 passed，0 regression**。

### L3 — 完整（废除 unit，纯百分比暴露模型）
- 删除/弃用 `UNIT_DOLLARS`/`MAX_OPEN_POSITIONS`，改为 1.3 六类百分比上限
- 重写 `process_buys` 仓位计算：基础×评分×止损×技术四层系数（1.4），按优先级排序（评分降序、同分止损距离升序）
- 全量暴露检查（单只/板块/总股票/总期权/单张/CSP/现金下限）放在每笔下单前
- 历史 unit 持仓需迁移映射（旧 Unit_ID → 新百分比权重）
- **评估**：✅ 完整落地用户设计，但改动半径最大，需数据迁移与回归测试扩充

> **建议**：先 L2 落地 CSP（现金担保 + 指派转股票），CC 阶段在已有股票池上追加覆盖卖；unit→百分比的彻底废除（L3）可作为后续独立 PR，避免单 PR 过大。

---

## 4. 数据依赖清单

| 数据 | 来源 | 免费？ | 用途 | 现状 |
|---|---|---|---|---|
| 到期日列表 `option_chain().expirations` | yfinance / Yahoo 直连 | ✅ | 选 30–45 DTE | 引擎已支持（L600-609） |
| 行权价 `strike` | 同上 | ✅ | OTM 5–10% 选价 | 引擎已支持 |
| 权利金 `bid/ask/lastPrice` | 同上 | ✅ | 金额计算、最大收益 | 引擎 `_mid_or_last`(L244) |
| IV `impliedVolatility` | 同上 | ✅ | IV 分位、Delta 推导 | 引擎已支持 |
| 成交量/OI `volume/openInterest` | 同上 | ✅ | 流动性/Wall | 引擎已支持 |
| Greeks（Delta 等） | **BS 自算**（L160-241） | ✅ | 技术系数、指派风险 | 引擎已支持 |
| 正股实时价（指派判定） | yfinance / `get_live_quote_bootstrap` | ✅ | 到期指派、CC 覆盖 | review.py 已用 |
| 技术因子（RSI/MACD/MA20） | quant 因子（`quant_score_v2.py` 等） | ✅ | 1.4 技术系数 | 需接入 option 模块 |
| 评分（Quant/Fundamental/Score） | scan 输出 `trade_history.csv` | ✅ | 1.4 评分系数 + 优先级 | 引擎已读 `item` |
| 板块分类（Sector） | 标的基础数据 | ✅ | 1.3 板块上限 | 现有 positions 有 `Sector`? 需确认字段源 |

**结论**：基础 wheel 所需数据**全部由现有免费源覆盖，无需付费 API**（Polygon/Tiingo 等仅在需要更精确 Greeks/实时深度时作为可选增强）。

---

## 5. 必须硬性禁止的策略

下列策略**亏损不封顶或超出现金担保范围**，一律禁止生成与执行：

| 禁止策略 | 原因 | 防护层 |
|---|---|---|
| **Naked Call（无担保卖 Call）** | 标的暴涨亏损无限 | 信号层白名单（仅允许 CSP/CC） |
| **Naked Put（无现金担保卖 Put）** | 超出账户现金的潜在接货义务 | 执行层担保现金冻结校验 |
| **Strangle（同时卖 OTM Call+Put）** | 两端均可能无限亏损 | 信号层白名单 |
| **Straddle（同时卖 ATM Call+Put）** | 两端均可能无限亏损 | 信号层白名单 |
| **任何亏损不封顶策略** | 违反"总期权暴露≤15%" | 执行层 MaxLoss 校验 |
| **杠杆/保证金买入期权组合** | 超出现金约束 | 现金下限 5% 硬顶 |

> 现有引擎**已天然不生成** Naked/Strangle/Straddle（只产出 SHORT_PUT/CALL_DEBIT_SPREAD/LONG_CALL），但这是"不生成"而非"显式禁止"——本设计需补**显式白名单 + 断言**，杜绝未来误加。

---

## 6. 三层白名单机制设计

### 信号层（Signal Layer）—— 生成端
- 位置：`scan_us_option_engine.py` 的 `build_option_recommendation` 前增 `ALLOWED_STRATEGIES = {"CSP", "CC"}`
- 强制：`strategy` 必须 ∈ 白名单，否则 `return None`
- 资格门：复用 `MIN_REWARD_RISK=2.0` + `_long_term_value_gate`；wheel 版新增 DTE∈[30,45]、OTM∈[5%,10%]、现金担保校验
- **断言**：任何不在白名单的策略类型在 CI 测试中断言失败

### 执行层（Execution Layer）—— 组合端
- 位置：`portfolio_50000.py` 的 `process_options`（L2 新增）
- 下单前校验：
  1. 策略 ∈ 白名单
  2. 现金担保：`Strike×100×张数 ≤ 可用现金 × 0.8`（单张 ≤ $5,000）
  3. 暴露上限：单只/板块/总股票/总期权/现金下限（1.3）逐项检查
  4. CC 必须 `持仓股 ≥ 100×张数` 且 `行权价 ≥ 成本+权利金`
- **断言**：任一超限 → 拒绝该笔、写 `Reject_Reason`，不静默通过

### 审计层（Audit Layer）—— 复核端
- 位置：`review.py` `build_active_option_reviews` + dashboard `build_options`
- 复用 `is_actionable_option`（dashboard_export.py）仅放行 `Status==Active` 且 `RR≥2.0`
- 新增：每日快照暴露汇总（单只/板块/总期权/现金），超硬顶则 dashboard 标红告警
- 邮件 Gate：`get_recent_option_recommendations` 已过滤 `Status==Active`（测试 12 验证）—— 禁止策略永不该进入邮件
- **不变式**：`∀ active position: RR≥2.0 AND 策略∈白名单 AND 暴露≤硬顶`（测试 14 同款 Invariant 扩展到 wheel）

---

## 7. 测试清单

> 以下为**待实施**测试清单（本轮不写）。建议放 `tests/test_options_wheel.py`。

1. **白名单断言**：传入 Naked Call/Put/Strangle/Straddle 输入 → 信号层 `return None` / 执行层拒绝
2. **CSP 现金担保**：卖出 PUT 后 `可用现金` 减少 = `Strike×100×张数` 被冻结；不冻结则失败
3. **CSP 指派转股票**：到期价内 → 担保解冻 + 按执行价建股票 Unit（复用股票结构），组合扩容 +1
4. **CC 覆盖校验**：无持仓时卖 Call → 拒绝；有 ≥100 股时卖 Call → 成功；`行权价 < 成本+权利金` → 拒绝
5. **四层金额公式**：Core($12k)×评分(≥90→1.3)×止损(≤5%→1.2)×技术(RSI>80→0.5) 正确计算；超 `min(单张$5k, 现金×0.8)` 截断
6. **优先级排序**：多信号按评分降序、同分按止损距离升序开仓
7. **DTE/OTM 参数**：只接受 DTE∈[30,45]、OTM∈[5%,10%]；越界被拒（验证与现有 45–90 参数分离）
8. **百分比上限**：单只>25%、板块>40%、总股票>80%、总期权>15%、现金<5% → 拒绝对应下单
9. **R/R 门回归**：复用 `test_options_reward_risk.py` 全部 15 组，wheel 策略仍满足 `RR≥2.0 才 Active`
10. **数据获取**：mock yfinance/Yahoo 链，验证 strike/expiry/premium/IV 解析；真实 API 不在单测内
11. **R1 原则**：无期权信号 / 无可用现金 → 不写期权子持仓、不冻结现金
12. **不硬编码绝对日期**：所有 DTE/到期用相对日期计算
13. **隔离不变式**：wheel 改动不污染现有股票 unit 逻辑（现有 191 测试 0 regression）
14. **回测（新增缺口）**：现有系统**无回测引擎**——需新增历史链回放，验证 wheel 在历史样本上的接货率/年化收益/最大回撤

---

## 8. 实施依赖（判决后 + 用户最终确认）

### 8.1 前置条件
- [ ] 10-08 判决 = OK / SYSTEMATIC（DEEPER/OTHER 不实施）
- [ ] 用户在 GitHub Secrets 配置 `FINNHUB_API_KEY`（新闻模块，独立）
- [ ] 用户最终确认本设计文档（尤其 L2 vs L3 取舍、CC 启动时机）
- [ ] 确认板块分类（Sector）字段数据源，用于 1.3 板块上限

### 8.2 实施顺序建议（判决后）
1. **先 CSP（L2）**：扩展 position schema + 担保现金 + `process_options` CSP 分支 + 信号层白名单 + 测试 1–9,11,13
2. **回测补齐**（测试 14）：历史链回放验证
3. **CC（第二阶段）**：在 CSP 跑通、已有指派股票池后，追加覆盖卖分支 + 测试 4
4. **L3（可选独立 PR）**：unit→百分比彻底废除 + 数据迁移

### 8.3 不改动项（铁律延续）
- 不改 `scan.py` / `review.py` 现有股票 Scan/Review 逻辑（仅新增 option 模块调用）
- 不改新闻模块（本轮已提交的 `fetch_news.py` / `news-fetch.yml` / dashboard 集成）
- 不碰监控 PID 536931 与 `/tmp/scan_1008_monitor.log`
- 不手工 backfill / snapshot

### 8.4 用户确认事项（已确认 ✅ → 见 §0 决策记录）

> 以下 5 项已于 **2026-10-08** 全部拍板固化，详见文档开头 **§0 决策记录**，不再处于「待确认」状态。

| # | 事项 | 决策 | 状态 |
|---|---|---|---|
| 1 | 改动半径 L2 / L3 | **L2**：扩展组合模型 + 担保现金 + `run()` 内 `process_options`；L3 废 unit 留后续独立 PR | ✅ 已确认 |
| 2 | CC 启动时机 | **CSP 跑通 3 个月后**启动 | ✅ 已确认 |
| 3 | 被迫调仓减仓优先级 | **表现最差 + 与当前信号冲突**优先（并列按市值小者先减） | ✅ 已确认 |
| 4 | 账本新建 / 复用 | **新建执行账本 `option_positions.csv`**（与信号层 `option_strategies.csv` 分离） | ✅ 已确认 |
| 5 | 回测窗口 | **先纸上记录 6 个月**，不造回测避免前视偏差 | ✅ 已确认 |

---

## 附：调查证据索引

| 事实 | 文件:行 |
|---|---|
| 期权引擎产出三类策略 | `scan_us_option_engine.py:650-661` |
| 现有 DTE 窗 45–90 / 目标 60 | `scan_us_option_engine.py:24-26` |
| Short Put 行权价折扣 3–15% | `scan_us_option_engine.py:52-53` |
| R/R 最终门 = 2.0 | `scan_us_option_engine.py:42` |
| 期权链 Layer1 yfinance / Layer2 Yahoo | `scan_us_option_engine.py:600-609` `:566-594` |
| 账本现状 14 行（10 Active/4 Rejected） | `option_strategies.csv`（实测） |
| 期权账本与 $50k 组合隔离 | `portfolio_50000.py` 无 `option_strategies` 引用（grep） |
| 持仓为 list[dict]，无 Instrument 类 | `portfolio_50000.py`（grep `class ` 零命中） |
| 现金由流水推导、无冻结概念 | `portfolio_50000.py:189` `derive_cash` |
| UNIT_DOLLARS/MAX_OPEN_POSITIONS 硬编码 | `portfolio_50000.py:41-42` |
| 现有测试无回测引擎 | `tests/test_options_reward_risk.py`（15 组资格回归） |
| review 按 Status==Active 过滤 | `review.py:935` |
| 期权指派结算逻辑 | `review.py:979-1020` `process_options` |

---

## 附：L2 实现草稿（可直接抄）

> **定位与偏差说明**：本草稿相对 §3 L2 做了一处**收敛**——把期权逻辑从「嵌进 `portfolio_50000.py`」改为「**独立模块 `option_wheel.py`**，只在集成点被调用」。理由：blast radius 更小、可单独测试、不污染主组合模型。§3 L2 的「担保现金 / 指派转股票」仍成立，只是落地位置换成了 `option_wheel.py` + 执行账本 `option_positions.csv`。
> **状态**：草稿，**未写代码、未改任何仓库文件、不 push**。**不在本周做**，等周一验证后启动。
> 复用约定（见 §0 / §2）：信号层 `option_strategies.csv`（由 `scan_us_option_engine` 产出）、执行层 `option_positions.csv`（本模块读写）、期权链 `yfinance.option_chain()`（`scan_us_option_engine.py:600-609` 已用）。

### 1. 新增 flag

`ENABLE_OPTIONS_WHEEL`（默认关闭），沿用 `ENABLE_*` 命名风格，与 `ENABLE_TARGET_FILE` / `ENABLE_AI_REASON_BACKFILL` 同级（在 `review.yml` 各步骤 env 块注入）。

- `ENABLE_OPTIONS_WHEEL != "1"` → 所有集成点直接 `return`，主流程零影响。
- 仅在 `scan.py` / `review.py` / `dashboard_export.py` 三个集成点读取。

### 2. 新增文件

`option_wheel.py`（仓库根，独立模块，**不碰 `portfolio_50000.py`**）。

- 负责：CSP/CC 下单草稿、指派检查、wheel 状态汇总。
- 不负责：生成信号（信号来自 `scan_us_option_engine` → `option_strategies.csv`）、不直写股票组合（只产出「指派事件」由 `review.py` 落库）。
- 读写账本：`option_positions.csv`（执行层，字段见下）。

**执行账本 `option_positions.csv` 字段设计**

| 列 | 含义 |
|---|---|
| `ticker` | 标的 |
| `kind` | `PUT` / `CALL` |
| `side` | 固定 `SELL`（卖方） |
| `strike` | 行权价 |
| `expiry` | 到期日 `YYYY-MM-DD` |
| `contracts` | 张数（1 张 = 100 股） |
| `premium` | 每张权利金（美元） |
| `status` | `OPEN` / `ASSIGNED` / `EXPIRED` / `CLOSED` |
| `cash_collateral` | CSP 冻结担保现金 = `strike * 100 * contracts` |
| `assigned_shares` | 被行权后转入的正股数（CC 为被 call 走的数） |
| `opened_at` / `closed_at` | 开/平仓时间 |

### 3. 主要函数（完整代码草稿）

```python
# option_wheel.py  —— L2 实现草稿（默认 flag 关闭时不参与主流程）
import csv
import os
import datetime as dt
from typing import List, Dict, Optional

LEDGER = "option_positions.csv"
MAX_DAILY_WRITES = 2          # 单日最多 2 张（硬性）
FORBIDDEN = {"NAKED_CALL", "NAKED_PUT"}   # 硬性禁止策略

# ── 内部工具 ──────────────────────────────
def _now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")

def _read_ledger() -> List[Dict]:
    if not os.path.exists(LEDGER):
        return []
    with open(LEDGER, newline="") as f:
        return list(csv.DictReader(f))

def _append_row(row: Dict) -> None:
    write_header = not os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            w.writeheader()
        w.writerow(row)

def _daily_writes(ticker_date: Optional[str] = None) -> int:
    d = ticker_date or dt.date.today().isoformat()
    return sum(1 for r in _read_ledger() if r.get("opened_at", "").startswith(d))

def _get_option_quote(ticker: str, kind: str, strike: float, expiry: str) -> float:
    # TODO(实盘前确认): yfinance Ticker(ticker).option_chain(expiry)
    #   取 strikes / calls / puts 中匹配 strike 的 mid 价。
    #   现用占位（测试以 mock 覆盖，不在单测内打真实 API）。
    raise NotImplementedError("用 yfinance.option_chain 实现，见 scan_us_option_engine.py:600-609")

# ── ① 卖 CSP ─────────────────────────────
def sell_csp(ticker: str, strike: float, expiry: str, ref_price: float) -> Dict:
    """现金担保卖 Put。担保现金 = strike * 100 * 1 张。"""
    if _daily_writes() >= MAX_DAILY_WRITES:
        raise RuntimeError(f"单日写入已达上限 {MAX_DAILY_WRITES} 张，今日不再开仓")
    premium = _get_option_quote(ticker, "PUT", strike, expiry)
    collateral = strike * 100.0          # 1 张
    row = {
        "ticker": ticker, "kind": "PUT", "side": "SELL",
        "strike": strike, "expiry": expiry, "contracts": 1,
        "premium": round(premium, 2),
        "status": "OPEN",
        "cash_collateral": round(collateral, 2),
        "assigned_shares": 0,
        "opened_at": _now(), "closed_at": "",
    }
    _append_row(row)
    return row   # 调用方据此冻结组合可用现金

# ── ② 检查到期指派 ───────────────────────
def check_assignment(positions: List[Dict], live_price_fn) -> List[Dict]:
    """遍历 OPEN 的 CSP/CC，按到期日与实时价判定指派/过期。
    返回指派事件列表，由 review.py 落库到股票组合（本模块不直写）。"""
    today = dt.date.today()
    events = []
    for r in positions:
        if r.get("status") != "OPEN":
            continue
        exp = dt.date.fromisoformat(r["expiry"])
        if exp > today:
            continue
        px = live_price_fn(r["ticker"])
        if r["kind"] == "PUT" and px <= float(r["strike"]):
            # 被行权：转入 100 股 @ strike，释放担保现金
            r["status"] = "ASSIGNED"
            r["assigned_shares"] = 100 * int(r["contracts"])
            r["closed_at"] = _now()
            events.append({"type": "PUT_ASSIGNED", "ticker": r["ticker"],
                           "shares": r["assigned_shares"],
                           "price": float(r["strike"])})
        else:
            r["status"] = "EXPIRED"
            r["closed_at"] = _now()
            events.append({"type": "EXPIRED", "ticker": r["ticker"]})
    return events

# ── ③ 卖 CC ──────────────────────────────
def sell_covered_call(ticker: str, strike: float, expiry: str,
                      long_shares: int) -> Dict:
    """备兑看涨。硬性要求正股 ≥ 100 * contracts。"""
    contracts = 1
    if long_shares < 100 * contracts:
        raise RuntimeError(
            f"卖 CC 需正股 ≥ {100*contracts} 股，当前 {long_shares} 股（禁止裸卖 Call）")
    if _daily_writes() >= MAX_DAILY_WRITES:
        raise RuntimeError(f"单日写入已达上限 {MAX_DAILY_WRITES} 张")
    premium = _get_option_quote(ticker, "CALL", strike, expiry)
    row = {
        "ticker": ticker, "kind": "CALL", "side": "SELL",
        "strike": strike, "expiry": expiry, "contracts": contracts,
        "premium": round(premium, 2), "status": "OPEN",
        "cash_collateral": 0.0, "assigned_shares": 0,
        "opened_at": _now(), "closed_at": "",
    }
    _append_row(row)
    return row

# ── ④ wheel 状态汇总（供 dashboard）──────
def wheel_status() -> Dict:
    rows = _read_ledger()
    open_csp = [r for r in rows if r["kind"] == "PUT" and r["status"] == "OPEN"]
    open_cc  = [r for r in rows if r["kind"] == "CALL" and r["status"] == "OPEN"]
    frozen   = sum(float(r.get("cash_collateral", 0) or 0) for r in open_csp)
    assigned = sum(int(r.get("assigned_shares", 0) or 0) for r in rows)
    return {
        "open_csp": open_csp, "open_cc": open_cc,
        "frozen_cash": round(frozen, 2),
        "assigned_shares": assigned,
        "total_open": len(open_csp) + len(open_cc),
    }
```

### 4. 集成点

- **`scan.py`**：在 `ENABLE_OPTIONS_WHEEL == "1"` 时，主流程结束前调用 `option_wheel` 读取 `option_strategies.csv` 中 `Strategy∈{CSP,CC} & Status==Active & RR≥2.0` 的候选，**只做候选交接、不生成信号**；flag 关闭则直接 `return`，主流程零影响。
- **`review.py`**：在到期处理（`process_options` 区段）前，若 flag 开，调用 `check_assignment(positions, get_live_quote)` 得到指派事件，将 `PUT_ASSIGNED` 事件按执行价转入 `portfolio_50000_positions.csv`（等价建仓），并 `git add option_positions.csv` 一并提交；flag 关闭则跳过。
- **`dashboard_export.py`**：新增 `build_wheel()`，读 `option_positions.csv` 经 `wheel_status()` 注入 `portfolio.wheel`（open_csp / open_cc / frozen_cash / assigned_shares）；`app.js` 新增 `renderWheel()` 渲染 wheel 板块（独立卡片，与主持仓卡并列）。

### 5. 5 个测试用例草稿

1. **卖 CSP 后现金冻结正确**：`sell_csp("XYZ", 100, exp, 105)` → `option_positions.csv` 新增行 `cash_collateral == 100*100`；断言组合可用现金减少额 == 该冻结额。
2. **被行权后持仓正确转换**：构造一条 `OPEN` 的 ITM CSP（`px=95 ≤ strike=100`），`check_assignment` 返回 `PUT_ASSIGNED` 事件 `shares=100 @ 100`，原行 `status` 变 `ASSIGNED`、担保现金释放。
3. **卖 CC 要求正股 ≥ 100**：`long_shares=50` 时 `sell_covered_call(...)` 抛 `RuntimeError`（裸卖 Call 被拒）。
4. **单日上限（最多 2 张）触发**：连续 `sell_csp` 3 次 → 第 3 次抛 `RuntimeError("单日写入已达上限 2 张")`。
5. **硬性禁止策略（Naked Call）被拒绝**：任何路径尝试生成 `NAKED_CALL`/`NAKED_PUT` → 在 `FORBIDDEN` 集合拦截并拒绝（单元级断言拒绝分支被命中）。

### 6. 实施依赖

- 需先确认：`option_strategies.csv` 的字段结构（信号层，§2 已列 14 行现状），明确 CSP/CC 候选的过滤列。
- 需先确认：`yfinance.option_chain()` 能否稳定拿到 `puts` / `calls` 链（`scan_us_option_engine.py:600-609` 已用，预期可行，实盘前再验证）。
- **不在本周做**，等周一验证（见 `archive/MONDAY_VERIFICATION_PLAN.md`）后启动；启动前先开 `ENABLE_OPTIONS_WHEEL` 仅做 dry-run 日志，确认无副作用再正式下单。

---

## 附二：接线方案（L2 模块 → 生产接线，下周启动）

> 前提：`option_wheel.py`（§附 L2 草稿）已实现、flag 关闭、`ENABLE_OPTIONS_WHEEL` 默认不设、零调用点、零副作用。本章只描述如何把孤岛模块接入三个现有 workflow，**不改任何策略逻辑**。所有接线都包在 `if os.environ.get("ENABLE_OPTIONS_WHEEL") == "1":` 之下，默认不激活。
>
> 真实接口（已确认 `option_wheel.py` 现状）：`sell_csp(ticker, strike, expiry, ref_price)`、`check_assignment(positions, live_price_fn)`、`sell_covered_call(ticker, strike, expiry, ref_price, long_shares)`、`wheel_status()`、`_enabled()`、`is_strategy_allowed(strategy)`；常量 `ALLOWED_STRATEGIES={"CSP","CC"}`、`FORBIDDEN_STRATEGIES={"NAKED_CALL","NAKED_PUT","STRANGLE","STRADDLE"}`、`DAILY_CAP=2`、账本文件 `option_positions.csv`。

### 1. scan.py 接线（CSP 信号触发）

**何时触发**：scan 主流程跑完 `strict_filter` → 候选 `to_write` / `chosen` 确定后。当前落在 `scan.py:3900` 的 pending 落盘段与 `scan.py:3956` 的 `ENABLE_TARGET_FILE` target 段之间，紧邻现有 target 段新增独立段即可。

**从哪些数据判断「该卖 Put」**：
- 数据源复用 `build_ai_input(pool_data, redef_positions, redef_candidates)` 的「持仓 + 候选」集合（已在 `scan.py:3779` 算出）。
- 对每个 Ticker 调 `yfinance.Ticker(t).option_chain(exp)` 取近月 ATM Put；`strike = round(Price × 0.95)`；用期权 mid 价算年化收益 `= premium / (strike × 100) × (365 / exp_days)`。
- 触发条件（白名单内）：年化收益 ≥ 阈值（建议常量 `CSP_MIN_ANNUAL_YIELD`，初值 `0.15`）+ `is_strategy_allowed("CSP")` 为真 + 该 Ticker 在 `option_positions.csv` 无 OPEN CSP。
- **硬约束**：`option_chain` 网络调用必须带超时 + `try/except`，失败仅 `print` 警告、**不阻断 scan 主流程**（与 H1 精神一致：Feature 段失败不阻断）。

**flag 门控写法**（参考 `scan.py:3957` 范式）：
```python
# >>> Feature: Options Wheel CSP 信号（默认关闭；ENABLE_OPTIONS_WHEEL=1 才写 option_positions.csv，失败不阻断）>>>
if os.environ.get("ENABLE_OPTIONS_WHEEL") == "1":
    try:
        from option_wheel import sell_csp, is_strategy_allowed
        exp = _next_monthly_expiry()          # 复用 scan_us_option_engine 的到期计算
        for t in redef_candidates:            # 以候选为主，持仓为辅
            chain = yf.Ticker(t).option_chain(exp)
            put = _nearest_atm_put(chain.puts, price_of[t])
            if put and is_strategy_allowed("CSP") and _csp_yield(put) >= CSP_MIN_ANNUAL_YIELD:
                sell_csp(t, put.strike, exp, price_of[t])
    except Exception as e:
        print(f"⚠️ Wheel CSP 信号生成失败（不影响 scan）：{e}")
```

**账本并发提示**：scan 写 `option_positions.csv` 在周一 21:07（独立 group `us-stock-scan`）；review 也写该文件在次日 06:23——**时间错峰、不重叠**，option 子账本不会触发 H1 式覆盖（H1 解决的是主 `portfolio_50000_positions.csv`）。

### 2. review.py 接线（检查到期 + 指派转持仓）

**何时检查到期**：review 全量 run 流程内（`review.py:3822` 调 `backfill_pending_reasons(".")` 之后，同属 review 单次 run）。新增相邻段。

**被行权后如何转持仓**：
- `check_assignment(positions, live_price_fn)` 读 `option_positions.csv` 的 OPEN CSP/CC，用实时价判 `PUT_ASSIGNED` / `CALL_CALLED` / `EXPIRED`，返回事件列表。
- **关键决策（守住铁律）**：被指派产生的「名义股数」**只写回 `option_positions.csv` 的 `assigned_shares` 字段**，由 `wheel_status()` 聚合展示；**不写入 `portfolio_50000_positions.csv`**。理由：① 避免侵入主组合占比/Unit 逻辑（Bonus D 天花板 + 4 单元锁）；② 不与 H1 已串行化的主账本冲突；③ 真正需要建仓时由人工或后续 L3 决定。→ wheel 是纯独立子账本。

**与 backfill_pending_reasons 的顺序**：两者无数据依赖（backfill 填交易原因文本，wheel 生成期权事件），可任意顺序。建议 wheel 检查放在 backfill **之后**（同一 `ENABLE_OPTIONS_WHEEL` 段内或紧邻），共用一次 run 的实时价拉取。

**flag 门控写法**（参考 `review.py:3822` 范式）：
```python
if os.environ.get("ENABLE_OPTIONS_WHEEL") == "1":
    from option_wheel import check_assignment
    ledger = _read_option_ledger()            # 即 option_wheel._read_ledger()
    events = check_assignment(ledger, _live_price)
    if events:
        _append_option_events(events)         # 仅写 option_positions.csv
        print(f"✅ Wheel 到期检查：{len(events)} 个事件")
```

### 3. dashboard_export.py 接线（build_wheel + 前端板块）

**新增 `build_wheel(data_dir)`**：调 `wheel_status()` 读 `option_positions.csv`，返回：
```python
{
  "open_csp": int,        # 未平仓 CSP 张数
  "open_cc": int,         # 未平仓 CC 张数
  "frozen_cash": float,   # 担保冻结现金合计
  "assigned_shares": int, # 被指派累计股数
  "ledger": [...],        # 明细（供前端展开）
}
```
在 `build_portfolio`（当前 `dashboard_export.py:2543` target 注入段之后）注入：
```python
if os.environ.get("ENABLE_OPTIONS_WHEEL") == "1":
    portfolio["wheel"] = build_wheel(data_dir)
else:
    portfolio["wheel"] = None
```

**前端新板块**：`app.js` 新增 `renderWheel()`，在主持仓卡下方渲染独立卡片（open_csp / open_cc / frozen_cash / assigned_shares），`wheel === null` 时整段隐藏（与 `renderTarget` 的 `!target` 隐藏逻辑一致）。不读 `wheel` 的页面在 flag 关闭时不受任何影响。

### 4. 风险与顺序

**建议接线顺序：dashboard → review → scan**（由低风险到高风险）：

| 顺序 | 接线 | 副作用 | 风险 | 理由 |
|------|------|--------|------|------|
| 1 | dashboard_export | 仅读 `option_positions.csv` + JSON 增字段 | 极低 | 纯展示，先验证读写与渲染链路 |
| 2 | review | 写 `option_positions.csv`（子账本） | 低 | 只读检查到期 + 事件生成，不碰主账本 |
| 3 | scan | 写 `option_positions.csv`（下单） | 中 | 真正产生 CSP，需前两步验证后再开 |

- **每个接线独立 commit**，且各自带「先 dry-run（仅 log 不写盘）确认无副作用」的最小验证。
- **不碰主账本**：三个接线都不会改 `portfolio_50000_positions.csv` / `transactions.csv`（H1 已串行化保护的对象），wheel 全部走独立子账本 `option_positions.csv`。
- **option 子账本并发天然错峰**：scan（周一 21:07）写、review（次日 06:23）写，二者不在同一时刻运行；dashboard-data 每 15 分钟只读该文件，无写竞争。故 option 账本无需加 `concurrency.group`（与主账本问题解耦）。

### 5. 测试（接线后各加几个测试）

| 接线 | 新增测试 | 覆盖 |
|------|----------|------|
| dashboard_export | 2 | ① flag 关 `portfolio.wheel is None` 不渲染；② flag 开 `build_wheel()` 聚合正确注入且字段齐全 |
| review | 2 | ① `check_assignment` 对 ITM CSP 返回 `PUT_ASSIGNED` 事件且 `assigned_shares` 更新；② 过期返回 `EXPIRED`；两者均**只写 `option_positions.csv`、不写主 positions** |
| scan | 2 | ① 对候选跑 `option_chain` 后 `sell_csp` 正确写入 `option_positions.csv`；② flag 关时不写 |

→ 接线后共 **+6 测试**，全量套件保持绿色。

---

## 附三：可直接抄的接线代码

> 仅代码草稿，**未改任何文件**。前提：`option_wheel.py`（L2 执行层，含 `sell_csp`/`check_assignment`/`wheel_status`/`_read_ledger`）已实现并通过 `test_option_wheel.py`；`ENABLE_OPTIONS_WHEEL` 为其模块级 flag（`option_wheel._enabled()`）。本附重述「生产接线」的复制即用片段，与 §附二 概念稿互补。

### 1. scan.py 接线（CSP 信号触发 → 写 `option_positions.csv`）

- **插入位置**：紧邻 `scan.py:3908` 的宏观 feature 块之后（同款 `if flag_enabled(): try/except` 包裹，**失败不阻断 scan**）。
- **导入**：在 scan.py 顶部 import 区加 `import option_wheel`（或 `from option_wheel import sell_csp, _enabled as options_wheel_enabled`）。
- **片段**：

```python
    # >>> Feature: Options Wheel CSP 信号（默认关闭；ENABLE_OPTIONS_WHEEL=1 才写 option_positions.csv，失败不阻断 scan）>>>
    if option_wheel._enabled():
        try:
            # csp_candidates: scan 严筛后、满足 R/R≥2.0 & 2%≤止损距离≤5% 的候选
            # 卖出 30D~45D 到期、strike = 当前价 × 0.92~0.95 的现金担保 Put
            for cand in (csp_candidates or []):
                tk = str(cand.get("Ticker", "")).upper()
                ref = float(cand.get("Price") or cand.get("ref_price") or 0.0)
                if ref <= 0:
                    continue
                exp = _next_monthly_expiry(reference_date=scan_date)   # 既有的到期日工具
                strike = round(ref * 0.93, 2)
                row = option_wheel.sell_csp(tk, strike, exp, ref)     # flag 关/超限 → 返回 None
                if row is not None:
                    print(f"🌀 Wheel CSP 开仓：{tk} strike={strike} exp={exp} 担保现金={row['cash_collateral']}")
        except Exception as _wheel_e:
            print(f"⚠️ [Wheel] CSP 信号写入失败（不影响 scan）：{type(_wheel_e).__name__}: {_wheel_e}")
```

> `_next_monthly_expiry` 为 scan 既有到期日助手（如不存在，用 `datetime` 求下个周五）；`csp_candidates` 由 §1.2/§1.4 信号强度四层结构产出，需 scan 先行计算（属于「判决后实施」范畴）。

### 2. review.py 接线（检查到期 + 指派转持仓）

- **插入位置**：在 review.py 主流程「处理期权 / `load_option_positions`」段落（约 `review.py:923` 之后，或 `process_options` 之前）插入；**先于** `backfill_pending_reasons`（AI 回填）或与之独立——指派事件生成的是独立 `option_positions.csv` 事件，不写主账本，故顺序无硬依赖，建议放在主账本 `run()` 之后、纯只读检查段。
- **片段**：

```python
    # >>> Options Wheel 到期指派检查（默认关闭；失败不阻断 review）>>>
    if option_wheel._enabled():
        try:
            positions = option_wheel._read_ledger()          # 读执行层子账本（私有读取器，可包一层公开 load_positions）
            events = option_wheel.check_assignment(
                positions, live_price_fn=lambda t: price_map.get(str(t).upper())
            )                                                # flag 关 → []；原地更新 status
            for ev in events:
                if ev["type"] == "PUT_ASSIGNED":
                    print(f"🌀 Wheel 指派：{ev['ticker']} 转入 {ev['shares']} 股 @ {ev['price']}")
                    # 此处可触发「次交易日由 portfolio_50000 买入指派股」的下游动作（L2.1 设计稿）
                else:
                    print(f"🌀 Wheel 过期：{ev['ticker']}")
            # check_assignment 已原地更新 status；如需落盘，调用 option_wheel 提供的写回：
            option_wheel._write_ledger(positions)            # 若该公开写回不存在，用 _append_row 重建或新增公开 save_ledger()
        except Exception as _wheel_e:
            print(f"⚠️ [Wheel] 到期指派检查失败（不影响 review）：{type(_wheel_e).__name__}: {_wheel_e}")
```

> 注意：`option_wheel._read_ledger()` / `_write_ledger()` 当前为私有（`_` 前缀，`option_wheel.py:61`）。接线时**建议新增公开 `load_positions()` / `save_ledger()`** 包装，避免依赖私有名；本片段按现状直接调用以贴近「可直接抄」。指派事件**只写 `option_positions.csv` 子账本**，不碰 `portfolio_50000_positions.csv` / `transactions.csv`（H1 串行化保护对象）。

### 3. dashboard_export.py 接线（`build_wheel` + 注入）

- **插入位置**：在 `dashboard_export.py` 的 `build_macro`（L2891）附近新增 `build_wheel`；在 payload 组装段（L3212-3219，`macro = build_macro(data_dir)` 之后）注入 `portfolio["wheel"]`。
- **片段**：

```python
    def build_wheel(data_dir: Path) -> dict | None:
        """读取 option_wheel 执行账本，汇总 wheel 状态（OPEN/已指派/过期、担保现金、权利金）。

        flag 关闭或账本不存在/空 → 返回 None（前端不渲染 wheel 板块）。只读、不写、不联网。
        复用 option_wheel.wheel_status()（option_wheel.py:191）；其返回结构含 positions/summary。
        """
        try:
            import option_wheel
            if not option_wheel._enabled():
                return None
            return option_wheel.wheel_status()      # 已封装 OPEN 列表 + 汇总（担保现金/权利金/指派数）
        except Exception:
            return None

    # —— payload 组装段（L3219 附近）——
    macro = build_macro(data_dir)
    wheel = build_wheel(data_dir)                  # ← 新增
    portfolio["wheel"] = wheel                     # ← 注入（None 时前端隐藏板块）
```

> `option_wheel.wheel_status()`（L191）已聚合 OPEN 持仓、担保现金、累计权利金、指派/过期计数，直接复用即可，无需重写汇总逻辑。

### 4. app.js 接线（`renderWheel` + 调用点）

- **插入位置**：在 `app.js` 的 `renderMacro`（宏观板块）之后新增 `renderWheel`；在 `renderDashboard`（或 `renderPortfolio`）内、`renderMacro(pf)` 调用附近加 `renderWheel(pf)`。
- **片段**：

```javascript
  // 期权 Wheel 板块（只读 portfolio.wheel；为 null 时隐藏整块，不崩）
  function renderWheel(pf) {
    var w = pf && pf.wheel;
    var box = document.getElementById("wheelCard");
    if (!box) return;
    if (!w || (w.positions && w.positions.length === 0 && !w.summary)) {
      box.style.display = "none";
      return;
    }
    box.style.display = "";
    var html = '<h3>🌀 期权 Wheel</h3>';
    if (w.summary) {
      html += '<div class="wheel-summary">' +
        'OPEN: <b>' + (w.summary.open_count || 0) + '</b> | ' +
        '担保现金: <b>$' + fmt(w.summary.cash_collateral || 0) + '</b> | ' +
        '权利金: <b>$' + fmt(w.summary.premium || 0) + '</b> | ' +
        '已指派: <b>' + (w.summary.assigned_count || 0) + '</b></div>';
    }
    if (w.positions && w.positions.length) {
      html += '<table class="wheel-tbl"><tr><th>标的</th><th>类型</th><th>Strike</th>' +
        '<th>到期</th><th>状态</th><th>担保</th></tr>';
      w.positions.forEach(function (r) {
        html += '<tr><td>' + esc(r.ticker) + '</td><td>' + esc(r.kind) + '</td>' +
          '<td>' + fmt(r.strike) + '</td><td>' + esc(r.expiry) + '</td>' +
          '<td>' + esc(r.status) + '</td><td>$' + fmt(r.cash_collateral || 0) + '</td></tr>';
      });
      html += '</table>';
    }
    box.innerHTML = html;
  }

  // renderDashboard 内调用点（renderMacro 之后）：
  //   renderMacro(pf);
  //   renderWheel(pf);
```

> `fmt` / `esc` 为 `app.js` 既有的金额格式化 / HTML 转义工具（与 `renderMacro`/`renderTradeStats` 复用同一套），无需新增。`index.html` 需新增 `<div id="wheelCard"></div>`（建议放在 `#macroCard` 之后或 Portfolio 区块内）。

### 5. 分步实施顺序（每个文件独立 commit，每步先 dry-run 验证）

| 顺序 | 改的文件 | 验证方式 |
|---|---|---|
| 1 | `option_wheel.py`（如 §2/§3 所述，新增公开 `load_positions()` / `save_ledger()` 包装） | 单测 + `python -c "import option_wheel; option_wheel._enabled()"` 确认 flag 关时全 None/[] |
| 2 | `dashboard_export.py`（`build_wheel` + 注入） | 2 测试：flag 关 `portfolio.wheel is None` 不渲染；flag 开聚合注入且字段齐全 |
| 3 | `review.py`（到期指派检查） | 2 测试：`check_assignment` 对 ITM CSP 返回 `PUT_ASSIGNED` 且只写子账本；过期返回 `EXPIRED` |
| 4 | `app.js` + `index.html`（`renderWheel` + `#wheelCard`） | node harness 测试：wheel null→隐藏；非空→渲染表格 |
| 5 | `scan.py`（CSP 信号触发） | 2 测试：候选跑 `sell_csp` 正确写入；flag 关时不写 |
| 6 | `scan.yml` + `review.yml`（注入 `ENABLE_OPTIONS_WHEEL: ${{ vars.ENABLE_OPTIONS_WHEEL }}`，**不硬编码 `"1"`**） | 与宏观/买入决策同款 vars. 门控；未设变量 → 全走旧路径 |

- **每步独立 commit**，各自带最小验证（先 dry-run 仅 log 不写盘确认无副作用）。
- **不碰主账本**：三个接线都不改 `portfolio_50000_positions.csv` / `transactions.csv`（H1 已串行化保护），wheel 全部走独立子账本 `option_positions.csv`。
- **并发错峰**：scan（周一 21:07）写、review（次日 06:23）写，不同时刻；dashboard-data 每 15 分钟只读 → 无需 `concurrency.group`。
- **激活**：与宏观同理，仅建 repo variable `ENABLE_OPTIONS_WHEEL=1` **且**在 `scan.yml`/`review.yml` env 注入该变量（未设即关）后生效。

---

## 附四：接线测试用例草稿

> 仅测试草稿：**函数签名 + 断言**，不写完整实现、不实施。
> 对应附三的 4 处接线（scan / review / dashboard_export / app.js）。
> 设计原则：每个接线点独立验证「flag 关 → 旧路径」「flag 开 → 新行为」「异常 → 不崩 / 不碰主账本」。

### C1. scan.py 接线测试（`ENABLE_OPTIONS_WHEEL` 门控的 CSP 信号触发）

```python
# tests/test_option_wheel_scan_wiring.py  （草稿）
import importlib

def _load_scan(monkeypatch):
    """导入 scan.py，并打桩 option_wheel + os.environ。"""
    ...

def test_scan_flag_off_does_not_call_sell_csp(monkeypatch):
    """flag 关 → sell_csp 不被调用。"""
    monkeypatch.setenv("ENABLE_OPTIONS_WHEEL", "")        # 关
    calls = []
    monkeypatch.setattr(option_wheel, "sell_csp",
                        lambda *a, **k: calls.append(1) or _fake())
    run_scan_wiring(dry=True)                              # 仅走接线分支
    assert calls == [], "flag 关时 sell_csp 不应被调用"

def test_scan_flag_on_and_yield_met_calls_sell_csp(monkeypatch):
    """flag 开 + 候选年化收益达标 → sell_csp 被调用。"""
    monkeypatch.setenv("ENABLE_OPTIONS_WHEEL", "1")        # 开
    monkeypatch.setattr(option_wheel, "sell_csp", _spy(calls))
    monkeypatch.setattr(option_wheel, "annualized_yield", lambda s: 0.42)  # 达标
    run_scan_wiring(dry=True, ticker="XYZ")
    assert len(calls) == 1 and calls[0]["ticker"] == "XYZ"

def test_scan_flag_on_chain_fail_does_not_crash(monkeypatch):
    """flag 开 + option_chain 拉取失败 → scan 不崩（异常被吞、主流程继续）。"""
    monkeypatch.setenv("ENABLE_OPTIONS_WHEEL", "1")
    def _boom(*a, **k):
        raise RuntimeError("option chain fetch failed")
    monkeypatch.setattr(option_wheel, "sell_csp", _boom)
    # 断言：不抛异常（try/except 包裹），scan 主流程退出码仍为 0
    assert run_scan_wiring(dry=True) == 0
    # 且 sell_csp 异常被 continue-on-error 语义吸收（无副作用文件）
```

### C2. review.py 接线测试（到期指派检查，只写子账本）

```python
# tests/test_option_wheel_review_wiring.py  （草稿）
def test_expiry_triggers_check_assignment(monkeypatch):
    """到期日 → check_assignment 被调用。"""
    monkeypatch.setenv("ENABLE_OPTIONS_WHEEL", "1")
    spy = _spy(calls)
    monkeypatch.setattr(option_wheel, "check_assignment", spy)
    monkeypatch.setattr(option_wheel, "open_positions", lambda: [_itm_put_expired_today()])
    run_review_wiring()                                   # 仅走接线分支
    assert len(calls) == 1, "到期持仓应触发一次 check_assignment"

def test_assignment_only_writes_subledger(monkeypatch, tmp_repo):
    """被行权 → 只写 option_positions.csv，不碰主账本。"""
    monkeypatch.setenv("ENABLE_OPTIONS_WHEEL", "1")
    monkeypatch.setattr(option_wheel, "check_assignment",
                        lambda p: ("PUT_ASSIGNED", p))     # 模拟被指派
    before = _sha256("portfolio_50000_positions.csv")      # 主账本快照
    run_review_wiring()
    after = _sha256("portfolio_50000_positions.csv")
    assert before == after, "主账本未被触碰"
    assert _subledger_has("XYZ", "ASSIGNED"), "option_positions.csv 写入被指派记录"

def test_assignment_order_before_backfill(monkeypatch, capfd):
    """check_assignment 在 backfill_pending_reasons 之前执行。"""
    log = []
    monkeypatch.setattr(option_wheel, "check_assignment",
                        lambda p: (log.append("wheel"); ("EXPIRED", p)))
    monkeypatch.setattr(review, "backfill_pending_reasons",
                        lambda *a, **k: log.append("backfill"))
    run_review_wiring()
    assert log.index("wheel") < log.index("backfill"), "wheel 指派检查应先于 pending 回填"
```

### C3. dashboard_export.py 接线测试（build_wheel 注入）

```python
# tests/test_option_wheel_export_wiring.py  （草稿）
def test_flag_off_wheel_is_null():
    """flag 关 → portfolio["wheel"] 为 null（前端隐藏整块）。"""
    pf = build_portfolio_for_test(flag_off=True)           # 注入 ENABLE_OPTIONS_WHEEL=""
    assert pf.get("wheel") is None, "flag 关时不应注入 wheel"

def test_flag_on_wheel_injected():
    """flag 开 → 正确注入 wheel（summary + positions 齐全）。"""
    pf = build_portfolio_for_test(flag_off=False)
    w = pf["wheel"]
    assert w is not None
    assert {"summary", "positions"} <= set(w.keys())
    assert w["summary"]["open_count"] >= 0
    # 字段与 app.js renderWheel 期望对齐（见附三）
    assert "cash_collateral" in w["summary"] and "premium" in w["summary"]
```

### C4. app.js 接线测试（renderWheel 渲染 / 隐藏）

```javascript
// tests/option_wheel_frontend.test.js  （草稿，node harness，复用 macro/trade 思路）
describe("renderWheel", () => {
  test("wheel 为 null → 隐藏整块", () => {
    const pf = { wheel: null };
    renderWheel(pf);
    assert.hidden("#wheelCard");
  });

  test("有数据 → 正确渲染表格", () => {
    const pf = {
      wheel: {
        summary: { open_count: 2, cash_collateral: 5000, premium: 120, assigned_count: 0 },
        positions: [
          { ticker: "XYZ", kind: "PUT", strike: 180, expiry: "2026-12-18", status: "OPEN", cash_collateral: 5000 }
        ]
      }
    };
    renderWheel(pf);
    assert.visible("#wheelCard");
    assert.contains("#wheelCard", "XYZ");
    assert.contains("#wheelCard", "担保现金");
  });

  // 额外：renderDashboard 调用点存在（renderMacro 之后）
  test("renderDashboard 调用 renderWheel", () => {
    assert.calledAfter("renderMacro", "renderWheel");
  });
});
```

### C5. 接线测试覆盖矩阵（草稿）

| 接线点 | flag 关 | flag 开（正常） | flag 开（异常） |
|---|---|---|---|
| scan.py (`sell_csp`) | ✅ 不调用（C1-1） | ✅ 调用（C1-2） | ✅ 不崩（C1-3） |
| review.py (`check_assignment`) | — | ✅ 到期触发（C2-1） | ✅ 只写子账本（C2-2）+ 顺序（C2-3） |
| dashboard_export (`build_wheel`) | ✅ null（C3-1） | ✅ 注入（C3-2） | — |
| app.js (`renderWheel`) | ✅ 隐藏（C4-1） | ✅ 渲染（C4-2） | — |

> 每处接线独立 commit（见附三 §5 分步表），各自带对应草稿用例。
