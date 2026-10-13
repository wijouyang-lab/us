# Options Risk / Reward-Risk 改造 — 完整实施报告

> 执行方式：自主闭环（只读审计 → 设计 → 实现 → 测试 → Code Review → 修复 → 复测 → 静态检查 → 验收）
> 完成时刻：2026-10-02（GMT+8）
> **未 commit、未 push**（工作区仅修改）

---

## 1. Executive Summary

### 原问题

系统会把 Reward/Risk 远低于用户要求的期权策略标记为 `Status = Active`。

实测案例（`option_strategies.csv` 中真实存在）：

| 字段 | 值 |
| --- | --- |
| Ticker / Strategy | ALL / SHORT_PUT |
| Strike / Premium | 210 / 3.70 |
| Max Profit | $370 |
| **Max Loss** | **$20,630** |
| 理论 Reward/Risk | **0.0179** |
| 原 Status | **Active** ❌ |

### 根因

`scan_us_option_engine.py` 中 **Status 是无条件硬编码**：

```python
"Status":"Active","Quantity":1,     # line 598（改造前）
```

同时：
- `SHORT_PUT` 的 `reward_risk` 恒为 `None`（从不计算），CSV `RewardRisk` 字段为空
- 唯一的 R/R 常量 `MIN_SPREAD_REWARD_RISK = 0.40` **只用于 Call 价差的候选结构筛选**，不覆盖 Short Put，也不是最终交易门槛
- 下游 Dashboard（`dashboard_export.py`）与前端（`app.js`）**均不过滤 status**

结果：全表 10 条策略无一条达到 2.0，却全部 Active。

### 修复结果

新增**最终交易资格门槛** `MIN_REWARD_RISK = 2.0`，与候选筛选门槛（0.40）严格分离；
Status 由硬编码改为判定；Dashboard / 前端 / Email / Review 同步只放行通过门槛的策略；
Rejected 数据完整保留在 CSV 底层（未删除、未重写历史）。

**Max Loss 定义全程未改动**——`(210 − 3.70) × 100 = 20,630` 仍是原值。

---

## 2. Code Review Findings

| 文件 | 位置 | 原问题 | 风险 | 修复 |
| --- | --- | --- | --- | --- |
| `scan_us_option_engine.py` | line 598 | `"Status":"Active"` 无条件硬编码 | 任何策略都会被当成可执行推荐 | 改为 `evaluate_trade_eligibility()` 判定结果 |
| `scan_us_option_engine.py` | line 362 | SHORT_PUT 的 `reward_risk` 恒为 `None` | 无从判断盈亏比 | 由统一 `theoretical_reward_risk()` 计算落库 |
| `scan_us_option_engine.py` | 全局 | 无最终 R/R 门槛；`MIN_SPREAD_REWARD_RISK=0.40` 被误当成唯一门槛 | 1.44 的价差也能成为 Active | 新增 `MIN_REWARD_RISK=2.0`，两概念分离 |
| `scan_us_option_engine.py` | line 420-421 | 价差 `max_profit/max_loss` 已 `round(2)` | 用 round 后的值做 gating 会失真 | 额外保留 `_raw_max_profit/_raw_max_loss` 供 gating |
| `dashboard_export.py` | `build_options` | 读取 status 但**不过滤**，全部输出 | Rejected 仍会展示给用户 | 新增 `is_actionable_option()` 并在输出层过滤 |
| `dashboard_export.py` | `build_options` | 无 `reward_risk` / `reject_reason` 字段 | 下游无法判定 | 新增两字段透传（reward_risk 保留原始精度） |
| `app.js` | line 152 | `OPTIONS = data.options \|\| []` 无过滤 | 前端展示所有记录 | `OPTIONS = (...).filter(isActionableOption)` |
| `app.js` | 全局 | 无 Actionable 判定 | 无法防御脏数据 | 新增 `isActionableOption()` |
| `review.py` | line 918 | 已按 `Status == "Active"` 过滤 | **无问题** | **未修改**（最小改动原则） |
| `scan.py` | line 645 数据源 | `get_recent_option_recommendations` 已过滤 Active | **无问题** | **未修改** |

---

## 3. Implementation

| 文件 | 改动类型 | 说明 |
| --- | --- | --- |
| `scan_us_option_engine.py` | 主要改动 | 新增 `MIN_REWARD_RISK=2.0` 与两个 Reject 原因常量；新增 `_safe_num()` / `_valid_qty()` / `theoretical_reward_risk()` / `evaluate_trade_eligibility()`；价差保留 raw 值；Status 改为判定；CSV columns 追加 `Reject_Reason` |
| `dashboard_export.py` | 小改动 | 新增 `MIN_ACTIONABLE_REWARD_RISK=2.0` 与 `is_actionable_option()`；`build_options` 透传 `reject_reason` / `reward_risk`；输出层过滤；新增 `rejected_options_count` 统计 |
| `app.js` | 小改动 | 新增 `isActionableOption()`；`OPTIONS` 赋值时过滤 |
| `tests/test_options_reward_risk.py` | **新增** | 80 项测试 |

