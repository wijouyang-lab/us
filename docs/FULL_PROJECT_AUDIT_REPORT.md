# 全项目程序实跑 + 只读深度审计报告

> 审计时间：2026-10-07 · 方式：READ-ONLY + ISOLATED EXECUTION（所有写入在 /tmp 隔离目录）
> 主工作区：**0 修改、0 commit、0 push** · HEAD `24b2e9b` == origin/main ✅

---

## A. 总体结论

**PASS WITH WARNINGS**

程序整体健康、可继续运行，但发现 1 个 P1 数据精度问题（价格浮点噪声）和若干 P2/P3 问题。无 P0（无数据错误/策略错误/生产安全/V2 误启用）。

---

## B. 实际运行结果

| 组件 | 结果 | 说明 |
|---|---|---|
| Scan | **BLOCKED** | 沙箱缺 CLAWSOCKET 环境变量 + 3.12 缺 pandas；当前时点（美东 00:30 EDT 周三）= PREMARKET_NOT_STARTED，本就不运行 |
| Review | **BLOCKED** | 沙箱缺 anthropic 依赖（pip 安装遇 typing_extensions 冲突）；生产 workflow 会安装 |
| Portfolio | **PASS** | 隔离运行成功，幂等验证通过 |
| Dashboard Export | **BLOCKED** | yfinance 限流（YFRateLimitError）导致 90s 超时未完成；非代码错误 |
| Quant Phase 1 | **PASS** | import OK，33 列 |
| Quant Phase 2 | **PASS** | 空数据 → NOT_ENOUGH_DATA |
| Quant Phase 2B | **PASS** | 空数据 → NO_SNAPSHOT |
| Quant Phase 3 | **PASS** | 空数据 → 72 行全 NOT_ENOUGH_DATA，N=0 时 Win_Rate 空（非 0） |
| Quant Phase 4 | **PASS** | ENABLED=False，3 模型全 NOT_ENOUGH_DATA |
| Quant Phase 5 | **PASS** | window_count=0，4 模型全 NOT_ENOUGH_DATA |
| Quant Phase 6 | **PASS** | SHADOW_DISABLED，5D/10D/20D 全 NOT_ENOUGH_DATA |
| Quant Phase 7 | **PASS** | V1_ACTIVE / V2 disabled / gate NOT_READY |

---

## C. 真正发现的问题（按优先级）

| Priority | Component | Problem | Evidence | Impact | Next Step |
|---|---|---|---|---|---|
| **P1** | review.py / 数据 | **价格浮点噪声未 round**：`backfill` 回填 Rec_Price 时 `str(new_price)` 未 `round(...,2)` | trade_history 155 条 Price 含 `479.8800048828125`；review_history Rec_Price 同样噪声；最新 2026-10-06 仍在产生 | Buy Price 显示污染，违反"2 位小数"约定；前端可能显示 `$483.2999877929688` | 修复 review.py:2535 及 backfill 逻辑，补 round(...,2)（需你授权，本次未改） |
| **P2** | 测试框架 | **pytest 无法收集**：测试是脚本式（模块级 `sys.exit`），`pytest -q` 报 INTERNALERROR | `pytest -q` → `SystemExit`，no tests ran | CI 无法用 pytest 统一跑；只能逐个 `python tests/*.py` | 可选：改为标准 pytest 风格（def test_ 无模块级 exit） |
| **P2** | 重复逻辑 | **Forward Return 两处定义**：`forward_return_nd`(backtest) 与 `compute_forward_return`(shadow) 同公式不同名 | 两文件各实现一次 | 未来口径漂移风险 | 可选：统一到一个共享函数 |
| **P3** | scan.py | **3.11 语法错误**（第 2497 行 f-string 反斜杠），3.12 正常 | py_compile 3.11 失败 | 非生产路径（scan.yml 用 3.12） | 可选：改用跨版本兼容写法 |
| **P3** | workflow | **Python 版本不一致**：scan/review/evolve 用 3.12，dashboard-data 用 3.11 | 4 个 workflow 两个版本 | 轻微维护负担 | 可选：统一 |
| **P3** | 死代码 | `build_full_email_html` 定义但零调用；Phase 3/4/5/6/7 模块有 `__main__` 但无 workflow 调用 | grep 确认 | 无功能影响 | 可选：清理或接入 |
| **P3** | Email 残留 | workflow 仍注入 `EMAIL_*` secrets，但生产代码无 SMTP 消费 | grep 确认 | 无实际影响 | 可选：清理 secrets（非 P0） |

