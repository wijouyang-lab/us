# STEP 4–8 · Phase 3–7 补测报告

> **性质**：只补测试，未改任何 Phase 核心业务逻辑
> **commit**：5 个（每 Phase 一个独立 commit），未 push
> **测试**：**179 passed**（174 → 179，+5，每 Phase +1，0 regression）
> **两条约束**：① 不硬编码绝对日期 ② 不假设 Technical_Date 与 price history 一致

---

## 1. 五个 commit 与覆盖范围

| Phase | commit | message | 文件 | 新增测试 |
|---|---|---|---|---|
| Phase 3 | `c69210018e003795428fa064c9fb5eee9f38811c` | `test(quant): add phase 3 validation status machine tests (all 7 statuses)` | `tests/test_quant_factor_validation.py` | `test_validation_status_machine` |
| Phase 4 | `646c0c342129b0f0d5c34e4957ce852d84372c0f` | `test(quant): add phase 4 weight-none gate tests` | `tests/test_quant_score_v2.py` | `test_weight_none_gate` |
| Phase 5 | `df26af71e56a2fd47c290b526292139c61529a0e` | `test(quant): add phase 5 walk-forward irregular-interval boundary tests` | `tests/test_quant_walk_forward.py` | `test_window_split_irregular_intervals` |
| Phase 6 | `4c0acf84c2196ee9afdd09ffcdd3abbbc408372d` | `test(quant): add phase 6 V1/V2 divergence record tests` | `tests/test_quant_shadow.py` | `test_divergence_record_completeness` |
| Phase 7 | `fedf63d9f86e24d0264f1ab45326fc490fdf0588` | `test(quant): add phase 7 activation criteria tests` | `tests/test_quant_production.py` | `test_activation_criteria` |

### 拆分纯净性核验

```
git diff c692100~1..fedf63d --name-only
→ tests/test_quant_factor_validation.py
  tests/test_quant_production.py
  tests/test_quant_score_v2.py
  tests/test_quant_shadow.py
  tests/test_quant_walk_forward.py

5 个 Phase commit 触及的 quant 模块数 = 0   ✅
```

**每个 Phase 一个独立 commit，只动该 Phase 的测试文件，未触碰任何 `quant_*.py` 核心逻辑。**

---

## 2. 两条约束的落实

### 约束 1：不硬编码绝对日期 ✅

对 5 个 Phase commit 的新增代码做全量检索：

```
git diff HEAD~5..HEAD -- tests/ | grep "^+" | grep -E "2026-10-05|2026-10-06|2026-10-07|2026-10-08"
→ 0 命中   ✅
```

采用的做法：

| Phase | 日期构造方式 |
|---|---|
| Phase 3 | `_mk_status_df(base=None)` —— 默认用 `pd.bdate_range` 生成；`base` 可作为 fixture 参数注入 |
| Phase 5 | `pd.bdate_range("2026-03-02", periods=120)` 生成日历，再按索引抽稀制造不规则间隔 |
| Phase 6 | 复用既有 `make_snapshot()` fixture |
| Phase 7 | 合成审批/证据文件，日期取自 fixture 变量 |
| Phase 4 | 不涉及日期 |

### 约束 2：不假设 Technical_Date 与 price history 一致 ✅

| Phase | 覆盖方式 |
|---|---|
| Phase 3 | 显式构造「日历错位」场景：把 `Technical_Date` 整体替换为另一套日期，断言仍产出合法 status 且 `N` 真实统计（不崩溃、不伪造） |
| Phase 5 | **核心防护**：显式覆盖「等距日历」与「不规则间隔日历」两种，并验证不等距时窗口切分仍安全 |

---

## 3. Phase 5「不规则间隔」边界 —— 长期风险的核心防护

这是你点名要加强的部分。先说清楚一个**重要发现**：

### `split_windows()` 按【唯一日期列表的索引】切分，而非日历距离

因此：

