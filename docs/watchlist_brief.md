# Watchlist Brief — 24 只

> 生成：`scripts/ticker_brief.py --watchlist ... --md`　仓库：us　日期：latest

- 共 **24** 只票（NXPI, AMZN, TEL, CSCO, VRT, CSX, NUE, TXN, CDNS, NDAQ, AAPL, MSFT, NVDA, GOOGL, META, TSLA, AVGO, TSM, BRK-B, JPM, V, UNH, XOM, COST）：**3** 只有 AI 快照记录，**8** 只有交易记录

## 宏观环境（结论化，仅打印一次）

- 恐惧贪婪指数：**35.86（恐惧）**　时间戳：2026-10-28T23:42:54+00:00
- FedWatch（会议 2026-10-28，目标区间 3.75%-4.00%）：维持不变 **93.4%** / 加息 25bp **6.6%**
- 宏观指标：
  - 10Y国债：**5.00%**（前值 4.99%，2026-10-28，N/A）
  - 5Y国债：**4.85%**（前值 4.84%，2026-10-28，N/A）
  - 13周国债：**4.05%**（前值 4.04%，2026-10-28，N/A）
  - CPI：**3.74%**（前值 N/A，2026-09-01，N/A）
  - 核心CPI：**2.57%**（前值 N/A，2026-09-01，N/A）
  - 失业率：**4.20%**（前值 4.10%，2026-09-01，N/A）
- 美联储讲话：最近一次 **N/A**（10-28 06:09，BNN Bloomberg）：U.S. Federal Reserve likely to skip rate hike despite elevated inflation - BNN Bloomberg　立场：**N/A**

---

## 1. `NXPI`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：2

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-23 | Core_Dragon | scan | N/A | N/A |
| 2026-10-20 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Other　Price：253.50

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 6.6919 | 91 |
| Momentum_20D_Pct | 7.2018 | 68 |
| Momentum_60D_Pct | 13.0838 | 86 |
| Realized_Volatility_20D_Pct | 36.8782 | 70 |
| Volume_Ratio_20D | 1.5725 | 86 |
| ZScore_20D | 2.6444 | 96 |
| Beta_60D_SPY | 2.1999 | 87 |
| Stock_RS_20D_vs_SPY | 6.4873 | 68 |
| Quant_Score | 85.0000 | 100 |
| MA20 | 235.7800 | 78 |
| MA50 | 230.9800 | 76 |
| ATR_Pct | 3.4100 | 68 |
| KDJ_J | 103.4500 | 95 |

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

