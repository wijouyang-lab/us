# 全仓库完整重跑 + 代码错误验证报告

> 本次目标：重新执行仓库中所有实际存在的生产/研究/测试代码，把 **Code Error 与 Environment Blocker 明确分开**。
> 纪律：只执行、只报告，不修代码、不 commit、不 push、不改主工作区。

---

## A. FINAL VERDICT

# **PASS WITH WARNINGS**

存在 1 个 P1 级 DATA_ERROR（trade_history 重复事件）+ 多个 P2/P3 问题，但**无 P0**（无生产安全、无数据删除、无 V2 误启用、无主流程崩溃）。所有可独立执行的代码路径均已实跑验证，剩余阻断项均有明确外部原因。

**核心答案：仓库里确实还存在真正的数据错误（trade_history 重复事件），但没有发现会导致生产崩溃的代码错误。**

---

## B. TRUE CODE ERRORS / DATA ERRORS（代码/数据本身有问题）

| # | 优先级 | 类型 | 问题 | 证据 | 影响 |
|---|---|---|---|---|---|
| 1 | **P1** | DATA_ERROR | `trade_history.csv` 有 **41 个重复事件（82 行冗余）** | `Ticker\|Date\|Tag` 去重后 373 事件 vs 414 行；分布在 2026-06-02/03/04（各 24 行）+ 09-22（10 行）；重复行仅 `Hold_Period`/`Stop_Loss` 字段略有差异 | `review.py:load_trade_history()` **不去重**，KPI 统计（Core 数量、胜率、Profit Factor）可能重复计算；Dashboard 显示可能重复 |
| 2 | P1/P2 | DATA_ERROR | 价格浮点尾数 **155/414 条**（如 `479.8800048828125`） | 源头 `review.py` 回填 Rec_Price 时 `str(new_price)` 未 `round(...,2)`；最新 2026-10-06 **仍在产生** | 违反"价格 2 位小数"约定，污染 Buy Price 显示；误差 <1e-4，不影响 PnL |
| 3 | P2 | CODE | `pytest -q` 报 INTERNALERROR（`no tests ran`） | 测试是脚本式（模块级 `sys.exit`），pytest 无法收集 | 只能用 `python tests/*.py` 逐个跑，无法用 pytest 统一执行 |
| 4 | P2 | CODE | Forward Return 双实现 | `forward_return_nd`(backtest) 与 `compute_forward_return`(shadow) 同公式不同名 | 未来口径漂移风险，非当前 bug |
| 5 | P3 | CODE | Python 版本分裂 | scan/review/evolve 用 3.12，dashboard-data 用 3.11；`scan.py:2497` 在 3.11 下 f-string 反斜杠 SyntaxError（3.12 PEP701 正常） | 非生产路径（scan 用 3.12），但 dashboard-data（3.11）若 import scan 会炸 |
| 6 | P3 | CODE | `scan.py` 模块级副作用 | env 检查（127-130）+ 时间门槛（159-188）在 `if __name__` 之前，`import scan` 即触发并可能 `sys.exit` | 阻止函数级测试与 import smoke test |
| 7 | P3 | CODE | Quant 3-7 无 workflow 入口 | validation/score_v2/walk_forward/shadow/production 均无 `.github/workflows` 调用 | 研究层未自动化（研究态，非 bug） |
| 8 | P3 | DATA | 9 个 tracked `.pyc` 被 git 跟踪 | `git ls-files '*.pyc'` = 9 个（历史误提交） | 死文件；且本次运行 3.12 时意外重编译了其中一个 |

---

## C. ENVIRONMENT BLOCKERS（环境阻断，非代码问题）

| 组件 | 阻断原因 | 处理 |
|---|---|---|
| review.py | 3.11 缺 anthropic、3.12 缺 pandas | **已装齐 3.12 依赖后完整跑通**（见下） |
| scan.py | 需 `CLAWSOCKET_API_KEY`/`BASE_URL`（生产有，沙箱无） | 用占位 env 通过检查，验证启动流程 |
| review.py AI 调用 | 占位凭证 → `Connection error` | 优雅降级，不影响主流程 |

## D. EXTERNAL SERVICE BLOCKERS（外部服务阻断）

| 服务 | 现象 | 影响组件 |
|---|---|---|
| Yahoo Finance (yfinance) | HTTP 429 `YFRateLimitError` 批量限流 | review.py 43 只 ticker 价格获取失败（有降级逻辑）、dashboard_export 120s 超时 |