```
git diff --stat
 app.js                   |  19 +++++++-
 dashboard_export.py      |  42 +++++++++++++++++-
 scan_us_option_engine.py | 111 +++++++++++++++++++++++++++++++++++++++++++++--
 3 files changed, 166 insertions(+), 6 deletions(-)
```

---

## 4. Reward/Risk Logic

所有策略统一使用 **Theoretical Reward/Risk**（当前项目不存在可执行的 Planned Risk 数值字段，StopLoss 为纯文本描述，故**未伪造** ATR / MA / Support / 百分比等风险数字）。

### SHORT PUT（Cash-Secured）

```
MaxProfit = premium × 100 × qty          = 3.70 × 100 × 1 = 370
MaxLoss   = (strike − premium) × 100 × qty = (210 − 3.70) × 100 × 1 = 20630
RewardRisk = MaxProfit / MaxLoss         = 370 / 20630 ≈ 0.0179
```
→ `< 2.0` ⇒ **Rejected**

### CALL DEBIT SPREAD

```
MaxProfit = (width − debit) × 100 × qty  = (5 − 2.05) × 100 = 295
MaxLoss   = debit × 100 × qty            = 2.05 × 100 = 205
RewardRisk = 295 / 205 ≈ 1.439
```
→ `< 2.0` ⇒ **Rejected**（即便已跨过 0.40 候选门槛）

### LONG CALL

当前代码 `max_profit = None`（收益无上限、无可靠目标价）⇒ `RewardRisk` 无法计算
⇒ **Rejected / Reward/Risk unavailable**（不因是 Long Call 而默认 Active）

---

## 5. Gate（最终交易资格门槛）

```python
MIN_REWARD_RISK = 2.0          # final actionable trade gate（新增）
MIN_SPREAD_REWARD_RISK = 0.40  # candidate / structure selection（保留不动）
```

| 条件 | Status | Reject_Reason |
| --- | --- | --- |
| `rr >= 2.0` | **Active** | `""` |
| `rr < 2.0` | **Rejected** | `Reward/Risk below 2.0` |
| `rr` 无法可靠计算（None / NaN / inf / 非数字 / max_loss≤0 / qty 无效） | **Rejected** | `Reward/Risk unavailable` |

- **不存在** `unknown → Active`、**不存在** `None → Active`
- gating 使用 **raw 浮点值**；`1.999` 即使显示为 `2.00` 仍 Rejected
- 落库 `RewardRisk` 保留 10 位精度，Dashboard JSON 不 round，双重避免 rounded gating

---

## 6. User Example（真实引擎代码路径验证）

```
==========================================================
  用户真实案例 · Options Engine 真实代码路径验证
==========================================================
  Strategy      : SHORT_PUT
  Ticker        : ALL  (Underlying $224.88)
  Strike        : 210.0   Expiry 2026-11-20  DTE 50
  Premium       : $3.7   Qty 1
  Max Profit    : $370.00
  Max Loss      : $20,630.00
  Break Even    : 206.3
----------------------------------------------------------
  Reward/Risk   : 0.02   (内部 raw = 0.0179350460)
  Status        : Rejected
  Reject Reason : Reward/Risk below 2.0
==========================================================
  Max Loss 公式校验: (210 - 3.70) x 100 = 20,630.00  -> 未被篡改
  判定: RR 0.0179 < 2.0 -> Rejected
==========================================================
```

> 显示 `0.02`，内部保持 `≈ 0.0179`；**Max Loss 未被修改**。

---

## 7. Dashboard

- `dashboard_export.py` 输出层：`options = [o for o in all_options if is_actionable_option(o)]`
- 前端 `app.js`：`OPTIONS = (data.options || []).filter(isActionableOption)`（双保险）
- **结论：Rejected 不会出现在 Actionable Options**
- Rejected **仍完整保留**在 `option_strategies.csv` 底层与 `all_options` 中，新增 `review["rejected_options_count"]` 供审计/统计
- 历史遗留记录（`Status=Active` 但 `RewardRisk` 为空）也被 `is_actionable_option` 判定为不可 Actionable（RR unavailable 不默认通过）

---

## 8. Review

