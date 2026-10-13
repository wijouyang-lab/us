# P3「依赖版本可重复性」只读审计报告

> 本阶段 **ONLY READ-ONLY**：未修改任何文件、未生成 lock、未安装/升级依赖、未 commit、未 push（tracked 修改/删除 = 0）。

---

## 1. Executive Summary

**核心结论：当前依赖版本已构成"中长期生产风险"，但尚未导致立即故障。**

风险本质是：仓库**没有统一的依赖锁文件**，各 workflow 通过 `pip install <包名>`（无版本号）现装**当时的最新版**。这意味着"代码不变，但依赖升级可能改变运行结果/兼容性"——尤其 pandas 已进入 3.0 大版本（breaking change 密集）、numpy 2.x、yfinance 频繁迭代。

同时发现两个次要问题：
- `openai` 被 `ai_router.py` import，但**所有 workflow 均未安装**（不过 ai_router.py 是 dead code，暂不影响生产）；
- `tushare` 被 evolve.yml 安装，但 `evolve.py` **并不使用**（多余安装）。

---

## 2. Workflow Dependency Matrix

| Workflow | Python | pip install 命令 | 版本约束 | requirements 文件 |
|---|---|---|---|---|
| scan.yml | 3.12 | `pip install pandas pandas-ta yfinance anthropic requests lxml html5lib` | **无约束** | 无 |
| review.yml | 3.12 | `pip install pandas yfinance anthropic requests lxml html5lib` | **无约束** | 无 |
| evolve.yml | 3.12 | `pip install pandas pandas-ta requests anthropic tushare` | **无约束** | 无 |
| dashboard-data.yml | 3.12 | `pip install -r requirements-dashboard.txt` | `yfinance>=0.2.40`（仅锁下限） | requirements-dashboard.txt |

**关键观察**：
- 4 个 workflow 的依赖清单**不一致**（scan 装 lxml/html5lib，review 也装，evolve 不装但装了 tushare）。
- `numpy` **从未被显式安装**（作为 pandas 的传递依赖间接获得）。
- 仅 dashboard 有 requirements 文件，且只锁 `yfinance` 下限。

---

## 3. Actual Import Dependency Matrix（实际 import → 包）

对全部生产 Python 文件用 AST 扫描（含 3.12 才能解析的 scan.py）：

| 包 | 使用文件 | 依赖性质 |
|---|---|---|
| pandas | scan / review / evolve / 8×quant / scan_us_option_engine / trade_history_quality（12 文件） | 运行时硬依赖 |
| numpy | 8×quant 模块 | 运行时硬依赖（但从未显式 pip install） |
| yfinance | scan / review / portfolio / dashboard_export / 3×quant（7 文件） | 运行时硬依赖（dashboard 有降级路径） |
| pandas_ta | scan.py | 运行时硬依赖 |
| anthropic | review.py（**模块级**）、ai_router.py | review 硬依赖 |
| requests | scan.py、clawsocket_compat.py | 运行时硬依赖 |
| lxml / html5lib | review.py 的 HTML 解析链路 | 间接依赖 |
| **openai** | ai_router.py（**函数内延迟导入**） | **ai_router 是 dead code → 缺口暂不触发** |
| **tushare** | **无任何文件 import** | evolve.yml 多余安装 |

**零第三方依赖的生产路径**（纯标准库，不需 pip）：
- `portfolio_50000.py`（csv/json/decimal/pathlib）
- `dashboard_export.py`（csv/urllib/pathlib，yfinance 仅可选优化）
- `dashboard/fetch_runtimes.py`、`dashboard/summarize_run.py`（urllib）

**分类**：
- A. 标准库：csv/json/os/sys/urllib/decimal/pathlib/zoneinfo/...（不锁）
- B. 第三方运行时依赖：pandas/numpy/yfinance/pandas_ta/anthropic/requests/lxml/html5lib
- C. 测试依赖：pytest（仅本地，不进生产）
- D. GitHub Actions 自身：actions/setup-python、actions/checkout、upload-artifact
- E. 内部模块：scan/review/portfolio/quant_*/clawsocket_compat/trade_history_quality

---

## 4. Current Installed Versions（本地沙箱，非生产）

| 包 | 3.11 沙箱 | 3.12 沙箱 | 说明 |
|---|---|---|---|
| pandas | 3.0.0 | 3.0.6 | 版本已漂移 |
| numpy | 2.3.5 | 2.2.6 | 版本已漂移 |
| yfinance | 1.1.0 | 1.7.0 | 版本已漂移 |
| pandas_ta | 未安装 | ?（无 __version__） | 仅 3.12 |
| anthropic | 未安装 | 1.11.0 | 仅 3.12 |
| openai | 未安装 | 未安装 | 缺口 |
| requests | 2.32.5 | 2.34.2 | 版本已漂移 |
| lxml | 6.0.2 | 6.1.3 | 版本已漂移 |
| html5lib | 1.1 | 1.1 | 稳定 |
| tushare | 1.4.24 | 未安装 | 仅本地，生产多余 |

> 注：本地沙箱版本不代表 GitHub Actions 生产（生产每次重装最新版），但**恰好印证了"无锁 → 版本漂移"这一事实**。

