# Phase 2–7 数据驱动路径健壮性预检（只读）

> 范围：只读核查，不改代码 / workflow / schedule，不 push / rebase，不重跑 snapshot / backfill，不碰监控。
> 仓库：`/tmp/us`，HEAD = `fedf63d`。
> 目的：数据攒够了，Phase 2–7 真跑起来会不会崩？—— 只回答"健壮性"，不重做架构审计（G1–G10 已完成）。
> 方法：测绘 7 个 quant 模块 + dashboard_export.py 的读/写契约、阈值、调用链、时序假设。

---

## 0. 调用链全景（实测文件名）

```
Phase 1  scan.py → quant_factor_snapshot.csv  (34 列 + schema_version=phase1.v1)
                 quant_factor_price.py → quant_factor_price_history.csv (Date,Ticker,Close, schema_version=phase2b.v1)
Phase 2  quant_factor_backtest.py   读 snapshot + price_history → quant_factor_backtest.csv + quant_factor_summary.csv (phase2.v1)
Phase 3  quant_factor_validation.py 读 backtest → quant_factor_validation.csv + quant_factor_correlation.csv + quant_factor_validation_report.json (phase3.v1)
Phase 4  quant_score_v2.py          读 validation + correlation → quant_factor_registry.csv + quant_factor_clusters.csv + candidates + config/report (phase4.v1)  [硬编码 DISABLED]
Phase 5  quant_walk_forward.py      读 backtest → quant_walk_forward_results.csv + quant_walk_forward_summary.json (phase5.v1)
Phase 6  quant_shadow.py           读 snapshot → quant_shadow_snapshot.csv + quant_shadow_performance.csv + quant_shadow_report.json (phase6.v1)  [硬编码 SHADOW_DISABLED]
Phase 7  quant_production.py       读 validation + walk_forward + snapshot + shadow_performance → 治理决议 + state json (phase7.v1)  [V1 ACTIVE / V2 DISABLED / Gate NOT_READY]
```

**结论性事实**：各 Phase 严格按"上一 Phase 的输出文件名"读取，文件名在常量中固定且与生产者一一对应（已逐个核对，见 §5）。调用链**无断链**。

---

## 1. 输入契约完整性 → ✅ 通过（含 1 个依赖）

| Phase | 读取的输入 | 是否由上游提供 |
|---|---|---|
| 2 Backtest | `quant_factor_snapshot.csv`（34 列）+ `quant_factor_price_history.csv` | ✅ snapshot 由 Phase1 写；price_history 由 Phase2B（scan 步骤 54）写 |
| 3 Validation | `quant_factor_backtest.csv` | ✅ Phase2 写 |
| 4 Score V2 | `quant_factor_validation.csv` + `quant_factor_correlation.csv` | ✅ Phase3 写 |
| 5 Walk-Forward | `quant_factor_backtest.csv` | ✅ Phase2 写 |
| 6 Shadow | `quant_factor_snapshot.csv` | ✅ Phase1 写 |
| 7 Production | validation + walk_forward_results + snapshot + shadow_performance | ✅ 各 Phase 写 |

- **snapshot 34 列齐全**（`quant_factor_lab.SNAPSHOT_COLUMNS` 实测 34 项：Scan_Date/Technical_Date/Ticker/…/Quant_Score/技术确认数/Gate_Status/schema_version），覆盖 Phase 2/6 所需全部列。
- **依赖点**：Phase 2 同时需要 price_history；scan.yml 步骤 49（snapshot）先于步骤 54（price history），故一次完整 Scan 后两者都在。**若只跑 Phase 1 不跑 Phase 2B，backtest 会因无 price_map 而 `_no_data_skip_write`（不落文件）**——这是预期降级，非 bug。
- **无"期望列不存在"风险**：下游按列名读取，snapshot 多/少列都向后兼容（多余列忽略、缺失列得 NaN，不 KeyError）。

---

## 2. 边界条件 → ✅ R1 全覆盖，阈值明确