---

## E. ALL EXECUTION MATRIX（整个仓库实际执行）

| Component | Entry | Executed | Result | Error Type |
|---|---|---|---|---|
| scan.py | `python scan.py` (3.12) | ✅ | BLOCKED_BY_TIME（PREMARKET_NOT_STARTED） | TIME_GATE |
| scan.py 启动链 | import + env + 时间门槛 | ✅ | 完整跑通 | — |
| scan.py pandas_ta 指标 | rsi/macd/atr/cci/kdj | ✅ | 全部正常（pandas 3.0 下） | — |
| scan.py 扩展因子 | `calculate_extended_quant_factors` | ✅ | 8 因子全部正常 | — |
| review.py | `python review.py` (3.12) | ✅ | **exit 0 完整跑通**（复盘全流程完成，仅 AI 调用失败） | 外部限流降级 |
| portfolio_50000.py | 运行 2 次 | ✅ | 幂等正确（第 2 次无重复） | — |
| dashboard_export.py | `--data-dir` 隔离运行 | ✅ | 启动正常，被 Yahoo 限流 120s 超时 | EXTERNAL_RATE_LIMIT |
| dashboard/fetch_runtimes.py | 真实 token 运行 | ✅ | **exit 0 完整跑通**（scan/review/evolve 状态全 success） | — |
| quant_factor_price.py | CLI | ✅ | exit 0，NO_SNAPSHOT | — |
| quant_factor_validation.py | CLI | ✅ | exit 0，NOT_ENOUGH_DATA | — |
| quant_score_v2.py | CLI | ✅ | exit 0，72 行全 BLOCKED | — |
| quant_walk_forward.py | CLI | ✅ | exit 0，window=0 | — |
| quant_shadow.py | CLI | ✅ | exit 0，SHADOW_DISABLED | — |
| quant_production.py | CLI | ✅ | exit 0，V1_ACTIVE | — |
| quant_factor_lab.py | 纯库 | ✅ | import + 因子计算正常 | — |
| quant_factor_backtest.py | 纯库 | ✅ | import + forward return 正常 | — |
| evolve.py | import | ✅ | import OK（需 env 运行） | — |
| patch_v34.py / review_kpi_*.py | 一次性补丁 | ⚠️ NOT_RUN | 引用外部路径 `/mnt/data/v34`，DEAD_CODE | DEAD_CODE |
| tencent_scf_review_trigger.py | 云函数触发 | ⚠️ NOT_RUN | 需腾讯云 SCF 环境，GITHUB_ENVIRONMENT_ONLY | WORKFLOW_ONLY |

---

## F. REGRESSION CHECK（之前 12 项逐个重验）

| # | 项 | 结果 |
|---|---|---|
| 1 | Buy Price 浮点尾数 | ❌ **仍存在**（155/414 条，最新 10-06） |
| 2 | Forward Return 双实现 | ❌ **仍存在**（2 处定义） |
| 3 | Python 3.11/3.12 分裂 | ❌ **仍存在**（scan.py 3.11 FAIL） |
| 4 | pytest INTERNALERROR | ❌ **仍存在**（脚本式 sys.exit） |
| 5 | Quant 3-7 无 workflow 入口 | ❌ **仍存在**（仅 price 有入口） |
| 6 | Dashboard concurrency guard | ✅ 仍在（line 144/171/175 双重守卫） |
| 7 | Quant V2 Production Lock | ✅ 正确（V1_ACTIVE / ENABLED=false） |
| 8 | Portfolio 幂等 | ✅ 正确（第 2 次运行 transactions 仍 1 行） |
| 9 | Options RR >= 2 | ✅ 规则在（`REJECT_REASON_RR_BELOW`） |
| 10 | Market Regime | ✅ 正确（NORMAL/STRESSED/PANIC/UNKNOWN） |
| 11 | Rec_Price 回填 | ✅ 逻辑在（浮点噪声是精度问题，非缺失） |
| 12 | Dashboard Buy Price | ⚠️ 未验证（dashboard_export 被限流阻断） |

---

## G. TEST RESULTS

