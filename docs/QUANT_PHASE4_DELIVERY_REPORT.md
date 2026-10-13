# Quant Research Phase 4 交付报告：Quant Score 2.0 Framework

> 交付时间：2026-10-07 · commit `f40e32e` · 状态：已 push，`HEAD == origin/main` ✅
> 原则：**今天完成"架构"，绝不今天完成"策略"**。

## 1-2. 修改 / 新增文件

**修改 0 个**（零侵入）。

**新增 2 个**
| 文件 | 作用 |
|---|---|
| `quant_score_v2.py` | Quant Score 2.0 候选模型框架：Factor Registry / Group / Direction / Evidence Gate / Candidate Models / Cluster / config |
| `tests/test_quant_score_v2.py` | 49 项纯函数测试 |

运行时产出（数据来了才生成）：`quant_factor_registry.csv`、`quant_factor_clusters.csv`、`quant_score_v2_candidates.csv`、`quant_score_v2_config.json`、`quant_score_v2_report.json`。

## 3-4. 当前真实 Snapshot / Validation N

| 项 | 值 |
|---|---|
| Snapshot N | **0** |
| Validation N | **0**（全部 NOT_ENOUGH_DATA） |

## 5-6. Candidate Models 数量 / 是否 DISABLED

- **候选模型 3 个**：`MODEL_A_CONSERVATIVE` / `MODEL_B_BALANCED` / `MODEL_C_MOMENTUM`
- **当前全部 `NOT_ENOUGH_DATA`**（无真实 Validation 证据，未产出任何权重）
- `QUANT_SCORE_V2_ENABLED = false`（恒 false，测试已锁死不可自动翻转）

## 7-12. 纪律核对

| 项 | 结果 |
|---|---|
| Quant_Score 改变 | ❌ 0（本模块不 import scan.py，不产生覆盖） |
| Final_Score 改变 | ❌ 0 |
| Scan 推荐改变 | ❌ 0 |
| AI Calls | ❌ 0（无 ClawSocket/OpenAI 依赖） |
| 网络请求 | ❌ 0（无 requests/yfinance） |
| 历史回填 | ❌ 0 |

## 核心架构（已实现、可测试）

- **Factor Registry**：24 个因子，含 Group / Secondary_Group / Direction / Evidence_Status / Enabled / Source
- **Factor Group**：TREND / MOMENTUM / MEAN_REVERSION / VOLATILITY / LIQUIDITY / RELATIVE_STRENGTH / MARKET_REGIME / FUNDAMENTAL / EVENT
- **Direction**：无证据时全部 `UNKNOWN`（绝不默认"高分一定好"）
- **Evidence Gate**：
  - NOT_ENOUGH_DATA / EXPLORATORY / WEAK_EVIDENCE / INCONCLUSIVE / POTENTIALLY_REDUNDANT → **BLOCKED**
  - PROMISING → ELIGIBLE（≠ APPROVED）
  - REGIME_DEPENDENT → ELIGIBLE_REGIME_ONLY
- **候选模型**：3 个，Group 权重为架构占位，Factor Weight 无证据时全 None（不伪造 0.20）
- **Factor Cluster**：|corr|≥0.9 → POTENTIALLY_REDUNDANT（只标记，不删除、不改权重）
- **状态机**：RESEARCH → CANDIDATE → APPROVED → PRODUCTION，本阶段只能 RESEARCH/CANDIDATE
- **config**：`QUANT_SCORE_V2_ENABLED=false` + models/weights/factor_groups/normalization/eligibility_rules
- **标准化预留**：cross_sectional_percentile / winsorized_zscore（记录方法，不拟合参数，为 Phase 5 Walk-Forward 留接口）

## 空数据时的实际输出（实测）

```
registry: 24 行，Evidence 全部 NOT_ENOUGH_DATA，Enabled 全 false
candidates: 72 行，全 BLOCKED，Weight 全空
config: QUANT_SCORE_V2_ENABLED = False
model statuses: 3 个全 NOT_ENOUGH_DATA
report state: RESEARCH
```

**没有出现任何 `Weight=0.20`、`Expected Return=2.4%` 之类的伪造数字。**

## 13-16. 测试 / 检查

| 项 | 结果 |
|---|---|
| 新增 Quant Score V2 测试 | **49 / 49 PASS** |
| **全量项目测试** | **486 / 486 PASS** |
| py_compile（3.12） | ✅ PASS |
| git diff --check | ✅ PASS |
| 确定性复跑 | ✅ 测试覆盖（registry/candidates 逐字节一致） |

## 16-17. Git 状态

| 项 | 值 |
|---|---|
| commit SHA | `f40e32ea131816465b94ac52cf7fe5a3bf34d421` |
| push | ✅ 成功（无 force） |
| HEAD == origin/main | ✅ **TRUE** |

## 未解决问题

**无 P0/P1。** 待真实数据通过 Phase 3 Validation 后，候选模型才可能获得实际权重；即使获得权重也绝不进生产，必须等 Phase 5 Walk-Forward / OOS 验证 + 人工批准。

## 测试覆盖对照（任务第十七节 20 项）

✅ Empty validation、✅ NOT_ENOUGH_DATA、✅ EXPLORATORY、✅ WEAK_EVIDENCE、✅ PROMISING、✅ REGIME_DEPENDENT、✅ REDUNDANT、✅ Candidate blocking、✅ Candidate eligibility、✅ Factor registry、✅ Factor grouping、✅ Direction、✅ correlation cluster、✅ weight normalization、✅ disabled-by-default、✅ production cannot auto-enable、✅ deterministic output、✅ no future data、✅ no AI dependency、✅ old Quant_Score untouched。

**Phase 4 目标达成**：Quant Score 2.0 候选框架已完成，严格无 Production Integration、无伪数据、无 AI、无网络、无历史回填，等待真实数据 + Phase 5 Walk-Forward 验证。