## 2. `AMZN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Consumer Discretionary　Price：253.10

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -3.6287 | 16 |
| Momentum_20D_Pct | 2.6067 | 40 |
| Momentum_60D_Pct | -10.8866 | 25 |
| Realized_Volatility_20D_Pct | 32.8821 | 60 |
| Volume_Ratio_20D | 0.9605 | 50 |
| ZScore_20D | -0.2661 | 28 |
| Beta_60D_SPY | 1.3459 | 75 |
| Stock_RS_20D_vs_SPY | 1.8923 | 40 |
| Quant_Score | 84.0000 | 99 |
| MA20 | 254.9000 | 80 |
| MA50 | 255.2100 | 81 |
| ATR_Pct | 2.5300 | 38 |
| KDJ_J | 14.0100 | 13 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 3. `TEL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Other　Price：225.35

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 5.4713 | 88 |
| Momentum_20D_Pct | 6.0022 | 60 |
| Momentum_60D_Pct | 9.9429 | 80 |
| Realized_Volatility_20D_Pct | 30.6153 | 56 |
| Volume_Ratio_20D | 2.2292 | 95 |
| ZScore_20D | 3.0844 | 97 |
| Beta_60D_SPY | 1.9223 | 83 |
| Stock_RS_20D_vs_SPY | 5.2877 | 60 |
| Quant_Score | 83.0000 | 99 |
| MA20 | 215.0500 | 74 |
| MA50 | 210.0900 | 74 |
| ATR_Pct | 2.6900 | 45 |
| KDJ_J | 95.5100 | 87 |

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

## 4. `CSCO`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Other　Price：111.38

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.3763 | 83 |
| Momentum_20D_Pct | 4.1519 | 48 |
| Momentum_60D_Pct | -3.8667 | 47 |
| Realized_Volatility_20D_Pct | 34.8246 | 64 |
| Volume_Ratio_20D | 0.9142 | 44 |
| ZScore_20D | 0.0828 | 33 |
| Beta_60D_SPY | 1.4633 | 77 |
| Stock_RS_20D_vs_SPY | 3.4374 | 48 |
| Quant_Score | 82.0000 | 98 |
| MA20 | 111.2400 | 55 |
| MA50 | 110.1700 | 54 |
| ATR_Pct | 2.6500 | 42 |
| KDJ_J | 79.0900 | 67 |

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

## 5. `VRT`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Utilities　Price：208.56

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.4563 | 68 |
| Momentum_20D_Pct | -16.0184 | 5 |
| Momentum_60D_Pct | -20.7147 | 6 |
| Realized_Volatility_20D_Pct | 50.0923 | 85 |
| Volume_Ratio_20D | 1.4988 | 84 |
| ZScore_20D | -0.9033 | 16 |
| Beta_60D_SPY | 2.6399 | 91 |
| Stock_RS_20D_vs_SPY | -16.7328 | 5 |
| Quant_Score | 82.0000 | 98 |
| MA20 | 226.0000 | 77 |
| MA50 | 244.1400 | 79 |
| ATR_Pct | 5.5900 | 92 |
| KDJ_J | 57.1000 | 44 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Utilities）
- N/A（无成交记录）

---

## 6. `CSX`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：2

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-09-28 | Observation | scan | N/A | N/A |
| N/A | N/A | legacy | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Other　Price：52.27

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 8.7146 | 95 |
| Momentum_20D_Pct | 11.3786 | 86 |
| Momentum_60D_Pct | 4.8966 | 69 |
| Realized_Volatility_20D_Pct | 28.4757 | 46 |
| Volume_Ratio_20D | 0.9684 | 52 |
| ZScore_20D | 2.7743 | 97 |
| Beta_60D_SPY | -0.0640 | 23 |
| Stock_RS_20D_vs_SPY | 10.6642 | 86 |
| Quant_Score | 81.0000 | 97 |
| MA20 | 48.4200 | 20 |
| MA50 | 48.7700 | 20 |
| ATR_Pct | 1.9700 | 15 |
| KDJ_J | 96.6900 | 88 |

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

## 7. `NUE`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Other　Price：270.79

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.5526 | 78 |
| Momentum_20D_Pct | 14.6250 | 93 |
| Momentum_60D_Pct | 3.6398 | 67 |
| Realized_Volatility_20D_Pct | 29.3148 | 52 |
| Volume_Ratio_20D | 1.9880 | 92 |
| ZScore_20D | 2.1851 | 92 |
| Beta_60D_SPY | 1.1181 | 69 |
| Stock_RS_20D_vs_SPY | 13.9105 | 93 |
| Quant_Score | 81.0000 | 97 |
| MA20 | 253.0200 | 80 |
| MA50 | 252.4400 | 80 |
| ATR_Pct | 3.2200 | 65 |
| KDJ_J | 66.4700 | 52 |

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

## 8. `TXN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Technology　Price：308.91

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 11.2067 | 98 |
| Momentum_20D_Pct | 9.6631 | 80 |
| Momentum_60D_Pct | 14.8194 | 88 |
| Realized_Volatility_20D_Pct | 34.1016 | 62 |
| Volume_Ratio_20D | 1.2831 | 80 |
| ZScore_20D | 3.5404 | 99 |
| Beta_60D_SPY | 1.6301 | 78 |
| Stock_RS_20D_vs_SPY | 8.9486 | 80 |
| Quant_Score | 81.0000 | 97 |
| MA20 | 286.1900 | 85 |
| MA50 | 273.3000 | 84 |
| ATR_Pct | 3.1400 | 63 |
| KDJ_J | 114.0300 | 99 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 9. `CDNS`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Other　Price：343.08

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 7.2561 | 92 |
| Momentum_20D_Pct | 5.8334 | 59 |
| Momentum_60D_Pct | 2.0616 | 64 |
| Realized_Volatility_20D_Pct | 46.2585 | 82 |
| Volume_Ratio_20D | 2.0081 | 92 |
| ZScore_20D | 0.5052 | 41 |
| Beta_60D_SPY | 1.8647 | 82 |
| Stock_RS_20D_vs_SPY | 5.1189 | 59 |
| Quant_Score | 79.0000 | 97 |
| MA20 | 336.1100 | 88 |
| MA50 | 319.1700 | 87 |
| ATR_Pct | 3.8200 | 77 |
| KDJ_J | 83.2300 | 72 |

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

