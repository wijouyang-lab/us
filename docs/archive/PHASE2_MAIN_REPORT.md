# STEP 3-B · Phase 2 补 main() + 4 类测试（含 R1 修复）

> **性质**：补 `main()` 入口 + 补测试 + **R1 防呆修复**
> **未改**：Phase 2 核心回测逻辑、Phase 3–7 核心逻辑、workflow、schedule
> **commit = 0 · push = 0 · 生产数据写入 = 0**
> **基准**：`HEAD = a220233`

---

## 1. R1 修复：无数据时不再落空文件

### 1.1 问题（审计发现的风险 R1）

旧实现 `quant_factor_backtest._write_empty()`：

```python
def _write_empty(backtest_path, summary_path):
    for p in (backtest_path, summary_path):
        if p:
            with open(p, "w", encoding="utf-8") as f:
                f.write("")      # ← 创建 0 字节 CSV
```

`run_backtest` 在 4 个无数据分支调用它：snapshot 不存在 / 读取失败 / snapshot 为空 / 无 price_map。

**为什么危险**：

| 状态 | 下游行为 | 可见性 |
|---|---|---|
| 文件不存在 | 明确报 `NOT_ENOUGH_DATA` | ✅ 问题可见 |
| **文件存在但为空** | 可能静默通过，误以为"有数据" | ❌ **问题被掩盖** |

正如你指出的：**"存在但为空"比"不存在"危险得多**。

### 1.2 修复

将 4 处调用改为 `_no_data_skip_write()`，该函数**什么都不写**：

```python
def _no_data_skip_write(backtest_path, summary_path):
    """R1 防呆修复：无数据时【绝不写出任何文件】。
    ...
    已存在的产物文件【不会被删除】——删除历史产物比保留更危险，
    是否覆盖由后续有真实数据的运行决定。
    """
    return None
```

同时在 `result` 中新增 **`written`** 标志，让调用方/日志可显式判断"是否真的产出了东西"：

- 有真实数据 → `"written": true`
- 无数据 → `"written": false`

### 1.3 一个刻意保留的行为

**无数据时不删除已存在的历史产物。** 若某天先成功产出、后因数据缺失再次运行，旧产物保持原样 —— 删除历史产物比留着更危险，且会让下游看到"数据凭空消失"。已在测试中断言（见第 3 节 `(e) 已存在产物未被删除/截断`）。

---

## 2. main() 调用方式

### 2.1 用法

```bash
python quant_factor_backtest.py                      # 默认路径
python quant_factor_backtest.py --snapshot  <path>   # 指定 Phase 1 快照
python quant_factor_backtest.py --price-history <p>  # 指定 Phase 2B 价格历史
python quant_factor_backtest.py --backtest  <path>   # 指定回测输出
python quant_factor_backtest.py --summary   <path>   # 指定汇总输出
python quant_factor_backtest.py --strict             # 数据不足时退出码 1
```

### 2.2 `--help`

```
usage: quant_factor_backtest.py [-h] [--snapshot SNAPSHOT] [--price-history PRICE_HISTORY]
                                [--backtest BACKTEST] [--summary SUMMARY] [--strict]

Quant Phase 2 · Factor Backtest（只读消费 snapshot + price history，绝不抓行情）

options:
  -h, --help            show this help message and exit
  --snapshot SNAPSHOT   Phase 1 因子快照 CSV（默认 quant_factor_snapshot.csv）
  --price-history PRICE_HISTORY
                        Phase 2B 价格历史 CSV（默认 quant_factor_price_history.csv）
  --backtest BACKTEST   Phase 2 回测输出 CSV（默认 quant_factor_backtest.csv）
  --summary SUMMARY     Phase 2 汇总输出 CSV（默认 quant_factor_summary.csv）
  --strict              数据不足时以退出码 1 退出（默认 0：数据不足是预期状态而非错误）
```

### 2.3 退出码语义（重要设计决策）

| 退出码 | 条件 | 理由 |
|---|---|---|
| **0** | 成功写出回测结果 | — |
| **0** | 数据不足 `NOT_ENOUGH_DATA` | 研究数据尚未就绪是**预期状态**，不是错误；默认不阻断 workflow |
| **1** | `--strict` 下数据不足 | 需要显式告警时使用 |

> 默认 0 是为了避免以后接线时，Phase 2 因"数据还没攒够"把整个 CI 打红。需要强告警时用 `--strict`。

### 2.4 实测三种场景

**场景 1 · 无数据（当前真实状态）**

```
$ cd <空目录> && python quant_factor_backtest.py
[Backtest] {"backtest_rows": 0, "maturity": {}, "reason": "snapshot 不存在：quant_factor_snapshot.csv",
            "snapshot_rows": 0, "status": "NOT_ENOUGH_DATA", "summary_rows": 0, "written": false}
退出码 = 0

$ ls -la        # 产物目录
drwxr-xr-x  .      ← 空！确认未创建任何文件
```

**场景 2 · `--strict`**