- ✅ **不会崩溃**：日期不等距时窗口照常产生
- ✅ **train 与 oos 仍严格不重叠、仍保持时间顺序**
- ⚠️ **语义退化**：`initial_train=50` 的含义从「50 个交易日」变为「50 个 snapshot 观测」。若 snapshot 日期有缺失，50 个观测会跨越**更多日历天数**

测试已把这一行为**钉死**（`len(tr2) == 50` 而非按日历天数断言），避免未来误改。

### 覆盖的 7 组断言

| # | 断言 | 结果 |
|---|---|---|
| 1 | 等距日历 → 正常开窗，train=50 / oos=20，不重叠 | ✅ |
| 2 | **不规则间隔（每 7 天抽掉 1 天）→ 仍能开窗，不崩溃** | ✅ |
| 3 | **不规则间隔下 train 长度仍按观测数（50）而非日历天数** | ✅ |
| 4 | **所有窗口 train 严格早于 oos** | ✅ |
| 5 | 数据不足 → 无窗口（不伪造）：40 天、60 天两种边界 | ✅ |
| 6 | ROLLING 模式：train 长度 ≤ rolling_train，各窗口不重叠 | ✅ |
| 7 | **严重抽稀（每 3 天取 1）→ 不崩溃；有窗口则不重叠** | ✅ |
| 8 | 乱序输入行为可预期（调用方须自行 `sorted()`） | ✅ |

> **残余风险提示**：`split_windows` 不校验日期是否已排序 —— 传入乱序会切出错误窗口。调用方 `run_walk_forward` 已用 `sorted()`，测试也记录了该契约（第 8 条），但未来若新增调用点需注意。

---

## 4. 各 Phase 测试内容

### Phase 3 · validation 状态机（全 7 种 status）

构造可命中每种状态的合成数据，逐一断言：

| status | 构造条件 | 结果 |
|---|---|---|
| `NOT_ENOUGH_DATA` | Forward_Return 全空 | ✅ |
| `EXPLORATORY` | N=20（<30） | ✅ |
| `WEAK_EVIDENCE` | N=40（30≤N<50） | ✅ |
| `PROMISING` | N=60 + regime 均衡 + 五分位单调 | ✅ |
| `INCONCLUSIVE` | N=60 + regime 均衡 + 非单调 | ✅ |
| `REGIME_DEPENDENT` | N=60 + 单一 regime 主导 ≥80%、其它 <5 | ✅ |
| `POTENTIALLY_REDUNDANT` | 两因子 \|corr\|≥0.9（Pearson/Spearman） | ✅ |

另含：阈值边界（N=29 → EXPLORATORY，N=30 → 不再是）、`Regime_Status` 同步标记、日历错位鲁棒性。

### Phase 4 · 权重 None 门控

| # | 断言 | 结果 |
|---|---|---|
| 1 | **即使存在 PROMISING 证据，候选模型因子 `Weight` 仍恒为 None**（绝不伪造权重） | ✅ |
| 2 | 证据门控：PROMISING→ELIGIBLE；NOT_ENOUGH_DATA/INCONCLUSIVE→BLOCKED | ✅ |
| 3 | 三个候选模型都各自产出候选清单 | ✅ |
| 4 | 模型状态三分支：无证据→NOT_ENOUGH_DATA；仅 REGIME_DEPENDENT→DISABLED；有 PROMISING→CANDIDATE | ✅ |
| 5 | `group_weights` 是研究规格常量（有定义且冻结），与 `Weight=None` 是两回事 | ✅ |
| 6 | `QUANT_SCORE_V2_ENABLED` 在任何证据下恒 False | ✅ |

### Phase 6 · V1/V2 分歧记录