| 边界 | 处理方式 | 位置 |
|---|---|---|
| Snapshot=0 / 文件不存在 | `_no_data_skip_write`：**绝不写文件**，下游报 NOT_ENOUGH_DATA | backtest:381/388/393/405 |
| 价格数据缺失 | 报缺口、不落文件、不擅自抓取 | backtest:403 |
| validation 有效 quintile < 3 | NOT_ENOUGH_DATA | validation:40 |
| walk-forward `min_train_observations`=50 | 窗口样本 < 50 → 该窗口 NOT_ENOUGH_DATA | walk_forward:63,358 |
| walk-forward `min_oos_observations`=20 | OOS 样本 < 20 → 综合 NOT_ENOUGH_DATA | walk_forward:64,476 |
| shadow 运行记录 < 30 | NOT_ENOUGH_DATA（绝不输出 Win_Rate=0%） | shadow:242 |
| 0/1/N 样本 | 全部走 NOT_ENOUGH_DATA 分支，无除零/越界 | 各模块 |

- **0 样本 / 1 样本 / 刚好 N 样本**：均被阈值与空值检查拦截，返回 NOT_ENOUGH_DATA，**不会崩、不会造假**。
- **关键保护**：R1（`_no_data_skip_write`）在 Phase 2/3/4/5/6 全部落地——"文件不存在"比"文件存在但为空"更安全，下游据此显式报错而非静默通过。

---

## 3. 调用链完整性 → ✅ 无断链

- 每个 Phase 的输出 = 下一个 Phase 的合法输入（文件名 + 列语义一致，见 §0）。
- Phase 7 聚合读 validation / walk_forward / snapshot / shadow_performance，四者均为前序真实产物。
- **唯一缺口（非断链）**：scan.py 只 `import quant_factor_lab` 做快照与契约告警，**不编排 Phase 2–7**（确认 scan.py 无 run_walk_forward/run_validation/production 调用）。即：Phase 2–7 目前**没有生产 runner**，需外部手动/定时串联。这是"G-appliance"类设计缺口，不是调用断链——手动跑链路本身能通。

---

## 4. 时序与日历假设 → ⚠️ 2 处语义风险（不崩，但结果会偏）

| 假设 | 现实 | 影响 | 严重度 |
|---|---|---|---|
| walk-forward `split_windows` 按**唯一日期索引**切分（非日历距离） | snapshot 不规则间隔（某日缺失/补跑） | train/oos 仍严格不重叠、仍有序，但 `initial_train=50` 从"50 个交易日"**退化为"50 个 snapshot 观测"**（缺失时跨更多日历天） | P3 |
| `split_windows` **不校验输入已排序** | 新调用方传入乱序日期 | 切出错误窗口（当前唯一调用方 `run_walk_forward` 已 `sorted()`，安全；新增调用点需注意） | P3 |
| validation "按时间顺序切 Early/Middle/Recent" | snapshot 时间有序 | 乱序→分段错误（同上，依赖上游有序） | P3 |
| Technical_Date ≠ Scan_Date（契约滞后） | 端点新鲜度差异 | forward return 在**陈旧 Technical_Date** 上计算 → 语义滞后（已被契约告警监控，非崩） | P2（已在观测） |

- **不崩**：以上均为"结果偏差 / 语义退化"，不会抛异常或中断整条链。
- Phase 5 的"索引切分"行为已在 STEP 5 测试（`df26af7`）钉死（`len(tr)==50` 而非按日历天数断言），防止未来误改。

---

## 5. 与 workflow / dashboard 的接口 → ✅ 核心已接线，无"写了读不到"

`dashboard_export.build_quant()` 实际读取的 quant 文件（已核对生产者文件名一致）：

| Phase | dashboard 读取的文件 | 生产者实际文件名 | 对齐 |
|---|---|---|---|
| 1 | quant_factor_snapshot.csv | quant_factor_snapshot.csv | ✅ |
| 2 | quant_factor_backtest.csv | quant_factor_backtest.csv | ✅ |
| 3 | quant_factor_validation.csv | quant_factor_validation.csv | ✅ |
| 5 | quant_walk_forward_results.csv | quant_walk_forward_results.csv | ✅ |
| 6 | quant_shadow_performance.csv | quant_shadow_performance.csv | ✅ |