---

## D. 最重要的 5 个问题

1. **P1 价格浮点噪声**：review.py 回填 Rec_Price 未 round，155 条 Buy Price 污染，仍在新产生。
2. **P2 pytest 不可用**：623/623 只能脚本式跑，标准 pytest 无法收集。
3. **P2 Forward Return 双实现**：backtest 与 shadow 各写一份，有口径漂移风险。
4. **P3 Python 版本分裂**：3.11/3.12 混用，scan.py 在 3.11 下语法报错。
5. **P3 Quant 3-7 无 workflow 入口**：模块齐全但未接入任何定时任务（Phase 1/2B 已接 scan.yml，其余纯手动/研究态）。

---

## E. 已确认无问题的关键模块

- ✅ **Quant V2 Production Lock**：即使 Phase3/5/6 全 PASS，无 Human Approval → gate=NOT_READY，V2 仍阻止
- ✅ **Portfolio 幂等**：第二次运行无重复初始化，transactions 仍仅表头
- ✅ **Concurrency Guard**：dashboard-data.yml 的 `reset --soft → reset HEAD → add allowed → scope guard` 完整存在
- ✅ **NOT_ENOUGH_DATA 传递链**：Phase 1→7 空数据全部正确传递，N=0 无伪 Win_Rate/Return
- ✅ **cron 正确**：scan `7 13 * * 1-5`、review `0 22 * * 1-5`、evolve `0 2 * * 6`、dashboard `*/15`
- ✅ **数据链接口一致**：Phase 间字段名（Forward_Return_ND/Win_ND/Status/Evidence_Status/模型名）全部对上，无 KeyError/Schema mismatch
- ✅ **0 语义正确**：PnL_Pct 无 0 填充缺失（0 条），空值用空串；研究模块 N=0 → None

---

## F. 是否建议下一步修改代码

**建议修复（按顺序）**，但**本次未改任何代码**，等你确认：

1. review.py 价格回填补 `round(...,2)`（P1，最优先）
2. 统一 Forward Return 为单一共享函数（P2）
3. （可选）测试改 pytest 风格（P2）
4. （可选）清理 Email secrets + 死代码（P3）

---

## G. Git 状态

| 项 | 值 |
|---|---|
| HEAD | `24b2e9b14430393d7bc726eb0bf9ae4effb9b75b` |
| origin/main | 同 HEAD（TRUE） |
| clean/dirty | **clean**（modified=0，仅 untracked __pycache__） |
| commit/push | 0 / 0 |

---

## H. 测试

| 项 | 结果 |
|---|---|
| 全量（脚本式，项目实际方式） | **623 / 623 PASS**（18 文件） |
| pytest -q | **无法收集**（脚本式 sys.exit，INTERNALERROR） |
| py_compile（3.12 生产） | 12 生产文件全 PASS |
| py_compile（3.11） | scan.py 报错（f-string 反斜杠），其余 PASS |
| YAML | 4 workflow 语法正常（未做深度校验） |
| node --check | 无 JS 改动，不适用 |

---

## I. 性能

| 项 | 观察 |
|---|---|
| Scan | 未完成（环境变量缺失），无法测时 |
| Review | 未完成（anthropic 缺失） |
| Portfolio | < 1 秒（空持仓初始化 + 幂等验证） |
| Dashboard Export | 因 yfinance 限流 90s 超时（外部限流，非性能缺陷） |
| Quant 1→7 | 全空数据链 < 1 秒 |

---

## J. 最终判断

**当前程序适合继续正常运行。** 核心结论：

- **V1 安全、Active**；**V2 禁用、未批准** —— 生产锁完整有效。
- 唯一需要尽快处理的实质问题是 **P1 价格浮点噪声**（review.py 回填未 round），它污染 Buy Price 显示且仍在产生，但**不影响 PnL 计算精度**（误差 <1e-4）。
- 其余为 P2/P3 的架构清理项（pytest 风格、重复函数、版本统一、死代码），不影响运行正确性。

**本次全程未修改任何文件、未 commit、未 push、未产生假数据、未启用 V2。**
