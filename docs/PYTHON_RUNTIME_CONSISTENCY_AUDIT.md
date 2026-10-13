# P3：Python Runtime Version Consistency 只读审计报告

> 历史快照：本文记录的是当时（2026-10-13）的测试基线。当前基线见 HANDOVER.md。

> 本次为只读审计：**未修改任何文件、未 commit、未 push**（tracked 修改/删除 = 0）。

## 结论：当前可正常运行，风险等级 P3（低）；建议统一到 3.12（1 行改动）

---

## 1. 全部 Workflow Python 版本矩阵

| Workflow | Python | setup-python | 运行的生产代码 | 是否调 AI |
|---|---|---|---|---|
| scan.yml | **3.12** | @v4 | scan.py（选股/评分/止损/Options） | 是 |
| review.yml | **3.12** | @v4 | review.py（复盘/PnL/胜率） | 是 |
| evolve.yml | **3.12** | @v5 | evolve.py（策略演化） | 是 |
| dashboard-data.yml | **3.11** ⚠️ | @v5 | dashboard_export.py + fetch_runtimes.py | **否**（明确声明零 AI） |

**结论**：3 个生产 workflow 已用 3.12，仅 dashboard-data.yml 用 3.11。

## 2. 全部 Python Runtime 来源

| 来源 | 现状 |
|---|---|
| `.github/workflows/*.yml` | 4 个 workflow 的 `python-version`（上表） |
| `requirements-dashboard.txt` | 唯一 requirements 文件，仅 `yfinance>=0.2.40`（锁下限，不锁上限） |
| pyproject.toml / setup.py / tox.ini / pytest.ini / .python-version / runtime.txt / Dockerfile | **全部不存在** |
| `tencent_scf_review_trigger.py` | 腾讯云函数（SCF 标准 `main_handler` 入口，无本地版本配置，由云平台指定 runtime） |

**关键事实**：仓库**没有统一的 requirements 锁文件**，依赖靠各 workflow 里的 `pip install <包名>` 现装（无版本号）。

## 3. 3.11 / 3.12 差异（全仓库编译矩阵）

对全部 23 个生产 Python 文件做 3.11 与 3.12 双版本 `py_compile` 对比：

| 结果 | 文件 |
|---|---|
| 3.11 = FAIL / 3.12 = PASS | **仅 scan.py** |
| 3.11 = PASS / 3.12 = PASS | 其余 22 个生产文件（review / dashboard_export / portfolio / 全部 quant / options / evolve / ai_router / clawsocket 等） |

## 4. scan.py 的 3.11 incompatibility 是否真实：**真实（PEP 701 语法差异）**

scan.py 有 **2 处** f-string 表达式内含反斜杠，均在 **AI prompt 构造的核心路径**：

| 行号 | 位置 | 代码片段 |
|---|---|---|
| 2495-2497 | `pre_scan_portfolio_review` 风控 prompt | `持仓：\n{'\n'.join(position_lines)}\n` |
| 2633 | 主 AI prompt 候选池 | `{'\n'.join(pool_lines)}` |

Python 3.11 及以下**禁止** f-string 表达式部分含反斜杠 → `SyntaxError: f-string expression part cannot include a backslash`；Python 3.12 通过 **PEP 701** 放开此限制。已用 `ast.parse` 验证：3.11 报错（line 2497）、3.12 通过。

**含义**：scan.py **必须运行在 3.12**（scan.yml 已正确配置 3.12）。若误改回 3.11，Scan 会在 import 阶段直接 SyntaxError 崩溃。

## 5. 依赖版本风险：**真实（长期隐患）**

各 workflow 依赖安装（全部**无版本锁定**）：
- scan.yml：`pip install pandas pandas-ta yfinance anthropic requests lxml html5lib`
- review.yml：`pip install pandas yfinance anthropic requests lxml html5lib`
- evolve.yml：`pip install pandas pandas-ta requests anthropic tushare`
- dashboard-data.yml：`pip install -r requirements-dashboard.txt`（仅 `yfinance>=0.2.40`）

**风险**：每次 workflow 运行都装"当时的最新版"。pandas 3.0、numpy 2.x 已有 breaking changes（当前恰好兼容）；未来 pandas 4.0 / numpy 3.0 / yfinance 2.x 一旦引入不兼容变更，生产可能在**无任何代码改动的情况下**突然失败或行为漂移。

**当前实测**（本地沙箱，非生产环境）：3.11 有 pandas 3.0.0 / numpy 2.3.5 / yfinance 1.1.0，3.12 有 pandas 3.0.6 / numpy 2.2.6 / yfinance 1.7.0 —— 版本已不一致，但生产每次会重装最新版，实际差异以 GitHub 托管环境为准。

## 6. pytest 当前运行环境

- Python **3.11.1**、pytest **9.0.2**（本地沙箱）
- 生产 workflow **均不运行 pytest**（测试仅在本地/CI 手动执行，不在任何 `.github/workflows` 里）
- 上一轮已标准化：`pytest -q` 152 passed，测试代码本身 3.11/3.12 双兼容（18 个测试文件 py_compile 均 PASS）

## 7. 推荐统一版本：**Python 3.12**

理由（非先验假设，据实推导）：
1. scan/review/evolve 三个生产 workflow **已用 3.12**，是事实上的主流；
2. scan.py **必须 3.12**（PEP 701，2 处 AI prompt f-string 反斜杠）；
3. dashboard-data.yml 的 3.11 是**历史遗留** —— `dashboard_export.py` 与 `dashboard/fetch_runtimes.py` 经编译验证 **3.11/3.12 双兼容**，且该 workflow 明确"零 AI、零选股"，切到 3.12 无任何语义风险。

## 8. 是否需要修改：**建议（可选，非紧急）**

当前生产可正常跑（各 workflow 用各自版本，且相互独立）。但存在一个**潜在一致性风险**：dashboard-data 用 3.11，若未来 `dashboard_export.py` 或 `fetch_runtimes.py` 无意引入 3.12 语法/特性，dashboard-data 会静默失败。

## 9. 最小修改方案（若授权）

**一行改动**：`.github/workflows/dashboard-data.yml` 第 63 行 `python-version: "3.11"` → `python-version: "3.12"`，使 4 个 workflow 全部统一到 3.12。

（另可选、但超出本 P3 范围：新增 `requirements.txt` 锁版本以消除依赖漂移风险 —— 属独立工程，需单独评估。）

## 10. P3 风险等级

| 项 | 等级 |
|---|---|
| Python 版本不一致（dashboard 3.11 vs 其余 3.12） | **P3（低）** —— 当前无故障，双兼容 |
| 依赖不锁版本（每次装最新版） | **P3 偏 P2 的长期隐患** —— 未来依赖升级可能破坏行为，但当前可跑 |

---

## 最终结论

- **scan.py 3.11 incompatibility 是真实的 PEP 701 语法差异**（2 处 AI prompt f-string 反斜杠），scan 必须 3.12（已正确配置）。
- **dashboard-data 的 3.11 是历史遗留**，非必须（dashboard_export.py 双兼容）。
- **统一到 3.12 是合理方向**，最小改动仅 1 行。
- **最大隐患其实是依赖不锁版本**，但属独立工程，不在本次 Python 版本一致性范围内。

**本次全程只读**：未改任何文件、未 commit、未 push（tracked 修改 0，`__pycache__/*.pyc` 被 py_compile 意外重编译的 1 个 tracked 文件已恢复原状）。