## 10. `NDAQ`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Other　Price：104.36

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 10.0844 | 98 |
| Momentum_20D_Pct | 13.6200 | 91 |
| Momentum_60D_Pct | 10.8562 | 82 |
| Realized_Volatility_20D_Pct | 31.2221 | 57 |
| Volume_Ratio_20D | 1.1539 | 71 |
| ZScore_20D | 2.3973 | 94 |
| Beta_60D_SPY | 0.3538 | 47 |
| Stock_RS_20D_vs_SPY | 12.9056 | 91 |
| Quant_Score | 79.0000 | 97 |
| MA20 | 95.1300 | 48 |
| MA50 | 95.1700 | 48 |
| ATR_Pct | 2.2400 | 24 |
| KDJ_J | 100.7800 | 93 |

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

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Technology　Price：347.10

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.2386 | 67 |
| Momentum_20D_Pct | 5.3734 | 57 |
| Momentum_60D_Pct | 14.3959 | 87 |
| Realized_Volatility_20D_Pct | 13.3579 | 1 |
| Volume_Ratio_20D | 1.0242 | 60 |
| ZScore_20D | 1.4215 | 75 |
| Beta_60D_SPY | 0.2916 | 43 |
| Stock_RS_20D_vs_SPY | 4.6589 | 57 |
| Quant_Score | 74.0000 | 93 |
| MA20 | 340.0700 | 89 |
| MA50 | 331.0600 | 88 |
| ATR_Pct | 1.8300 | 10 |
| KDJ_J | 56.3300 | 44 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 12. `MSFT`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Technology　Price：531.33

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.1015 | 42 |
| Momentum_20D_Pct | 4.3952 | 50 |
| Momentum_60D_Pct | 8.9572 | 78 |
| Realized_Volatility_20D_Pct | 19.6194 | 11 |
| Volume_Ratio_20D | 0.9672 | 52 |
| ZScore_20D | 0.3604 | 36 |
| Beta_60D_SPY | 1.2560 | 72 |
| Stock_RS_20D_vs_SPY | 3.6808 | 50 |
| Quant_Score | 30.0000 | 23 |
| MA20 | 528.9900 | 96 |
| MA50 | 510.1900 | 95 |
| ATR_Pct | 2.0600 | 20 |
| KDJ_J | 49.3500 | 40 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 13. `NVDA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Technology　Price：217.94

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.6791 | 50 |
| Momentum_20D_Pct | -4.0799 | 23 |
| Momentum_60D_Pct | 5.4684 | 71 |
| Realized_Volatility_20D_Pct | 30.2832 | 55 |
| Volume_Ratio_20D | 0.8230 | 30 |
| ZScore_20D | -0.7772 | 20 |
| Beta_60D_SPY | 2.0396 | 85 |
| Stock_RS_20D_vs_SPY | -4.7944 | 23 |
| Quant_Score | 27.0000 | 14 |
| MA20 | 224.4400 | 76 |
| MA50 | 222.1600 | 76 |
| ATR_Pct | 2.7300 | 47 |
| KDJ_J | 57.8300 | 46 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 14. `GOOGL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Communication　Price：320.58

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -5.7894 | 6 |
| Momentum_20D_Pct | -5.9662 | 18 |
| Momentum_60D_Pct | -14.1710 | 15 |
| Realized_Volatility_20D_Pct | 21.7831 | 22 |
| Volume_Ratio_20D | 1.1926 | 74 |
| ZScore_20D | -2.0152 | 4 |
| Beta_60D_SPY | 1.2121 | 71 |
| Stock_RS_20D_vs_SPY | -6.6807 | 18 |
| Quant_Score | 73.0000 | 91 |
| MA20 | 340.7700 | 89 |
| MA50 | 341.8900 | 89 |
| ATR_Pct | 2.5700 | 40 |
| KDJ_J | -3.0200 | 3 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 15. `META`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Communication　Price：620.19

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -10.6676 | 2 |
| Momentum_20D_Pct | -16.0533 | 5 |
| Momentum_60D_Pct | 5.0742 | 70 |
| Realized_Volatility_20D_Pct | 36.5058 | 69 |
| Volume_Ratio_20D | 2.6419 | 97 |
| ZScore_20D | -2.6273 | 2 |
| Beta_60D_SPY | 1.6757 | 79 |
| Stock_RS_20D_vs_SPY | -16.7677 | 5 |
| Quant_Score | 22.0000 | 1 |
| MA20 | 707.4700 | 97 |
| MA50 | 665.6500 | 97 |
| ATR_Pct | 3.9700 | 81 |
| KDJ_J | -7.8200 | 1 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 16. `TSLA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Consumer Discretionary　Price：407.46

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 9.0311 | 96 |
| Momentum_20D_Pct | 15.4801 | 95 |
| Momentum_60D_Pct | 26.5089 | 95 |
| Realized_Volatility_20D_Pct | 39.1498 | 73 |
| Volume_Ratio_20D | 1.2234 | 76 |
| ZScore_20D | 3.2345 | 98 |
| Beta_60D_SPY | 2.4658 | 89 |
| Stock_RS_20D_vs_SPY | 14.7656 | 95 |
| Quant_Score | 58.0000 | 64 |
| MA20 | 374.3100 | 90 |
| MA50 | 366.1200 | 90 |
| ATR_Pct | 3.3600 | 67 |
| KDJ_J | 103.4500 | 95 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 17. `AVGO`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Technology　Price：342.33

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.3806 | 68 |
| Momentum_20D_Pct | -3.5962 | 25 |
| Momentum_60D_Pct | -12.7221 | 18 |
| Realized_Volatility_20D_Pct | 41.8907 | 77 |
| Volume_Ratio_20D | 1.1851 | 74 |
| ZScore_20D | -0.3336 | 27 |
| Beta_60D_SPY | 2.3117 | 88 |
| Stock_RS_20D_vs_SPY | -4.3106 | 25 |
| Quant_Score | 71.0000 | 88 |
| MA20 | 347.0500 | 90 |
| MA50 | 354.4800 | 90 |
| ATR_Pct | 3.3800 | 68 |
| KDJ_J | 70.5000 | 59 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 18. `TSM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-28 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- N/A（无成交记录）

