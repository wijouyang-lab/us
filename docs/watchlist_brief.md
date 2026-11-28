# Watchlist Brief — 24 只

> 生成：`scripts/ticker_brief.py --watchlist ... --md`　仓库：us　日期：latest

- 共 **24** 只票（V, MKC, AMGN, AIG, DIS, CSCO, UNP, AJG, PEP, DECK, AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, AVGO, TSM, BRK-B, JPM, UNH, XOM, COST）：**2** 只有 AI 快照记录，**7** 只有交易记录

## 宏观环境（结论化，仅打印一次）

- 恐惧贪婪指数：**24.89（极度恐惧）**　时间戳：2026-11-27T23:59:59+00:00
- FedWatch（会议 2026-12-09，目标区间 3.75%-4.00%）：维持不变 **3.0%** / 加息 25bp **97.0%**
- 宏观指标：
  - 10Y国债：**4.90%**（前值 4.85%，2026-11-27，N/A）
  - 5Y国债：**4.71%**（前值 4.66%，2026-11-27，N/A）
  - 13周国债：**4.16%**（前值 4.16%，2026-11-27，N/A）
  - CPI：**指数 337.51**（前值 指数 336.94，2026-10-01，N/A）
  - 核心CPI：**指数 339.90**（前值 指数 338.90，2026-10-01，N/A）
  - 失业率：**4.10%**（前值 4.20%，2026-10-01，N/A）
- 美联储讲话：最近一次 **Trump**（11-25 20:49，www.equiti.com）：Trump Tariffs 2027: Inflation, Fed Rates & Stock Risks - www.equiti.com　立场：**N/A**

---

## 1. `V`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Financials　Price：424.39

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.2085 | 73 |
| Momentum_20D_Pct | 5.9386 | 72 |
| Momentum_60D_Pct | 13.8782 | 89 |
| Realized_Volatility_20D_Pct | 30.1170 | 27 |
| Volume_Ratio_20D | 0.8927 | 44 |
| ZScore_20D | 0.6950 | 72 |
| Beta_60D_SPY | 0.4289 | 45 |
| Stock_RS_20D_vs_SPY | 13.1391 | 72 |
| Quant_Score | 83.0000 | 100 |
| MA20 | 419.0900 | 94 |
| MA50 | 397.2100 | 93 |
| ATR_Pct | 2.2000 | 12 |
| KDJ_J | 72.8100 | 73 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 2. `MKC`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-02 | Observation | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Other　Price：49.85

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 7.5977 | 98 |
| Momentum_20D_Pct | 8.2284 | 80 |
| Momentum_60D_Pct | -8.1275 | 36 |
| Realized_Volatility_20D_Pct | 40.9936 | 51 |
| Volume_Ratio_20D | 1.7595 | 98 |
| ZScore_20D | 1.7033 | 90 |
| Beta_60D_SPY | -0.0891 | 12 |
| Stock_RS_20D_vs_SPY | 15.4289 | 80 |
| Quant_Score | 82.0000 | 99 |
| MA20 | 47.6400 | 20 |
| MA50 | 47.1700 | 20 |
| ATR_Pct | 3.4500 | 52 |
| KDJ_J | 105.0500 | 97 |

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

