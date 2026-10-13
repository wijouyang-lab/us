# US 仓库 Quant Research / Factor Lab —— 第一阶段只读审计报告

> 审计时间：2026-10-06 · 审计方式：**全程只读**（未修改任何文件、未 commit、未 push、未 dispatch）
> 审计对象：`wijouyang-lab/us`（本地 clone `/tmp/us`，`HEAD=369f83d`，`origin/main=da262d0c`）

---

## 0. 仓库当前状态（只读快照）

| 项 | 值 |
|---|---|
| branch | `main` |
| 本地 HEAD | `369f83d` |
| origin/main | `da262d0c`（远端有 dashboard-data 自动提交领先，本地未同步） |
| 工作区改动 | `modified: 0`；仅有未跟踪 `__pycache__/`（无业务文件） |
| 核心代码 | `scan.py` 3859 行 / `review.py` 3677 行 / `portfolio_50000.py` 534 行 / `dashboard_export.py` 2962 行 |
| 数据文件 | `trade_history.csv` 409 行 / `review_history.csv` 1572 行 |
| 测试 | 10 个 `tests/test_*.py`（含 38 项 Portfolio 测试） |
| workflows | `scan.yml`（cron `7 13 * * 1-5`）/ `review.yml`（cron `0 22 * * 1-5`）/ `dashboard-data.yml`（`*/15`）/ `evolve.yml` |

---

## 1. 当前 Scan 量化指标完整清单

以下是 `scan.py` **实际计算**的指标（按公式/位置/去向逐项核实，非变量名猜测）：