```
$ python quant_factor_backtest.py --strict
[Backtest] {... "status": "NOT_ENOUGH_DATA", "written": false}
退出码 = 1
```

**场景 3 · 正常路径**（临时目录内构造 snapshot + price history，**非生产数据**）

```
snapshot 行数: 2
price history 行数: 72

$ python quant_factor_backtest.py
[Backtest] {"backtest_rows": 2, "maturity": {"5D": 2, "10D": 2, "20D": 2},
            "snapshot_rows": 2, "status": "OK", "summary_rows": 72, "written": true}
退出码 = 0

产物：
  quant_factor_backtest.csv   835 B
  quant_factor_summary.csv   5425 B

backtest.csv：
 Scan_Date   Ticker  Price  Forward_Return_5D  Forward_Return_20D  schema_version
 2026-01-30  AAA     100.00  0.085              0.19                phase2.v1
 2026-01-30  BBB     100.00 -0.051             -0.114               phase2.v1
```

数值与构造的价格序列（AAA 涨 / BBB 跌）方向一致，**无 look-ahead**（用 T 之后第 5/20 个交易日）。Summary 72 行 = 24 因子 × 3 horizon。

---

## 3. 4 类测试结果

新增 5 个测试函数（`test_quant_factor_backtest.py` 由 12 → **17**）。

### 类别 1 · 正常数据路径 —— `test_run_backtest_normal_path`

| 断言 | 结果 |
|---|---|
| status = OK | ✅ |
| `written` = True | ✅ |
| backtest.csv / summary.csv 已写且非空 | ✅ |
| backtest 行数 = snapshot 行数（5） | ✅ |
| 含 `Forward_Return_5D/10D/20D` 三列 | ✅ |
| backtest `schema_version` = `phase2.v1` | ✅ |
| summary 非空且带 `phase2.v1` | ✅ |
| summary 含 `N` 列（必须有样本量） | ✅ |

### 类别 2 · 无数据路径（R1 核心）—— `test_run_backtest_no_data_no_file`

| 分支 | status | **文件未创建** |
|---|---|---|
| (a) snapshot 不存在 | NOT_ENOUGH_DATA | ✅ backtest/summary 均不存在 |
| (b) snapshot 为空 | NOT_ENOUGH_DATA | ✅ |
| (c) 有 snapshot 但 `price_map=None` | NOT_ENOUGH_DATA | ✅ |
| (d) `price_map={}` 空字典 | NOT_ENOUGH_DATA | ✅ |
| (e) 已存在产物 + 后续无数据运行 | NOT_ENOUGH_DATA | ✅ **旧产物未被删除/截断** |

> 每个分支都断言 `not os.path.exists(bt_path)`，直接验证"不落空文件"。

### 类别 3 · 异常数据路径 —— `test_run_backtest_invalid_data`

| 场景 | 断言 | 结果 |
|---|---|---|
| (a) 缺关键列（无 Ticker/Technical_Date/Price） | 不崩溃 | ✅ |
| | Forward_Return 全空**而非 0** | ✅ |
| (b) Price = `abc` / 空 / `nan` / `inf` / `-inf` | 不崩溃 | ✅ |
| | 输出**不含** `inf`/`-inf`/`nan` 字面量 | ✅ |
| (c) 因子值为 `not_a_number` | 不崩溃，统计不伪造 | ✅ |

### 类别 4 · idempotency —— `test_run_backtest_idempotent`

| 断言 | 结果 |
|---|---|
| 重复运行 `backtest.csv` **逐字节一致** | ✅ |
| 重复运行 `summary.csv` **逐字节一致** | ✅ |
| status 一致 | ✅ |
| `backtest_rows` 一致 | ✅ |
| 无重复记录（全量重写而非 append） | ✅ |

### 附加 · CLI 入口 —— `test_main_cli`

| 断言 | 结果 |
|---|---|
| 无数据时 CLI 退出码 0 | ✅ |
| 输出含 `[Backtest]` 状态行 | ✅ |
| 输出含 `NOT_ENOUGH_DATA` | ✅ |
| **CLI 无数据 → 不落文件** | ✅ |
| `--strict` 数据不足 → 退出码 1 | ✅ |

---

## 4. 测试汇总

| 范围 | 数量 | 结果 |
|---|---|---|
| `test_quant_factor_backtest.py` 单文件 | **17** | ✅ 17 passed |
| **全量 pytest** | **168** | ✅ **168 passed** |

```
$ python3 -m pytest -q
168 passed, 2 warnings in 10.75s
```

### 关于 163 → 168 的说明

你在指令中要求 STEP 3-A "确认 163 passed 不变" —— **STEP 3-A 阶段确认为 163（未变）**，因为 schema_version 是纯新增字段，未增加测试。

进入 STEP 3-B 后新增 5 个测试函数，总数自然变为 **168**：

```
163（3-A 后基线）
 +5（3-B 新增：正常路径 / 无数据 / 异常 / idempotency / CLI）
=168
```

**0 regression**（原有 163 条全部保持通过）。2 条 warning 为既有 `test_quant_factor_validation.py::test_regime` 的 numpy/pandas 相关性告警，与本次无关。