## 3. `AMGN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Healthcare　Price：469.24

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 5.7109 | 94 |
| Momentum_20D_Pct | 3.8532 | 64 |
| Momentum_60D_Pct | 7.1031 | 75 |
| Realized_Volatility_20D_Pct | 34.3550 | 37 |
| Volume_Ratio_20D | 1.1656 | 81 |
| ZScore_20D | 0.8511 | 76 |
| Beta_60D_SPY | 0.5818 | 54 |
| Stock_RS_20D_vs_SPY | 11.0537 | 64 |
| Quant_Score | 81.0000 | 99 |
| MA20 | 460.7400 | 95 |
| MA50 | 435.6200 | 94 |
| ATR_Pct | 2.7300 | 30 |
| KDJ_J | 94.2400 | 91 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 4. `AIG`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Other　Price：82.23

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.9970 | 71 |
| Momentum_20D_Pct | 2.9419 | 61 |
| Momentum_60D_Pct | 8.3685 | 77 |
| Realized_Volatility_20D_Pct | 26.9691 | 17 |
| Volume_Ratio_20D | 0.8292 | 32 |
| ZScore_20D | 0.8104 | 75 |
| Beta_60D_SPY | 0.1470 | 26 |
| Stock_RS_20D_vs_SPY | 10.1424 | 61 |
| Quant_Score | 80.0000 | 98 |
| MA20 | 81.2400 | 38 |
| MA50 | 78.8900 | 36 |
| ATR_Pct | 2.0400 | 8 |
| KDJ_J | 47.7300 | 50 |

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

## 5. `DIS`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Communication　Price：125.60

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.6479 | 76 |
| Momentum_20D_Pct | 15.1871 | 94 |
| Momentum_60D_Pct | 18.2451 | 94 |
| Realized_Volatility_20D_Pct | 29.7613 | 26 |
| Volume_Ratio_20D | 1.5952 | 96 |
| ZScore_20D | 2.2163 | 96 |
| Beta_60D_SPY | 0.3957 | 43 |
| Stock_RS_20D_vs_SPY | 22.3876 | 94 |
| Quant_Score | 80.0000 | 98 |
| MA20 | 118.0900 | 57 |
| MA50 | 111.5100 | 55 |
| ATR_Pct | 2.5500 | 23 |
| KDJ_J | 91.1200 | 88 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 6. `CSCO`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Other　Price：94.20

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -3.0665 | 24 |
| Momentum_20D_Pct | -14.5888 | 18 |
| Momentum_60D_Pct | -14.1607 | 22 |
| Realized_Volatility_20D_Pct | 56.1509 | 72 |
| Volume_Ratio_20D | 0.8040 | 29 |
| ZScore_20D | -0.9179 | 30 |
| Beta_60D_SPY | 1.4960 | 81 |
| Stock_RS_20D_vs_SPY | -7.3883 | 18 |
| Quant_Score | 79.0000 | 98 |
| MA20 | 98.1600 | 49 |
| MA50 | 105.3900 | 52 |
| ATR_Pct | 4.3000 | 71 |
| KDJ_J | 40.4800 | 45 |

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

## 7. `UNP`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Other　Price：298.38

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.8375 | 41 |
| Momentum_20D_Pct | 0.1948 | 53 |
| Momentum_60D_Pct | 2.6702 | 66 |
| Realized_Volatility_20D_Pct | 28.5412 | 22 |
| Volume_Ratio_20D | 0.9971 | 59 |
| ZScore_20D | -0.0706 | 57 |
| Beta_60D_SPY | 0.2807 | 35 |
| Stock_RS_20D_vs_SPY | 7.3952 | 53 |
| Quant_Score | 79.0000 | 98 |
| MA20 | 298.8500 | 88 |
| MA50 | 288.7700 | 87 |
| ATR_Pct | 2.3600 | 16 |
| KDJ_J | 37.1200 | 39 |

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

## 8. `AJG`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Other　Price：292.39

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.6036 | 85 |
| Momentum_20D_Pct | 12.2763 | 91 |
| Momentum_60D_Pct | 11.5992 | 87 |
| Realized_Volatility_20D_Pct | 34.3905 | 37 |
| Volume_Ratio_20D | 1.3146 | 89 |
| ZScore_20D | 1.8790 | 93 |
| Beta_60D_SPY | -0.1825 | 6 |
| Stock_RS_20D_vs_SPY | 19.4768 | 91 |
| Quant_Score | 78.0000 | 97 |
| MA20 | 281.1700 | 87 |
| MA50 | 257.1600 | 84 |
| ATR_Pct | 2.7100 | 29 |
| KDJ_J | 82.4600 | 81 |

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