- `review.py: load_option_positions()` 原本即按 `Status == "Active"` 严格过滤（line 918），`close_option_position()` 同样只匹配 Active
- **结论：Rejected（Status="Rejected"）不会进入 Active Positions**
- **未修改 review.py**（已正确，遵循最小改动）
- Dashboard 侧新增 `rejected_options_count`，与 `active_options_count` 严格分开统计

---

## 9. Email

- 邮件数据源为 `scan_us_option_engine.get_recent_option_recommendations()`，其已按 `Status == "Active"` 过滤
- **结论：Rejected 不会进入最终推荐列表**
- **未修改 scan.py**（已正确使用过滤后的数据源，无 Status 硬编码兜底）
- 运行时验证：临时 CSV（1 Active + 2 Rejected）→ 仅返回 `['WIN']`

---

## 10. Tests

| Test | 内容 | 结果 |
| --- | --- | --- |
| Test 1 | 用户案例 210/3.70/1 → 370 / 20630 / RR≈0.0179 / Rejected | ✅ PASS |
| Test 2 | RR = 2.0 → Active | ✅ PASS |
| Test 3 | RR = 1.99 → Rejected | ✅ PASS |
| Test 4 | RR = 1.999（显示 2.00）→ Rejected | ✅ PASS |
| Test 5 | Call Spread RR=1.44 → Rejected；RR=2.0 → Active；0.40 未被改成 2.0 | ✅ PASS |
| Test 6 | Long Call（MaxProfit=None）→ Rejected / unavailable | ✅ PASS |
| Test 7 | None 输入 → Rejected（不默认 Active） | ✅ PASS |
| Test 8 | NaN / inf → Rejected | ✅ PASS |
| Test 9 | MaxLoss=0 / 负 / qty 无效 / 非数字 → Rejected，不除零 | ✅ PASS |
| Test 10 | Dashboard：Active/Rejected/Rejected → 只剩 Active | ✅ PASS |
| Test 11 | Review：Rejected 不进入 Active Position | ✅ PASS |
| Test 12 | Email：Rejected 不进入推荐列表 | ✅ PASS |
| Test 13 | 真实引擎代码路径（mock 期权链，走 `build_option_recommendation`） | ✅ PASS |
| Test 14 | Invariant：无「RR<2.0 却 Active」/「RR unavailable 却 Active」 | ✅ PASS |
| Test 15 | Dashboard 端到端 `build_options` → Actionable 过滤 | ✅ PASS |

### 完整测试数量

| 测试文件 | 结果 |
| --- | --- |
| `tests/test_options_reward_risk.py`（新增） | **80 / 80** ✅ |
| `tests/test_dashboard_runtime.py` | 19 / 19 ✅ |
| `tests/test_event_key_p2.py` | 15 / 15 ✅ |
| `tests/test_milestone_win_rate.py` | 16 / 16 ✅ |
| `tests/test_p05_repair_regression.py` | 45 / 45 ✅ |
| `tests/test_p3_5_rec_price_repair.py` | 12 / 12 ✅ |
| `tests/test_p3_data_quality.py` | 16 / 16 ✅ |
| **合计** | **203 / 203 全部通过** |

> 项目测试为脚本式（无 pytest 配置），已按项目现有方式 `python3.11 tests/xxx.py` 完整运行。

---

## 11. Static Checks

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| Python 编译（3.11） | `python3.11 -m py_compile scan_us_option_engine.py dashboard_export.py review.py` | ✅ OK |
| Python 编译（3.12，含 scan.py） | `python3.12 -m py_compile scan.py review.py dashboard_export.py scan_us_option_engine.py` | ✅ OK |
| JavaScript 语法 | `node --check app.js` | ✅ OK |
| 空白/冲突检查 | `git diff --check` | ✅ OK（无输出） |

> 注：`scan.py` 使用了 Python 3.12+ 的 f-string 语法（反斜杠），需在 3.12 下编译，与本任务无关（`scan.py` 未修改）。

---

## 12. Final Code Review（逐项明确回答）