| 因子/指标 | 已计算 | Python 位置 | 数据周期 | 进推荐记录 | 进 AI Prompt | 进 CSV | 可复用 |
|---|---|---|---|---|---|---|---|
| **RSI(14)** | ✅ | `build_stock_pool` L879 `ta.rsi` | 日线 6mo | ✅ `RSI` | ✅ | ✅ | ✅ |
| **MACD 线/信号/柱** | ✅ | L878 `ta.macd` | 日线 6mo | ✅ `MACD_HIST_*`/`MACD趋势` | ✅（趋势） | ✅ | ✅ |
| **MACD 金叉** | ✅ | L899 手工判断 | 日线 | ✅ `MACD金叉` | ❌（间接） | ✅ | ✅ |
| **MACD 绿柱缩短** | ✅ | L900 | 日线 | ✅ | ❌ | ✅ | ✅ |
| **MA20** | ✅ | L880 `ta.sma(20)` | 日线 6mo | ✅ `MA20` | ✅ | ✅(仅66条) | ✅ |
| **MA50** | ✅ | L881 `ta.sma(50)` | 日线 6mo | ✅ `MA50` | ✅ | ✅(仅66条) | ✅ |
| **MA200** | ❌ | — | — | — | — | — | 需新增 |
| **MA20 斜率(5D)** | ✅ | L972 `(ma20_now/ma20_prev5-1)` | 日线 | ✅ `MA20_Slope_Pct_5D` | ✅ slope5d | ❌ | ✅ |
| **乖离率 Bias** | ✅ | L903 `(Close-MA20)/MA20` | 日线 | ✅ `乖离率(%)` | ✅ | ✅(409/409) | ✅ |
| **ATR(14)** | ✅ | L882 `ta.atr` | 日线 6mo | ✅ `ATR_Pct` | ❌（仅风控门槛） | ✅(187条) | ✅ |
| **KDJ(J)** | ✅ | L938-953 手写 KDJ | 日线 9日 | ✅ `KDJ_J`/`KDJ_J回升`/`KDJ_J超卖` | ✅ | ✅ | ✅ |
| **量比 Volume Ratio** | ✅ | L956-958 `vol[-1]/avg5` | 日线 | ✅ `量比` | ✅ | ✅ | ✅ |
| **近5日最大量比** | ✅ | L963-968 | 日线 5日 | ✅ `近5日最大量比` | ✅ recentVol | ✅ | ✅ |
| **放量阳线** | ✅ | L969 | 日线 5日 | ✅ `近5日放量阳线`/`量能放大` | ❌ | ✅ | ✅ |
| **周线共振(MA5>MA10+MACD升)** | ✅ | L910-934 | 周线 1y | ✅ `周线共振`/`周线MACD上升`/`周线MACD_V型` | ❌（间接） | ✅ | ✅ |
| **蜡烛形态(吞没/锤子/刺穿/启明星)** | ✅ | L976-995 | 日线 | ✅ `看涨形态` | ❌ | ❌ | 部分 |
| **周期共振(日+周MACD)** | ✅ | `check_period_resonance` L1263 | 日+周 | ✅ `周期共振` | ❌ | ✅ | ✅ |
| **技术确认数** | ✅ | `screen_technical_setups` L1271 | — | ✅ `技术确认数/信号` | ✅ | ✅ | ✅ |
| **技术评分(0-40)** | ✅ | L1313 | — | ✅ `技术评分` | ❌ | ✅ | ✅ |
| **CCI** | ❌ | — | — | — | — | — | 需新增 |
| **Bollinger Band** | ❌ | — | — | — | — | — | 需新增 |
| **Stochastic(独立)** | ❌ | —（KDJ 已含，但非标准 Stoch %K/%D） | — | — | — | — | 需新增 |
| **Momentum/ROC** | ❌ | — | — | — | — | — | **需新增** |
| **Z-Score** | ❌ | — | — | — | — | — | **需新增** |
| **Beta** | ❌ | — | — | — | — | — | **需新增** |
| **实现波动率** | ❌ | —（仅有 ATR%） | — | — | — | — | **需新增** |
| **估值评分(0-20)** | ✅ | `enrich_pool_with_fundamentals` L685-720 | 行业相对 | ✅ `估值评分` | ✅ | ✅ | ✅ |
| **PE_TTM/Forward/EPS/PB** | ✅ | L672 从 yfinance info | 快照 | ✅ | ✅ PE_F/EPS/PB | ✅(130条) | ✅ |
| **营收/盈利增长/ROE/净利率** | ✅ | L672 | 快照 | ✅ | ❌ | ✅(71条) | ✅ |
| **Market_Cap** | ✅ | L672 | 快照 | ✅ | ❌ | ✅ | ✅ |
| **Avg_Dollar_Volume_20D** | ✅ | L1007 | 日线 20日 | ✅ | ❌ | ✅ | ✅ |
| **Sector_RS_20D_Pct** | ✅ | `get_market_regime_context` L1086-1091 | 11行业ETF 20日 | ✅ | ✅ | ✅(仅8条) | ✅ |
| **Market_Regime** | ✅ | L1049-1093 | SPY/VIX | ✅ | ✅ | ✅(仅8条) | ✅ |
| **VIX** | ✅ | L1063 | 15日 | ✅ | ✅ | ✅(仅8条) | ✅ |
| **SPY Above MA20 / 5D return** | ✅ | L1056-1062 | SPY 60日 | ❌（仅用于门控） | 间接 | ❌ | 部分 |
| **Event_Score(0-20)** | ✅ | `score_candidate_quality` L1140-1151 | 新闻关键词 | ✅ | ✅ | ✅ | ✅ |
| **Quant_Score(0-100)** | ✅ | L1185 | 组合 | ✅ | ✅ | ✅(71条) | ✅ |
| **AI_Score(0-100)** | ✅ | `match_pool_to_report` | AI 输出 | ✅ | — | ✅(71条) | ✅ |
| **Final_Score** | ✅ | L3768 `0.7*Quant+0.3*AI` | 组合 | ✅ | — | ✅ | ✅ |

**关键结论**：现有系统已具备 **约 25 个可落盘的量化因子**，覆盖技术面（RSI/MACD/MA/ATR/KDJ/量比/周线/形态/斜率）、估值面（PE/PB/EPS/增长）、事件面、相对强弱、市场环境。**但缺少专业 Quant 因子**：Momentum/ROC、Z-Score、Beta、实现波动率、Volume Ratio(20D)、Bollinger、CCI、标准 Stochastic。

