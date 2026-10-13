# STEP 3-A · schema_version 实施报告

> **性质**：纯增量改动，不改字段名/类型、不改业务逻辑
> **commit = 0 · push = 0 · 生产文件写入 = 0**
> **基准**：`HEAD = a220233`；改动未提交，Scan 仍运行旧代码（无迁移风险，因为 snapshot 尚未生成）

---

## 1. 前置确认结果（提交来源）

按你的要求先回答这 8 个 Phase 提交是谁、什么时候做的。

### 1.1 作者

```
git log --format="%h %ad %an %s" --date=short
```

8 个 Phase 提交（含后续 refactor）署名**完全一致**：

| commit | 日期 | 作者 | 说明 |
|---|---|---|---|
| `01db04f` | 2026-10-07 | `wijouyang-lab <wijouyang@gmail.com>` | Phase 1 factor library + daily snapshot |
| `fdfc3dd` | 2026-10-07 | 同上 | Phase 2 backtest framework |
| `9398983` | 2026-10-07 | 同上 | Phase 2B persistent price history |
| `1f30bb5` | 2026-10-07 | 同上 | Phase 3 validation engine |
| `f40e32e` | 2026-10-07 | 同上 | Phase 4 Quant Score 2.0 candidate |
| `396cd85` | 2026-10-07 | 同上 | Phase 5 walk-forward OOS |
| `8f7dcf3` | 2026-10-07 | 同上 | Phase 6 shadow mode |
| `24b2e9b` | 2026-10-07 | 同上 | Phase 7 production governance |
| `1faffff` | 2026-10-07 | 同上 | refactor: unify forward return single source |

### 1.2 关键判断：作者字段**不能**区分人与 AI

我核对了仓库身份配置：

```
git config user.name  = wijouyang-lab
git config user.email = wijouyang@gmail.com   （local，无 global 配置）
```

而**我在本次会话提交的 `a220233 feat: add quant research dashboard` 署名也是 `wijouyang-lab <wijouyang@gmail.com>`**。

> 因此：repo 里所有人工与 AI 会话提交都复用同一身份，**单看作者无法区分**。

仓库中确实存在两个**真正不同**的署名，可作为对照：

| 作者 | 提交数 | 时间 | 是否涉及 quant |
|---|---|---|---|
| `github-actions[bot]` | 1552 | 持续 | 否（dashboard-data 定时刷新） |
| `wijouyang-lab` | 425 | — | **是（11 条 quant 提交）** |
| `Alpha Bot` | 106（5 条含 quant 字样） | **2026-05-27** | ❌ 是 `"Auto update quant logs"`，与本次 7-Phase 无关 |
| `WorkBuddy` | 14 | **2026-09-30 ~ 10-02** | ❌ 全部是 review/dashboard 修复，**未触及任何 quant 文件** |

### 1.3 时间分布

```
10:56:26  01db04f  Phase 1
   ↓ 18.9 min
11:15:16  fdfc3dd  Phase 2
   ↓ 15.3 min
11:30:32  9398983  Phase 2B
   ↓ 18.9 min
11:49:29  1f30bb5  Phase 3
   ↓ 7.8 min
11:57:14  f40e32e  Phase 4
   ↓ 7.5 min
12:04:45  396cd85  Phase 5
   ↓ 8.9 min
12:13:37  8f7dcf3  Phase 6
   ↓ 9.8 min
12:23:24  24b2e9b  Phase 7
   ↓ 72.2 min
13:35:33  1faffff  refactor
```

**全部发生在今天（2026-10-07），跨度 1 小时 27 分钟**，间隔 7.5–19 分钟。

### 1.4 是否同一连续会话

**是 —— 一个连续工作段**（非一次性 burst）。证据：

- 8 条间隔均匀（7.5–19 min），符合逐阶段实现的节奏；
- 中间夹杂的**只有** `github-actions[bot]` 的 dashboard-data 定时刷新（每 ~15 min 一次，属 CI 噪声）；
- 仅 1 条人工提交混入：`20a29e5 fix(ci): prevent dashboard-data retry from deleting concurrent files`（11:40，与 Quant 无关）；
- 72 分钟后的 `1faffff` 是针对 Phase 2 forward return 的后续重构，属同一工作段的收尾。

### 1.5 是否历史遗留

**不是。** 距今仅数小时；且**有 129 个 quant 测试当前全绿**（全量 163 passed）。

> **维护策略建议**：可按"近期产出 + 有测试覆盖 + 设计自洽"直接补缺口。但**不必假设上下文仍在** —— 我这次是**重新读代码**建立的理解，而非依赖记忆。这也正是本次审计先把事实钉死（提交 + 行号 + 测试数）的原因。

---

## 2. Phase 1 现状确认

| 检查 | 结果 |
|---|---|
| `quant_factor_lab.py` 是否已有 schema_version | ❌ **无** |
| 全仓库现有 version 类常量 | 仅 `quant_production.py:55 PRODUCTION_VERSION = "V1"` |
| 该常量语义 | **模型版本**（V1/V2），**不是**数据结构版本 → 不可复用 |

