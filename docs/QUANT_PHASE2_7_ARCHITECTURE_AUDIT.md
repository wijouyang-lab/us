# Quant Research Phase 2–7 架构只读审计报告

> **审计性质**：READ-ONLY AUDIT
> **修改文件 = 0 · commit = 0 · push = 0**
> **审计基准**：`HEAD = a220233995651a7698ce98e1a9643e71b3a474b3`；`origin/main = 4bc5a55`（本地 behind 4，均为 dashboard-data 定时刷新，**未同步以保持工作区只读**）
> **审计时间**：2026-10-07 10:47 UTC / 18:47 +0800
> **回归验证**：全量 pytest **163 passed**

---

## 1. Executive Summary

### 核心结论

**Phase 2–7 的框架在过去数轮迭代中已经全部建成，本次审计确认其设计完整、状态机齐备、无假数据风险。**

真正的缺口**不在"框架缺失"，而在"验证完备性"与"生产接线"**：

| 类别 | 结论 |
|---|---|
| 7 个 Phase 的 Python 模块 | ✅ **全部已存在**（8 个 quant 模块，共 3,318 行） |
| 状态机 / 枚举 | ✅ **全部已实现**（用户要求的 7 种 validation status 一字不差） |
| enable/disable gate | ✅ **全部已实现**（V2 恒 DISABLED、Shadow 恒 DISABLED、kill switch、rollback） |
| 空数据 → NOT_ENOUGH_DATA | ✅ **全部已实现**（无数据返回 `None` 而非 `0`） |
| 防 look-ahead | ✅ **Phase 2 用 `side="right"`；Phase 5 用 train-only frozen normalization** |
| 测试 | ⚠️ **129 个测试函数已存在，但 10 类要求中有 4 类覆盖不足** |
| **schema / version 字段** | ❌ **缺失**（用户第五部分明确要求） |
| **跨阶段集成测试** | ❌ **缺失** |
| **Phase 2–7 生产 runner** | ❌ **缺失**（workflow 仅接了 Phase 1 与 2B） |

### 三个必须提前澄清的时间事实

| 阶段 | 真实激活所需 | 预计最早 |
|---|---|---|
| Phase 2 / 3 | 首个 snapshot 后 **T+20 交易日**才有 20D 前瞻收益 | ~4 周（20D）／~1 周（5D） |
| Phase 4 | 依赖 Phase 3 出现 PROMISING 证据 | 晚于 Phase 3 |
| **Phase 5 Walk-Forward** | **需 ≥70 个不同 snapshot 日期**（`initial_train=50` + `oos_step=20`） | **约 14 周 ≈ 3.3 个月** |

> **这是本次审计最重要的一条**：Phase 5/6/7 在可预见的数月内将合法地保持 `NOT_ENOUGH_DATA`。框架先建成的价值正在于此——**不必等数据，但不能假装有数据**。

---

## 2. Git 状态确认

| 项 | 值 |
|---|---|
| 本地 HEAD | `a220233995651a7698ce98e1a9643e71b3a474b3` |
| origin/main | `4bc5a556fbfa4dc449bb045706580f86cf10423b` |
| ahead / behind | **ahead = 0，behind = 4** |
| 已跟踪文件修改 | **0** |
| 未跟踪 | 仅 `__pycache__/` 运行期缓存 |

`behind 4` 的来源：远端在此期间自然产生 4 条 `chore(dashboard): refresh market data [skip ci]`。**未执行同步**，以保持本地工作区只读；本审计全部通过 `git cat-file` 读取远端，不影响结论。

### Quant 相关提交历史（完整链路）

```
01db04f  feat(quant): add factor library and daily snapshot              ← Phase 1
fdfc3dd  feat(quant): add factor backtest framework                      ← Phase 2
9398983  feat(quant): add persistent price history layer …                ← Phase 2B
1f30bb5  feat(quant): add factor validation engine                        ← Phase 3
f40e32e  feat(quant): add Quant Score 2.0 candidate framework            ← Phase 4
396cd85  feat(quant): add walk-forward out-of-sample validation framework ← Phase 5
8f7dcf3  feat(quant): add Quant Score V2 shadow mode framework           ← Phase 6
24b2e9b  feat(quant): add production integration and governance framework← Phase 7
1faffff  refactor(quant): unify forward return to single source in quant_factor_backtest
a220233  feat: add quant research dashboard                              ← Dashboard 7 阶段
```

---

## 3. 7-Phase 架构地图