---

## 5. Version Constraint Analysis

| 依赖 | 约束状态 | 风险 |
|---|---|---|
| pandas | 无约束 | **高** —— 3.0 大版本 breaking change 密集，未来 4.0 风险 |
| numpy | 无约束 + 从未显式声明 | **中高** —— 靠 pandas 传递依赖，版本不可控 |
| yfinance | 无约束（dashboard 有 `>=0.2.40` 下限） | **中** —— 接口/限流行为频繁变化 |
| anthropic | 无约束 | **中** —— SDK 接口可能变 |
| pandas_ta | 无约束 | **中** —— 项目维护不活跃，与 pandas 3.0 兼容性脆弱 |
| requests / lxml / html5lib | 无约束 | 低 —— 相对稳定 |

**Python 3.12 兼容性**：当前实测 scan/review/portfolio/quant 在 3.12 + pandas 3.0.6 + numpy 2.2.6 下**全部跑通**（之前已实跑验证）。风险不在"当前"，而在"未来依赖升级打破兼容"。

---

## 6. Cross-Workflow Consistency（跨 workflow 一致性）

| 观察 | 结论 |
|---|---|
| scan / review / evolve / dashboard 依赖清单不一致 | ⚠️ 各自独立声明，无统一真源 |
| numpy 无 workflow 显式安装 | ⚠️ 传递依赖，脆弱 |
| tushare 装了不用 | ⚠️ 多余（evolve.yml） |
| openai 用了不装 | ⚠️ 缺口（但 ai_router 是 dead code） |
| 同一包不同 workflow 可能装到不同版本 | ⚠️ **真实存在**（各自运行时间不同，装的"最新版"可能不同） |

---

## 7. Production Risk Assessment

| 风险 | 等级 | 说明 |
|---|---|---|
| 核心依赖无锁 → 依赖升级导致行为/兼容性漂移 | **P2（中长期）** | 主要风险，当前可跑 |
| numpy 未显式声明（靠传递依赖） | P2 子项 | 建议显式声明 |
| openai 缺口（ai_router dead code） | P3 | 复活 ai_router 前需补装 |
| tushare 多余安装 | P3 | 清理项 |
| 跨 workflow 版本不一致 | P2 子项 | 统一 lock 后消除 |

**直接回答："当前依赖版本是否已经构成实际生产风险？"**
→ **尚未构成立即故障，但已构成明确的中长期风险**。核心是 pandas/numpy/yfinance 无锁，一旦上游发布不兼容版本，生产会在无任何代码改动的情况下静默失败或结果漂移。

---

## 8. Recommended Locking Strategy（推荐方案）

**推荐方案 A：单一 `requirements-production.txt`**（作为唯一依赖真源）。

理由：
1. 仓库生产依赖集其实很小（7 个包：pandas、numpy、yfinance、pandas_ta、anthropic、requests、lxml、html5lib），统一管理成本低；
2. 消除"4 个 workflow 各自声明、清单不一致"的问题；
3. 一个文件即可让 scan/review/evolve/dashboard 全部 `pip install -r requirements-production.txt`。

锁法建议（**范围锁而非精确锁**，兼顾可重复性与安全更新）：
```
pandas>=3.0,<4
numpy>=2,<3
yfinance>=1.0,<2
pandas_ta>=0.3
anthropic>=1.0,<2
requests>=2.31,<3
lxml>=5,<7
html5lib>=1.1
```

（dashboard 可继续用现有 `requirements-dashboard.txt`，或统一并入后单独 `--no-deps` 安装 yfinance。）

**不推荐**：`constraints.txt`（需要额外引用，增加心智负担）、workflow-specific requirements（延续现状的碎片化）。

---

## 9. Proposed Future Implementation Scope（下一阶段最小安全实施）

若授权实施，最小方案为：
1. 新增 `requirements-production.txt`（8 个包，范围锁）；
2. 4 个 workflow 的 `pip install ...` 改为 `pip install -r requirements-production.txt`；
3. 移除 evolve.yml 的 `tushare`；
4. （可选）确认 ai_router.py 是否需保留，若保留则补 `openai`。

**本次不做任何上述修改**（仅审计）。

---

## 10. Files Not Modified

本次只读，**未修改任何文件**。确认：
- `git status --short` → 无 tracked 修改/删除（0 个）
- 无因执行 Python/pytest 产生的 tracked 文件变化（py_compile 未触碰任何 tracked .pyc）
- 未 commit、未 push、未生成 lock、未安装依赖

---

## 最终回答

1. **"当前依赖版本是否已经构成实际生产风险？"**
   → **是（中长期 P2 风险，非立即故障）**：核心依赖 pandas/numpy/yfinance/anthropic/pandas_ta 全部无版本约束，跨 workflow 清单不一致，numpy 未显式声明、tushare 多余、openai 缺口。

2. **"如果下一阶段锁版本，最小安全实施方案是什么？"**
   → 新增单一 `requirements-production.txt`（8 个核心包，范围锁 `>=x,<y`），4 个 workflow 统一改为 `pip install -r requirements-production.txt`，移除 tushare，可选补 openai。约 2 文件新增/5 行 workflow 改动，即可消除依赖漂移风险。
