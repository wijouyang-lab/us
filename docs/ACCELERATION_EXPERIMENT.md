# 技术因子 OOS 加速实验（Acceleration Experiment）

> 状态：**真实实验被沙箱环境阻断**（yfinance 限流 + 本地无 10y 行情）。
> 本文档 = 实验方法（设计）+ 代码集成验证（合成数据，**非证据**）+ 结论与下一步。
> 铁律：仅读 `/tmp/us`、仅在 `/tmp/experiment/` 写脚本、未 `push`/`rebase`/`commit`、未改任何仓库文件。

---

## 0. TL;DR

- **能否独立调用仓库因子函数？** ✅ 能。三个目标函数均可脱离主流程调用（详见 §1）。
- **真实实验跑成了吗？** ❌ 没跑成。沙箱出口被 Yahoo 限流（`YFRateLimitError: Too Many Requests`），且仓库自带行情历史仅 10 个交易日，不足以支撑 60D 因子或任何前瞻窗口。
- **那本文的数字哪来的？** 是**合成数据**做的**代码集成验证**（证明 4 个脚本 + 仓库函数能串起来、指标 machinery 能正确产出 IC / 五分位 / 组合指标），**绝不**作为"技术因子在真实市场 OOS 有效"的任何结论。
- **结论**：技术因子是否 OOS 有效，**本沙箱无法判定**；需在非限流环境用真实 10y 数据重跑（见 §5）。

---

## 1. 第一步 · 只读确认结果（三个函数能否独立调用）

| 函数 | 文件 | 输入 | 输出 | 纯函数？ | 能否独立调用 |
|---|---|---|---|---|---|
| `calculate_extended_quant_factors(df, spy_close)` | `quant_factor_lab.py:202` | 个股 OHLCV（`Close`/`Volume`）+ SPY 收盘序列 | 8 个因子的 dict（float / None） | **纯** ✅ | ✅ 无 I/O、无网络、无副作用 |
| `run_backtest(snapshot_path, price_map, backtest_path, summary_path)` | `quant_factor_backtest.py:366` | snapshot CSV + `price_map`（可选） | 状态 dict，**写** backtest/summary CSV | ⚠️ 有文件 I/O | ✅ **4 个路径均为参数**，全部指向 `/tmp/experiment` 即可零写入仓库 |
| `run_validation(backtest_path, validation_path, correlation_path, report_path)` | `quant_factor_validation.py:403` | backtest CSV | 状态 dict，**写** 3 份文件 | ⚠️ 有文件 I/O | ✅ 同上，路径可重定向 |

**判定：实验可行。** 核心计算（`compute_forward_returns`、`compute_validation`、`calculate_extended_quant_factors` 等）全部为纯函数；两个 `run_*` 入口虽有文件写入，但路径参数可被调用方完全指定，指向实验目录后**不会触碰 `/tmp/us` 任何文件**。无网络副作用（`price_map` 由调用方传入，`run_backtest` 不会触发 yfinance 下载）。

> 注：`quant_factor_validation.py` 顶层的 `from quant_factor_backtest import ...` 在 import 即执行，但只 import numpy/pandas，**不触发 yfinance**（yfinance 仅在 `load_price_history` 内惰性导入）。因此 import 安全。

---

## 2. 第二步 · 实验脚本清单（`/tmp/experiment/`）

| 脚本 | 作用 | 数据源 | 输出 |
|---|---|---|---|
| `fetch_history.py` | yfinance 分批（5 只/批 + sleep 2s + 重试 3）拉 20 只 SP500 + SPY 的 10y 日线 | yfinance | `history.csv` |
| `build_factor_snapshot.py` | 对每天/每只复用 `calculate_extended_quant_factors` 算 8 个技术因子，对齐 `SNAPSHOT_COLUMNS` | `history.csv` | `snapshot.csv` |
| `run_backtest.py` | 调 `run_backtest`（路径指向实验目录）算前瞻收益 | `snapshot.csv` + `price_map` | `backtest.csv` / `summary.csv` |
| `run_validation.py` | 调 `run_validation` + 补充基线 / Top-Q 组合 Sharpe·最大回撤 | `backtest.csv` | `validation.csv` / `correlation.csv` / `report.json` / `results.json` |
| `_smoke_synthetic.py` | **仅验证用**：生成 ~2y 合成行情（注入弱动量可预测性） | 本地随机 | `history.csv`（覆盖） |