```
┌──────────────────────────────────────────────────────────────────────┐
│  Scan 生产（V1，不可改动）                                             │
│  get_kline_data() 6mo OHLCV  +  _download_close_series("SPY","6mo")   │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ 内存中直接计算，个股 0 增量请求
                            ▼
┌──── Phase 1 · Factor Library + Daily Snapshot ───────────────────────┐
│ quant_factor_lab.py        输出 quant_factor_snapshot.csv (32 列)      │
│ 键 Scan_Date|Ticker · 幂等 upsert · 原子写                             │
│ ★ 已接入 scan.py:887/3729 · scan.yml:49                               │
│ 状态：WAITING_FOR_REAL_SNAPSHOT                                       │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ snapshot（只含 <=T 数据，无前瞻列）
                            ▼
──── Phase 2B · Persistent Price History（数据基础设施）───────────────┐
│ quant_factor_price.py     输出 quant_factor_price_history.csv         │
│ 键 Date|Ticker · 只增不改 · auto_adjust=False（与 Phase 1 同口径）      │
│ ★ 已接入 scan.yml:54                                                  │
│ ⚠ 与 Phase 2 的区别：2B = 存价格；2 = 用价格算回测。绝不混淆。         │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ price_map
                            ▼
┌──── Phase 2 · Factor Backtest ───────────────────────────────────────┐
│ quant_factor_backtest.py  输出 _backtest.csv + _summary.csv            │
│ forward_return_nd(side="right") · 24 因子 × 3 horizon · 五分位         │
│ 无数据 → status=NOT_ENOUGH_DATA + 写空表（不写假行）                   │
│ 状态：NOT_ENOUGH_DATA（待 T+20）                                       │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ backtest（含 Forward_Return_5/10/20D）
                            ▼
┌──── Phase 3 · Factor Validation ─────────────────────────────────────┐
│ quant_factor_validation.py  输出 _validation.csv + _correlation.csv    │
│                                     + _report.json                    │
│ 7 种状态：NOT_ENOUGH_DATA/EXPLORATORY/WEAK_EVIDENCE/PROMISING/         │
│           INCONCLUSIVE/REGIME_DEPENDENT/POTENTIALLY_REDUNDANT          │
│ 状态：NOT_ENOUGH_DATA                                                 │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ validation（Evidence_Status）
                            ▼
┌──── Phase 4 · Quant Score V2 ────────────────────────────────────────┐
│ quant_score_v2.py  输出 registry/clusters/candidates/config/report     │
│ Model A Conservative · Model B Balanced · Model C Momentum            │
│ QUANT_SCORE_V2_ENABLED = False（恒）· Weight = None（不伪造权重）      │
│ ★ V2 绝不进入 Scan；Final = 0.7 Quant + 0.3 AI 不变                    │
│ 状态：DISABLED                                                        │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ candidate model spec
                            ▼
┌──── Phase 5 · Walk-Forward / OOS ────────────────────────────────────┐
│ quant_walk_forward.py  输出 _results.csv + _summary.json               │
│ Train →(frozen normalization)→ OOS → Rolling Forward → Aggregate      │
│ 输出严格区分 Train_* / OOS_*；PASS ≠ PRODUCTION APPROVED               │
│ 状态：NOT_ENOUGH_DATA（需 ≥70 个 snapshot 日期）                       │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ OOS evidence
                            ▼
┌──── Phase 6 · Shadow Mode ───────────────────────────────────────────┐
│ quant_shadow.py  输出 _snapshot.csv + _performance.csv + _report.json  │
│ SHADOW_ENABLE = False（恒）· 只计算不交易 · 记录 V1/V2 分歧            │
│ 状态：SHADOW_DISABLED                                                 │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ shadow evidence
                            ▼
┌──── Phase 7 · Production Governance ─────────────────────────────────┐
│ quant_production.py  输出 approval/config/state.json + audit.jsonl     │
│ 4 层 Gate：research / walk_forward / shadow / human_approval           │
│ + kill switch + config hash + rollback(V2→V1 only)                     │
│ 状态：V1_ACTIVE / V2_DISABLED / NOT_READY                              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. 每个 Phase 的「框架」与「真实数据激活条件」

### Phase 1 · Factor Library + Daily Snapshot

| 项 | 内容 |
|---|---|
| 模块 | `quant_factor_lab.py`（309 行） |
| 框架 | ✅ **已存在并已接入 Scan**（`scan.py:887` 计算、`scan.py:3729` 落盘） |
| 生产 runner | ✅ `scan.yml:49` |
| 输入 | Scan 内存中的 6mo OHLCV（`Close`/`Volume`）+ SPY 6mo Series |
| 输出 | `quant_factor_snapshot.csv`（32 列，键 `Scan_Date\|Ticker`） |
| 网络请求 | 模块内 **0**（仅 os/numpy/pandas） |
| 真实数据 | ⏳ 等待第一次真实 production snapshot |
| **当前状态** | **`WAITING_FOR_REAL_SNAPSHOT`** |

---

### Phase 2 · Factor Backtest

| 项 | 内容 |
|---|---|
| 模块 | `quant_factor_backtest.py`（430 行） |
| 框架 | ✅ 已存在 |
| 生产 runner | ❌ **无** |
| 输入 | `quant_factor_snapshot.csv` + price_map（`quant_factor_price_history.csv`） |
| 输出 | `quant_factor_backtest.csv`、`quant_factor_summary.csv` |
| 覆盖 | 24 因子 × 3 horizon；forward return / 五分位 / summary / 样本量 / Pearson+Spearman / regime 分层 |
| **Look-ahead 防护** | ✅ `forward_return_nd` 用 `searchsorted(ts, side="right")`，**严格从 T+1 起**（`quant_factor_backtest.py:100-101`）；未到期返回 `None`，**绝不填 0/插值** |
| 样本分级 | `sample_size_label`：<30 Exploratory Only / <50 Weak Evidence / <100 Observable Trend / ≥100 Formal Comparison OK |
| 成熟度 | `maturity_status()` 按 horizon 统计**已成熟样本数**，未成熟不计入统计 |
| 数据不足 | `status = NOT_ENOUGH_DATA` + `_write_empty()` 写**空文件**（不是假行） |
| **激活条件** | ① snapshot 存在且非空 ② price_map 非空 ③ 目标 horizon 已有 ≥1 个成熟样本 |
| **当前状态** | `NOT_ENOUGH_DATA` |

---

### Phase 2B · Persistent Price History（数据基础设施，≠ Phase 2）

| 项 | 内容 |
|---|---|
| 模块 | `quant_factor_price.py`（278 行） |
| 框架 | ✅ 已存在 |
| 生产 runner | ✅ `scan.yml:54` |
| 定位 | **为 Phase 2 提供 T+5/10/20 前瞻收益所需的真实历史收盘价** |
| 与 Phase 2 的界限 | **2B 只存价格（Date, Ticker, Close）；2 用价格算回测。二者绝不混淆** |
| 输入 | snapshot 历史 ticker + 单次批量 `yf.download` |
| 输出 | `quant_factor_price_history.csv`，键 `Date\|Ticker` |
| 幂等 | ✅ 只增不改（`upsert_price_history` 保留历史值），原子写 |
| 口径 | `auto_adjust=False`，与 Phase 1 因子同源 |
| 回填禁令 | docstring 明确"绝不反向生成/回填历史 Factor Snapshot" |

---

### Phase 3 · Factor Validation

| 项 | 内容 |
|---|---|
| 模块 | `quant_factor_validation.py`（471 行） |
| 框架 | ✅ 已存在 |
| 生产 runner | ❌ **无** |
| 输入 | `quant_factor_backtest.csv` |
| 输出 | `quant_factor_validation.csv`（24×3=72 行）、`quant_factor_correlation.csv`、`quant_factor_validation_report.json` |
| **7 种状态** ✅ 全部实现 | `NOT_ENOUGH_DATA` / `EXPLORATORY` / `WEAK_EVIDENCE` / `PROMISING` / `INCONCLUSIVE` / `REGIME_DEPENDENT` / `POTENTIALLY_REDUNDANT` |
| 判定阈值 | N=0→NOT_ENOUGH_DATA；N<30→EXPLORATORY；N<50→WEAK_EVIDENCE；regime 主导→REGIME_DEPENDENT；Q1–Q5 单调→PROMISING；否则 INCONCLUSIVE（`_compose_status:288-304`） |
| 保留维度 | 样本量 N / Win_Rate / Avg / Median / Std / Pearson / Spearman / 五分位 / 单调性 / Regime 分层 / 稳定性 / 冗余相关 |
| **无数据行为** | 所有指标为 **`None`，不是 0**（`validate_factor_horizon:130-149`）✅ |
| 冗余 | Pearson 或 Spearman ≥0.9 → `POTENTIALLY_REDUNDANT` |
| 决策纪律 | report 含 `no_decision_rule`："Phase 3 research evidence only; no factor is auto-approved" |
| **当前状态** | `NOT_ENOUGH_DATA` |

---

### Phase 4 · Quant Score V2

| 项 | 内容 |
|---|---|
| 模块 | `quant_score_v2.py`（403 行） |
| 框架 | ✅ 已存在 |
| 生产 runner | ❌ **无** |
| 输入 | Phase 3 的 validation + correlation |
| 输出 | `quant_factor_registry.csv` / `quant_factor_clusters.csv` / `quant_score_v2_candidates.csv` / `config.json` / `report.json` |
| 三个模型 | **Model A — Conservative** / **Model B — Balanced** / **Model C — Momentum**（`CANDIDATE_MODELS:109-124`，group_weights 冻结，待 Phase 5 后人工批准） |
| **V2 开关** | `QUANT_SCORE_V2_ENABLED = False`（`:55`，恒 False，注释："默认且永远关闭"） |
| 权重 | `Weight = None` —— **绝不伪造权重**（`build_candidate_models:247`） |
| 状态机 | `RESEARCH → CANDIDATE → APPROVED → PRODUCTION`；本阶段只能停留在 RESEARCH/CANDIDATE |
| Evidence Gate | PROMISING→ELIGIBLE；REGIME_DEPENDENT→ELIGIBLE_REGIME_ONLY；其余→BLOCKED |
| 模型状态 | 无 PROMISING/REGIME_DEPENDENT → 全部 `NOT_ENOUGH_DATA` |
| **生产安全** | ✅ **V2 绝不进入 Scan；当前 Final = 0.7 Quant + 0.3 AI 与 V1 Quant_Score 完全未被触碰** |
| **当前状态** | `DISABLED` |

---

### Phase 5 · Walk-Forward / Out-of-Sample

| 项 | 内容 |
|---|---|
| 模块 | `quant_walk_forward.py`（540 行） |
| 框架 | ✅ 已存在 |
| 生产 runner | ❌ **无** |
| 输入 | `quant_factor_backtest.csv` |
| 输出 | `quant_walk_forward_results.csv`、`quant_walk_forward_summary.json` |
| 窗口链 | `split_windows()` → Train → Validation/OOS → Rolling Forward → 聚合（`split_windows:93`） |
| **防泄漏** | ✅ `fit_normalization(train_df)` **只用 train 拟合**，再 `transform_normalization(oos_df, params)`（`:354-358`）—— frozen params，杜绝用全样本拟合 |
| **输出区分** | results schema 显式分列 `Train_N`/`OOS_N`、`Train_Win_Rate`/`OOS_Win_Rate`、`Train_Average_Return`/`OOS_Average_Return` 等 |
| 防过拟合 | `overfit_status()`：Train/OOS 收益差 >5 个百分点 → `POSSIBLE_OVERFIT` → 判 `INCONCLUSIVE` |
| 稳定性 | OOS 段按时间序拆 Early/Middle/Recent（`stability_status`）+ Regime 分层（`regime_status`） |
| 结论纪律 | `PASS` 仅表示满足预定义 OOS 条件，**≠ PRODUCTION APPROVED**（`_model_verdict:477` 与 summary 的 `no_decision_rule`） |
| 生产锁 | summary 含 `production_lock.QUANT_SCORE_V2_ENABLED=false` |
| 数据不足 | 全部模型 `NOT_ENOUGH_DATA`，写空 results |
| **激活条件** | ⚠️ **需 ≥70 个不同 snapshot 日期**（`initial_train_size=50` + `oos_step=20`；`min_train_observations=50`、`min_oos_observations=20`） |
| **当前状态** | `NOT_ENOUGH_DATA`（预计约 14 周内保持） |

> **存活偏差说明**：候选池为每日 Top300 成交量，历史成分会滚动变化。现有设计**未显式处理存活偏差**，属已知边界，需在 Phase 5 结论解读时声明（见风险 R6）。

---

### Phase 6 · Shadow Mode

| 项 | 内容 |
|---|---|
| 模块 | `quant_shadow.py`（409 行） |
| 框架 | ✅ 已存在 |
| 生产 runner | ❌ **无** |
| 输入 | `quant_factor_snapshot.csv` + price_map |
| 输出 | `quant_shadow_snapshot.csv`、`quant_shadow_performance.csv`、`quant_shadow_report.json` |
| **影子快照字段**（16 列）✅ 覆盖用户要求 | `Scan_Date`, `Ticker`, `Name`, `Sector`, `Existing_Quant_Score`, `Existing_Final_Score`, `Existing_Tag`, `Shadow_Model`, `Shadow_Score`, `Shadow_Rank`, `Existing_Selected`, `Shadow_Selected`, `Difference_Type`, `Market_Regime`, `VIX`, `Price` |
| 只算不交易 | ✅ V2 shadow 仅计算，不参与任何生产决策 |
| **开关** | `SHADOW_ENABLE = False` + `SHADOW_START_DATE = None`（`:62-63`） |
| 未启用行为 | `shadow_status = SHADOW_DISABLED`，写**空表 + 禁用态 report**，不产生任何 shadow 结果 |
| 防回填 | 启用后只处理 `Scan_Date >= SHADOW_START_DATE` 的快照（`:360-362`） |
| 分歧记录 | `classify_difference()` 对比 V1 实选 vs V2 假设选 |
| **当前状态** | `SHADOW_DISABLED`，**不得自动启用** |

---

### Phase 7 · Production Governance

| 项 | 内容 |
|---|---|
| 模块 | `quant_production.py`（478 行） |
| 框架 | ✅ 已存在 |
| 生产 runner | ❌ **无** |
| 输入 | Phase 3 + Phase 5 + Phase 6 证据 + 人工审批文件 |
| 输出 | `quant_production_approval.json` / `config.json` / `state.json` / `audit.jsonl` |
| **4 层 Gate** | ① `research_evidence_gate` ② `walk_forward_gate` ③ `shadow_gate` ④ `human_approval_gate` |
| 生产门 | 全 PASS → `READY_FOR_PRODUCTION`，否则 `NOT_READY`（`evaluate_production_gates:306-307`） |
| **安全监视** | `safety_monitor()`：kill switch → ROLLBACK_REQUIRED；未知模型 → BLOCK；**V1 → 永远 PASS**；V2 需逐项校验 config hash + 审批 + gate |
| Kill switch | `QUANT_SCORE_V2_KILL_SWITCH = False`（可人工置 True → 强制回退 V1） |
| **Rollback** | `rollback_to_v1()`：**只允许 V2→V1，禁止 V1→V2**；`ROLLBACK_AVAILABLE = True` |
| 状态机 | `STATES = [RESEARCH, CANDIDATE, OOS_VALIDATED, SHADOW, READY_FOR_PRODUCTION, HUMAN_APPROVED, PRODUCTION_ACTIVE, ROLLED_BACK]` |
| 回退触发 | `CONFIG_MISMATCH` / `INVALID_OUTPUT` / `MISSING_REQUIRED_DATA` / `RUNTIME_ERROR` / `PRODUCTION_GATE_FAIL` / `KILL_SWITCH` |
| 输出状态 | `V1_ACTIVE` / `V2_DISABLED` / `NOT_READY` |
| **当前状态** | **`V1_ACTIVE` / `V2_DISABLED` / `NOT_READY`** |

---

## 5. 生产安全确认（当前状态未因审计改变）

| 项 | 值 | 依据 |
|---|---|---|
| 当前生产模型 | `CURRENT_EXISTING_QUANT_SCORE`（**V1**） | `quant_production.py:54-55` |
| Quant V2 | **DISABLED** | `quant_score_v2.py:55`、`quant_production.py:51` |
| Shadow | **DISABLED** | `quant_shadow.py:62` |
| Production Gate | **NOT_READY** | 4 层 gate 均有 NOT_ENOUGH_DATA |
| Kill switch | False（可人工开启） | `quant_production.py:52` |
| Rollback | 可用（V2→V1 only） | `quant_production.py:56, 345` |
| V1 Final Score 公式 | **未被任何 Quant 模块触碰** | 仅 `scan.py` 内，本审计未改动 |
| Email | 未恢复（无相关代码路径） | — |

---

## 6. Dashboard 支持情况

| 组件 | 覆盖 | 位置 |
|---|---|---|
| 数据层 `build_quant()` | ✅ **7 个 Phase 全覆盖** | `dashboard_export.py:2628 / 2639 / 2652 / 2663 / 2674 / 2684 / 2693` |
| HTML section | ✅ `#quantSec` + `#quantSummary` + `#quantPhases` | `index.html:78/83/84` |
| 渲染 `renderQuant()` | ✅ + `qPhaseCard()` `case 1..7` | `app.js:580 / 538-576` |
| 样式 | ✅ 中性语义化徽章（灰/黄/蓝绿/蓝） | `app.css` |

