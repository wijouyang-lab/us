# Watchlist Brief — 24 只

> 生成：`scripts/ticker_brief.py --watchlist ... --md`　仓库：us　日期：latest

- 共 **24** 只票（COP, APA, NXPI, WRB, OXY, ABNB, AMGN, MNST, AAPL, SYK, MSFT, NVDA, GOOGL, AMZN, META, TSLA, AVGO, TSM, BRK-B, JPM, V, UNH, XOM, COST）：**5** 只有 AI 快照记录，**7** 只有交易记录

## 宏观环境（结论化，仅打印一次）

- 恐惧贪婪指数：**26.86（恐惧）**　时间戳：2026-10-19T12:42:16+00:00
- FedWatch（会议 2026-10-28，目标区间 3.75%-4.00%）：维持不变 **84.5%** / 加息 25bp **15.5%**
- 宏观指标：
  - 10Y国债：**5.10%**（前值 5.10%，2026-10-19，中性）
  - 5Y国债：**4.90%**（前值 4.90%，2026-10-19，中性）
  - 13周国债：**4.07%**（前值 4.07%，2026-10-19，中性）
  - CPI：**4.00%**（前值 N/A，2026-09-01，偏空）
  - 核心CPI：**2.79%**（前值 N/A，2026-09-01，中性）
  - 失业率：**4.20%**（前值 4.10%，2026-09-01，偏空）
- 美联储讲话：最近一次 **Warsh**（10-16 13:21，PBS）：美联储主席沃什表示价格稳定是关键，但未就利率发出信号　立场：**中性**

---

## 1. `COP`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Energy　Price：146.51

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 9.2543 | 99 |
| Momentum_20D_Pct | 11.1355 | 95 |
| Momentum_60D_Pct | 21.8885 | 92 |
| Realized_Volatility_20D_Pct | 27.9233 | 53 |
| Volume_Ratio_20D | 1.1772 | 67 |
| ZScore_20D | 2.7553 | 87 |
| Beta_60D_SPY | -1.0239 | 1 |
| Stock_RS_20D_vs_SPY | 10.9307 | 95 |
| Quant_Score | 81.0000 | 100 |
| MA20 | 131.6400 | 61 |
| MA50 | 131.7700 | 60 |
| ATR_Pct | 2.2100 | 26 |
| KDJ_J | 107.3900 | 95 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Energy）
- N/A（无成交记录）

---