---

## 2. 已进入 AI Prompt 的指标（`generate_ai_report` 的 `pool_lines`）

每只股票一行，当前字段（实测模板，327 字符不含新闻正文）：

```
[TICKER] Name | 昨收:Price | 盘前:Premarket(Change%) | 盘前时间 | RSI | Bias% |
MA20 + slope5d% | MACD趋势 | KDJ | Vol(量比) + recentVol | 技术确认数 |
Quant/100 (F/E/T/R 四维) | Market Regime | VIX | SectorRS20D | 估值/20 |
PE_F | EPS | PB | 新闻快照 | 新闻(最多6条)
```

| 指标 | 进 Prompt | 传入格式 | 每只字符规模 | 是否必要 |
|---|---|---|---|---|
| RSI / Bias / MA20+斜率 / MACD / KDJ / 量比 | ✅ | 数值内联 | ~60 字符 | 必要（技术状态） |
| Quant + F/E/T/R 四维拆分 | ✅ | `Quant:78.5/100 (F28 E16 T20 R14.5)` | ~40 字符 | 必要（评分） |
| Market/VIX/SectorRS20D | ✅ | 内联 | ~30 字符 | 必要（环境） |
| 估值/PE_F/EPS/PB | ✅ | 内联 | ~40 字符 | 必要（估值） |
| 个股新闻(≤6条) | ✅ | 中文正文 | **~200-400 字符（大头）** | 必要（事件） |

**每只股票 Prompt 约 400-800 token（新闻是主要消耗）**。若硬门槛后约 30-80 只进入 AI，则 `pool_lines` 合计约 **1.2万-6.4万 token**，是单次 AI 调用的最大输入块。

---

## 3. 已保存到 CSV / trade_history 的指标

`trade_history.csv` 共 **54 列**，其中量化因子字段 30+ 个（详见第 1 节"进 CSV"列）。**但存在严重的时间断层**（这是回测可行性的核心约束）：

| 字段组 | 首次出现 | 覆盖条数 | 说明 |
|---|---|---|---|
| RSI / Bias | 2026-05-27 | 409/409 | ✅ 全历史可用 |
| ATR_Pct | 2026-05-28 | 187/409 | 约一半 |
| MA20 / MA50 | 2026-05-28 | 66/409 | 仅早期少量 |
| PE / EPS / PB | 2026-09-02 | 130/409 | 估值因子 9 月起 |
| 增长/ROE/净利率/MarketCap/ADV | 2026-09-17 | 71/409 | 基本面扩展 9/17 起 |
| **Quant_Score / AI_Score / 四维评分** | 2026-09-17 | 71/409 | 透明评分 9/17 起 |
| **Market_Regime / VIX / Sector_RS** | 2026-10-02 | 8/409 | **仅最新 8 条** |

`review_history.csv`（1572 行，315 个事件）含**里程碑未来收益**字段：`Price_5D/PnL_5D`（152 事件）、`PnL_10D`（114）、`PnL_20D`（59），是 Factor→Future Return 的**黄金数据源**。

---

## 4. 可直接复用的指标（无需重算）

| 指标 | 复用方式 | 样本量 |
|---|---|---|
| RSI、Bias、ATR_Pct | 直接从 trade_history 读 | 409/187 |
| MACD金叉、周线共振、KDJ回升、量能放大 | 布尔信号，直接读 | 409 |
| 技术确认数、技术评分 | 直接读 | 409 |
| Quant_Score、AI_Score、Final_Score | 直接读（9/17 起） | 71 |
| PE/PB/EPS/增长/ROE | 直接读（9/2、9/17 起） | 130/71 |
| 未来收益 PnL_5D/10D/20D | 从 review_history 事件级聚合 | 152/114/59 |

## 5. 必须重新计算的指标（历史数据缺失）