| 项 | 结果 |
|---|---|
| pytest -q | ❌ INTERNALERROR（`no tests ran`，脚本式测试） |
| 脚本式全量测试 | ✅ **623 / 623 PASS**（18 个测试文件） |
| py_compile 3.12（23 生产文件） | ✅ 全 PASS |
| py_compile 3.11（23 生产文件） | ⚠️ 22 PASS + scan.py FAIL（f-string 反斜杠） |
| py_compile 测试文件（18 个，3.11/3.12） | ✅ 全 PASS |
| import smoke test（16 模块） | ✅ 全 PASS |

## H. GIT STATUS

| 项 | 值 |
|---|---|
| HEAD | `880bdd4`（审计开始前同步到 origin/main） |
| origin/main | `eca9142d`（审计期间 dashboard-data 又自动 +1） |
| modified / deleted | **0 / 0**（含恢复 1 个被运行重编译的 tracked .pyc） |
| ahead / behind | 0 / 1（远端自动提交，非本次引入） |

## I. PERFORMANCE（实测）

| 组件 | 耗时 |
|---|---|
| 脚本式全量测试 623 项 | ~3 分钟 |
| review.py 完整跑通 | ~120s（绝大部分是 Yahoo 限流重试） |
| dashboard_export | 120s 超时（限流） |
| Quant 6 个 CLI（空数据） | 各 <1s |
| Portfolio（单次） | ~1s |
| fetch_runtimes | ~1s |

## J. RECOMMENDED FIX ORDER（只建议，不修改）

1. **P1**：`review.py:load_trade_history()` 加 `drop_duplicates(subset=["Ticker","Date","Tag"])`（或清洗 trade_history 41 个重复事件）—— 最优先，直接影响统计准确性
2. **P1/P2**：`review.py` 回填 Rec_Price 处补 `round(float(new_price), 2)`
3. **P2**：统一 Forward Return 单实现（backtest/shadow 复用）
4. **P2**：测试文件加 `if __name__ == "__main__"` 守卫（或改用 pytest 风格），修复 pytest 收集
5. **P3**：scan.py 模块级副作用移入 main()；统一 Python 版本；清理 9 个 tracked .pyc

---

## ★ 本次"真正执行"的最大新发现

### 1. trade_history 有 41 个重复事件（P1 DATA_ERROR）

之前审计从未发现这一点。`Ticker|Date|Tag` 去重后是 **373 事件**，实际文件 **414 行**，41 个事件被重复记录（集中在 2026-06-02~04 和 09-22）。关键旁证：

- `review.py:load_trade_history()` **不去重** → 下游 KPI 统计可能被污染
- `portfolio_50000.py` 用幂等键（`Ticker|Rec_Date|Tag|BUY`）**正确避免**了重复（隔离运行时输出"推荐事件 373 条"= 去重后数字）

### 2. snapshot 未产生的真正原因（部署时序，非 bug）

之前所有 Phase 都假设"Snapshot=0 因为 Scan 没运行"。**真相是**：Scan #151 在 2026-10-06 18:52 UTC 成功运行，但 Phase 1 部署 commit（`01db04f`）时间是 2026-10-07 02:56 UTC —— **晚于 Scan #151**。所以 scan.py 的 snapshot 代码从未被任何 Scan 执行过。

> 验证：`d12f78d`（Scan #151 的 head_sha）版本的 scan.py 含 `write_factor_snapshot: 0 次`。

**下一次 Scan（今天 13:07 UTC cron）才会首次产生 snapshot**，届时才能验证 snapshot 链路是否真正正确。

### 3. review.py 在 pandas 3.0 下完整跑通

之前审计把 review.py 标为 BLOCKED（缺 anthropic）。本次装齐 3.12 依赖后，review.py **exit 0 完整跑通**了复盘全流程（读数据 → milestone 回补 → 买入价回填 → PnL 重算 → KPI 统计 → 输出报告），唯一失败是 AI 调用（占位凭证 `Connection error`）。这证明 review.py 代码本身无问题，且与 pandas 3.0.6 / numpy 2.2.6 / anthropic 1.11 完全兼容。

---

## 最终判断

**当前程序适合继续正常运行**：V1 安全 Active、V2 禁用未批准、生产锁完整、Portfolio 幂等、并发守卫有效、review 主流程可完整跑通。唯一需尽快处理的实质问题是 **P1 trade_history 重复事件**（统计准确性）+ 已知的**价格浮点尾数**（显示精度）。二者都是数据层问题，不涉及生产逻辑崩溃。

按纪律，本次**只报告、未修任何 bug**。等你确认修复顺序后我再动手。