## 2. `APA`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：3

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-19 | Core_Dragon | scan | N/A | N/A |
| 2026-10-02 | Observation | scan | N/A | N/A |
| 2026-09-29 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Other　Price：49.15

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 7.1273 | 94 |
| Momentum_20D_Pct | 9.5387 | 92 |
| Momentum_60D_Pct | 34.9533 | 96 |
| Realized_Volatility_20D_Pct | 35.7410 | 73 |
| Volume_Ratio_20D | 1.1160 | 61 |
| ZScore_20D | 2.5527 | 85 |
| Beta_60D_SPY | -1.0663 | 1 |
| Stock_RS_20D_vs_SPY | 9.3339 | 92 |
| Quant_Score | 80.0000 | 99 |
| MA20 | 44.5500 | 19 |
| MA50 | 43.6100 | 17 |
| ATR_Pct | 3.1000 | 65 |
| KDJ_J | 97.6700 | 80 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：8（按日期倒序展示最近 8 笔）

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-16（仅日期） | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14（仅日期） | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13（仅日期） | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13（仅日期） | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07（仅日期） | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07（仅日期） | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07（仅日期） | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07（仅日期） | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 3. `NXPI`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Other　Price：229.33

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.7955 | 42 |
| Momentum_20D_Pct | 0.5877 | 51 |
| Momentum_60D_Pct | -17.2960 | 9 |
| Realized_Volatility_20D_Pct | 32.8506 | 69 |
| Volume_Ratio_20D | 1.3808 | 82 |
| ZScore_20D | -0.7211 | 29 |
| Beta_60D_SPY | 1.7020 | 80 |
| Stock_RS_20D_vs_SPY | 0.3829 | 51 |
| Quant_Score | 80.0000 | 99 |
| MA20 | 233.9900 | 81 |
| MA50 | 230.1800 | 80 |
| ATR_Pct | 3.5400 | 73 |
| KDJ_J | 33.8400 | 27 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：8（按日期倒序展示最近 8 笔）

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-16（仅日期） | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14（仅日期） | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13（仅日期） | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13（仅日期） | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07（仅日期） | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07（仅日期） | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07（仅日期） | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07（仅日期） | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 4. `WRB`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-07 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Other　Price：75.42

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.8811 | 77 |
| Momentum_20D_Pct | 7.7583 | 87 |
| Momentum_60D_Pct | 2.7101 | 65 |
| Realized_Volatility_20D_Pct | 19.5015 | 19 |
| Volume_Ratio_20D | 0.8589 | 20 |
| ZScore_20D | 2.3775 | 80 |
| Beta_60D_SPY | -0.4432 | 6 |
| Stock_RS_20D_vs_SPY | 7.5534 | 87 |
| Quant_Score | 80.0000 | 99 |
| MA20 | 70.1400 | 34 |
| MA50 | 69.8200 | 33 |
| ATR_Pct | 1.8800 | 12 |
| KDJ_J | 92.4500 | 68 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：8（按日期倒序展示最近 8 笔）

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-16（仅日期） | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14（仅日期） | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13（仅日期） | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13（仅日期） | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07（仅日期） | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07（仅日期） | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07（仅日期） | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07（仅日期） | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 5. `OXY`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Energy　Price：62.38

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.7764 | 67 |
| Momentum_20D_Pct | 6.0163 | 78 |
| Momentum_60D_Pct | 8.2986 | 75 |
| Realized_Volatility_20D_Pct | 30.6309 | 62 |
| Volume_Ratio_20D | 1.2536 | 73 |
| ZScore_20D | 2.0229 | 71 |
| Beta_60D_SPY | -0.9404 | 2 |
| Stock_RS_20D_vs_SPY | 5.8115 | 78 |
| Quant_Score | 79.0000 | 98 |
| MA20 | 58.5300 | 27 |
| MA50 | 59.3200 | 25 |
| ATR_Pct | 2.4500 | 35 |
| KDJ_J | 92.1100 | 67 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Energy）
- N/A（无成交记录）

---

