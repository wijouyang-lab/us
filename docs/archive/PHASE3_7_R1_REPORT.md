# STEP 3-C · Phase 3–7 R1 全面修复报告

> **性质**：把 Phase 3–7 的"无数据写空文件"统一改为"无数据不落文件"，与 Phase 2 一致
> **未改**：任何 Phase 的核心业务逻辑、schema_version 相关代码、workflow、schedule
> **commit = 3（逻辑拆分）· push = 0 · 生产数据写入 = 0**
> **基准**：`HEAD = a220233` → 现 `61b42b7`（ahead 3）

---

## 1. R1 修复全景

| Phase | 模块 | 旧函数（危险） | 新行为 | `written` 标志 |
|---|---|---|---|---|
| Phase 2 | `quant_factor_backtest.py` | `_write_empty()` | `_no_data_skip_write()` | ✅ |
| **Phase 3** | `quant_factor_validation.py` | `_write_empty_outputs()` | `_no_data_skip_write()` | ✅ |
| **Phase 4** | `quant_score_v2.py` | 无独立函数（无数据仍写 5 份） | 提前 return，不写 | ✅ |
| **Phase 5** | `quant_walk_forward.py` | `_write_empty_outputs()` | `_no_data_skip_write()` | ✅ |
| **Phase 6** | `quant_shadow.py` | `_write_disabled_outputs()` | `_no_data_skip_write()` | ✅ |
| **Phase 7** | `quant_production.py` | —（**本无 R1 风险**） | 保持写入真实治理状态 | ✅ 恒 True |

> 全文检索确认：仓库中已**不存在** `_write_empty_outputs` / `_write_disabled_outputs` / `_write_empty` 的函数定义，仅保留在说明"为什么改"的注释里。

---

## 2. 每个 Phase 的改动位置

### Phase 3 · `quant_factor_validation.py`

| 位置 | 改动 |
|---|---|
| `run_validation()` result 初始化 | 新增 `"written": False` + R1 注释 |
| `run_validation()` 3 个无数据分支（backtest 不存在 / 读取失败 / 为空） | `_write_empty_outputs(...)` → `_no_data_skip_write(...)` |
| `run_validation()` 成功路径 | `result["written"] = True` |
| `_write_empty_outputs()` | **整体替换**为 `_no_data_skip_write()`（只返回 None，不写任何文件） |
| `main()` | 新增 argparse 参数（`--backtest/--validation/--correlation/--report/--strict`） |

**旧行为危害**：无数据时写出 **72 行全 `NOT_ENOUGH_DATA` 的 validation.csv** —— 文件存在且有内容，最容易被误读为"已完成验证"。

### Phase 4 · `quant_score_v2.py`

| 位置 | 改动 |
|---|---|
| `run_quant_score_v2()` result 初始化 | 新增 `"written": False` |
| `run_quant_score_v2()` | **新增守卫**：`validation_path` 不存在 或 `validation_df` 为空 → 直接 return（不构建、不落盘） |
| `run_quant_score_v2()` 成功路径 | `result["written"] = True` |
| `main()` | 新增 argparse 参数 + `--strict` |

**旧行为危害**：无数据时用全 `NOT_ENOUGH_DATA` 写出 **5 份文件**（registry/clusters/candidates/config/report）。

> 附带修正：Phase 4 旧 `main()` 把"非 OK 一律返回 1"，与其余 Phase 不一致。现统一为"数据不足默认 0，`--strict` 才 1"。

### Phase 5 · `quant_walk_forward.py`

| 位置 | 改动 |
|---|---|
| `run_walk_forward()` result 初始化 | 新增 `"written": False` |
| 3 个无数据分支（backtest 空 / 缺 `Technical_Date` / window 数=0） | `_write_empty_outputs(...)` → `_no_data_skip_write(...)` |
| 成功路径 | `results_df` 非空时 `result["written"] = True` |
| `_write_empty_outputs()` | **整体替换**为 `_no_data_skip_write()`（保留 `model_statuses` 内存态赋值，去掉所有文件写入） |
| `main()` | 新增 argparse 参数 + `--strict` |

**旧行为危害**：写出 **0 行 results.csv + summary.json**，下游看到文件存在会误以为已完成 OOS。

### Phase 6 · `quant_shadow.py`

| 位置 | 改动 |
|---|---|
| `run_shadow()` result 初始化 | 新增 `"written": False` |
| 3 个分支（`SHADOW_ENABLE=false` / `SHADOW_START_DATE=null` / snapshot 为空） | `_write_disabled_outputs(...)` → `_no_data_skip_write(...)` |
| `_write_disabled_outputs()` | **整体替换**为 `_no_data_skip_write()` |
| `main()` | 新增 argparse 参数 + `--strict` |

**旧行为危害**：Shadow **恒为 DISABLED**，等于每次运行都往仓库丢 **0 行 shadow_snapshot.csv + 0 行 performance.csv + report.json**。这是 5 个 Phase 里唯一"只要运行就必然产生空文件"的场景。

### Phase 7 · `quant_production.py`