## 9. `PEP`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Consumer Staples　Price：143.93

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.4520 | 66 |
| Momentum_20D_Pct | 8.5199 | 82 |
| Momentum_60D_Pct | 2.9616 | 66 |
| Realized_Volatility_20D_Pct | 27.2899 | 19 |
| Volume_Ratio_20D | 0.6163 | 5 |
| ZScore_20D | 0.8719 | 77 |
| Beta_60D_SPY | -0.1051 | 12 |
| Stock_RS_20D_vs_SPY | 15.7204 | 82 |
| Quant_Score | 78.0000 | 97 |
| MA20 | 141.4500 | 65 |
| MA50 | 134.5300 | 62 |
| ATR_Pct | 2.3300 | 16 |
| KDJ_J | 48.9800 | 51 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Staples）
- N/A（无成交记录）

---

## 10. `DECK`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Other　Price：85.56

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.3445 | 74 |
| Momentum_20D_Pct | 5.9698 | 72 |
| Momentum_60D_Pct | 1.1587 | 60 |
| Realized_Volatility_20D_Pct | 51.6870 | 66 |
| Volume_Ratio_20D | 0.8861 | 42 |
| ZScore_20D | 0.3089 | 65 |
| Beta_60D_SPY | 0.9564 | 70 |
| Stock_RS_20D_vs_SPY | 13.1703 | 72 |
| Quant_Score | 77.0000 | 95 |
| MA20 | 84.7100 | 41 |
| MA50 | 82.8100 | 40 |
| ATR_Pct | 4.0600 | 66 |
| KDJ_J | 77.5900 | 75 |

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