- **Momentum / ROC（5D/10D/20D/60D）**：trade_history 无此字段 → 需从 OHLC 重算。
- **Z-Score、Distance from MA20/MA50**：有 MA20 但覆盖仅 66 条，且无 MA50 完整序列 → 需重算。
- **Beta / Alpha**：无基准对齐序列 → 需重算（用 SPY 日收益回归）。
- **实现波动率（20D/60D）**：仅有 ATR%，无日收益标准差 → 需重算。
- **Volume Ratio 20D**：仅有 5D 量比 → 需重算。
- **Bollinger %B、CCI、标准 Stochastic**：完全缺失 → 需重算。
- **MA200**：缺失 → 需重算。

> 重算需要的历史 OHLC 当前**未被系统持久化**（`get_kline_data` 每次实时下载 `6mo`，用完即弃）。这是 Phase 1 必须补齐的基础设施缺口（见第 21 节）。

---

## 6. trade_history 可支持的回测（现在就能做，无需新数据）

实测 join `(Ticker, Date, Tag)` 后的事件样本：

| 因子 → 未来收益 | 样本量 | 结论 |
|---|---|---|
| RSI → PnL_5D | **154** | ✅ 可做 |
| RSI → PnL_10D | **111** | ✅ 可做（偏少） |
| RSI → PnL_20D | **58** | ⚠️ 勉强（<60） |
| ATR_Pct → PnL_5D | **128** | ✅ 可做 |
| MACD金叉/周线/KDJ/量能(布尔) → 5D/10D | 与上述同源 | ✅ 可做（分组胜率） |
| Bias → PnL_5D/10D | 154/111 | ✅ 可做 |
| Quant_Score → 闭环 PnL | 仅 14（Quant+Exit_Price） | ⚠️ 样本极小 |
| 技术评分 → 闭环 PnL | 153（Core 闭环） | ✅ 可做 |

**结论**：基于 `trade_history × review_history` 的 **RSI/ATR/Bias/MACD/技术信号 → 5D/10D 收益** 回测现在就能做，样本 100-150 级别（5D 维度），足以做**分组统计 + 单调性检查**，但不足以做高置信度因子选优。

## 7. trade_history 无法支持的回测

- **20D 以上长周期收益**：PnL_20D 仅 59 事件，60D 完全无数据。
- **新因子（Momentum/Z-Score/Beta/波动率）的历史验证**：字段从未落盘，需先重算历史 OHLC 才能回测。
- **Market_Regime × Factor**：Regime 字段仅 8 条（10-02 起），**当前完全无法回测**。
- **Quant_Score/AI_Score 的分层回测**：仅 71 条且与 Exit_Price 交集仅 14 条，**暂不可做**。
- **Position Sizing 研究**：portfolio 尚未初始化（无持仓历史），无 sizing 实证样本。

---

## 8. Market Regime 当前能力

系统已有**两层 Regime**，但持久化极不完整：

1. **技术 Regime**（`get_market_regime_context`）：`NORMAL / STRESSED / PANIC / UNKNOWN`，由 `VIX(≥25 STRESSED / ≥30 PANIC)` + `SPY vs MA20` + `SPY 5D return` 判定，含 **11 个行业 ETF 的 20D 相对 SPY 强弱**。
2. **事件 Regime**（`build_event_regime_gate`）：`NEUTRAL / HAWKISH_REPRICING / HAWKISH_WATCH / DOVISH_WATCH`，含 `hard_avoid_sectors / watch_sectors / confidence`。

| 能力 | 现状 | Quant 是否可复用 |
|---|---|---|
| VIX | ✅ 实时 | ✅ 可复用 |
| SPY MA20 / 5D return | ✅ 实时 | ✅ 可复用 |
| 行业相对强弱(11 ETF) | ✅ 实时 | ✅ 可复用 |
| Risk-On/Neutral/Risk-Off 三分类 | ❌ 未定义（现有是 4 类技术 + 4 类事件） | 需在 Quant 层**新增映射**，不改 scan |
| Breadth / 10Y / QQQ trend | ❌ 无 | 需新增 |
| **Regime 历史落盘** | ❌ 仅 8 条（10-02 起） | **Phase 1 需开始持久化** |