- **核心产物文件名全部对齐** → "数据写了但 dashboard 读不到"的崩塌风险**不成立**。
- **Phase 4（score_v2）未接 dashboard**：设计使然——`QUANT_SCORE_V2_ENABLED=False` 硬编码，dashboard 也硬编码 Phase 4 = DISABLED。未来启用 Phase 4 时需让 dashboard 改读 registry/clusters。
- **Phase 7（production）状态硬编码**：dashboard 用常量表达 V1 ACTIVE / V2 DISABLED / Gate NOT_READY，**不读** `quant_production` 的 state json。当前正确（Phase 7 未激活）；若未来 Phase 7 落 state 文件，dashboard 需增补读取。
- **辅助文件**（correlation.csv / summary.csv / *report.json）dashboard 不读，但属补充材料，核心展示不依赖。

---

## 6. 真实风险分级

### P1（高，需决策/修复后才建议进生产）
- **无。预检未发现任何会导致崩溃或静默错误的数据驱动路径缺陷。**

### P2（中，建议进生产前处理）
- **P2-1 无生产 runner**：Phase 2–7 不被 scan.yml 编排，需手动/定时串联。数据攒够后若只靠 scan 自动跑，Phase 2–7 不会产生任何产物（dashboard 显示 NOT_ENOUGH_DATA）。建议：新增编排（cron 或 scan.yml 追加步骤）或明确"手动研究流程"。
- **P2-2 Phase 7 state 文件未接 dashboard**：当前硬编码常量可用；Phase 7 一旦激活并落 state json，dashboard 需增补读取，否则治理状态展示与真实文件脱节。

### P3（低，已知/已钉死，观察即可）
- **P3-1 walk-forward 索引切分语义退化**（不规则间隔 → 50 观测 ≠ 50 交易日）：不崩，结果偏保守；已在测试钉死行为。
- **P3-2 split_windows / validation 不校验排序**：当前调用方已 sorted()，新调用点需注意；建议在 `split_windows` 入口加 `assert` 或文档化。
- **P3-3 Technical_Date 滞后**：语义风险，已被契约告警 + 10-08 观测器覆盖。

---

## 7. "数据来了但代码跑不起来"场景清单

**结论：场景为空（无崩溃型场景）。** 全部边界走 NOT_ENOUGH_DATA 优雅降级，无 KeyError / 除零 / 越界 / 文件竞争。

可能"跑通但结果不对"的非崩溃场景（供进生产前留意）：
1. price_history 缺 snapshot 中某 ticker → 该 ticker forward return=NaN，被 maturity_status 排除（不崩，样本减少）。
2. snapshot 不规则间隔累积 → walk-forward 窗口退化为"50 观测"而非"50 交易日"（结果偏，不崩）。
3. Technical_Date 滞后 → forward return 在陈旧日期计算（语义滞后，已被监控）。
4. 只跑 Phase 1 不跑 Phase 2B → backtest 不落文件，下游全 NOT_ENOUGH_DATA（预期降级）。

---

## 8. 修复优先级建议（不实施）

| 优先级 | 动作 | 触发条件 |
|---|---|---|
| P2-1 | 为 Phase 2–7 增加编排（scan.yml 追加步骤或独立 cron） | 决定"每日自动研究"还是"按需手动研究"后 |
| P2-2 | dashboard 增补读取 quant_production state json | Phase 7 激活并落 state 文件时 |
| P3-1 | 保持现状（行为已测试钉死） | 无需动作，观察即可 |
| P3-2 | `split_windows` 入口加排序断言/文档 | 新增调用点前 |
| P3-3 | 保持契约告警 + 观测器 | 10-08 判决后按 Playbook 处理 |

> 总体结论：**数据驱动路径健壮，不会因为"数据攒够了"而崩溃。** 主要待办是"编排（让 Phase 2–7 真跑起来）"和"Phase 4/7 的未来接线"，均为设计/运维层面，非代码缺陷。
> 注：本轮仅报告，未改任何文件。