| 位置 | 改动 |
|---|---|
| `run_production_governance()` 返回值 | 新增 `"written": True` + `skip_empty_writes_note` 说明 |
| `main()` | 新增 argparse 参数 + `--strict`（非 PASS 时返回 1） |

**审计结论：Phase 7 不存在 R1 风险。** 它没有 `_write_empty_outputs`，从不写空文件——`state.json` 恒含 `active_model`/`active_version=V1` 等**真实治理状态**，且 `V1_ACTIVE` 是安全默认值、必须持久存在。因此这里**不是"改成不写"**，而是通过 `written=True` + 说明字段与其它 Phase 口径对齐，并用测试断言"它写出的一定是真实非空内容"。

---

## 3. 无数据行为实测（临时目录，确认目录为空）

方式：在 `tempfile.mkdtemp()` 空目录中执行各模块 `main([])`，然后列出目录内容。

| Phase | 模块 | 退出码 | 目录内容 | 判定 |
|---|---|---|---|---|
| Phase 2 | `quant_factor_backtest.py` | 0 | **空 ✓** | ✅ |
| Phase 3 | `quant_factor_validation.py` | 0 | **空 ✓** | ✅ |
| Phase 4 | `quant_score_v2.py` | 0 | **空 ✓** | ✅ |
| Phase 5 | `quant_walk_forward.py` | 0 | **空 ✓** | ✅ |
| Phase 6 | `quant_shadow.py` | 0 | **空 ✓** | ✅ |
| Phase 7 | `quant_production.py` | 0 | `state.json` + `audit.jsonl`，**均非空** | ✅（治理状态，恒真实） |

```
汇总：PASS 6 · FAIL 0
```

各模块输出的状态行（节选）：

```
[Validation] {'status': 'NOT_ENOUGH_DATA', ..., 'written': False, 'reason': 'backtest 不存在：quant_factor_backtest.csv'}
[Quant Score V2] {'status': 'NOT_ENOUGH_DATA', ..., 'written': False, 'reason': 'validation 不存在：quant_factor_validation.csv（Phase 3 尚无真实结果）'}
[Walk-Forward] {'status': 'NOT_ENOUGH_DATA', 'window_count': 0, ..., 'written': False, ...}
[Shadow] {'shadow_status': 'SHADOW_DISABLED', ..., 'written': False, 'reason': 'SHADOW_ENABLE=false（未人工启用），Shadow 保持 DISABLED'}
```

### `--strict` 退出码实测

| 模块 | `--strict` 退出码 | 期望 |
|---|---|---|
| `quant_factor_backtest.py` | 1 | ✅ |
| `quant_factor_validation.py` | 1 | ✅ |
| `quant_score_v2.py` | 1 | ✅ |
| `quant_walk_forward.py` | 1 | ✅ |
| `quant_shadow.py` | 1 | ✅ |

（Phase 7 的 `--strict` 语义不同：`monitor_status != PASS` 才返回 1；当前 V1 恒 PASS，故返回 0 —— 这是正确行为。）

### 已存在产物不被删除（刻意保留）

所有 Phase 的 skip-write 都**不删除**已存在的历史产物。已加测试断言（`已存在产物未被删除/截断`）——删除历史产物比保留更危险。

---

## 4. 测试结果

### 4.1 关键发现：5 个旧测试固化了 R1 危险行为

首次运行全量测试时 5 个测试失败——**它们断言的正是旧的"无数据也写文件"行为**：

| 失败测试 | 原因 |
|---|---|
| `test_quant_factor_validation.py::test_run_validation_empty` | 读了不再生成的 `validation.csv` |
| `test_quant_score_v2.py::test_run_end_to_end` | 断言无 validation 时 `status == "OK"` 并读文件 |
| `test_quant_shadow.py::test_shadow_disabled_active` | 读了不再生成的 `report.json` |
| `test_quant_shadow.py::test_empty_report` | 同上 |
| `test_quant_walk_forward.py::test_no_fake_production_data` | 读了不再生成的 `results.csv` |

已将这 5 个测试改为断言**新行为**（不落文件 + 内存态不伪造），并保留其原有意图（"不造假"校验改为直接调用纯函数，如 `validate_factor_horizon(None, ...)` 断言 `Win_Rate is None`）。

### 4.2 新增 5 个专项测试（每个 Phase +1）

| Phase | 测试文件 | 测试函数 |
|---|---|---|
| Phase 3 | `tests/test_quant_factor_validation.py` | `test_no_data_no_files` |
| Phase 4 | `tests/test_quant_score_v2.py` | `test_no_data_no_files` |
| Phase 5 | `tests/test_quant_walk_forward.py` | `test_no_data_no_files` |
| Phase 6 | `tests/test_quant_shadow.py` | `test_no_data_no_files` |
| Phase 7 | `tests/test_quant_production.py` | `test_no_empty_files` |

每个测试覆盖：无数据分支 → 断言文件未创建；有数据 → 断言正常写出（确认不是"永远不写"）；已存在产物 → 断言不被删除。

### 4.3 全量 pytest

```
$ python3 -m pytest -q
173 passed, 2 warnings in 11.34s
```

**168 → 173，正好 +5（每个 Phase +1），0 regression。**

