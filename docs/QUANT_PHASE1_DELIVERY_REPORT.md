# Quant Research Phase 1 交付报告：Factor Library + Daily Factor Snapshot

> 交付时间：2026-10-06 · commit `01db04f` · 状态：已 push，`HEAD == origin/main` ✅

## 1. 修改文件（2 个）

| 文件 | 改动 | 性质 |
|---|---|---|
| `scan.py` | ① import quant_factor_lab ② 新增 `QUANT_FACTOR_SNAPSHOT_FILE` 常量 ③ `build_stock_pool` 复用已下载 OHLCV 计算扩展因子（SPY 只抓一次）④ gate 后写全候选池 snapshot | **纯新增**，评分/门槛/选股逻辑零改动 |
| `.github/workflows/scan.yml` | ① upload-artifact 加 `quant_factor_snapshot.csv` ② git add 加该文件 | 仅新增持久化，cron/concurrency/runner/push 架构零改动 |

## 2. 新增文件（2 个）

| 文件 | 作用 |
|---|---|
| `quant_factor_lab.py` | 8 个纯因子函数 + snapshot 幂等 upsert 写入（不 import yfinance，零网络请求） |
| `tests/test_quant_factor_lab.py` | 30 项纯函数回归测试（不依赖真实 Yahoo 网络） |

## 3. 每个 Factor 数学公式（已写进 `quant_factor_lab.py` 顶部 docstring）

| Factor | 公式 | 窗口 | 口径 |
|---|---|---|---|
| Momentum_5D_Pct | `(close[-1]/close[-6]-1)*100` | 5 日 | 需 ≥6 bar |
| Momentum_20D_Pct | `(close[-1]/close[-21]-1)*100` | 20 日 | 需 ≥21 bar |
| Momentum_60D_Pct | `(close[-1]/close[-61]-1)*100` | 60 日 | 需 ≥61 bar |
| Realized_Volatility_20D_Pct | `std(ret[-20:],ddof=1)*√252*100` | 20 个日收益 | annualize |
| Volume_Ratio_20D | `vol[-1] / mean(vol[-21:-1])` | 当前/前20均 | 均值不含当前 bar |
| ZScore_20D | `(close[-1]-mean(前20))/std(前20,ddof=1)` | 20 日 | std=0→None |
| Beta_60D_SPY | `Cov(s_ret,p_ret)/Var(p_ret)` | 60 个重叠日收益 | 除零→None |
| Stock_RS_20D_vs_SPY | `个股20D收益 - SPY20D收益` | 20 日 | SPY缺失→None |

## 4. Snapshot Schema（33 列，固定顺序）

`Scan_Date, Technical_Date, Ticker, Name, Sector, Price, RSI_14, Bias_Pct, MACD_Hist, MA20, MA50, MA20_Slope_5D, ATR_Pct, KDJ_J, Volume_Ratio_5D, Momentum_5D_Pct, Momentum_20D_Pct, Momentum_60D_Pct, Realized_Volatility_20D_Pct, Volume_Ratio_20D, ZScore_20D, Beta_60D_SPY, Stock_RS_20D_vs_SPY, Sector_RS_20D_Pct, VIX, Market_Regime, Fundamental_Score, Event_Score, Technical_Score_25, Risk_Liquidity_Score, Quant_Score, 技术确认数, Gate_Status`

## 5. Snapshot 起始日期

**从首次成功实施后的下一次 Scan 开始**（今晚 13:07 UTC 定时触发）。不做历史回填，不虚构历史因子。

## 6. 是否全 Candidate Pool 记录

✅ **是**。在 `apply_entry_quality_gate` 之前保存完整候选池引用，gate 之后写入 —— 快照含**所有经过行情/技术/市场环境/评分计算的候选标的**，并带每项的 `Gate_Status`（PASS_PRE_AI / TECH_FAIL / QUANT_FAIL / ATR_FAIL / SECTOR_RS_FAIL / SPY_TREND_FAIL / PANIC_FAIL 等），避免只记录最终 Core/Observation 造成 selection bias。

## 7. 新增网络请求

| 项 | 说明 |
|---|---|
| 个股 OHLCV | **零新增**（完全复用 `build_stock_pool` 已下载的 df） |
| SPY | **1 次共享请求**（`_download_close_series("SPY","6mo")`），供全部股票 Beta/RS 复用，绝不逐股重复下载 |

## 8. 实际 Scan Runtime 增量

无法在只读环境实测完整 Scan（需 Yahoo/API key），但按代码复杂度：新增因子为**纯 pandas 向量计算**（复用已下载 df），SPY 一次下载约 1-2 秒。**预计每日 Scan 增量 < 5 秒，可忽略**。

## 9. AI Token 是否增加

✅ **0 增量**。未新增任何 GPT/Claude/ClawSocket 调用；未修改任何 AI Prompt；新因子只写 item + snapshot 本地文件，不进 AI 文本。

## 10. 推荐结果前后是否一致

✅ **一致**。diff 审查确认 `Quant_Score` / `Final_Score`(70%+30%) / Core/Observation 门槛 / Regime Gate / Stop Loss 全部零改动；新增代码只有 `**ext_factors` 写 item 字段 + snapshot 落盘，不影响任何评分、排序、门槛、AI 匹配逻辑。

## 11-13. 测试 / 检查

| 项 | 结果 |
|---|---|
| 新增 Quant 测试 | **30 / 30 PASS** |
| **全量项目测试** | **339 / 339 PASS**（含既有 309 + 新增 30） |
| py_compile（Python 3.12，与生产一致） | ✅ PASS |
| git diff --check | ✅ PASS |
| node --check | 无需执行（无 JS 改动） |

## 14-16. Git 状态

| 项 | 值 |
|---|---|
| commit SHA | `01db04f2113be4c9ed18e1e50642d1af062e076c` |
| push | ✅ 成功（无 force） |
| HEAD == origin/main | ✅ **TRUE** |

## 17. 未解决问题

**无 P0/P1 阻塞。** 唯一记录在案的口径提示：`py_compile` 在 Python 3.11 下会因**原有代码**（`pre_scan_portfolio_review` 的 f-string 反斜杠）报错 —— 这是历史代码在 3.11 下的既有问题，生产环境 `scan.yml` 用 Python 3.12（PEP 701 允许），本次未触碰该处。新增的 `quant_factor_lab.py` 在 3.11/3.12 均兼容。

---

## 红线确认

- ❌ 未改 Quant_Score / Final_Score 公式
- ❌ 未改 Core / Observation 门槛、Regime Gate、Stop Loss、Review、$50K Portfolio
- ❌ 未新增任何 AI 调用，AI Token 增量 = 0%
- ❌ 新 Factor 未参与选股、评分、门槛
- ❌ 未做历史回填
- ❌ 未删任何文件/功能
- ❌ 未改 cron / concurrency / runner / push 架构
- ❌ 未改 review.py / portfolio_50000.py / dashboard_export.py / app.js / index.html / strategy_params.json / 各 workflow

**Phase 1 已交付，未进入 Phase 2。** 因子数据层将随今晚 Scan 自然运行开始积累，为后续 Factor Backtest 提供无 Look-Ahead Bias 的研究快照。