## 6. `ABNB`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Other　Price：173.70

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.7206 | 75 |
| Momentum_20D_Pct | 4.5001 | 72 |
| Momentum_60D_Pct | 26.2630 | 95 |
| Realized_Volatility_20D_Pct | 40.7759 | 78 |
| Volume_Ratio_20D | 0.9773 | 40 |
| ZScore_20D | 2.1157 | 76 |
| Beta_60D_SPY | 0.9061 | 62 |
| Stock_RS_20D_vs_SPY | 4.2953 | 72 |
| Quant_Score | 78.0000 | 97 |
| MA20 | 162.1000 | 68 |
| MA50 | 172.7900 | 69 |
| ATR_Pct | 2.8800 | 59 |
| KDJ_J | 93.0300 | 70 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：8（按日期倒序展示最近 8 笔）

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-16（仅日期） | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14（仅日期） | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13（仅日期） | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13（仅日期） | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07（仅日期） | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07（仅日期） | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07（仅日期） | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07（仅日期） | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 7. `AMGN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Healthcare　Price：432.49

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.2471 | 72 |
| Momentum_20D_Pct | 12.1457 | 97 |
| Momentum_60D_Pct | 16.4172 | 88 |
| Realized_Volatility_20D_Pct | 29.1260 | 58 |
| Volume_Ratio_20D | 0.8209 | 15 |
| ZScore_20D | 1.9106 | 69 |
| Beta_60D_SPY | 0.5429 | 51 |
| Stock_RS_20D_vs_SPY | 11.9409 | 97 |
| Quant_Score | 78.0000 | 97 |
| MA20 | 413.3900 | 94 |
| MA50 | 415.0100 | 94 |
| ATR_Pct | 2.4600 | 36 |
| KDJ_J | 92.5200 | 69 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 8. `MNST`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-02 | Observation | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Other　Price：45.73

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.7892 | 75 |
| Momentum_20D_Pct | 2.2814 | 58 |
| Momentum_60D_Pct | -2.2445 | 51 |
| Realized_Volatility_20D_Pct | 24.3776 | 39 |
| Volume_Ratio_20D | 1.2312 | 70 |
| ZScore_20D | 2.4230 | 82 |
| Beta_60D_SPY | -0.1867 | 13 |
| Stock_RS_20D_vs_SPY | 2.0766 | 58 |
| Quant_Score | 78.0000 | 97 |
| MA20 | 43.3800 | 18 |
| MA50 | 44.7300 | 18 |
| ATR_Pct | 2.2000 | 25 |
| KDJ_J | 89.7800 | 64 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：8（按日期倒序展示最近 8 笔）

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-16（仅日期） | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14（仅日期） | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13（仅日期） | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13（仅日期） | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07（仅日期） | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07（仅日期） | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07（仅日期） | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07（仅日期） | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 9. `AAPL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Technology　Price：343.46

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.0259 | 50 |
| Momentum_20D_Pct | 2.1807 | 58 |
| Momentum_60D_Pct | 6.7773 | 72 |
| Realized_Volatility_20D_Pct | 16.2008 | 6 |
| Volume_Ratio_20D | 1.5628 | 90 |
| ZScore_20D | 1.6228 | 63 |
| Beta_60D_SPY | -0.0199 | 21 |
| Stock_RS_20D_vs_SPY | 1.9759 | 58 |
| Quant_Score | 77.0000 | 96 |
| MA20 | 337.4200 | 90 |
| MA50 | 325.7000 | 89 |
| ATR_Pct | 1.9500 | 15 |
| KDJ_J | 74.8600 | 46 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 10. `SYK`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-09-29 | Observation | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Other　Price：294.66

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 6.2489 | 88 |
| Momentum_20D_Pct | 7.1024 | 83 |
| Momentum_60D_Pct | -7.6214 | 33 |
| Realized_Volatility_20D_Pct | 25.1292 | 43 |
| Volume_Ratio_20D | 1.3055 | 78 |
| ZScore_20D | 3.2041 | 96 |
| Beta_60D_SPY | 0.1946 | 37 |
| Stock_RS_20D_vs_SPY | 6.8976 | 83 |
| Quant_Score | 77.0000 | 96 |
| MA20 | 278.5200 | 86 |
| MA50 | 299.9500 | 87 |
| ATR_Pct | 2.7200 | 51 |
| KDJ_J | 94.8300 | 75 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：8（按日期倒序展示最近 8 笔）

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-16（仅日期） | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14（仅日期） | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13（仅日期） | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13（仅日期） | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07（仅日期） | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07（仅日期） | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07（仅日期） | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07（仅日期） | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 11. `MSFT`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-19 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- N/A（无成交记录）

---