### 当前真实展示状态

| Phase | Dashboard 显示 | 是否伪造 |
|---|---|---|
| 1 Factor Library | `NOT_ENOUGH_DATA` + 8 因子名称 | 否 |
| 2 Backtest | `NOT_ENOUGH_DATA` + 5D/10D/20D | 否 |
| 3 Validation | `NOT_ENOUGH_DATA` + 24×3=72 | 否 |
| 4 Quant Score V2 | `DISABLED` + A/B/C | 否 |
| 5 Walk-Forward | `NOT_ENOUGH_DATA` + 3 候选 + 1 基准 | 否 |
| 6 Shadow | `SHADOW_DISABLED` | 否 |
| 7 Production | `V1_ACTIVE` / V2 `DISABLED` / Gate `NOT_READY` | 否 |

**无任何 0% / 0 wins / 0 Sharpe / 0 IC 出现**（`test_quant_dashboard.py` 已断言禁止）。

> ⚠️ 一处需细化：Phase 1 当前报 `NOT_ENOUGH_DATA`，按本阶段目标应改为 **`WAITING_FOR_REAL_SNAPSHOT`**，以区分"数据缺失"与"尚待首次生成"。列为 G8。

---

## 7. 数据契约（含 schema / version 缺口）

| Phase | Input | Output | 键 | 幂等 | **schema_version** |
|---|---|---|---|---|---|
| 1 | Scan OHLCV + SPY | `quant_factor_snapshot.csv` | `Scan_Date\|Ticker` | ✅ | ❌ 无 |
| 2B | snapshot tickers + yf batch | `quant_factor_price_history.csv` | `Date\|Ticker` | ✅ | ❌ 无 |
| 2 | snapshot + price_map | `quant_factor_backtest.csv`<br>`quant_factor_summary.csv` | 逐行 append（全量重写） | — | ❌ 无 |
| 3 | `quant_factor_backtest.csv` | `quant_factor_validation.csv`<br>`quant_factor_correlation.csv`<br>`quant_factor_validation_report.json` | `Factor\|Horizon` | 全量重写 | ❌ 无 |
| 4 | validation + correlation | `quant_factor_registry.csv`<br>`quant_factor_clusters.csv`<br>`quant_score_v2_candidates.csv`<br>`quant_score_v2_config.json`<br>`quant_score_v2_report.json` | `Factor` / `Model\|Factor` | 全量重写 | ❌ 无 |
| 5 | `quant_factor_backtest.csv` | `quant_walk_forward_results.csv`<br>`quant_walk_forward_summary.json` | `Model\|Window_ID\|Horizon` | 全量重写 | ❌ 无 |
| 6 | snapshot + price_map | `quant_shadow_snapshot.csv`<br>`quant_shadow_performance.csv`<br>`quant_shadow_report.json` | `Scan_Date\|Ticker` | 全量重写 | ❌ 无 |
| 7 | Phase 3+5+6 + 审批 | `quant_production_state.json`<br>`config.json` / `approval.json` / `audit.jsonl` | 单文件 | append-only audit | ⚠️ 仅 `PRODUCTION_VERSION="V1"` |