**回答"能否直接复用"**：能复用**实时计算逻辑**（同一套 SPY/VIX/行业 ETF 数据），但**历史序列几乎不存在**，Regime × Factor 回测需要从今天起持续积累，或重算历史 SPY/VIX 补齐。

---

## 9. 建议新增 Factor Library（分层）

### Layer 1 —— 现有 Scan 因子（直接读，零成本）
RSI、Bias、ATR_Pct、MACD金叉/绿柱、MA20/MA50/斜率、KDJ_J、量比、近5日最大量比、周线共振、技术确认数、技术评分、估值评分、PE/PB/EPS、Quant_Score、AI_Score、Final_Score、Sector_RS、VIX、Market_Regime。

### Layer 2 —— 新增标准 Quant Factors（建议优先，全部本地可算）

| 因子 | 公式 | 数据需求 | 研究价值 | 成本 |
|---|---|---|---|---|
| Momentum 5D/10D/20D | `Close/Close[-N]-1` | 日线 Close | 高 | 低 |
| ROC 60D | `Close/Close[-60]-1` | 60日 Close | 中 | 低 |
| 实现波动率 20D/60D | 日收益 std×√252 | 日线 Close | 高（仓位/止损） | 低 |
| Volume Ratio 20D | `Vol[-1]/mean(Vol[-20:-1])` | 日线 Volume | 中 | 低 |
| Z-Score(20D) | `(Close-MA20)/std20` | 日线 | 高（均值回归） | 低 |
| Dist from MA20/MA50 | `Close/MA-1` | 日线 | 高 | 低 |
| Beta(60D) | 对 SPY 日收益回归斜率 | 股票+SPY 日线 | 中 | 中 |
| Bollinger %B | `(Close-Lower)/(Upper-Lower)` | 日线 | 中 | 低 |
| CCI(20) | 标准公式 | 日线 | 低 | 低 |
| 标准 Stochastic %K/%D | 标准公式 | 日线 | 低 | 低 |
| 个股 vs SPY 相对强度 20D | `个股20D收益-SPY20D收益` | 个股+SPY | 高 | 低 |
| MA200 距离 | `Close/MA200-1` | 日线(需≥200根) | 中 | 低 |

> 全部为 **Python 本地纯计算**，不消耗 AI Token。数据源仅需 `yfinance` 日线 OHLCV（现有依赖已具备）。

---

## 10. Factor Backtest 方案

```
数据源：trade_history(因子) ⋈ review_history(PnL_5D/10D/20D)  ← 现有，无需新数据
         + Phase 1 新增的历史 OHLC 重算因子（补齐 Layer 2）
```

1. **事件级聚合**：review_history 每日快照 → 事件级取最新非空 PnL_N。
2. **因子分位**：每因子按值分 5 档（Top20% / 20-40% / 40-60% / 60-80% / Bottom20%）。
3. **每档统计**：n、Win Rate、Mean Return、Median Return、Profit Factor、Expectancy、Sharpe（样本够时）、Max Drawdown。
4. **单调性检验**：Top 档 vs Bottom 档的收益差（IC 方向）+ 简单 Spearman 相关。
5. **时间 OOS**：`evolve.py` 已实现 60/40 时间切分 OOS，可复用同一套逻辑做因子 OOS。
6. **诚实样本门槛**：单档 `n ≥ 8` 才输出结论，否则标"样本不足"（`evolve.py` 已有此纪律）。

**当前能立刻跑的回测**：RSI / ATR / Bias / MACD金叉 / 周线共振 / 技术确认数 → 5D/10D 收益（100-150 样本）。
**待补数据才能跑**：Momentum / Z-Score / Beta / 波动率 / Regime × Factor。

---

## 11. Market Regime × Factor 方案

框架：`Factor × Regime × Outcome`。