---

## 19. `BRK-B`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-02 | Observation | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Other　Price：542.99

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.5872 | 48 |
| Momentum_20D_Pct | 8.0900 | 72 |
| Momentum_60D_Pct | 5.8171 | 72 |
| Realized_Volatility_20D_Pct | 11.8695 | 1 |
| Volume_Ratio_20D | 0.6860 | 15 |
| ZScore_20D | 1.3163 | 70 |
| Beta_60D_SPY | -0.2444 | 12 |
| Stock_RS_20D_vs_SPY | 7.3755 | 72 |
| Quant_Score | 67.0000 | 79 |
| MA20 | 522.8900 | 96 |
| MA50 | 512.6000 | 96 |
| ATR_Pct | 1.1800 | 0 |
| KDJ_J | 76.1900 | 64 |

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

## 20. `JPM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Financials　Price：335.79

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.1581 | 45 |
| Momentum_20D_Pct | 0.2418 | 33 |
| Momentum_60D_Pct | -4.7782 | 45 |
| Realized_Volatility_20D_Pct | 13.4089 | 1 |
| Volume_Ratio_20D | 0.6464 | 11 |
| ZScore_20D | 0.9360 | 56 |
| Beta_60D_SPY | 0.3963 | 50 |
| Stock_RS_20D_vs_SPY | -0.4727 | 33 |
| Quant_Score | 32.0000 | 36 |
| MA20 | 333.6100 | 88 |
| MA50 | 344.3300 | 89 |
| ATR_Pct | 1.8000 | 9 |
| KDJ_J | 34.6900 | 30 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 21. `V`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Financials　Price：401.86

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -1.1585 | 33 |
| Momentum_20D_Pct | 9.8338 | 80 |
| Momentum_60D_Pct | 9.8969 | 80 |
| Realized_Volatility_20D_Pct | 20.2582 | 13 |
| Volume_Ratio_20D | 1.3985 | 82 |
| ZScore_20D | 0.7907 | 53 |
| Beta_60D_SPY | 0.3213 | 45 |
| Stock_RS_20D_vs_SPY | 9.1194 | 80 |
| Quant_Score | 72.0000 | 89 |
| MA20 | 388.8800 | 92 |
| MA50 | 378.7300 | 91 |
| ATR_Pct | 1.6600 | 4 |
| KDJ_J | 32.3800 | 28 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 22. `UNH`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Healthcare　Price：410.39

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -2.1156 | 25 |
| Momentum_20D_Pct | 9.4548 | 79 |
| Momentum_60D_Pct | -1.1965 | 53 |
| Realized_Volatility_20D_Pct | 29.7600 | 52 |
| Volume_Ratio_20D | 0.6199 | 9 |
| ZScore_20D | 0.9700 | 58 |
| Beta_60D_SPY | -0.0975 | 22 |
| Stock_RS_20D_vs_SPY | 8.7404 | 79 |
| Quant_Score | 35.0000 | 47 |
| MA20 | 392.6300 | 92 |
| MA50 | 389.0400 | 92 |
| ATR_Pct | 2.6900 | 45 |
| KDJ_J | 51.8200 | 41 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 23. `XOM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-28 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- N/A（无成交记录）

---

## 24. `COST`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-28（该日共 292 只；全表 16 个日期 / 4529 行）
- Sector：Consumer Staples　Price：992.13

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.2493 | 39 |
| Momentum_20D_Pct | 7.3049 | 68 |
| Momentum_60D_Pct | 3.9881 | 68 |
| Realized_Volatility_20D_Pct | 17.5446 | 5 |
| Volume_Ratio_20D | 1.0496 | 62 |
| ZScore_20D | 0.8649 | 54 |
| Beta_60D_SPY | -0.1000 | 21 |
| Stock_RS_20D_vs_SPY | 6.5904 | 68 |
| Quant_Score | 70.0000 | 86 |
| MA20 | 965.6300 | 99 |
| MA50 | 940.5200 | 99 |
| ATR_Pct | 1.6300 | 3 |
| KDJ_J | 40.2600 | 34 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Staples）
- N/A（无成交记录）

---

说明：只读简报；缺失项统一 N/A。宏观环境在头部统一展示，不重复。