> **G1（用户第五部分明确要求）：所有 Phase 输出均缺 `schema_version` 字段。** 建议为每个输出文件增加 `schema_version` 常量（如 `"1.0"`）并写入 JSON/CSV 头，防止未来字段变化导致静默错误。

---

## 8. 测试现状与缺口

### 现状

| 测试文件 | 测试函数数 |
|---|---|
| `test_quant_dashboard.py` | 11 |
| `test_quant_factor_lab.py` | 12 |
| `test_quant_factor_price.py` | 12 |
| `test_quant_factor_backtest.py` | 12 |
| `test_quant_factor_validation.py` | 12 |
| `test_quant_score_v2.py` | 14 |
| `test_quant_walk_forward.py` | 16 |
| `test_quant_shadow.py` | 18 |
| `test_quant_production.py` | 22 |
| **合计** | **129** |

**全量 pytest：163 passed**（含非 quant 测试），审计期间 **0 regression**。

### 10 类要求覆盖矩阵

| # | 要求 | 覆盖 | 缺口 |
|---|---|---|---|
| 1 | insufficient data | ✅ 51 处命中 | — |
| 2 | empty input | ✅ 36 处 | — |
| 3 | missing columns | ⚠️ 11 处 | 部分 Phase 缺 |
| 4 | duplicate records | ⚠️ 仅 Phase 1/2B/2 有 | **缺 3/4/5/6/7** |
| 5 | invalid numeric / inf | ❌ **inf 0 命中** | **全部缺 inf 测试** |
| 6 | date ordering | ⚠️ 3 处 | 偏弱 |
| 7 | look-ahead protection | ✅ 已有 `test_no_lookahead` | 建议扩充到全链路 |
| 8 | deterministic output | ✅ 19 处 | — |
| 9 | **idempotency** | ⚠️ 仅 Phase 1/2B 有（`upsert` 命中） | **缺 2/3/4/5/6/7** |
| 10 | schema compatibility | ❌ 无 version 概念 | **全部缺** |

