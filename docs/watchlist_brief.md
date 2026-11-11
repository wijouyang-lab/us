# Watchlist Brief — 24 只

> 生成：`scripts/ticker_brief.py --watchlist ... --md`　仓库：us　日期：latest

- 共 **24** 只票（LLY, NXPI, ABNB, UNP, AIG, APP, CLX, FAST, DECK, GE, AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, AVGO, TSM, BRK-B, JPM, V, UNH, XOM）：**4** 只有 AI 快照记录，**9** 只有交易记录

## 宏观环境（结论化，仅打印一次）

- 恐惧贪婪指数：**36.60（恐惧）**　时间戳：2026-11-11T13:43:57+00:00
- FedWatch（会议 2026-12-09，目标区间 3.75%-4.00%）：加息 25bp **92.0%**
- 宏观指标：
  - 10Y国债：**5.00%**（前值 4.98%，2026-11-11，N/A）
  - 5Y国债：**4.83%**（前值 4.81%，2026-11-11，N/A）
  - 13周国债：**4.12%**（前值 4.11%，2026-11-11，N/A）
  - CPI：**指数 337.51**（前值 指数 336.94，2026-10-01，N/A）
  - 核心CPI：**指数 339.90**（前值 指数 338.90，2026-10-01，N/A）
  - 失业率：**4.10%**（前值 4.20%，2026-10-01，N/A）
- 美联储讲话：最近一次 **Waller**（11-10 15:54，Bloomberg.com）：Interest-Rate Hike Debate Sparked by Fed's Waller, Logan After Hot Inflation - Bloomberg.com　立场：**N/A**

---