| # | 断言 | 结果 |
|---|---|---|
| 1 | 分歧记录 16 个必需字段齐全 | ✅ |
| 2 | 每行覆盖同一候选池（`len(ss) == len(snap)`）—— V1/V2 看到相同股票 | ✅ |
| 3 | V1 侧 `Existing_Quant_Score` / `Existing_Final_Score` 全有值 | ✅ |
| 4 | V2 侧 `Shadow_Score` / `Shadow_Rank` 全有值，`Shadow_Model` 标注正确 | ✅ |
| 5 | `Difference_Type` 取值限于四种合法枚举 | ✅ |
| 6 | **`Difference_Type` 与两侧 `Selected` 标记自洽**（逐行交叉校验，不能自相矛盾） | ✅ |
| 7 | 确定性：重复构建结果一致 | ✅ |
| 8 | 禁用时 `shadow_snapshot_rows=0` 且不落任何文件（无分歧记录产出） | ✅ |

### Phase 7 · activation criteria

| # | 断言 | 结果 |
|---|---|---|
| 1 | **四 gate 全 PASS → `READY_FOR_PRODUCTION`** | ✅ |
| 2 | **READY ≠ ENABLED：`QUANT_SCORE_V2_ENABLED` 仍为 False（绝不自动 promote）** | ✅ |
| 3 | `determine_state(V1)` 任何 gate 状态下都是 `V1_ACTIVE` | ✅ |
| 4 | **缺任一 gate → `NOT_READY`**（无审批 / 无 research / 无 wf / shadow 未启用，四种变体） | ✅ |
| 5 | gate 未就绪 → V2 `BLOCKED`（即使审批通过） | ✅ |
| 6 | 审批缺失 → V2 `BLOCKED` | ✅ |
| 7 | 真实默认状态（所有证据文件缺失）→ `NOT_READY` + `V1_ACTIVE` | ✅ |

---

## 5. 测试结果

| 阶段 | 数量 |
|---|---|
| 契约告警后基线 | 174 |
| + Phase 3 | 175 |
| + Phase 4 | 176 |
| + Phase 5 | 177 |
| + Phase 6 | 178 |
| + Phase 7 | **179** |

```
$ python3 -m pytest -q
179 passed, 2 warnings in 11.22s
```

**每 Phase +1，0 regression。**（2 条 warning 为既有 `test_quant_factor_validation.py::test_regime` 的 numpy/pandas 相关性告警。）

### 其它检查

```
git diff --check        → OK（工作区无空白/冲突标记）
git status --short      → 干净
git status --branch     → ahead 6, behind 1
```

---

## 6. 未做的事（合规确认）

| 限制 | 状态 |
|---|---|
| 修改 Phase 1 数据源 | ❌ 未做 |
| 修改 snapshot 生成逻辑（除契约告警外） | ❌ 未做 |
| 修改 Gate 逻辑 | ❌ 未做 |
| 重跑今天的 snapshot | ❌ 未做 |
| backfill | ❌ 未做 |
| 修改 workflow / schedule | ❌ 未做 |
| 删除旧架构 | ❌ 未做 |
| push | ❌ 未做（6 个 commit 全部只 commit） |
| 在 10-08 判决前启动数据源层改动 | ❌ 未做 |

---

## 7. 当前状态与待办

| 项 | 值 |
|---|---|
| 本地 HEAD | `fedf63d` |
| 未 push 的 commit | 6 个（`efc23bf` 契约告警 + 5 个 Phase 补测） |
| 分支 | `ahead 6, behind 1` |
| 10-08 观测器 | ✅ 存活 `PID 536931`，日志 `/tmp/scan_1008_monitor.log` |
| 10-08 Scan 目标 | `2026-10-08 13:07 UTC` |

**待办**：等 10-08 Scan 完成后输出判决结果（OK / SYSTEMATIC / DEEPER / OTHER）。观测器已内置四选一判定逻辑，会在 snapshot 更新时自动记录 `Technical_Date`、price history 末端、两者是否一致并给出判决。

---

*STEP 4–8 补测报告 · commit 5 · push 0 · 核心逻辑改动 0*