### 跨阶段集成测试

| 项 | 结论 |
|---|---|
| 现有 | 每个测试文件仅 import 1–3 个 quant 模块（多为自身模块） |
| **缺口 G4** | ❌ **无 Phase 1→2→3→4→5→6→7 全链路集成测试** |
| 测试/生产数据隔离 | ✅ 各测试用 `tempfile` 构造 fixture，**未写入任何 production CSV**（已核查） |

---

## 9. 缺失项与风险

### 缺失清单

| # | 缺失 | 影响 | 优先级 |
|---|---|---|---|
| **G1** | 所有输出缺 `schema_version` | 字段变化会静默错误 | **P1** |
| **G2** | `quant_factor_backtest.py` **无 `main()`** | 无法独立运行 / 无法被 workflow 调用 | **P1** |
| **G3** | Phase 2–7 **无生产 workflow** | 数据链在 Phase 2 处断 | **P1** |
| **G4** | 无跨阶段集成测试 | 契约漂移无拦截 | **P2** |
| **G5** | duplicate 测试缺 Phase 3/4/5/6/7 | 重复记录风险 | P2 |
| **G6** | idempotency 测试缺 Phase 2/3/4/5/6/7 | 重跑不确定性 | P2 |
| **G7** | inf / 非法数值测试全缺 | 极端值未覆盖 | P2 |
| **G8** | Dashboard Phase 1 状态应为 `WAITING_FOR_REAL_SNAPSHOT` | 语义不够精确 | P3 |
| **G9** | date-ordering 测试偏弱 | 时序假设未充分验证 | P3 |
| **G10** | Phase 2 `load_price_history` 默认 `auto_adjust=True`，与 2B 的 `False` 冲突 | 休眠路径，误用会口径不一致 | P3 |