## 1. `LLY`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：2

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-26 | Core_Dragon | scan | N/A | N/A |
| 2026-10-21 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Healthcare　Price：1432.29

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.6255 | 55 |
| Momentum_20D_Pct | 22.7842 | 97 |
| Momentum_60D_Pct | 21.0563 | 95 |
| Realized_Volatility_20D_Pct | 40.4061 | 49 |
| Volume_Ratio_20D | 0.9819 | 74 |
| ZScore_20D | 1.5612 | 79 |
| Beta_60D_SPY | 0.4141 | 44 |
| Stock_RS_20D_vs_SPY | 26.3947 | 97 |
| Quant_Score | 83.0000 | 100 |
| MA20 | 1326.7100 | 100 |
| MA50 | 1224.5100 | 99 |
| ATR_Pct | 3.3500 | 50 |
| KDJ_J | 77.8300 | 75 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 2. `NXPI`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：2

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-23 | Core_Dragon | scan | N/A | N/A |
| 2026-10-20 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Other　Price：261.56

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.4681 | 36 |
| Momentum_20D_Pct | 15.5709 | 87 |
| Momentum_60D_Pct | 12.3926 | 87 |
| Realized_Volatility_20D_Pct | 50.1006 | 67 |
| Volume_Ratio_20D | 0.5906 | 10 |
| ZScore_20D | 1.2007 | 67 |
| Beta_60D_SPY | 1.7053 | 83 |
| Stock_RS_20D_vs_SPY | 19.1814 | 87 |
| Quant_Score | 82.0000 | 99 |
| MA20 | 246.8200 | 82 |
| MA50 | 237.4900 | 81 |
| ATR_Pct | 4.4900 | 77 |
| KDJ_J | 51.6700 | 52 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 3. `ABNB`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Other　Price：186.90

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 11.9430 | 96 |
| Momentum_20D_Pct | 12.8759 | 81 |
| Momentum_60D_Pct | 4.2445 | 68 |
| Realized_Volatility_20D_Pct | 55.7707 | 73 |
| Volume_Ratio_20D | 0.9980 | 77 |
| ZScore_20D | 1.9869 | 91 |
| Beta_60D_SPY | 0.8442 | 64 |
| Stock_RS_20D_vs_SPY | 16.4864 | 81 |
| Quant_Score | 81.0000 | 99 |
| MA20 | 173.8700 | 71 |
| MA50 | 169.1600 | 70 |
| ATR_Pct | 3.6600 | 61 |
| KDJ_J | 84.6500 | 82 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 4. `UNP`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Other　Price：300.62

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.9261 | 33 |
| Momentum_20D_Pct | 6.4669 | 56 |
| Momentum_60D_Pct | 0.2401 | 56 |
| Realized_Volatility_20D_Pct | 26.6105 | 17 |
| Volume_Ratio_20D | 0.7327 | 33 |
| ZScore_20D | 0.7115 | 49 |
| Beta_60D_SPY | 0.2890 | 38 |
| Stock_RS_20D_vs_SPY | 10.0774 | 56 |
| Quant_Score | 81.0000 | 99 |
| MA20 | 296.1500 | 87 |
| MA50 | 286.4900 | 87 |
| ATR_Pct | 2.2100 | 11 |
| KDJ_J | 28.6400 | 29 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 5. `AIG`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Other　Price：82.32

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.2228 | 62 |
| Momentum_20D_Pct | 6.0142 | 53 |
| Momentum_60D_Pct | 8.5873 | 80 |
| Realized_Volatility_20D_Pct | 29.5141 | 24 |
| Volume_Ratio_20D | 0.9767 | 73 |
| ZScore_20D | 1.1322 | 63 |
| Beta_60D_SPY | 0.0602 | 24 |
| Stock_RS_20D_vs_SPY | 9.6247 | 53 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 80.7500 | 39 |
| MA50 | 77.6400 | 37 |
| ATR_Pct | 2.3200 | 16 |
| KDJ_J | 63.4500 | 65 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 6. `APP`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-07 | Observation | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Other　Price：395.51

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 61.0973 | 100 |
| Momentum_20D_Pct | 45.2586 | 100 |
| Momentum_60D_Pct | 26.7742 | 98 |
| Realized_Volatility_20D_Pct | 134.7378 | 100 |
| Volume_Ratio_20D | 0.9461 | 69 |
| ZScore_20D | 2.3950 | 96 |
| Beta_60D_SPY | -0.9868 | 0 |
| Stock_RS_20D_vs_SPY | 48.8691 | 100 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 285.3800 | 86 |
| MA50 | 296.8700 | 87 |
| ATR_Pct | 5.7200 | 84 |
| KDJ_J | 116.2300 | 100 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 7. `CLX`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Other　Price：106.60

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 13.6461 | 98 |
| Momentum_20D_Pct | 26.2285 | 99 |
| Momentum_60D_Pct | 0.6230 | 57 |
| Realized_Volatility_20D_Pct | 38.9305 | 47 |
| Volume_Ratio_20D | 3.3711 | 99 |
| ZScore_20D | 2.6992 | 97 |
| Beta_60D_SPY | 0.6679 | 57 |
| Stock_RS_20D_vs_SPY | 29.8390 | 99 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 91.1700 | 46 |
| MA50 | 87.9500 | 44 |
| ATR_Pct | 3.2600 | 47 |
| KDJ_J | 95.3800 | 93 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 8. `FAST`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Other　Price：54.84

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.7965 | 82 |
| Momentum_20D_Pct | 6.6304 | 57 |
| Momentum_60D_Pct | 7.0467 | 78 |
| Realized_Volatility_20D_Pct | 23.4606 | 7 |
| Volume_Ratio_20D | 0.5666 | 7 |
| ZScore_20D | 2.8723 | 98 |
| Beta_60D_SPY | 0.3792 | 41 |
| Stock_RS_20D_vs_SPY | 10.2409 | 57 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 52.3300 | 21 |
| MA50 | 50.8600 | 21 |
| ATR_Pct | 2.5100 | 22 |
| KDJ_J | 94.9000 | 92 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 9. `DECK`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Other　Price：89.79

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 6.7785 | 89 |
| Momentum_20D_Pct | 6.8674 | 58 |
| Momentum_60D_Pct | -0.3551 | 54 |
| Realized_Volatility_20D_Pct | 42.1504 | 53 |
| Volume_Ratio_20D | 0.7830 | 44 |
| ZScore_20D | 1.7093 | 83 |
| Beta_60D_SPY | 0.9864 | 68 |
| Stock_RS_20D_vs_SPY | 10.4779 | 58 |
| Quant_Score | 79.0000 | 96 |
| MA20 | 85.0400 | 43 |
| MA50 | 82.4500 | 41 |
| ATR_Pct | 3.6300 | 60 |
| KDJ_J | 92.2100 | 89 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 10. `GE`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Industrials　Price：337.91

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 5.3762 | 85 |
| Momentum_20D_Pct | 9.8430 | 72 |
| Momentum_60D_Pct | -8.5321 | 32 |
| Realized_Volatility_20D_Pct | 42.5332 | 54 |
| Volume_Ratio_20D | 0.5954 | 11 |
| ZScore_20D | 2.2390 | 95 |
| Beta_60D_SPY | 1.0146 | 69 |
| Stock_RS_20D_vs_SPY | 13.4535 | 72 |
| Quant_Score | 79.0000 | 96 |
| MA20 | 309.9200 | 88 |
| MA50 | 314.5500 | 88 |
| ATR_Pct | 3.2700 | 47 |
| KDJ_J | 98.9400 | 95 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Industrials）
- N/A（无成交记录）

