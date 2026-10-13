# 生产依赖可重复性最小实施 — 交付报告

## 结论：已建立统一版本约束，发现并补上缺失的 scipy 依赖，全量测试通过

---

## 1. 最终 requirements-production.txt（9 个包）

```
pandas>=3.0,<4
numpy>=2.0,<3
yfinance>=1.0,<2
pandas-ta>=0.4,<0.5
anthropic>=1.0,<2
requests>=2.31,<3
lxml>=5.0,<7
html5lib>=1.1,<2
scipy>=1.14,<2
```

## 2. 每个版本选择依据（基于实际验证，非猜测）

| 包 | 约束 | 已验证版本（Python 3.12） | 依据 |
|---|---|---|---|
| pandas | `>=3.0,<4` | 3.0.6 | scan/review/portfolio/quant 已实跑通过 |
| numpy | `>=2.0,<3` | 2.2.6 | 8 个 quant 模块直接 `import numpy` |
| yfinance | `>=1.0,<2` | 1.7.0 | scan/review 行情源 |
| pandas-ta | `>=0.4,<0.5` | 0.4.71b0 | scan.py 技术指标 |
| anthropic | `>=1.0,<2` | 1.11.0 | review.py 模块级硬依赖 |
| requests | `>=2.31,<3` | 2.34.2 | scan/clawsocket |
| lxml | `>=5.0,<7` | 6.1.3 | review HTML 解析 |
| html5lib | `>=1.1,<2` | 1.1 | review 解析（长期稳定） |
| **scipy** | `>=1.14,<2` | 1.18.1 | **本次新发现**，见下 |

**★ 重要发现：scipy 是缺失的必要依赖**
- `quant_factor_backtest.py` 与 `quant_factor_validation.py` 调用 pandas 的 `corr(method="spearman")`，pandas 内部 `from scipy.stats import spearmanr`。
- scipy 是 pandas 的 **optional extra**（`scipy>=1.14.1; extra=="computation"`），**不会随 pandas 自动安装**。
- 之前 3.11 沙箱恰好残留 scipy 1.17.0，测试才"误通过"；3.12 环境缺 scipy 导致 **9 个测试 ModuleNotFoundError**，补装 scipy 后 152 passed 恢复。
- 因此 scipy 被显式加入 production requirements（同理于 numpy 的显式声明原则）。

## 3. 四个 workflow 的修改

| Workflow | 修改 |
|---|---|
| scan.yml | `pip install pandas pandas-ta yfinance anthropic requests lxml html5lib` → `python -m pip install -r requirements-production.txt` |
| review.yml | `pip install pandas yfinance anthropic requests lxml html5lib` → `python -m pip install -r requirements-production.txt` |
| evolve.yml | `pip install pandas pandas-ta requests anthropic tushare` → `python -m pip install -r requirements-production.txt`（移除 tushare） |
| dashboard-data.yml | `pip install -r requirements-dashboard.txt` → `python -m pip install -r requirements-production.txt`（保留降级容错） |

四个 workflow 的 Python 版本均保持 **3.12**，cron/concurrency/permissions/runtime/AI routing/git 操作等**零改动**。

## 4. tushare 为什么移除

`evolve.py` 全文件 grep `tushare` = **0 次**（确认不使用）。evolve.yml 安装 tushare 属多余安装，统一到 production requirements 后自然移除。

## 5. openai 为什么不加入

`ai_router.py` 有 `from openai import OpenAI`（函数内延迟导入），但 `ai_router.py` 全仓库**无任何模块 import**（dead code），当前 Scan/Review/Evolve/Dashboard 生产执行路径均不使用。故 openai 不加入 production requirements。**未删除、未修改 ai_router.py**。

## 6. numpy 为什么显式声明

8 个 quant 模块（backtest/lab/price/validation/production/score_v2/shadow/walk_forward）直接 `import numpy as np`，是明确的运行时硬依赖。此前依赖 pandas 的传递依赖（不可靠），本次显式声明 `numpy>=2.0,<3`。

## 7. 全部测试结果

| 项 | 结果 |
|---|---|
| requirements 解析（dry-run） | ✅ 全部 "already satisfied"，版本约束可满足 |
| pip check | ✅ 生产依赖无冲突（仅沙箱 oslo 包缺 tzdata，与生产无关） |
| pytest（Python 3.12） | ✅ **152 passed**（补 scipy 后） |
| dashboard runtime / stability tests | ✅ 包含在 pytest 152 内（subprocess 运行通过） |
| py_compile（14 生产文件，3.12） | ✅ 全 PASS |
| git diff --check | ✅ PASS |

**验证过程记录**：首次 3.12 pytest 出现 **9 failed（ModuleNotFoundError: scipy）** → 定位为 scipy 间接依赖缺失 → 补 `scipy>=1.14,<2` → 复跑 152 passed。符合"发现冲突即停、定位后修复"的纪律。

## 8-9. Git

| 项 | 值 |
|---|---|
| commit SHA | `1266a4b`（rebase 前 `1a9a70a`） |
| push | ✅ 无 force（`50b8a00..1266a4b`） |
| HEAD == origin/main | ✅ **TRUE** |

## 10. 是否存在未预期修改

**无**。工作区变更严格限于预期范围：
- 新增 `requirements-production.txt`
- 修改 4 个 workflow（scan/review/evolve/dashboard-data）

未改动：scan.py / review.py / evolve.py / portfolio / quant / dashboard_export / requirements-dashboard.txt / trade_history / review_history / dashboard_data.json / 任何 tracked .pyc。`requirements-dashboard.txt` 保留未删（不在本次范围）。

---

## 一句话总结

新增统一 `requirements-production.txt`（9 包范围锁，`>=verified,<next-breaking`），四个 workflow 统一引用；移除了 tushare 多余依赖、明确不加入 dead-code 的 openai、显式声明 numpy，并**发现且补上了此前隐藏的 scipy 缺失依赖**（pandas corr spearman 的 optional extra，此前靠沙箱残留"误通过"）。全量 pytest 152 passed，已推送并保持 HEAD == origin/main。