| 检查项 | 结论 |
| --- | --- |
| **是否存在低于 2.0 的 Active Option？** | ❌ **不存在**。Invariant 测试（Test 14）+ 端到端（Test 15h）均验证通过 |
| **是否存在 RR unavailable 的 Active Option？** | ❌ **不存在**。`rr is None` 一律 `Rejected / Reward/Risk unavailable` |
| **是否修改了 MaxLoss 定义？** | ❌ **未修改**。`(strike − premium) × 100` 原样保留，实测 20,630 未变 |
| **是否修改了 Runtime？** | ❌ **未修改**（`dashboard/fetch_runtimes.py` 等未触碰） |
| **是否修改了 Schedule？** | ❌ **未修改**（`.github/workflows/*` 未触碰） |
| **是否修改了股票逻辑？** | ❌ **未修改**（`scan.py` 未改动） |
| **是否修改了数据源？** | ❌ **未修改**（期权链读取逻辑未动） |
| **是否修改 AI 模型？** | ❌ **未修改** |
| 是否把 candidate threshold 当成 final threshold？ | ❌ 否。`MIN_SPREAD_REWARD_RISK=0.40` 保留，另立 `MIN_REWARD_RISK=2.0` |
| 是否残留 `"Status": "Active"` 硬编码？ | ❌ 已消除（引擎、scan.py 均无） |
| 是否存在 `if rr is None: status = "Active"`？ | ❌ 不存在（实际为 `Rejected`） |
| NaN 是否导致比较异常？ | ❌ `_safe_num()` 用 `math.isfinite` 过滤，前端 `num()` 检查 `isFinite` |
| 是否存在 rounded gating（1.999→2.00→Active）？ | ❌ gating 全程用 raw 值；CSV 存 10 位，Dashboard JSON 不 round |
| Dashboard 是否仍显示 Rejected？ | ❌ 不显示（导出层 + 前端双重过滤） |
| Review 是否仍把 Rejected 当 Active Position？ | ❌ 不会（按 Status 过滤，Rejected 不匹配） |
| Email 是否仍输出 Rejected？ | ❌ 不会（数据源已过滤 Active） |
| 是否误删原有功能？ | ❌ 无删除，仅新增 + 2 处精确替换 |
| 是否修改无关文件？ | ❌ 仅 3 个业务文件 + 1 个新增测试 |
| 是否引入循环依赖？ | ❌ 无新增 import |
| 是否破坏 CSV schema？ | ❌ `Reject_Reason` 追加到末尾；缺列时由既有 `if c not in old.columns: old[c]=""` 补空 |
| 是否破坏历史数据读取？ | ❌ 未破坏；历史记录无 `Reject_Reason` 时为空，无 `RewardRisk` 时判定为 unavailable |
| **是否 Commit？** | ❌ **未 commit** |
| **是否 Push？** | ❌ **未 push** |
| **历史 CSV 是否未被重写？** | ✅ **未重写**（`git diff -- option_strategies.csv` 无输出） |

---

## 13. 验收标准核对

| 项 | 状态 |
| --- | --- |
| MAX LOSS 定义正确 | ✅ |
| SHORT PUT RR 正确 | ✅ |
| CALL DEBIT SPREAD RR 正确 | ✅ |
| LONG CALL RR 有可靠定义，否则 Rejected | ✅（无可靠定义 → Rejected） |
| MIN_REWARD_RISK = 2.0 | ✅ |
| RR >= 2.0 才 Active | ✅ |
| RR < 2.0 必须 Rejected | ✅ |
| RR unavailable 必须 Rejected | ✅ |
| None/NaN/Zero Risk 安全处理 | ✅ |
| 使用 raw RR gating | ✅ |
| Display rounding 不影响 gating | ✅ |
| 用户 210 PUT 正确 Rejected | ✅ |
| 1.99 正确 Rejected | ✅ |
| 2.0 正确 Active | ✅ |
| Call Spread 1.44 正确 Rejected | ✅ |
| Dashboard 只显示 Active Actionable Options | ✅ |
| Rejected 保留在底层数据 | ✅ |
| Review 不把 Rejected 当 Active Position | ✅ |
| Email 不推荐 Rejected | ✅ |
| 历史 CSV 未被重写 | ✅ |
| Runtime 未修改 | ✅ |
| Schedule 未修改 | ✅ |
| 股票扫描未修改 | ✅ |
| 数据源未修改 | ✅ |
| AI 模型未修改 | ✅ |
| 无无关代码删除 | ✅ |
| 全部测试通过（203/203） | ✅ |
| 静态检查通过 | ✅ |
| git diff --check 通过 | ✅ |
| 未 commit | ✅ |
| 未 push | ✅ |
| 最终报告生成 | ✅ |

---

# ✅ IMPLEMENTATION COMPLETE

改造已完成并全部验收通过。工作区修改（未提交，等待你决定是否 commit）：

```
 M app.js
 M dashboard_export.py
 M scan_us_option_engine.py
?? tests/test_options_reward_risk.py   （新增）
```

**预期影响**：下一次 Scan 运行时，现有 10 条策略（RR 0.018–1.44）将全部被重新生成为 `Rejected`；
在出现真实满足 RR ≥ 2.0 的结构之前，Dashboard 的 Actionable Options 将为空——这是规则的真实结果，非缺陷。