## 11. `AAPL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Technology　Price：355.58

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.8881 | 58 |
| Momentum_20D_Pct | 3.4174 | 63 |
| Momentum_60D_Pct | 9.3655 | 80 |
| Realized_Volatility_20D_Pct | 28.8497 | 23 |
| Volume_Ratio_20D | 1.0725 | 69 |
| ZScore_20D | 1.2016 | 81 |
| Beta_60D_SPY | 0.5250 | 51 |
| Stock_RS_20D_vs_SPY | 10.6179 | 63 |
| Quant_Score | 72.0000 | 87 |
| MA20 | 348.6700 | 92 |
| MA50 | 343.0500 | 91 |
| ATR_Pct | 2.4100 | 18 |
| KDJ_J | 66.0400 | 67 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 12. `MSFT`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Technology　Price：489.93

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -3.6121 | 21 |
| Momentum_20D_Pct | -7.7362 | 32 |
| Momentum_60D_Pct | -2.2135 | 49 |
| Realized_Volatility_20D_Pct | 38.9040 | 48 |
| Volume_Ratio_20D | 0.8701 | 38 |
| ZScore_20D | -1.6136 | 6 |
| Beta_60D_SPY | 0.9065 | 68 |
| Stock_RS_20D_vs_SPY | -0.5357 | 32 |
| Quant_Score | 27.0000 | 14 |
| MA20 | 517.1400 | 95 |
| MA50 | 519.5500 | 95 |
| ATR_Pct | 3.4500 | 52 |
| KDJ_J | 24.7100 | 22 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 13. `NVDA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Technology　Price：149.30

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -1.0996 | 38 |
| Momentum_20D_Pct | -30.6807 | 6 |
| Momentum_60D_Pct | -31.3374 | 7 |
| Realized_Volatility_20D_Pct | 138.0444 | 98 |
| Volume_Ratio_20D | 1.0868 | 71 |
| ZScore_20D | -1.0579 | 25 |
| Beta_60D_SPY | 3.0942 | 96 |
| Stock_RS_20D_vs_SPY | -23.4802 | 6 |
| Quant_Score | 25.0000 | 7 |
| MA20 | 172.4800 | 71 |
| MA50 | 203.6500 | 76 |
| ATR_Pct | 8.9600 | 93 |
| KDJ_J | 72.1300 | 72 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 14. `GOOGL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Communication　Price：273.10

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -3.3069 | 24 |
| Momentum_20D_Pct | -15.9408 | 15 |
| Momentum_60D_Pct | -18.4825 | 16 |
| Realized_Volatility_20D_Pct | 58.5980 | 73 |
| Volume_Ratio_20D | 0.8865 | 43 |
| ZScore_20D | -1.0518 | 25 |
| Beta_60D_SPY | 1.1177 | 74 |
| Stock_RS_20D_vs_SPY | -8.7403 | 15 |
| Quant_Score | 32.0000 | 38 |
| MA20 | 283.0500 | 87 |
| MA50 | 318.2400 | 89 |
| ATR_Pct | 4.3400 | 71 |
| KDJ_J | 27.5500 | 27 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 15. `AMZN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Consumer Discretionary　Price：244.43

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -8.7062 | 7 |
| Momentum_20D_Pct | -3.9945 | 41 |
| Momentum_60D_Pct | -4.1150 | 46 |
| Realized_Volatility_20D_Pct | 46.9036 | 61 |
| Volume_Ratio_20D | 1.1575 | 79 |
| ZScore_20D | -1.4751 | 10 |
| Beta_60D_SPY | 1.1202 | 74 |
| Stock_RS_20D_vs_SPY | 3.2060 | 41 |
| Quant_Score | 27.0000 | 14 |
| MA20 | 257.1900 | 85 |
| MA50 | 255.1200 | 84 |
| ATR_Pct | 4.2700 | 70 |
| KDJ_J | 13.5200 | 8 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 16. `META`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Communication　Price：609.89

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -1.0529 | 38 |
| Momentum_20D_Pct | -0.4245 | 51 |
| Momentum_60D_Pct | 5.4188 | 71 |
| Realized_Volatility_20D_Pct | 48.9321 | 63 |
| Volume_Ratio_20D | 0.9763 | 56 |
| ZScore_20D | -0.2813 | 51 |
| Beta_60D_SPY | 1.4046 | 79 |
| Stock_RS_20D_vs_SPY | 6.7760 | 51 |
| Quant_Score | 32.0000 | 38 |
| MA20 | 615.2700 | 97 |
| MA50 | 672.4200 | 97 |
| ATR_Pct | 4.1600 | 68 |
| KDJ_J | 48.6000 | 51 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 17. `TSLA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Consumer Discretionary　Price：380.14

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.9330 | 40 |
| Momentum_20D_Pct | -5.9571 | 36 |
| Momentum_60D_Pct | 6.7539 | 74 |
| Realized_Volatility_20D_Pct | 72.6951 | 82 |
| Volume_Ratio_20D | 0.9807 | 56 |
| ZScore_20D | -0.1835 | 55 |
| Beta_60D_SPY | 2.0826 | 88 |
| Stock_RS_20D_vs_SPY | 1.2433 | 36 |
| Quant_Score | 51.0000 | 60 |
| MA20 | 382.1500 | 93 |
| MA50 | 377.1700 | 92 |
| ATR_Pct | 5.1500 | 78 |
| KDJ_J | 61.3100 | 65 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 18. `AVGO`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Technology　Price：300.86

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -15.0233 | 1 |
| Momentum_20D_Pct | -14.4823 | 18 |
| Momentum_60D_Pct | -18.6161 | 16 |
| Realized_Volatility_20D_Pct | 83.3531 | 86 |
| Volume_Ratio_20D | 1.0800 | 71 |
| ZScore_20D | -1.3825 | 13 |
| Beta_60D_SPY | 1.9273 | 87 |
| Stock_RS_20D_vs_SPY | -7.2818 | 18 |
| Quant_Score | 30.0000 | 22 |
| MA20 | 326.9900 | 90 |
| MA50 | 340.5500 | 90 |
| ATR_Pct | 6.6400 | 86 |
| KDJ_J | 2.7400 | 3 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 19. `TSM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-11-27 无因子快照

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

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Other　Price：579.32

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.8179 | 57 |
| Momentum_20D_Pct | 7.2140 | 77 |
| Momentum_60D_Pct | 15.3266 | 90 |
| Realized_Volatility_20D_Pct | 20.3572 | 7 |
| Volume_Ratio_20D | 0.8032 | 29 |
| ZScore_20D | 0.4575 | 68 |
| Beta_60D_SPY | 0.1329 | 25 |
| Stock_RS_20D_vs_SPY | 14.4144 | 77 |
| Quant_Score | 35.0000 | 47 |
| MA20 | 573.7400 | 96 |
| MA50 | 540.4100 | 95 |
| ATR_Pct | 1.6100 | 0 |
| KDJ_J | 28.0100 | 28 |

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

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Financials　Price：316.74

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -2.2739 | 30 |
| Momentum_20D_Pct | -6.6490 | 35 |
| Momentum_60D_Pct | -10.7649 | 30 |
| Realized_Volatility_20D_Pct | 31.7089 | 31 |
| Volume_Ratio_20D | 1.0509 | 67 |
| ZScore_20D | -1.5995 | 7 |
| Beta_60D_SPY | 0.7345 | 61 |
| Stock_RS_20D_vs_SPY | 0.5515 | 35 |
| Quant_Score | 32.0000 | 38 |
| MA20 | 333.6600 | 90 |
| MA50 | 335.3300 | 90 |
| ATR_Pct | 2.5300 | 23 |
| KDJ_J | 18.2300 | 13 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 22. `UNH`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Healthcare　Price：346.19

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -1.0631 | 38 |
| Momentum_20D_Pct | -14.9619 | 17 |
| Momentum_60D_Pct | -12.6445 | 25 |
| Realized_Volatility_20D_Pct | 50.3862 | 65 |
| Volume_Ratio_20D | 0.8837 | 42 |
| ZScore_20D | -1.4196 | 12 |
| Beta_60D_SPY | 0.2147 | 31 |
| Stock_RS_20D_vs_SPY | -7.7615 | 17 |
| Quant_Score | 35.0000 | 47 |
| MA20 | 384.3200 | 93 |
| MA50 | 386.4900 | 92 |
| ATR_Pct | 4.5200 | 73 |
| KDJ_J | 20.1300 | 16 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 23. `XOM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Energy　Price：158.08

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -1.5569 | 34 |
| Momentum_20D_Pct | -13.1524 | 21 |
| Momentum_60D_Pct | -3.9319 | 46 |
| Realized_Volatility_20D_Pct | 31.1295 | 29 |
| Volume_Ratio_20D | 1.4289 | 93 |
| ZScore_20D | -1.2075 | 19 |
| Beta_60D_SPY | -0.2369 | 4 |
| Stock_RS_20D_vs_SPY | -5.9519 | 21 |
| Quant_Score | 27.0000 | 14 |
| MA20 | 167.5600 | 70 |
| MA50 | 168.8500 | 70 |
| ATR_Pct | 2.5000 | 21 |
| KDJ_J | 1.5600 | 2 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Energy）
- N/A（无成交记录）

---

## 24. `COST`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-11-27（该日共 298 只；全表 37 个日期 / 10775 行）
- Sector：Consumer Staples　Price：1086.81

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.8946 | 40 |
| Momentum_20D_Pct | 10.5909 | 87 |
| Momentum_60D_Pct | 15.6230 | 91 |
| Realized_Volatility_20D_Pct | 21.1159 | 8 |
| Volume_Ratio_20D | 1.0329 | 63 |
| ZScore_20D | 0.4995 | 69 |
| Beta_60D_SPY | -0.1054 | 11 |
| Stock_RS_20D_vs_SPY | 17.7914 | 87 |
| Quant_Score | 32.0000 | 38 |
| MA20 | 1072.2500 | 99 |
| MA50 | 997.9800 | 99 |
| ATR_Pct | 1.7600 | 3 |
| KDJ_J | 24.4500 | 22 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Staples）
- N/A（无成交记录）

---

说明：只读简报；缺失项统一 N/A。宏观环境在头部统一展示，不重复。