| 维度 | 现状 | 方案 |
|---|---|---|
| Regime 分类 | 现有 4 类技术 Regime + 4 类事件 Regime | Quant 层**新增** `Risk-On / Neutral / Risk-Off` 三分类映射（不改 scan 现有逻辑），由 SPY>MA20 且 VIX<阈值 → Risk-On，VIX≥25 或 SPY<MA20 → Risk-Off，其余 Neutral |
| 数据缺口 | Regime 历史仅 8 条 | **Phase 1 起逐日持久化 regime 快照**；或用 SPY/VIX 历史 OHLC 重算历史 regime（可回溯至 trade_history 起点 2026-05） |
| 交叉分析 | 无 | `RSI × Regime`、`MACD × Regime`、`Momentum × Regime` 的分组胜率/EV 表 |

> 结论：**框架可行，但 Regime 历史序列是硬缺口**，需要"从现在起积累 + 用 SPY/VIX 历史重算补齐过去 4 个月"双轨。

---

## 12. Position Sizing 方案（只研究，不改 Portfolio）

保持 `UNIT_DOLLARS=10000`、`MAX_OPEN_POSITIONS=4` 完全不动。研究层对比：

| 方法 | 说明 | 数据需求 |
|---|---|---|
| Equal Weight（基准） | 每 Unit $10K | 无（现状） |
| Volatility Adjusted | `Shares ∝ 1/ATR_Pct` 或 `1/实现波动率` | ATR%（已有）/ 波动率（需算） |
| ATR-based | 止损距离 = k×ATR，仓位 = 风险预算/止损距离 | ATR（已有） |
| Risk Parity | 波动率倒数归一 | 波动率（需算） |

> 产出为**研究报告**，不反向改 `portfolio_50000.py` 的正式逻辑。

---

## 13. Monte Carlo / Stress Test 方案

数据：真实 `trade_history` 闭环收益序列（153 条 Core 闭环，PnL_Pct 可算）。

| 方法 | 说明 |
|---|---|
| Bootstrap | 有放回重采样收益序列，N=10000 次，生成 equity curve 分布 |
| Monte Carlo | 对收益率抽样模拟 4-position 组合的 equity path |
| Max Drawdown 分布 | 从模拟路径统计 MDD 分位数 |
| P(亏损>X%) / P(达到+Y%) | 从分布读分位 |
| Worst-case sequence | 按真实亏损排序的最坏顺序 |
| Risk of ruin | 固定风险预算下的破产概率 |

**样本门槛（诚实声明）**：153 条闭环 + 59 条 20D 收益，对"盈亏分布形状"有一定参考，但 **Bootstrap 结论的置信区间会很宽**；报告须标注"样本量不足，仅作方向性参考，不虚构显著性"。真正有统计意义通常需要 **≥200-300 个独立闭环事件**，当前约 153，处于"可用但需谨慎"区间。

---

## 14. Daily Scan 架构（Quant 增量目标 +5%~10% Token）

```
Daily Scan（13:07 UTC）—— 不变
  scan.py 技术指标计算（现有）
      ↓
  【新增】quant_factor_lib.py：Python 本地算 Layer 2 因子（Momentum/Z-Score/Beta/波动率…）
      ↓
  【新增】本地聚合为「Quant 摘要」：每只股票只输出 2-3 个聚合字段
      ↓
  scan.py AI Prompt 的 pool_line 追加 1-2 个短字段（约 30-60 字符/只）
```

**关键设计原则**：**Python 算全部因子，AI 只收极少摘要**。绝不给 AI 塞几十个新因子。

具体：pool_line 末尾追加类似 `| QMom:2.1 Z:0.8 B:1.2`（约 25 字符/只，约 20-30 token/只）。若 50 只 → 增量约 **1000-1500 token**，相对当前 4-6 万 token 总输入，增幅 **~2-5%**，达标。

---

## 15. Weekly Quant Research 架构（After Market / 每周）

