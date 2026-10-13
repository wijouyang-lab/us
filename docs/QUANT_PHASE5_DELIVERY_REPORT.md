# Quant Research Phase 5 交付报告：Walk-Forward / OOS Validation Engine

> 交付时间：2026-10-07 · commit `396cd85` · 状态：已 push，`HEAD == origin/main` ✅
> 原则：**今天完成"验证框架"，绝不今天完成"模型有效性"**。

## 1-2. 修改 / 新增文件

**修改 0 个**（零侵入，quant_score_v2.py 未触碰）。

**新增 2 个**
| 文件 | 作用 |
|---|---|
| `quant_walk_forward.py` | Walk-Forward / OOS 验证引擎：Expanding/Rolling window、frozen normalization/weights、OOS 评估、风险指标、过拟合检测、模型比较、Production Lock |
| `tests/test_quant_walk_forward.py` | 43 项纯函数测试 |

运行时产出：`quant_walk_forward_results.csv`、`quant_walk_forward_summary.json`。

## 3. Window 设计

- **EXPANDING**（默认）：Window1 TRAIN T1→T50 / OOS T51→T70；Window2 TRAIN T1→T70 / OOS T71→T90；依此类推。
- **ROLLING**：固定 train 窗口长度（默认 100），随 OOS 步进滑动。
- 严格时间顺序，**绝不 shuffle / random split / k-fold**。

## 4. Train/OOS 定义

| 项 | 说明 |
|---|---|
| Train | 只用当时已存在数据，估计：归一化参数（winsorized z-score 的 winsor 边界 + mean/std）、group 权重（冻结用 Phase 4 定义） |
| OOS | 只用 frozen TRAIN 参数做 transform + 评价，绝不参与任何拟合/选择/阈值/聚类 |
| Freeze | fit 完成即冻结，OOS transform 用 frozen 参数 |

## 5-8. 当前真实数据量 / OOS 数量 / Model 状态 / 是否全 NOT_ENOUGH_DATA

| 项 | 值 |
|---|---|
| Snapshot N | **0** |
| Window 数量 | **0** |
| 真实 OOS 数量 | **0** |
| Model 状态 | **4 个模型全 NOT_ENOUGH_DATA**（3 候选 + 1 基准 CURRENT_EXISTING_QUANT_SCORE） |
| 是否全 NOT_ENOUGH_DATA | ✅ 是 |

## 9-14. 纪律核对

| 项 | 结果 |
|---|---|
| 历史回填 | ❌ 0 |
| 生成假生产数据 | ❌ 0（空数据时 results.csv 只有表头 0 行，summary 全 NOT_ENOUGH_DATA，无 0% 胜率/0 收益/0 回撤） |
| 修改 Quant_Score | ❌ 0 |
| 修改 Scan | ❌ 0 |
| AI Calls | ❌ 0 |
| 网络请求 | ❌ 0 |

## 核心架构（已实现、可测试）

- **Window 切分**：`split_windows()` 支持 EXPANDING / ROLLING，train/oos 严格 disjoint、时间有序
- **Frozen Normalization**：`fit_normalization()`（train）→ `transform_normalization()`（oos 用 frozen 参数）
- **Frozen Weights**：group 权重来自 Phase 4 `CANDIDATE_MODELS`，`score_model()` 不重估
- **基准模型**：`CURRENT_EXISTING_QUANT_SCORE`（直接用现有 Quant_Score，明确是 benchmark 非候选）
- **OOS 评估**：N / Win_Rate / Average / Median / Std / Cumulative_Return / Max_Drawdown / Profit_Factor
- **过拟合检测**：Train/OOS Gap > 阈值 → POSSIBLE_OVERFIT（不因一次失败否定模型）
- **稳定性**：Early/Middle/Recent + NORMAL/STRESSED/PANIC 分层
- **模型比较**：3 候选 vs 基准，比较 OOS Win Rate / Average / Median / Max DD / Cumulative
- **门槛集中配置**：`CONFIG` 常量（MIN_TRAIN/OOS、MIN_OOS_WINDOWS、overfit_gap_threshold 等），不散落代码
- **Production Lock**：`QUANT_SCORE_V2_ENABLED` 恒 false，PASS 也不 enable，必须 PASS + HUMAN APPROVAL
- **状态机**：PASS / FAIL / INCONCLUSIVE / NOT_ENOUGH_DATA（PASS ≠ PRODUCTION APPROVED）

## 15-18. 测试 / 检查

| 项 | 结果 |
|---|---|
| 新增 Walk-Forward 测试 | **43 / 43 PASS** |
| **全量项目测试** | **529 / 529 PASS** |
| py_compile（3.12） | ✅ PASS |
| git diff --check | ✅ PASS |
| 确定性复跑 | ✅ 测试覆盖（两次运行 window_count / model_statuses 一致） |

## 19-20. Git 状态

| 项 | 值 |
|---|---|
| commit SHA | `396cd851de71159724dfeb9f7ae7fa2195e2f0a8` |
| push | ✅ 成功（无 force） |
| HEAD == origin/main | ✅ **TRUE** |

## 未解决问题

**无 P0/P1。** 待真实数据积累后，Walk-Forward 引擎将自动产生窗口与 OOS 评估，从 NOT_ENOUGH_DATA 演进。但即使未来某模型 PASS，仍必须人工批准才能进入生产（Production Lock 恒 false）。

## 测试覆盖对照（任务第二十三节 23 项）

✅ Empty dataset、✅ Insufficient train/OOS data、✅ Expanding window、✅ Rolling window、✅ Train/OOS disjoint、✅ Time ordering、✅ No future leakage、✅ Frozen normalization、✅ Frozen weights、✅ Forward Return、✅ OOS Win Rate、✅ OOS Average Return、✅ Max Drawdown、✅ Train/OOS gap、✅ Overfit detection、✅ Regime split、✅ Model comparison、✅ Deterministic repeat、✅ Production lock、✅ No AI、✅ No network、✅ No fake production data。

**Phase 5 目标达成**：Walk-Forward / OOS 验证框架已完成，严格无数据泄漏、无伪数据、无 AI、无网络、无历史回填。真实数据到来后自动产生验证结论，但任何 PASS 都需要人工批准才能进生产。