## 12. `NVDA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Technology　Price：214.13

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -6.6076 | 18 |
| Momentum_20D_Pct | -3.6622 | 29 |
| Momentum_60D_Pct | 2.5723 | 64 |
| Realized_Volatility_20D_Pct | 24.7165 | 41 |
| Volume_Ratio_20D | 1.1156 | 60 |
| ZScore_20D | -2.5608 | 10 |
| Beta_60D_SPY | 1.9384 | 85 |
| Stock_RS_20D_vs_SPY | -3.8670 | 29 |
| Quant_Score | 22.0000 | 11 |
| MA20 | 228.1800 | 80 |
| MA50 | 223.0800 | 79 |
| ATR_Pct | 2.7900 | 55 |
| KDJ_J | -7.9300 | 8 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 13. `GOOGL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Communication　Price：340.59

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -3.1479 | 25 |
| Momentum_20D_Pct | -2.5605 | 35 |
| Momentum_60D_Pct | 7.2083 | 73 |
| Realized_Volatility_20D_Pct | 22.6324 | 32 |
| Volume_Ratio_20D | 1.0934 | 55 |
| ZScore_20D | -1.2544 | 22 |
| Beta_60D_SPY | 1.1957 | 69 |
| Stock_RS_20D_vs_SPY | -2.7653 | 35 |
| Quant_Score | 25.0000 | 18 |
| MA20 | 346.4100 | 91 |
| MA50 | 344.5800 | 90 |
| ATR_Pct | 2.6100 | 45 |
| KDJ_J | 11.6000 | 19 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 14. `AMZN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Consumer Discretionary　Price：250.00

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -4.7365 | 21 |
| Momentum_20D_Pct | -1.4623 | 41 |
| Momentum_60D_Pct | 6.9931 | 73 |
| Realized_Volatility_20D_Pct | 24.3913 | 40 |
| Volume_Ratio_20D | 1.1074 | 59 |
| ZScore_20D | -0.7213 | 29 |
| Beta_60D_SPY | 1.7232 | 82 |
| Stock_RS_20D_vs_SPY | -1.6671 | 41 |
| Quant_Score | 22.0000 | 11 |
| MA20 | 253.2300 | 83 |
| MA50 | 257.0800 | 85 |
| ATR_Pct | 2.3800 | 32 |
| KDJ_J | 6.4100 | 16 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 15. `META`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Communication　Price：709.33

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -1.2996 | 32 |
| Momentum_20D_Pct | 6.5460 | 81 |
| Momentum_60D_Pct | 17.0319 | 89 |
| Realized_Volatility_20D_Pct | 57.3452 | 91 |
| Volume_Ratio_20D | 0.9308 | 32 |
| ZScore_20D | -1.1068 | 24 |
| Beta_60D_SPY | 1.1358 | 67 |
| Stock_RS_20D_vs_SPY | 6.3412 | 81 |
| Quant_Score | 17.0000 | 2 |
| MA20 | 735.7700 | 98 |
| MA50 | 655.2400 | 98 |
| ATR_Pct | 3.5700 | 74 |
| KDJ_J | 20.0100 | 22 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 16. `TSLA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Consumer Discretionary　Price：354.72

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -7.3112 | 16 |
| Momentum_20D_Pct | -2.6217 | 34 |
| Momentum_60D_Pct | 10.9575 | 80 |
| Realized_Volatility_20D_Pct | 31.5636 | 66 |
| Volume_Ratio_20D | 1.8211 | 94 |
| ZScore_20D | -1.6409 | 18 |
| Beta_60D_SPY | 2.1297 | 88 |
| Stock_RS_20D_vs_SPY | -2.8265 | 34 |
| Quant_Score | 27.0000 | 28 |
| MA20 | 370.3300 | 92 |
| MA50 | 359.4600 | 91 |
| ATR_Pct | 3.3400 | 69 |
| KDJ_J | 2.3300 | 13 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 17. `AVGO`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Technology　Price：328.75

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -9.0695 | 13 |
| Momentum_20D_Pct | -8.0702 | 15 |
| Momentum_60D_Pct | -16.2356 | 11 |
| Realized_Volatility_20D_Pct | 36.3958 | 74 |
| Volume_Ratio_20D | 1.2900 | 76 |
| ZScore_20D | -3.1552 | 3 |
| Beta_60D_SPY | 2.0504 | 87 |
| Stock_RS_20D_vs_SPY | -8.2750 | 15 |
| Quant_Score | 22.0000 | 11 |
| MA20 | 355.3900 | 91 |
| MA50 | 365.7300 | 91 |
| ATR_Pct | 3.5200 | 73 |
| KDJ_J | -8.4200 | 8 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 18. `TSM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-19 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- N/A（无成交记录）