```
Weekly（新 workflow 或 evolve.yml 扩展）
  quant_research.py：
    1. Factor Performance（分位表 + 单调性）
    2. Factor Correlation（因子间相关矩阵）
    3. Factor Quantile 回测（5 档胜率/EV）
    4. Regime × Factor
    5. Position Sizing 对比
    6. Monte Carlo / Stress Test
  → 输出 quant_report.json / quant_report.html（只读，不反向改 scan）
```

运行频率：**每周 1 次**（如周六），绝不每分钟/每日跑深度研究。

---

## 16. 当前 AI Token 基线（估算）

单次 Scan 有 **4 次 AI 调用**：

| 调用 | 函数 | max_tokens(输出) | 输入规模(估) |
|---|---|---|---|
| 1 | `analyze_market_signals` | 12000 | 宏观新闻 ~3-6K token |
| 2 | `pre_scan_portfolio_review` | 3000 | 持仓+宏观 ~2-4K |
| 3 | `generate_ai_report`（**最大**） | 30000(Claude 时 8000) | 见下 |
| 4 | `enrich_verified_items_with_ai_details` | 10000 | 最终入账 ≤12 只 ~3-5K |

`generate_ai_report` 输入构成估算：
- 固定指令 + HTML 模板：~2-3K token
- 宏观新闻 `combined_news[:12000]`：~8-10K
- 经济数据 + 人物讲话 + event_regime + 演化规则：~4-6K
- **pool_lines（30-80 只 × 400-800）**：~12K-64K ← 最大变量

**当前每日 Scan 总 Input Token 估算：约 3万-9万 token（中位 ~5万），由候选池规模决定。**（注：无保留的运行日志可精确统计，此值为基于代码结构的估算，Phase 1 需用真实 usage 校准。）

---

## 17. Quant 后预计 Token 增量

| 项 | 增量 | 说明 |
|---|---|---|
| Daily AI Input | **+2%~5%**（约 +1000-1500 token/日） | 仅追加 1-2 个聚合字段 |
| Daily AI Output | 0 | 不改输出格式 |
| Weekly Research | 本地算，AI 可选 1 次"解读"（~5K） | 每周 1 次，非每日 |

**结论：达标（目标 +5%~10%）。** 前提是严格遵循"Python 本地算、AI 只收摘要"。

---

## 18. 当前 Scan 运行时间（估算）

无本地 Scan 日志（workflow 日志需 API 查询，当前 429 限流未查），基于代码复杂度估算：

| 阶段 | 预估 | 依据 |
|---|---|---|
| get_scan_pool（Top300 成交量） | 1-2 min | 批量 yfinance 5d |
| build_stock_pool（300 只 × 日线6mo + 周线1y，串行） | **20-50 min（主要瓶颈）** | 每只 2 次 yf.download，3 次重试 |
| 基本面（120 只，10 线程） | 2-4 min | ThreadPool |
| 新闻（逐只 RSS） | 3-8 min | 网络依赖 |
| 4 次 AI 调用 | 3-8 min | 流式 |
| 宏观数据（BLS/FRED/新闻） | 2-5 min | 多源抓取 |

**估算总量：30-75 分钟/次 Scan**（GitHub 默认 360 分钟上限内，无 timeout-minutes 覆盖）。

---

## 19. Quant 后预计新增运行时间

| 项 | 增量 | 说明 |
|---|---|---|
| Daily 因子计算（Layer 2，50-120 只） | **+10-30 秒** | 纯 pandas，复用已下载的 K 线，无额外下载 |
| Daily 因子落盘 | +2 秒 | 写 CSV |
| Weekly Factor Backtest | +1-3 min | 纯本地 |
| Weekly Monte Carlo（10000 次） | +30-60 秒 | 纯 numpy |
| Weekly 历史 OHLC 回填（首次） | +10-20 min（一次性） | 仅首次重算历史 |

**结论：Daily 增量可忽略（<1 分钟）；Weekly 一次性回填较慢但仅首次。** 运行时间不是障碍。

---