**使用的 8 个技术因子**（来自 `calculate_extended_quant_factors`，纯技术、无需 AI）：
`Momentum_5D_Pct` / `Momentum_20D_Pct` / `Momentum_60D_Pct` / `Realized_Volatility_20D_Pct` / `Volume_Ratio_20D` / `ZScore_20D` / `Beta_60D_SPY` / `Stock_RS_20D_vs_SPY`。

**前瞻收益口径**（复用仓库定义，杜绝前视）：`T = Technical_Date`，`Forward_Return_ND = Close[T 之后第 N 个交易日] / Close[T] - 1`；因子取值只用 ≤T 的数据。期限 `HORIZONS = (5, 10, 20)`。

---

## 3. 第三步 · 实验执行结果

### 3.1 真实实验（设计目标）—— 被阻断

- 运行 `fetch_history.py`：yfinance 在沙箱出口被 **`YFRateLimitError: Too Many Requests`** 限流，分批重试 3 次后仍全部失败，脚本按设计**优雅退出、不写 `history.csv`、不伪造数据**。
- 退路核查：仓库自带 `quant_factor_price_history.csv` 仅 **325 只 × 10 个交易日（2026-09-27 ~ 10-08）**。10 天既不够 60D 因子窗口，也不存在任何前瞻窗口（horizon 5/10/20 需要 T 之后的交易日），**无法支撑真实 OOS 回测**。
- **结论：真实实验在本沙箱无法执行**（限流 + 无 10y 行情）。这与任务授权中的"可能限流，做好降级"预判一致。

### 3.2 代码集成验证（合成数据 —— **非实验结论 / 非证据**）

为证明 4 个脚本与仓库函数能正确串联、指标 machinery 能产出，用 `_smoke_synthetic.py` 生成 ~2 年合成行情（8 只 × 504 日，注入"过去 20 日动量弱预测次日收益"的信号），跑通全链路：

- `build` → 2,968 条 snapshot 行（7 只主力股 × ~424 交易日，SPY 作基准）
- `run_backtest` → `status=OK`，maturity 5/10/20D 全部 = 2,968
- `run_validation` → 72 行（24 因子 × 3 期限，含大量 `NOT_ENOUGH_DATA`），正确产出

**合成数据的 IC（信息系数，因子 vs 前瞻收益）—— 仅演示格式，非真实市场结论：**

| 因子 | IC(5D) | IC(10D) | IC(20D) | 解读（合成） |
|---|---|---|---|---|
| Momentum_5D_Pct | **+0.73** | +0.70 | +0.63 | 强正相关（注入信号被检出） |
| Momentum_20D_Pct | +0.63 | +0.61 | +0.55 | 强正相关 |
| Momentum_60D_Pct | +0.37 | +0.36 | +0.31 | 中正相关（长动量衰减） |
| ZScore_20D | +0.61 | +0.58 | +0.51 | 与动量同源 |
| Stock_RS_20D_vs_SPY | +0.54 | +0.53 | +0.49 | 与动量同源 |
| Beta_60D_SPY | +0.09 | +0.09 | +0.08 | 弱 |
| Realized_Volatility_20D_Pct | −0.05 | −0.06 | −0.05 | 弱负（符合直觉） |
| Volume_Ratio_20D | ~0.00 | ~0.00 | ~0.00 | **无信号 → IC≈0，machinery 正确表现为"无效"** |

**合成数据 Top-Q（Q5）多头组合 vs 随机基线（无条件均值）—— 仅演示格式：**

| 因子 | Top-Q 5D 均值 | Top-Q 5D 夏普 | 随机基线 5D 均值 |
|---|---|---|---|
| Momentum_5D_Pct | **+4.19%** | 3.97 | −1.77% |
| ZScore_20D | +4.08% | 3.83 | −1.77% |
| Stock_RS_20D_vs_SPY | +3.20% | 2.86 | −1.77% |
| Volume_Ratio_20D | −1.93% | −1.59 | −1.77% |
| Realized_Volatility_20D_Pct | −1.93% | −1.54 | −1.77% |