---

## 11. `AAPL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Technology　Price：348.51

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 5.0045 | 83 |
| Momentum_20D_Pct | 2.1215 | 42 |
| Momentum_60D_Pct | 14.0450 | 90 |
| Realized_Volatility_20D_Pct | 27.0534 | 18 |
| Volume_Ratio_20D | 0.5963 | 12 |
| ZScore_20D | 1.0715 | 61 |
| Beta_60D_SPY | 0.5214 | 50 |
| Stock_RS_20D_vs_SPY | 5.7320 | 42 |
| Quant_Score | 71.0000 | 86 |
| MA20 | 344.2300 | 91 |
| MA50 | 337.2700 | 90 |
| ATR_Pct | 2.5100 | 22 |
| KDJ_J | 84.2900 | 81 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 12. `MSFT`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Technology　Price：533.16

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.3359 | 64 |
| Momentum_20D_Pct | -1.8935 | 33 |
| Momentum_60D_Pct | 10.9941 | 85 |
| Realized_Volatility_20D_Pct | 37.3962 | 44 |
| Volume_Ratio_20D | 1.0365 | 79 |
| ZScore_20D | 0.1520 | 39 |
| Beta_60D_SPY | 1.2979 | 74 |
| Stock_RS_20D_vs_SPY | 1.7170 | 33 |
| Quant_Score | 27.0000 | 15 |
| MA20 | 531.0900 | 96 |
| MA50 | 517.8000 | 96 |
| ATR_Pct | 2.9700 | 37 |
| KDJ_J | 63.1900 | 65 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 13. `NVDA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Technology　Price：168.89

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -18.2883 | 2 |
| Momentum_20D_Pct | -26.0940 | 7 |
| Momentum_60D_Pct | -24.9411 | 9 |
| Realized_Volatility_20D_Pct | 49.6981 | 66 |
| Volume_Ratio_20D | 3.1071 | 99 |
| ZScore_20D | -2.9920 | 0 |
| Beta_60D_SPY | 1.5307 | 80 |
| Stock_RS_20D_vs_SPY | -22.4835 | 7 |
| Quant_Score | 20.0000 | 1 |
| MA20 | 206.1800 | 77 |
| MA50 | 218.0000 | 78 |
| ATR_Pct | 5.1500 | 80 |
| KDJ_J | 4.9300 | 7 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 14. `GOOGL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Communication　Price：287.38

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.6247 | 68 |
| Momentum_20D_Pct | -18.7687 | 12 |
| Momentum_60D_Pct | -16.4593 | 17 |
| Realized_Volatility_20D_Pct | 50.1800 | 67 |
| Volume_Ratio_20D | 0.7106 | 28 |
| ZScore_20D | -0.9679 | 24 |
| Beta_60D_SPY | 0.9684 | 68 |
| Stock_RS_20D_vs_SPY | -15.1582 | 12 |
| Quant_Score | 27.0000 | 15 |
| MA20 | 310.8900 | 89 |
| MA50 | 330.7200 | 89 |
| ATR_Pct | 3.6300 | 60 |
| KDJ_J | 49.5000 | 48 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 15. `AMZN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Consumer Discretionary　Price：270.87

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 8.0498 | 92 |
| Momentum_20D_Pct | 4.7529 | 50 |
| Momentum_60D_Pct | 3.6585 | 65 |
| Realized_Volatility_20D_Pct | 42.6559 | 55 |
| Volume_Ratio_20D | 0.7824 | 43 |
| ZScore_20D | 2.1620 | 94 |
| Beta_60D_SPY | 1.2795 | 73 |
| Stock_RS_20D_vs_SPY | 8.3634 | 50 |
| Quant_Score | 68.0000 | 81 |
| MA20 | 255.2600 | 84 |
| MA50 | 254.1800 | 84 |
| ATR_Pct | 3.5000 | 55 |
| KDJ_J | 98.9300 | 95 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 16. `META`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Communication　Price：641.39

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.2784 | 73 |
| Momentum_20D_Pct | -15.8833 | 16 |
| Momentum_60D_Pct | 12.7283 | 88 |
| Realized_Volatility_20D_Pct | 41.4279 | 51 |
| Volume_Ratio_20D | 0.5226 | 3 |
| ZScore_20D | -0.3194 | 32 |
| Beta_60D_SPY | 1.4450 | 78 |
| Stock_RS_20D_vs_SPY | -12.2728 | 16 |
| Quant_Score | 27.0000 | 15 |
| MA20 | 651.5400 | 98 |
| MA50 | 677.5700 | 97 |
| ATR_Pct | 3.7600 | 63 |
| KDJ_J | 107.8800 | 99 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 17. `TSLA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Consumer Discretionary　Price：379.78

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -4.6976 | 20 |
| Momentum_20D_Pct | 1.2126 | 39 |
| Momentum_60D_Pct | 11.9304 | 86 |
| Realized_Volatility_20D_Pct | 60.0803 | 77 |
| Volume_Ratio_20D | 0.5870 | 10 |
| ZScore_20D | -0.0346 | 37 |
| Beta_60D_SPY | 2.1464 | 87 |
| Stock_RS_20D_vs_SPY | 4.8231 | 39 |
| Quant_Score | 35.0000 | 41 |
| MA20 | 380.6500 | 92 |
| MA50 | 372.9600 | 92 |
| ATR_Pct | 4.3900 | 75 |
| KDJ_J | 41.3100 | 40 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 18. `AVGO`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Technology　Price：331.98

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.0452 | 39 |
| Momentum_20D_Pct | -7.0891 | 24 |
| Momentum_60D_Pct | -15.4040 | 18 |
| Realized_Volatility_20D_Pct | 66.2870 | 81 |
| Volume_Ratio_20D | 1.1352 | 87 |
| ZScore_20D | 0.0969 | 38 |
| Beta_60D_SPY | 2.2455 | 89 |
| Stock_RS_20D_vs_SPY | -3.4786 | 24 |
| Quant_Score | 35.0000 | 41 |
| MA20 | 329.1000 | 90 |
| MA50 | 346.1300 | 90 |
| ATR_Pct | 4.8000 | 78 |
| KDJ_J | 63.8500 | 65 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 19. `TSM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-11-11 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- N/A（无成交记录）

---

## 20. `BRK-B`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-02 | Observation | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Other　Price：583.34

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.7157 | 81 |
| Momentum_20D_Pct | 12.0536 | 78 |
| Momentum_60D_Pct | 17.0825 | 92 |
| Realized_Volatility_20D_Pct | 19.8547 | 2 |
| Volume_Ratio_20D | 0.9039 | 63 |
| ZScore_20D | 2.1617 | 94 |
| Beta_60D_SPY | 0.0965 | 26 |
| Stock_RS_20D_vs_SPY | 15.6641 | 78 |
| Quant_Score | 69.0000 | 83 |
| MA20 | 549.7300 | 97 |
| MA50 | 524.5500 | 96 |
| ATR_Pct | 1.7200 | 1 |
| KDJ_J | 87.6000 | 85 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 21. `JPM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Financials　Price：342.07

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.2101 | 52 |
| Momentum_20D_Pct | 3.2103 | 44 |
| Momentum_60D_Pct | -5.2333 | 40 |
| Realized_Volatility_20D_Pct | 27.7348 | 20 |
| Volume_Ratio_20D | 0.6578 | 20 |
| ZScore_20D | 0.9879 | 58 |
| Beta_60D_SPY | 0.7794 | 61 |
| Stock_RS_20D_vs_SPY | 6.8208 | 44 |
| Quant_Score | 69.0000 | 83 |
| MA20 | 337.9500 | 91 |
| MA50 | 341.2400 | 90 |
| ATR_Pct | 2.2800 | 14 |
| KDJ_J | 21.0100 | 23 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 22. `V`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Financials　Price：423.00

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.6137 | 47 |
| Momentum_20D_Pct | 6.8020 | 58 |
| Momentum_60D_Pct | 17.8798 | 94 |
| Realized_Volatility_20D_Pct | 26.4350 | 16 |
| Volume_Ratio_20D | 0.7549 | 36 |
| ZScore_20D | 1.0878 | 61 |
| Beta_60D_SPY | 0.4435 | 45 |
| Stock_RS_20D_vs_SPY | 10.4125 | 58 |
| Quant_Score | 75.0000 | 93 |
| MA20 | 411.8500 | 94 |
| MA50 | 387.5300 | 92 |
| ATR_Pct | 2.1300 | 9 |
| KDJ_J | 46.1000 | 45 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 23. `UNH`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Healthcare　Price：405.12

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.1681 | 41 |
| Momentum_20D_Pct | 7.2427 | 60 |
| Momentum_60D_Pct | 2.4013 | 63 |
| Realized_Volatility_20D_Pct | 31.1244 | 30 |
| Volume_Ratio_20D | 0.7346 | 33 |
| ZScore_20D | -0.0615 | 36 |
| Beta_60D_SPY | 0.4082 | 43 |
| Stock_RS_20D_vs_SPY | 10.8532 | 60 |
| Quant_Score | 71.0000 | 86 |
| MA20 | 407.1400 | 94 |
| MA50 | 391.0600 | 92 |
| ATR_Pct | 2.8800 | 33 |
| KDJ_J | 49.6600 | 49 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 24. `XOM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-11（该日共 298 只；全表 26 个日期 / 7498 行）
- Sector：Energy　Price：164.47

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -7.3200 | 12 |
| Momentum_20D_Pct | -5.5205 | 28 |
| Momentum_60D_Pct | 1.8642 | 61 |
| Realized_Volatility_20D_Pct | 31.7353 | 31 |
| Volume_Ratio_20D | 0.8070 | 48 |
| ZScore_20D | -1.9598 | 3 |
| Beta_60D_SPY | -0.4851 | 3 |
| Stock_RS_20D_vs_SPY | -1.9100 | 28 |
| Quant_Score | 22.0000 | 3 |
| MA20 | 176.5100 | 72 |
| MA50 | 169.0600 | 70 |
| ATR_Pct | 2.8200 | 32 |
| KDJ_J | -4.5300 | 3 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Energy）
- N/A（无成交记录）

---

说明：只读简报；缺失项统一 N/A。宏观环境在头部统一展示，不重复。