→ 因此需要定义统一格式。

---

## 3. 统一命名规则

```
schema_version = "phase<阶段>.v<主版本>"
```

| 规则 | 说明 |
|---|---|
| 键名/列名 | **统一为 `schema_version`**（CSV 列与 JSON 键同名，满足"命名规则统一"） |
| 值格式 | `phase` + 阶段号 + `.v` + 主版本号 |
| 版本递增 | 字段结构变更（增/删/改名/改类型）时递增主版本号：`v1 → v2` |
| 与 `PRODUCTION_VERSION` 分离 | 前者是**数据 schema 版本**，后者是**模型版本**，语义不同不可混用（已在代码中注释锁定） |

---

## 4. 每个 Phase 的 schema_version 值

| Phase | 模块 | 值 | 输出文件 |
|---|---|---|---|
| **Phase 1** | `quant_factor_lab.py` | **`phase1.v1`** | `quant_factor_snapshot.csv` |
| **Phase 2B** | `quant_factor_price.py` | **`phase2b.v1`** | `quant_factor_price_history.csv` |
| **Phase 2** | `quant_factor_backtest.py` | **`phase2.v1`** | `quant_factor_backtest.csv`、`quant_factor_summary.csv` |
| **Phase 3** | `quant_factor_validation.py` | **`phase3.v1`** | `quant_factor_validation.csv`、`quant_factor_correlation.csv`、`quant_factor_validation_report.json` |
| **Phase 4** | `quant_score_v2.py` | **`phase4.v1`** | `quant_factor_registry.csv`、`quant_factor_clusters.csv`、`quant_score_v2_candidates.csv`、`quant_score_v2_config.json`、`quant_score_v2_report.json` |
| **Phase 5** | `quant_walk_forward.py` | **`phase5.v1`** | `quant_walk_forward_results.csv`、`quant_walk_forward_summary.json` |
| **Phase 6** | `quant_shadow.py` | **`phase6.v1`** | `quant_shadow_snapshot.csv`、`quant_shadow_performance.csv`、`quant_shadow_report.json` |
| **Phase 7** | `quant_production.py` | **`phase7.v1`** | `quant_production_state.json`、默认 config、`quant_production_audit.jsonl` |

### 一处关键处理：避免上游版本串味

`quant_factor_backtest.csv` 由 snapshot 派生，而 snapshot 自带 `phase1.v1` 列。若不处理，backtest 输出会错误地标注 `phase1.v1`。

已在 `run_backtest` 写出前**显式覆盖**为本阶段版本：

```python
bt = compute_forward_returns(snap, price_map)
# 输入 snapshot 带有上游 phase1.v1 版本列，此处覆盖为本阶段版本
bt["schema_version"] = SCHEMA_VERSION
```

验证脚本已断言该行为（见第 6 节 `[PASS] phase2 值覆盖为 phase2.v1（非上游 phase1）`）。

---

## 5. 修改的文件列表

| 文件 | 改动 | 说明 |
|---|---|---|
| `quant_factor_lab.py` | +7 | 新增 `SCHEMA_VERSION`；`SNAPSHOT_COLUMNS` 加列；`build_snapshot_rows` 每行写入 |
| `quant_factor_price.py` | +7/-1 | 新增 `SCHEMA_VERSION`；`PRICE_HISTORY_COLUMNS` 加列；`fetch_batch_prices` 每行写入 |
| `quant_factor_backtest.py` | +8 | 新增 `SCHEMA_VERSION`；backtest/summary 写出前加列并覆盖 |
| `quant_factor_validation.py` | +10 | 新增 `SCHEMA_VERSION`；validation/correlation 加列（含空数据路径）；report JSON 加键 |
| `quant_score_v2.py` | +9 | 新增 `SCHEMA_VERSION`；registry/clusters/candidates 加列；config/report JSON 加键 |
| `quant_walk_forward.py` | +7 | 新增 `SCHEMA_VERSION`；results 加列（含空输出路径）；summary JSON 加键 |
| `quant_shadow.py` | +11/-1 | 新增 `SCHEMA_VERSION`；shadow snapshot/performance 加列（含禁用路径）；report JSON 加键 |
| `quant_production.py` | +8 | 新增 `SCHEMA_VERSION`；默认 config / state JSON / audit entry 加键 |

**未修改**：字段名、字段类型、任何业务逻辑、任何 Phase 3–7 核心逻辑、workflow、schedule。

### `git diff --stat`

```
 quant_factor_backtest.py   |  8 ++++++++
 quant_factor_lab.py        |  7 +++++++
 quant_factor_price.py      |  7 ++++++-
 quant_factor_validation.py | 10 ++++++++++
 quant_production.py        |  8 ++++++++
 quant_score_v2.py          |  9 +++++++++
 quant_shadow.py            |  11 ++++++++++-
 quant_walk_forward.py      |  7 +++++++
 8 files changed, 65 insertions(+), 2 deletions(-)
```