### py_compile

```
python3 -m py_compile quant_factor_backtest.py tests/test_quant_factor_backtest.py
→ OK
```

---

## 5. Dashboard 未受影响（smoke test）

```
$ python dashboard_export.py --no-network --data-dir . --out /tmp/dash_smoke_3b.json
Core 数量            : 13
Observation 数量     : 21
history 条数         : 46
Quant 研究状态       : RESEARCH · 数据可用性 NOT_ENOUGH_DATA · 生产 V1 V1_ACTIVE · V2 DISABLED · Gate NOT_READY
```

| 数据 | 改动前 → 后 |
|---|---|
| stocks | 34 → 34 **[SAME]** |
| review.records | 391 → 391 **[SAME]** |
| history | 46 → 46 **[SAME]** |
| options | 0 → 0 **[SAME]** |

Quant 7 阶段状态保持正确：

| Phase | status |
|---|---|
| factor_lab | NOT_ENOUGH_DATA |
| backtest | NOT_ENOUGH_DATA |
| validation | NOT_ENOUGH_DATA |
| score_v2 | DISABLED |
| walk_forward | NOT_ENOUGH_DATA |
| shadow | SHADOW_DISABLED |
| production | V1_ACTIVE |

---

## 6. `git diff --stat`

```
 quant_factor_backtest.py            |  92 +++++++++++++--
 quant_factor_lab.py                 |   7 ++
 quant_factor_price.py               |   7 +-
 quant_factor_validation.py          |  10 ++
 quant_production.py                 |   8 ++
 quant_score_v2.py                   |   9 ++
 quant_shadow.py                     |  11 +-
 quant_walk_forward.py               |   7 ++
 tests/test_quant_factor_backtest.py | 220 ++++++++++++++++++++++++++++++++++++
 9 files changed, 359 insertions(+), 12 deletions(-)
```

- `quant_factor_backtest.py` 的 92 行 = R1 修复（替换 `_write_empty`）+ `main()` + schema_version
- 其余 7 个 quant 模块 = STEP 3-A 的 schema_version（各 7–11 行）
- `tests/test_quant_factor_backtest.py` = STEP 3-B 新增 5 个测试

**未修改**：任何 workflow、schedule、Phase 3–7 核心逻辑、旧架构（未删除 `_write_empty` 之外的任何既有函数）。

## 7. `git diff --check`

```
（无输出）
→ OK，无空白错误 / 冲突标记
```

---

## 8. 生产文件零污染确认

```
MISSING(正常): quant_factor_snapshot.csv
MISSING(正常): quant_factor_backtest.csv
MISSING(正常): quant_factor_summary.csv
MISSING(正常): quant_factor_validation.csv
```

- 未手工创建 snapshot
- 未 backfill
- 所有端到端验证均在 `/tmp` 临时目录内完成（CLI 演示 + 正常路径演示）
- **后台 Phase 1 监控未被干扰**，仍在等待今日 13:07 UTC 的 Scan

---

## 9. 生产安全状态（未改变）

| 项 | 值 |
|---|---|
| 当前生产模型 | V1 (`CURRENT_EXISTING_QUANT_SCORE`) |
| Quant V2 | DISABLED |
| Shadow | DISABLED |
| Production Gate | NOT_READY |
| V1 Final Score 公式 | 未触碰 |
| workflow / schedule | 未触碰 |

---

## 10. 需要你知晓的两点

| # | 说明 |
|---|---|
| T1 | **R1 只在 Phase 2 修复了。** Phase 3 (`_write_empty_outputs`) 与 Phase 5 (`_write_empty_outputs`) 仍有同样的"写空文件"行为。按你的指令本阶段不动 Phase 3–7 核心逻辑，所以留到 STEP 4–8 各自补测时同步修复。在 STEP 11（workflow 接线）之前必须全部修完 |
| T2 | Phase 3 的空输出会写 72 行全 `NOT_ENOUGH_DATA` 的合法"状态表"。它与 Phase 2 的空文件**性质不同**（它有内容、明确标了状态），但同样存在"看起来像有数据"的风险，建议 STEP 4 一并评估是否改为不落文件 |

---

## 11. 下一步

STEP 3-A + 3-B 完成，等待你按五项清单验收：

1. ✅ 提交来源（见 SCHEMA_VERSION_REPORT.md 第 1 节）
2. ✅ schema_version 一致性（8 个 Phase，统一 `phaseN.v1`）
3. ✅ Phase 2 main() 无数据行为（已断言不落文件）
4. ✅ 测试 **168 passed**（163 基线 + 5 新增，0 regression）
5. ✅ git diff 范围（9 个文件，均为本次该动的范围）

验收通过后进入 **STEP 4–8**（Phase 3/4/5/6/7 各自补测 + 各自的 R1 同类修复），然后 **STEP 9**（跨阶段集成测试），最后 **STEP 11**（workflow 接线，需单独确认）。

---

*STEP 3-B 报告结束 · commit 0 · push 0 · 生产写入 0*