## 20. 分 Phase 实施计划

| Phase | 内容 | 改动范围 | 是否改 scan |
|---|---|---|---|
| **Phase 0（本次）** | 只读审计 | 无 | ❌ |
| **Phase 1** | ①`quant_factor_lib.py`（Layer 2 因子纯计算）②历史 OHLC 落盘（`quant_ohlc_cache/`）③因子逐日落盘（`quant_factors.csv`）④Daily pool_line 追加 2-3 聚合字段（+2%~5% Token） | 新增模块 + scan.py **最小 1 处追加字段** | ⚠️ 需极小改动 |
| **Phase 2** | `quant_backtest.py`：Factor 分位 → 5D/10D 收益，分位表+单调性+OOS | 新增模块（只读 trade_history/review_history） | ❌ |
| **Phase 3** | Regime × Factor；Regime 历史持久化 + SPY/VIX 重算回补 | 新增模块 | ❌ |
| **Phase 4** | Position Sizing 对比 + Monte Carlo/Stress Test | 新增模块（只读 portfolio 数据） | ❌ |
| **Phase 5** | Scan Feedback：**仅当**某因子经 ≥200 样本 OOS 验证有效，才以报告形式提示（不自动改 scan.py） | 报告产出 | ⚠️ 需你逐项确认 |

> Phase 1 中唯一触及 scan.py 的点是"pool_line 追加 2-3 个聚合字段"，属于最小侵入；若你希望**完全零改动 scan.py**，可将因子摘要作为独立 CSV 由 AI 侧读取（但当前架构下 AI 不读外部文件），故追加字段是低 Token 方案的最优解。此点留待你拍板。

---

## 21. 风险与数据缺口

| 风险/缺口 | 等级 | 说明 |
|---|---|---|
| **因子历史字段断层** | 🔴 高 | Quant_Score/Regime/VIX 仅最近 71/8 条，新因子无任何历史 → 大部分回测要等积累或重算 |
| **历史 OHLC 未持久化** | 🔴 高 | 重算 Layer 2 因子必须先补历史 K 线缓存 |
| **样本量偏少** | 🟠 中 | 5D 回测 154 样本、20D 仅 59、Quant_Score 闭环仅 14 → 统计显著性弱，需诚实标注 |
| **Scan 运行时间波动** | 🟠 中 | 串行 K 线下载 20-50 min，未来因子复用同一数据则无新增压力 |
| **Token 基线是估算** | 🟡 低 | 无精确 usage 记录，Phase 1 需首次运行校准 |
| **Regime × Factor 目前不可回测** | 🟠 中 | Regime 历史仅 8 条 |
| **AI 只收摘要的纪律** | 🟡 低 | 需在 Phase 1 测试里锁死"不得塞 N 个因子" |

---

## 22. 本次是否修改任何文件

**❌ 未修改任何文件。** 全程只读：未改代码、未 commit、未 push、未 dispatch、未 rerun。`git status` modified = 0（仅未跟踪 `__pycache__/`，系历史遗留，未触碰）。

---

## 最终架构原则（贯穿全部 Phase）

```
Scan  = 交易信号生成器（现有，不动）
Review = 交易结果验证器（现有，不动）
$50K Portfolio = 真实资金账本模拟（现有，不动）
Quant Research = 研究/统计/验证层（新增，只读式消费，产出报告）
```

- **Python 负责**：Factor Calculation、Statistics、Backtest、Monte Carlo、Risk Metrics。
- **AI 负责**：少量 Quant Summary 的解释 + 新闻/宏观/事件结合 + 综合分析。
- **Quant 不成为第二个 Scan**：不自动买卖、不反向改 Portfolio 规则、不自动优化 scan.py（Phase 5 反馈必须经你逐项确认）。

---

**下一步**：请确认 Phase 1 是否实施，以及是否接受"scan.py 最小 1 处 pool_line 追加 2-3 个聚合字段"的侵入（否则 Quant 摘要无法以低 Token 进入 AI）。