---

## 6. 测试结果

### 6.1 全量 pytest

```
$ python3 -m pytest -q
163 passed, 2 warnings in 10.77s
```

**与改动前完全一致（163），0 regression。**
（2 条 warning 为既有 `test_quant_factor_validation.py::test_regime` 的 numpy/pandas 相关性告警，与本次无关。）

### 6.2 py_compile

```
python3 -m py_compile quant_factor_{lab,price,backtest,validation}.py \
                      quant_score_v2.py quant_walk_forward.py \
                      quant_shadow.py quant_production.py
→ OK
```

### 6.3 schema_version 功能验证（33 项，全部 PASS）

验证脚本在**临时目录**内运行（`os.chdir(tempfile)`），**零生产写入**。

```
汇总：PASS 33 · FAIL 0
```

覆盖：

- ✅ 8 个模块 `SCHEMA_VERSION` 常量值正确
- ✅ Phase 1 snapshot 含列且值 = `phase1.v1`（列数 32 → **33**）
- ✅ Phase 2B `PRICE_HISTORY_COLUMNS` 含列
- ✅ Phase 2 两个 CSV 含列，且**值覆盖为 `phase2.v1`（非上游 phase1）**
- ✅ Phase 3 validation/correlation CSV + report JSON 含版本
- ✅ Phase 4 registry/clusters/candidates CSV + config/report JSON 含版本
- ✅ Phase 5 results CSV + summary JSON 含版本
- ✅ Phase 6 shadow snapshot/performance CSV + report JSON 含版本
- ✅ Phase 7 state JSON + audit.jsonl + 默认 config 含版本

### 6.4 生产安全未被破坏（同步验证）

| 断言 | 结果 |
|---|---|
| Phase 4 `QUANT_SCORE_V2_ENABLED` 仍 `False` | ✅ |
| Phase 6 `shadow_status` 仍 `SHADOW_DISABLED` | ✅ |
| Phase 7 `active_version` 仍 `V1` | ✅ |
| Phase 7 `production_gate` 仍 `NOT_READY` | ✅ |
| `PRODUCTION_VERSION`(V1) 与 `SCHEMA_VERSION` 语义分离 | ✅ |
| **Phase 3 极少量样本未伪造证据**（仅 NOT_ENOUGH_DATA/EXPLORATORY，无 PROMISING） | ✅ |
| **Phase 3 N=0 行指标为 None 而非 0** | ✅ |

> 关于"N=0 行为 None 而非 0"这条：验证中一度出现 `Win_Rate=0.0`，经核查**不是伪造** —— 该行 N=1 且唯一样本确实亏损，胜率真实为 0%；而 **N=0 的行指标全部为空**。这正是"不造假"原则的正确体现，已按此修正断言并通过。

---

## 7. 生产文件零污染确认

```
MISSING(正常): quant_factor_snapshot.csv
MISSING(正常): quant_factor_price_history.csv
MISSING(正常): quant_factor_backtest.csv
MISSING(正常): quant_factor_validation.csv
MISSING(正常): quant_score_v2_candidates.csv
MISSING(正常): quant_walk_forward_results.csv
MISSING(正常): quant_shadow_performance.csv
MISSING(正常): quant_production_state.json
```

**8 个 quant 数据文件全部仍为 MISSING** —— 未手工创建、未 backfill、未干扰后台 Phase 1 监控。

---

## 8. 已知取舍（需你知晓）

| # | 取舍 | 说明 |
|---|---|---|
| T1 | CSV 采用**每行重复** schema_version | 简单、自描述、无需额外文件；代价是长表（尤其 `quant_factor_price_history.csv`）每行多 ~11 字节。若未来该文件超百万行，可改为 sidecar 元数据文件 |
| T2 | CSV 列名用 `schema_version`（snake_case） | 而这些文件其它列多为 Title_Case（`Scan_Date`…）。为严格遵守"命名规则统一"选择了字面统一，视觉上略有不一致。如你更看重文件内风格一致，可改为 `Schema_Version`（改法极简，一行替换） |
| T3 | Phase 7 默认 config 新增字段会改变 `config_hash` | 全量测试已确认无影响（无测试断言固定 hash）；但未来若有已批准的 config_hash，需注意 v1 引入会使其失效 |
| T4 | 未提交，故今日 13:07 UTC 的 Scan 仍用旧代码（32 列） | 因 snapshot 尚未生成，**零迁移风险**；提交后首个 snapshot 即带 33 列 |

---

## 9. 下一步

STEP 3-A 完成。可进入 **STEP 3-B**：`quant_factor_backtest.py` 补 `main()` + 4 类测试 + R1 修复（无数据不落空文件）。

---

*STEP 3-A 报告结束 · commit 0 · push 0 · 生产写入 0*