### 风险清单

| # | 风险 | 等级 | 说明 | 缓解 |
|---|---|---|---|---|
| **R1** | **Phase 2/3 在无数据时仍会写出空文件**（`_write_empty`、`_write_empty_outputs`） | **P2** | 若在真实数据就绪前于生产运行，会**创建空的 production CSV**，造成"文件存在但无数据"的误导 | workflow 必须等 snapshot 存在后再启用；或改为"无数据则不写文件" |
| **R2** | Phase 3 空输出会写 72 行全 NOT_ENOUGH_DATA | P2 | 合法的"状态表"，但需明确它不是"结果" | 同上 |
| **R3** | 无 schema version | P1 | 字段变更静默传播 | G1 |
| **R4** | 无跨阶段集成测试 | P2 | 契约漂移 | G4 |
| **R5** | Phase 2B 下载区间随 snapshot 历史增长，首跑为一次大批量 | P3 | 文件体积与首跑耗时 | 可接受，需监控 |
| **R6** | **存活偏差未处理**：候选池为滚动 Top300 | P2 | Phase 5 结论解读需声明该边界 | 在 summary/report 中显式标注 |
| **R7** | Phase 5 需 ≥70 个 snapshot 日期（≈14 周） | P2 | 用户需有正确预期；期间合法保持 NOT_ENOUGH_DATA | 文档化时间线 |
| **R8** | Phase 1 `write_factor_snapshot` 的 try/except 只 print | P1（既有） | Scan 全绿但快照可能缺失 | 已在 Phase 1 验证脚本中专项覆盖 |
| **R9** | 两个 P3（SPY auto_adjust、Stock_RS 日期对齐）**本阶段保持不动** | P3 | 按用户指令，先观察首份真实 snapshot | 首份数据后单独评估 |