---

## 19. `BRK-B`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-02 | Observation | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Other　Price：532.02

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.1806 | 61 |
| Momentum_20D_Pct | 4.3647 | 71 |
| Momentum_60D_Pct | 8.3875 | 75 |
| Realized_Volatility_20D_Pct | 10.7317 | 0 |
| Volume_Ratio_20D | 0.8793 | 25 |
| ZScore_20D | 2.8292 | 88 |
| Beta_60D_SPY | -0.0989 | 18 |
| Stock_RS_20D_vs_SPY | 4.1599 | 71 |
| Quant_Score | 71.0000 | 89 |
| MA20 | 509.7400 | 96 |
| MA50 | 508.5100 | 96 |
| ATR_Pct | 1.1400 | 0 |
| KDJ_J | 97.9700 | 80 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：8（按日期倒序展示最近 8 笔）

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-16（仅日期） | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14（仅日期） | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13（仅日期） | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13（仅日期） | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07（仅日期） | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07（仅日期） | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07（仅日期） | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07（仅日期） | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 20. `JPM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Financials　Price：339.72

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.0211 | 49 |
| Momentum_20D_Pct | -2.8455 | 33 |
| Momentum_60D_Pct | -2.9094 | 47 |
| Realized_Volatility_20D_Pct | 18.1220 | 12 |
| Volume_Ratio_20D | 0.9701 | 39 |
| ZScore_20D | 0.5886 | 48 |
| Beta_60D_SPY | 0.6405 | 54 |
| Stock_RS_20D_vs_SPY | -3.0504 | 33 |
| Quant_Score | 59.0000 | 65 |
| MA20 | 335.6500 | 89 |
| MA50 | 348.1200 | 91 |
| ATR_Pct | 1.9200 | 14 |
| KDJ_J | 76.4700 | 47 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 21. `V`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Financials　Price：402.61

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.4519 | 73 |
| Momentum_20D_Pct | 9.3187 | 92 |
| Momentum_60D_Pct | 14.5080 | 85 |
| Realized_Volatility_20D_Pct | 20.8011 | 26 |
| Volume_Ratio_20D | 1.0293 | 48 |
| ZScore_20D | 2.3722 | 80 |
| Beta_60D_SPY | 0.2402 | 40 |
| Stock_RS_20D_vs_SPY | 9.1139 | 92 |
| Quant_Score | 72.0000 | 91 |
| MA20 | 374.7200 | 92 |
| MA50 | 372.5000 | 92 |
| ATR_Pct | 1.7200 | 7 |
| KDJ_J | 100.2100 | 86 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 22. `UNH`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：Healthcare　Price：401.43

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 5.8344 | 84 |
| Momentum_20D_Pct | 6.5084 | 80 |
| Momentum_60D_Pct | -5.2248 | 43 |
| Realized_Volatility_20D_Pct | 26.2120 | 47 |
| Volume_Ratio_20D | 1.3607 | 80 |
| ZScore_20D | 2.6281 | 86 |
| Beta_60D_SPY | 0.0851 | 30 |
| Stock_RS_20D_vs_SPY | 6.3036 | 80 |
| Quant_Score | 66.0000 | 79 |
| MA20 | 378.5700 | 92 |
| MA50 | 387.3000 | 94 |
| ATR_Pct | 3.0100 | 62 |
| KDJ_J | 83.1200 | 55 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 23. `XOM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-19 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- N/A（无成交记录）

---

## 24. `COST`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 285 只；全表 9 个日期 / 2479 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-19 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- N/A（无成交记录）

---

说明：只读简报；缺失项统一 N/A。宏观环境在头部统一展示，不重复。