### 4.4 提交后复核

```
$ python3 -m pytest -q
173 passed   （与提交前一致，工作区文件校验和亦一致）
```

---

## 5. `git diff --stat`（STEP 3-C 全部改动）

```
 quant_factor_validation.py            |  66 ++++++----
 quant_production.py                   |  37 +++++-
 quant_score_v2.py                     |  49 +++++++-
 quant_shadow.py                       |  71 +++++++----
 quant_walk_forward.py                 |  66 ++++++----
 tests/test_quant_factor_validation.py |  68 ++++++++++-
 tests/test_quant_production.py        |  43 +++++++
 tests/test_quant_score_v2.py          |  84 ++++++++++++-
 tests/test_quant_shadow.py            |  61 ++++++++--
 tests/test_quant_walk_forward.py      |  72 ++++++++++-
```

**未修改**：workflow、schedule、任何 Phase 核心业务逻辑、schema_version 相关代码、旧架构（未删除任何既有函数，仅替换 R1 相关的 3 个私有函数）。

### `git diff --check`

```
（无输出）→ OK
```

---

## 6. 三个 commit 的拆分结果

| # | SHA | message | 文件数 | 内容 |
|---|---|---|---|---|
| **1** | `3172aa53f94c50c82d006de967bb18eec109562a` | `feat(quant): add schema_version to all phase outputs` | 8 | 仅 schema_version |
| **2** | `6ed63f1a3090545fa15670c78b81c2d50f7eb5d6` | `feat(quant): add phase2 main() and skip empty writes` | 2 | 仅 Phase 2 main() + R1 |
| **3** | `61b42b7bc60ca9d43e4d965cffc6de7a61d71456` | `fix(quant): extend skip-empty-writes to phase 3-7` | 10 | 仅 Phase 3–7 R1 |

### 拆分方法（只动 index，未触碰工作区）

用 hunk 级补丁拆分：把完整 diff 按 (文件, hunk) 分类为 C1/C2/C3 三组，再用 `git apply --cached` **只写入 index** 逐个提交。

**工作区全程未被修改** —— 提交前后 14 个文件的 md5 逐一比对，**全部一致**：

```
md5sum -c /tmp/before_commit.md5
→ 全部 OK
```

未使用 `reset --hard`、未 `amend`、未 `force push`。

### 逐个 commit 的纯净性校验

**Commit 1**（`git show --stat`）：仅 8 个 Phase 模块的 schema_version，55 行新增。
暂存内容中检索 `no_data_skip` / `written` / `argparse` / `strict` / `def main` → **0 命中** ✓
且 8 个模块在该中间态**均可编译**（`compile()` 逐个校验通过）✓

**Commit 2**：仅 `quant_factor_backtest.py` + `tests/test_quant_factor_backtest.py`。

**Commit 3**：仅 Phase 3–7 的 5 个模块 + 5 个测试文件。

> 效果：若将来 revert Commit 2（Phase 2 R1）或 Commit 3（Phase 3–7 R1），**都不会连带回滚 schema_version**。

---

## 7. 生产安全状态（未改变）

| 项 | 值 |
|---|---|
| 当前生产模型 | V1 (`CURRENT_EXISTING_QUANT_SCORE`) |
| Quant V2 | DISABLED |
| Shadow | DISABLED（且现在连空文件都不再产生） |
| Production Gate | NOT_READY |
| V1 Final Score 公式 | 未触碰 |
| workflow / schedule | 未触碰 |

---

## 8. 需要你知晓的三点

| # | 说明 |
|---|---|
| T1 | **首份真实 snapshot 会用旧代码生成。** 我的 3 个 commit 未 push，今日 13:07 UTC 的 Scan 仍从 origin/main 运行 → 产出的 snapshot **是 32 列（无 schema_version）**，而非 33 列。这**无害**（读者都按列名取值），但首次验证时会看到列数 32、无 schema_version 列，属预期 |
| T2 | Phase 4 的 `main()` 默认退出码由"非 OK 即 1"改为"数据不足 0"。这是与其它 Phase 对齐所需；若有外部脚本依赖旧行为，需改用它新增的 `--strict` |
| T3 | Phase 7 未做"改成不写"，原因是它没有 R1 风险。若你希望它也不落文件，需先讨论——`state.json` 缺失会让治理状态无从持久化（我判断不该改） |

---

## 9. 下一步

STEP 3-C 完成，等待你按五项清单验收：

1. ✅ 监控在跑（PID 209240，日志 `/tmp/phase1_scan_monitor.log`）
2. ✅ Phase 3–7 无数据真的不落文件（临时目录实测目录为空，非仅改函数名）
3. ✅ 测试 168 → **173**（每 Phase +1）
4. ✅ 三个 commit 拆分干净（`git show --stat` 可逐个查）
5. ✅ git diff 范围仅该动的 10 个文件

验收通过后进 **STEP 4–8**（Phase 3/4/5/6/7 各自补测）。STEP 9（跨阶段集成）与 STEP 11（workflow 接线）待首份真实 snapshot 落地后再谈。

---

*STEP 3-C 报告结束 · commit 3 · push 0 · 生产写入 0*