> ⚠️ 合成验证的两点说明（避免误读）：
> 1. 上述数字来自**人为注入信号**的合成数据，**不代表任何真实市场因子有效性**。
> 2. Top-Q 组合的"最大回撤 = −1.0"是**逐笔非重叠近似 + 合成序列漂移**的副产物（把 848 笔交易按日期顺序串成净值），是方法学近似产物，**不可作为真实回撤结论**。真实实验应用重叠持仓的净值曲线或更严谨的回测框架。

**验证达成的事实**（与数据真假无关）：
- 4 个脚本能正确 import 仓库函数、以实验路径调用、零写入 `/tmp/us`；
- 指标 machinery 能正确区分"有信号因子（IC 高）"与"无信号因子（IC≈0）"；
- IC / 五分位 / 组合指标的计算与落盘链路全部打通。

---

## 4. 对比基线（真实实验）与局限

| 维度 | 真实实验设计 | 当前状态 |
|---|---|---|
| 随机基线 | 各期限"无条件均值前瞻收益"（买入并持有任意股） | **未计算**（无真实数据） |
| 因子是否显著优于随机 | 看 Top-Q − 基线 spread + IC 显著性 | **未判定** |
| 幸存者偏差 | 20 只当前大盘龙头，均存活 10 年 → 样本偏差 | 局限项（真实实验时仍需说明） |
| 样本量 | 20 × ~2,500 日 × 8 因子 → N 远超 100/期限 | 设计上充分；合成验证 N=2,968 |

> 真实实验若跑成，需报告：因子 IC（Pearson/Spearman）、Top-Q vs Bottom-Q 收益差、胜率、组合夏普/最大回撤，并与随机基线对照；并按仓库纪律给出 `NOT_ENOUGH_DATA / EXPLORATORY / WEAK_EVIDENCE / PROMISING` 等状态，**绝不自动接入生产**（Phase 3 Strict No-Decision Rule）。

---

## 5. 结论与下一步

**结论（本沙箱）**：技术因子的 OOS 有效性**无法在本环境判定**——yfinance 限流使 10y 真实行情不可得，本地行情仅 10 天不足以回测。所有脚本与仓库函数已验证可独立串联。

**下一步建议**：
1. **在 GitHub Actions 或非限流网络重跑**（推荐）：Action runner 出口通常不受 Yahoo 限流，且有真实 egress。`fetch_history.py` 的分批 + 重试已就位，直接 `python3 fetch_history.py && python3 build_factor_snapshot.py && python3 run_backtest.py && python3 run_validation.py` 即可得真实 IC / 五分位 / 组合指标。
2. **若仍受限于流**：可改用仓库已有的 `quant_factor_price_history.csv` 的生产级拉取链路（Phase 2B 的 `quant_factor_price.py`）在 CI 上补齐 10y 历史，再喂给本实验的 `build/backtest/validation`。
3. **真实结论判读**：只看"随机基线对照"与"IC 显著性"，不要被单期 Top-Q 收益误导；技术因子在美股大盘股上普遍 IC 偏低（|IC|>0.05 已算可用，>0.1 强），预期真实值远低于本次合成演示。
4. **12-06 后是否正式集成**：取决于真实 IC 是否稳定为正且单调；即便 PROMISING 也只作研究证据，按纪律不自动改生产权重/门槛。

---

## 6. 铁律确认

- 本文为**报告 + 方法 + 合成验证**，**未修改** `/tmp/us` 任何文件；未 `push`/`rebase`/`commit`。
- 今 21:00 scan 与周二 06:23 review 链路未触及（实验脚本只在 `/tmp/experiment/`，且 import 为只读）。
- 所有"真实市场结论"相关数字**均未产生**；合成数字已明确标注"非证据"。
- `/tmp/experiment/` 产物：`history.csv`（合成）、`snapshot.csv`、`backtest.csv`、`summary.csv`、`validation.csv`、`correlation.csv`、`report.json`、`results.json` —— 均为实验目录文件，不影响仓库。
