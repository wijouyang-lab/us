# P2：pytest Test Runner 标准化专项 — 交付报告

> 历史快照：本文记录的是当时（2026-10-13）的测试基线。当前基线见 HANDOVER.md。

## 结论：`pytest -q` 现已成为标准测试入口，152 个测试单元全通过，0 INTERNALERROR

| 项 | 结果 |
|---|---|
| pytest -q | ✅ **152 passed, 2 warnings, ~10s**（无 INTERNALERROR） |
| 旧脚本式 `python tests/*.py` | ✅ 20 个文件全通过 |
| HEAD == origin/main | ✅ **TRUE**（`fc02fcd`） |

---

## 1. INTERNALERROR 根因

pytest 在 **collection 阶段会 import 每个 `test_*.py` 文件**。仓库中有 **10 个"脚本式"测试文件**（如 `test_dashboard_data_stability.py`、`test_options_reward_risk.py`、`test_portfolio_50000.py` 等）采用**模块级执行 + 尾部 `sys.exit(0/1)`** 结构，没有 `if __name__ == "__main__"` 守卫。pytest import 时触发模块级 `SystemExit`，直接抛 `INTERNALERROR`（`caught unexpected SystemExit!`），导致 `no tests ran`。

## 2. 修改了哪些 tests（只改测试运行方式，不改测试语义）

**改动 10 个"函数式"测试文件**（`test_quant_*.py` / `test_forward_return_unified.py` / `test_trade_history_quality.py`）：
- `check()` 从"FAIL 只记录 + print"改为 **"FAIL 时 raise AssertionError"**（pytest 可正确捕获 FAIL）
- `main()` 从"逐个直接调用"改为 **"try/except 循环"**（脚本模式仍能汇总 FAIL 并 `sys.exit(0/1)`）
- 清理 dead code 计数变量（`_passed/_failed/_failures` / `passed/total`）

**新增 2 个**：
- `tests/conftest.py`：`collect_ignore` 跳过 10 个脚本式文件的 import（避免 SystemExit）
- `tests/test_script_runner.py`：`@pytest.mark.parametrize` 以 **subprocess** 运行 10 个脚本式文件，退出码 0 = PASS

**10 个脚本式文件（类型 A）零改动**，保持 `python tests/test_xxx.py` 原样运行。

## 3. 为什么不改变测试语义

- **assertion / 测试输入 / 期望输出 / factor formula / trade history rules / Forward Return / Portfolio / Production Lock 全部未动** —— 仅改了 `check()` 的 FAIL 表达方式（print → print + raise）和 `main()` 的调用方式（直接调用 → try/except 循环）。
- 脚本式文件（类型 A）**一个字节未改**，subprocess 运行的是完全相同的脚本。

## 4/5. 两种方式结果

| 方式 | 结果 |
|---|---|
| `pytest -q` | **152 passed**（142 个 `test_` 函数 + 10 个 subprocess 脚本） |
| `python tests/test_*.py`（20 文件） | 全部通过（类型 A：30/30、38/38 等；类型 B：10/10、12/12、22/22 等） |

## 6. pytest 与 663 的覆盖关系（无漏测）

旧脚本式的 **663 = 663 个 `check()` 断言**（分布在 20 个文件）。改造后：

| 层 | 旧（脚本式） | 新（pytest） |
|---|---|---|
| 函数式 10 文件 | 354 个 check 断言 | 142 个 `test_` 函数（内部覆盖同样的 354 个 check，FAIL 由 raise 上报） |
| 脚本式 10 文件 | 309 个 check 断言 | 10 个 `test_script` subprocess（运行完整脚本，覆盖同样的 309 个 check） |
| **合计** | **663 个 check 断言** | **152 个测试单元，覆盖全部 663 个 check 行为** |

即：**663 是 check 断言粒度，152 是 pytest 测试单元粒度**。断言一个未少，只是从"逐 check"归组为"逐函数/逐脚本"。pytest 的 152 个测试单元跑通，等价于 663 个 check 全部通过。

## 7. 是否存在漏测：**无**

pytest 的 142 个 test 函数 = 类型 B 全部 test 函数；10 个 test_script = 类型 A 全部 10 个脚本。20 个测试文件 100% 覆盖。

## 8. Production code 是否 0 修改：**是**

scan.py / review.py / portfolio_50000.py / dashboard_export.py / 全部 quant 模块 / trade_history / review_history **零改动**（逐文件核对确认）。仅改动 `tests/` 下的 10 个测试文件 + 新增 2 个测试基础设施文件。

## 9-11. 验证

| 项 | 结果 |
|---|---|
| pytest -q | 152 passed |
| 脚本式全量（20 文件） | 全通过 |
| py_compile（21 个 tests 文件 + conftest） | 全 PASS |
| git diff --check | PASS |
| 生产代码回归 | 0 修改 |

## 12-13. Git

| 项 | 值 |
|---|---|
| commit SHA | `fc02fcd`（rebase 前 `84e3698`） |
| push | ✅ 无 force（`848bf26..fc02fcd`） |
| HEAD == origin/main | ✅ **TRUE** |

---

## 一句话总结

根因是脚本式测试文件的模块级 `sys.exit` 在 pytest collection 阶段触发 SystemExit。修复分两路：函数式测试的 `check()` 改为 FAIL 抛 AssertionError（pytest 可捕获），脚本式测试用 `collect_ignore` 跳过 import 并由 subprocess 运行。pytest 现在能正常收集 152 个测试单元并全部通过，且覆盖了原 663 个 check 断言的完整行为，两种运行方式（pytest / 脚本）均可独立使用，生产代码零改动。
