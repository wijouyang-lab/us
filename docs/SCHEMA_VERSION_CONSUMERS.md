# schema_version 消费方预调查

> 生成日期：2026-10-11 21:15（GMT+8）｜ 性质：**只读预调查，未改任何文件**
> 目的：评估「Phase 1 snapshot 加列（phase1.v1 → phase1.v2）」是否会破坏下游消费方，从而决定要不要升 version。

---

## 1. 全仓 grep 结果（`schema_version\|phase1\|phase2\|phase2b`）

| 文件:行 | 角色 | 出现内容 |
|---|---|---|
| `quant_factor_lab.py:89` | **生产者** | `SCHEMA_VERSION = "phase1.v1"`（snapshot 输出） |
| `quant_factor_lab.py:80,248` | 生产者 | `schema_version` 列 + 写出 |
| `quant_factor_price.py` | 生产者 | price_history = `phase2b.v1`（`test_*.py:211,253` 印证） |
| `quant_factor_backtest.py:65,410,415` | 生产者/覆盖 | `phase2.v1`，写出前**强制覆盖**上游 phase1 标记 |
| `quant_factor_validation.py:73` | 生产者 | `phase3.v1` |
| `quant_score_v2.py:69` | 生产者 | `phase4.v1` |
| `quant_walk_forward.py:78` | 生产者 | `phase5.v1` |
| `quant_shadow.py:71` | 生产者 | `phase6.v1` |
| `quant_production.py:78` | 生产者 | `phase7.v1` |
| `dashboard/fetch_news.py:50,393` | 生产者 | `news.v1` |
| `scan.py:1953` / `test_macro_panel*.py` | 生产者/消费 | `macro.v1` |
| `quant_research_runner.py:37-38` | **消费方** | inputs 期望 `quant_factor_snapshot.csv → phase1.v1`、`price_history → phase2b.v1` |
| `quant_research_runner.py:73-107` | 消费逻辑 | `_read_schema_version` + `_precheck` |
| `tests/test_quant_research_runner.py:50-52` | 测试 | 占位输入写 `phase1.v1` / `phase2b.v1` / `phase2.v1` 末行 |

---

## 2. 每个 schema_version 的消费方与校验强度

| 版本 | 消费方 | 期望值 | 校验性质 |
|---|---|---|---|
| `phase1.v1`（snapshot） | `quant_research_runner.py:37` | `phase1.v1` | **软警告**（见 §3 代码证据） |
| `phase2b.v1`（price_history） | `quant_research_runner.py:38` | `phase2b.v1` | **软警告** |
| `phase2.v1`（backtest） | `quant_factor_backtest.py` 自身读取上游 snapshot 但**直接覆盖**为 phase2.v1 | 不限 | 写覆盖，无硬依赖 |
| `phase3.v1` ~ `phase7.v1` | 各自 Phase 模块 | 自产自销 | 无外部硬校验 |
| `macro.v1` | `dashboard_export.build_macro` | 不校验（只读 dict 结构） | 无校验 |
| `news.v1` | `dashboard/fetch_news` 自产，`test_fetch_news` 断言 | `news.v1` | **测试断言**（仅测试层，非运行时） |

### §3 代码证据：`_precheck` 是软校验（关键）

`quant_research_runner.py:96-107`：

```python
def _precheck(spec, workdir):
    warnings = []
    for fname, expected in spec.get("inputs", []):
        fpath = os.path.join(workdir, fname)
        if not os.path.exists(fpath) or os.path.getsize(fpath) == 0:
            return False, "输入缺失或为空: %s" % fname, warnings   # ← 仅文件缺失才 False
        if expected is not None:
            actual = _read_schema_version(fpath)
            if actual is not None and actual != expected:
                warnings.append(...)                               # ← 版本不符仅追加 warning
    return True, None, warnings                                     # ← ok 仍为 True，Phase 照常跑
```

**结论**：`phase1.v1` 不匹配时，`ok` 仍为 `True`，Phase 2–6 **照常执行**，只在结果 dict 里带一条 `schema_warnings`（R1 既定降级展示行为）。**全仓没有任何对 `phase1.v1` 的硬校验（hard-check）。**

---

## 4. 关键判断：Phase 1 加列要不要升 version？

1. **有消费方 hard-check `phase1.v1` 吗？** → **没有**。唯一消费方 `quant_research_runner` 是软警告；其他 Phase 模块全部自产自销；`dashboard_export` 按列名读取（加列不影响旧列解析）；`quant_factor_backtest` 写出时强制覆盖。
2. **加列是否改变语义？** → 否。纯**追加列（additive column）**，旧 34 列含义、顺序、取值全部不变，下游按列名/位置读取均向后兼容。
3. **STEP 3-A 约定怎么说？** → "字段结构变更时递增主版本号"。加列属于结构变更，**约定层面建议递增**。

### 结论
- **功能性上不升版本也不会坏**（无硬校验 + 纯追加）→ 保守做法可直接加列、保持 `phase1.v1`。
- **但为遵守 STEP 3-A 约定、让下游显式感知结构变化**，建议**升到 `phase1.v2`**。代价极小：仅 `quant_research_runner.py:37` 的期望值字符串 + 测试占位（`test_quant_research_runner.py:50`）同步改成 `phase1.v2`，且改后只产生一条软警告的消除（本就无害）。

### 受影响文件清单（若升 v2）
| 文件 | 改动 |
|---|---|
| `quant_factor_lab.py` | `SCHEMA_VERSION = "phase1.v2"`（L89）+ 列加 15 个 |
| `quant_research_runner.py` | inputs 期望值 `phase1.v1` → `phase1.v2`（L37） |
| `tests/test_quant_research_runner.py` | 占位末行 `phase1.v1` → `phase1.v2`（L50） |
| `tests/test_quant_factor_*`（如有快照断言） | 列数断言 +15 |
| 下游 `dashboard_export.py` / Phase 2–6 | **无需改**（按列名/覆盖语义兼容） |

> 若选择**不升版本**（保持 `phase1.v1`），则仅改 `quant_factor_lab.py` 一处 + 测试列数断言，**受影响文件最少**。

---

## 附：铁律确认
- 本文件为**只读预调查**；`quant_research_runner.py` / `quant_factor_lab.py` 等**未改动**；
- 未执行 `git push` / `git rebase`；未调用任何 AI。