---

## 10. 实施计划（供审阅，本次不执行）

> 原则：**FRAMEWORK FIRST · REAL DATA SECOND · REAL EVIDENCE BEFORE ACTIVATION · V1 UNCHANGED**

由于框架已存在，实施计划性质为 **「补齐完备性 + 接线」，而非「从零开发」**。

| 步骤 | 内容 | 涉及文件 | Commit 建议 |
|---|---|---|---|
| **STEP 3-A** | **Schema versioning**：为 8 个 Phase 输出增加 `schema_version` 常量并写入 | `quant_factor_*.py`、`quant_score_v2.py`、`quant_walk_forward.py`、`quant_shadow.py`、`quant_production.py` | `feat(quant): add schema version to quant artifacts` |
| **STEP 3-B** | **Phase 2 闭环**：补 `main()` 入口 + 补 duplicate/inf/idempotency 测试 | `quant_factor_backtest.py`、`tests/test_quant_factor_backtest.py` | `feat(quant): add phase 2 backtest framework` |
| **STEP 4** | **Phase 3 补测**：duplicate / invalid numeric / date ordering / schema | `tests/test_quant_factor_validation.py` | `feat(quant): add phase 3 validation framework` |
| **STEP 5** | **Phase 4 补测** + Dashboard V2 DISABLED 语义强化 | `tests/test_quant_score_v2.py` | `feat(quant): add phase 4 quant score v2 framework` |
| **STEP 6** | **Phase 5 补测** + 存活偏差声明 | `tests/test_quant_walk_forward.py` | `feat(quant): add phase 5 walk-forward framework` |
| **STEP 7** | **Phase 6 补测** | `tests/test_quant_shadow.py` | `feat(quant): add phase 6 shadow framework` |
| **STEP 8** | **Phase 7 补测** + 8 项 activation criteria 显式化 | `tests/test_quant_production.py` | `feat(quant): add phase 7 production governance framework` |
| **STEP 9** | **跨阶段集成测试**（TEST FIXTURE 隔离，绝不写 production CSV） | 新增 `tests/test_quant_pipeline_integration.py` | `test(quant): add cross-phase pipeline integration tests` |
| **STEP 10** | **Dashboard 语义细化**：Phase 1 → `WAITING_FOR_REAL_SNAPSHOT` | `dashboard_export.py` | `feat(quant): refine quant dashboard phase states` |
| **STEP 11** | **生产接线（最后做，且需你确认）**：Phase 2–7 workflow | `.github/workflows/` | 待数据就绪后再议 |

### 每次 commit 前的固定检查

```
pytest -q                          # 全量通过
python -m py_compile <改动文件>     # 编译通过
dashboard export smoke test         # 生成正常
git diff --check                    # 无空白/冲突
git status                          # production 文件未被无关修改
```

### 明确不做

- ❌ 不修改 `scan.py` 的 V1 决策/选股逻辑
- ❌ 不改 Final Score 公式
- ❌ 不改 Review / Portfolio / Options
- ❌ 不恢复 Email
- ❌ 不改 workflow schedule
- ❌ 不修两个 P3（SPY auto_adjust、Stock_RS 日期对齐）
- ❌ 不做 legacy cleanup、不删现有功能
- ❌ 不 force push / reset --hard / amend
- ❌ 不手工创建 snapshot、不 backfill

---

## 11. 结论

> **现有架构与本次目标一致，无需推倒重建。**

具体对应：

| 你的目标 | 现状 |
|---|---|
| Phase 2–7 Python module | ✅ 8 个模块 3,318 行已存在 |
| 数据输入/输出契约 | ✅ 已定义（缺 schema_version → G1） |
| 状态机 | ✅ Phase 3 七态、Phase 5 四态、Phase 7 八态齐备 |
| 数据结构 | ✅ 各输出 CSV/JSON 列已固定 |
| 测试 | ⚠️ 129 个已存在，4 类覆盖不足（G4–G7） |
| Dashboard 状态 | ✅ 7 阶段已展示（Phase 1 语义待细化 → G8） |
| 阶段间接口 | ✅ 文件路径衔接清晰 |
| enable/disable gate | ✅ V2 / Shadow / kill switch / rollback 齐备 |

**因此 STEP 3 的正确形态不是"新建 Phase 2"，而是「补齐 Phase 2 的完备性缺口（main 入口 + 4 类测试 + schema version），接线后再等真实数据激活」。**

建议下一步从 **STEP 3-A（schema version）+ STEP 3-B（Phase 2 闭环）** 开始，二者均为纯增量、零生产风险。

---

## 附录 A：只读合规自证

| 操作 | 次数 |
|---|---|
| 修改代码文件 | **0** |
| 创建/修改 production CSV | **0** |
| 手工生成 snapshot / backfill | **0** |
| 提前启用 V2 / Shadow | **0** |
| 修改 V1 逻辑 | **0** |
| 新增 workflow | **0** |
| commit | **0** |
| push | **0** |

使用命令均为只读：`git log/status/rev-parse/cat-file/show`、`grep`、`sed -n p`（打印）、`wc`、`date`、`ls`、`python -m pytest`、`python -m py_compile`（不产出仓库内文件）。

**唯一写操作**：生成本报告（仓库外）。

## 附录 B：回归验证

```
$ python3 -m pytest -q
163 passed, 2 warnings in 9.62s
```

2 条 warning 为既有 `test_quant_factor_validation.py::test_regime` 的 numpy/pandas 相关性告警，与本次审计无关。

---

*报告结束 · Quant Phase 2–7 架构只读审计 · 2026-10-07 10:55 UTC*
