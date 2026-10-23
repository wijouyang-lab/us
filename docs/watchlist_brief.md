# Watchlist Brief — 24 只

> 生成：`scripts/ticker_brief.py --watchlist ... --md`　仓库：us　日期：latest

- 共 **24** 只票（LLY, HAS, NXPI, COP, FAST, KO, MA, V, MMM, ABNB, AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, AVGO, TSM, BRK-B, JPM, UNH, XOM, COST）：**3** 只有 AI 快照记录，**6** 只有交易记录

## 宏观环境（结论化，仅打印一次）

- 恐惧贪婪指数：**23.46（极度恐惧）**　时间戳：2026-10-23T12:43:37+00:00
- FedWatch（会议 2026-10-28，目标区间 3.75%-4.00%）：维持不变 **94.5%** / 加息 25bp **5.5%**
- 宏观指标：
  - 10Y国债：**4.97%**（前值 4.95%，2026-10-23，N/A）
  - 5Y国债：**4.79%**（前值 4.77%，2026-10-23，N/A）
  - 13周国债：**4.04%**（前值 4.02%，2026-10-23，N/A）
  - CPI：**4.00%**（前值 N/A，2026-09-01，N/A）
  - 核心CPI：**2.79%**（前值 N/A，2026-09-01，N/A）
  - 失业率：**4.20%**（前值 4.10%，2026-09-01，N/A）
- 美联储讲话：最近一次 **Warsh**（10-22 04:43，Yahoo Finance）：The Latest Inflation Data Spells Bad News for Fed Chair Kevin Warsh and the Stock Market - Yahoo Finance　立场：**N/A**

---

## 1. `LLY`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-21 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Healthcare　Price：1306.69

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.4007 | 74 |
| Momentum_20D_Pct | 10.5594 | 78 |
| Momentum_60D_Pct | 7.9891 | 75 |
| Realized_Volatility_20D_Pct | 29.0723 | 53 |
| Volume_Ratio_20D | 1.1611 | 45 |
| ZScore_20D | 2.5991 | 74 |
| Beta_60D_SPY | -0.5601 | 6 |
| Stock_RS_20D_vs_SPY | 10.9791 | 78 |
| Quant_Score | 83.0000 | 100 |
| MA20 | 1200.4400 | 99 |
| MA50 | 1185.3200 | 99 |
| ATR_Pct | 2.8500 | 52 |
| KDJ_J | 93.0600 | 63 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 2. `HAS`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Other　Price：117.23

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 19.1241 | 100 |
| Momentum_20D_Pct | 35.0421 | 99 |
| Momentum_60D_Pct | 23.1796 | 91 |
| Realized_Volatility_20D_Pct | 44.1290 | 81 |
| Volume_Ratio_20D | 1.4827 | 78 |
| ZScore_20D | 3.2504 | 90 |
| Beta_60D_SPY | 0.0743 | 34 |
| Stock_RS_20D_vs_SPY | 35.4618 | 99 |
| Quant_Score | 82.0000 | 99 |
| MA20 | 95.7800 | 50 |
| MA50 | 93.5400 | 49 |
| ATR_Pct | 2.8100 | 50 |
| KDJ_J | 103.9800 | 90 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22（仅日期） | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19（仅日期） | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
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

- 记录数：2

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-23 | Core_Dragon | scan | N/A | N/A |
| 2026-10-20 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Other　Price：237.79

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.8993 | 57 |
| Momentum_20D_Pct | 3.3151 | 50 |
| Momentum_60D_Pct | -1.3238 | 49 |
| Realized_Volatility_20D_Pct | 33.4353 | 64 |
| Volume_Ratio_20D | 2.2497 | 93 |
| ZScore_20D | 0.5377 | 38 |
| Beta_60D_SPY | 1.5136 | 77 |
| Stock_RS_20D_vs_SPY | 3.7348 | 50 |
| Quant_Score | 82.0000 | 99 |
| MA20 | 234.6100 | 79 |
| MA50 | 230.2800 | 78 |
| ATR_Pct | 3.4500 | 72 |
| KDJ_J | 102.0700 | 86 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22（仅日期） | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19（仅日期） | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16（仅日期） | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14（仅日期） | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13（仅日期） | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13（仅日期） | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07（仅日期） | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07（仅日期） | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07（仅日期） | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07（仅日期） | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 4. `COP`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Energy　Price：145.63

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.7517 | 54 |
| Momentum_20D_Pct | 12.5947 | 86 |
| Momentum_60D_Pct | 23.3525 | 91 |
| Realized_Volatility_20D_Pct | 22.6344 | 27 |
| Volume_Ratio_20D | 0.9540 | 20 |
| ZScore_20D | 1.4076 | 47 |
| Beta_60D_SPY | -0.8686 | 1 |
| Stock_RS_20D_vs_SPY | 13.0144 | 86 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 135.2600 | 62 |
| MA50 | 133.5400 | 61 |
| ATR_Pct | 2.3000 | 29 |
| KDJ_J | 85.5400 | 52 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Energy）
- N/A（无成交记录）

---

## 5. `FAST`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Other　Price：52.73

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.6645 | 76 |
| Momentum_20D_Pct | 3.9424 | 52 |
| Momentum_60D_Pct | 10.3600 | 79 |
| Realized_Volatility_20D_Pct | 19.7281 | 14 |
| Volume_Ratio_20D | 1.1598 | 44 |
| ZScore_20D | 2.6356 | 76 |
| Beta_60D_SPY | 0.3231 | 47 |
| Stock_RS_20D_vs_SPY | 4.3622 | 52 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 50.9100 | 21 |
| MA50 | 50.3800 | 21 |
| ATR_Pct | 2.5700 | 38 |
| KDJ_J | 100.7700 | 81 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22（仅日期） | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19（仅日期） | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16（仅日期） | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14（仅日期） | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13（仅日期） | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13（仅日期） | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07（仅日期） | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07（仅日期） | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07（仅日期） | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07（仅日期） | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 6. `KO`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Consumer Staples　Price：95.34

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.6304 | 63 |
| Momentum_20D_Pct | 8.2179 | 65 |
| Momentum_60D_Pct | 7.0274 | 73 |
| Realized_Volatility_20D_Pct | 18.6472 | 10 |
| Volume_Ratio_20D | 1.0692 | 34 |
| ZScore_20D | 2.1915 | 62 |
| Beta_60D_SPY | -0.4515 | 8 |
| Stock_RS_20D_vs_SPY | 8.6376 | 65 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 89.3200 | 47 |
| MA50 | 89.0000 | 46 |
| ATR_Pct | 1.5600 | 1 |
| KDJ_J | 98.4800 | 76 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Staples）
- N/A（无成交记录）

---

## 7. `MA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Financials　Price：633.21

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.7405 | 53 |
| Momentum_20D_Pct | 11.8587 | 83 |
| Momentum_60D_Pct | 12.4068 | 83 |
| Realized_Volatility_20D_Pct | 17.6755 | 6 |
| Volume_Ratio_20D | 1.3537 | 67 |
| ZScore_20D | 1.9236 | 56 |
| Beta_60D_SPY | 0.1898 | 40 |
| Stock_RS_20D_vs_SPY | 12.2785 | 83 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 587.3900 | 96 |
| MA50 | 580.5200 | 96 |
| ATR_Pct | 1.5600 | 1 |
| KDJ_J | 101.2600 | 82 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 8. `V`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Financials　Price：414.34

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.6498 | 64 |
| Momentum_20D_Pct | 12.5985 | 86 |
| Momentum_60D_Pct | 12.3695 | 83 |
| Realized_Volatility_20D_Pct | 18.2077 | 8 |
| Volume_Ratio_20D | 1.2233 | 53 |
| ZScore_20D | 1.9582 | 57 |
| Beta_60D_SPY | 0.2077 | 41 |
| Stock_RS_20D_vs_SPY | 13.0182 | 86 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 383.2300 | 90 |
| MA50 | 376.2200 | 90 |
| ATR_Pct | 1.6200 | 2 |
| KDJ_J | 101.2700 | 83 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 9. `MMM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Other　Price：175.56

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 6.1876 | 87 |
| Momentum_20D_Pct | 4.7994 | 54 |
| Momentum_60D_Pct | -1.3431 | 49 |
| Realized_Volatility_20D_Pct | 27.9422 | 47 |
| Volume_Ratio_20D | 1.8237 | 88 |
| ZScore_20D | 2.7093 | 77 |
| Beta_60D_SPY | 0.3940 | 51 |
| Stock_RS_20D_vs_SPY | 5.2191 | 54 |
| Quant_Score | 79.0000 | 97 |
| MA20 | 165.5500 | 69 |
| MA50 | 169.3200 | 69 |
| ATR_Pct | 2.3200 | 30 |
| KDJ_J | 110.0100 | 97 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22（仅日期） | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19（仅日期） | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16（仅日期） | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14（仅日期） | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13（仅日期） | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13（仅日期） | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07（仅日期） | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07（仅日期） | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07（仅日期） | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07（仅日期） | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 10. `ABNB`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Other　Price：175.76

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.8492 | 40 |
| Momentum_20D_Pct | 16.0975 | 95 |
| Momentum_60D_Pct | 14.8683 | 86 |
| Realized_Volatility_20D_Pct | 26.6929 | 42 |
| Volume_Ratio_20D | 0.9005 | 16 |
| ZScore_20D | 1.5784 | 49 |
| Beta_60D_SPY | 0.8225 | 65 |
| Stock_RS_20D_vs_SPY | 16.5172 | 95 |
| Quant_Score | 78.0000 | 96 |
| MA20 | 165.7100 | 69 |
| MA50 | 172.2700 | 70 |
| ATR_Pct | 2.6800 | 44 |
| KDJ_J | 76.5400 | 45 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22（仅日期） | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19（仅日期） | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16（仅日期） | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14（仅日期） | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13（仅日期） | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13（仅日期） | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07（仅日期） | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07（仅日期） | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07（仅日期） | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07（仅日期） | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 11. `AAPL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Technology　Price：348.22

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.8187 | 45 |
| Momentum_20D_Pct | 3.6616 | 51 |
| Momentum_60D_Pct | 2.9658 | 63 |
| Realized_Volatility_20D_Pct | 17.1296 | 4 |
| Volume_Ratio_20D | 1.2652 | 58 |
| ZScore_20D | 2.2440 | 64 |
| Beta_60D_SPY | -0.1108 | 24 |
| Stock_RS_20D_vs_SPY | 4.0813 | 51 |
| Quant_Score | 77.0000 | 94 |
| MA20 | 338.5700 | 87 |
| MA50 | 328.6200 | 87 |
| ATR_Pct | 1.8500 | 11 |
| KDJ_J | 92.4900 | 63 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 12. `MSFT`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Technology　Price：521.08

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -3.4035 | 21 |
| Momentum_20D_Pct | 4.6493 | 54 |
| Momentum_60D_Pct | 33.4255 | 97 |
| Realized_Volatility_20D_Pct | 23.3895 | 29 |
| Volume_Ratio_20D | 0.9959 | 25 |
| ZScore_20D | -0.3276 | 31 |
| Beta_60D_SPY | 2.2589 | 87 |
| Stock_RS_20D_vs_SPY | 5.0690 | 54 |
| Quant_Score | 22.0000 | 7 |
| MA20 | 526.2900 | 95 |
| MA50 | 507.8800 | 94 |
| ATR_Pct | 2.1800 | 24 |
| KDJ_J | -2.5300 | 4 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 13. `NVDA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Technology　Price：212.21

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -2.3109 | 26 |
| Momentum_20D_Pct | -5.5081 | 21 |
| Momentum_60D_Pct | 11.6836 | 82 |
| Realized_Volatility_20D_Pct | 29.3600 | 53 |
| Volume_Ratio_20D | 1.2072 | 51 |
| ZScore_20D | -1.9935 | 10 |
| Beta_60D_SPY | 2.0180 | 85 |
| Stock_RS_20D_vs_SPY | -5.0883 | 21 |
| Quant_Score | 22.0000 | 7 |
| MA20 | 226.2500 | 78 |
| MA50 | 222.7700 | 77 |
| ATR_Pct | 2.9400 | 55 |
| KDJ_J | 13.8600 | 17 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 14. `GOOGL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Communication　Price：324.22

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -7.1588 | 12 |
| Momentum_20D_Pct | -5.2985 | 22 |
| Momentum_60D_Pct | -3.7094 | 39 |
| Realized_Volatility_20D_Pct | 20.8207 | 19 |
| Volume_Ratio_20D | 1.1638 | 45 |
| ZScore_20D | -4.1630 | 1 |
| Beta_60D_SPY | 1.3857 | 75 |
| Stock_RS_20D_vs_SPY | -4.8788 | 22 |
| Quant_Score | 22.0000 | 7 |
| MA20 | 344.2700 | 88 |
| MA50 | 343.4700 | 88 |
| ATR_Pct | 2.7500 | 48 |
| KDJ_J | -6.2000 | 1 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 15. `AMZN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Consumer Discretionary　Price：250.38

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -1.7193 | 27 |
| Momentum_20D_Pct | 0.4010 | 36 |
| Momentum_60D_Pct | 10.4699 | 79 |
| Realized_Volatility_20D_Pct | 32.6330 | 62 |
| Volume_Ratio_20D | 1.3721 | 69 |
| ZScore_20D | -0.7170 | 27 |
| Beta_60D_SPY | 1.9232 | 84 |
| Stock_RS_20D_vs_SPY | 0.8207 | 36 |
| Quant_Score | 27.0000 | 25 |
| MA20 | 254.5100 | 80 |
| MA50 | 255.9900 | 81 |
| ATR_Pct | 2.7500 | 48 |
| KDJ_J | 37.3200 | 27 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 16. `META`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Communication　Price：648.85

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -11.9272 | 3 |
| Momentum_20D_Pct | -16.5563 | 8 |
| Momentum_60D_Pct | 10.7990 | 80 |
| Realized_Volatility_20D_Pct | 42.6612 | 80 |
| Volume_Ratio_20D | 2.0740 | 91 |
| ZScore_20D | -3.8712 | 2 |
| Beta_60D_SPY | 1.3812 | 75 |
| Stock_RS_20D_vs_SPY | -16.1366 | 8 |
| Quant_Score | 18.0000 | 1 |
| MA20 | 723.1000 | 97 |
| MA50 | 662.8600 | 97 |
| ATR_Pct | 4.1400 | 83 |
| KDJ_J | -0.1700 | 6 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 17. `TSLA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Consumer Discretionary　Price：374.58

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.3495 | 61 |
| Momentum_20D_Pct | -0.8890 | 31 |
| Momentum_60D_Pct | 25.5631 | 94 |
| Realized_Volatility_20D_Pct | 36.8655 | 72 |
| Volume_Ratio_20D | 1.4483 | 75 |
| ZScore_20D | 0.4308 | 37 |
| Beta_60D_SPY | 2.2560 | 87 |
| Stock_RS_20D_vs_SPY | -0.4693 | 31 |
| Quant_Score | 35.0000 | 40 |
| MA20 | 369.8600 | 89 |
| MA50 | 363.1200 | 89 |
| ATR_Pct | 3.3700 | 68 |
| KDJ_J | 77.6100 | 46 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 18. `AVGO`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Technology　Price：323.24

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -6.1249 | 14 |
| Momentum_20D_Pct | -7.7406 | 18 |
| Momentum_60D_Pct | -12.7133 | 14 |
| Realized_Volatility_20D_Pct | 38.5694 | 75 |
| Volume_Ratio_20D | 1.3038 | 61 |
| ZScore_20D | -2.2529 | 7 |
| Beta_60D_SPY | 2.1908 | 86 |
| Stock_RS_20D_vs_SPY | -7.3209 | 18 |
| Quant_Score | 25.0000 | 13 |
| MA20 | 350.2700 | 88 |
| MA50 | 358.6800 | 89 |
| ATR_Pct | 3.5700 | 74 |
| KDJ_J | 3.7000 | 7 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 19. `TSM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-23 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- N/A（无成交记录）

---

## 20. `BRK-B`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-02 | Observation | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Other　Price：546.97

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.0500 | 69 |
| Momentum_20D_Pct | 8.2723 | 66 |
| Momentum_60D_Pct | 7.4259 | 73 |
| Realized_Volatility_20D_Pct | 10.0227 | 0 |
| Volume_Ratio_20D | 1.3474 | 66 |
| ZScore_20D | 2.3818 | 68 |
| Beta_60D_SPY | -0.2192 | 17 |
| Stock_RS_20D_vs_SPY | 8.6920 | 66 |
| Quant_Score | 76.0000 | 92 |
| MA20 | 516.7500 | 94 |
| MA50 | 510.1100 | 95 |
| ATR_Pct | 1.1600 | 0 |
| KDJ_J | 93.8700 | 66 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22（仅日期） | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19（仅日期） | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16（仅日期） | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14（仅日期） | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13（仅日期） | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13（仅日期） | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07（仅日期） | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07（仅日期） | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07（仅日期） | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07（仅日期） | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 21. `JPM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Financials　Price：336.54

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.3010 | 37 |
| Momentum_20D_Pct | -0.5966 | 32 |
| Momentum_60D_Pct | -2.3701 | 45 |
| Realized_Volatility_20D_Pct | 14.6142 | 1 |
| Volume_Ratio_20D | 0.7874 | 9 |
| ZScore_20D | 0.6596 | 39 |
| Beta_60D_SPY | 0.4113 | 52 |
| Stock_RS_20D_vs_SPY | -0.1769 | 32 |
| Quant_Score | 32.0000 | 37 |
| MA20 | 334.2700 | 87 |
| MA50 | 346.0400 | 88 |
| ATR_Pct | 1.8900 | 14 |
| KDJ_J | 54.9800 | 31 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 22. `UNH`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Healthcare　Price：424.98

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.5024 | 74 |
| Momentum_20D_Pct | 13.3250 | 89 |
| Momentum_60D_Pct | 1.0486 | 59 |
| Realized_Volatility_20D_Pct | 27.7488 | 46 |
| Volume_Ratio_20D | 0.9001 | 16 |
| ZScore_20D | 2.4253 | 69 |
| Beta_60D_SPY | -0.0918 | 26 |
| Stock_RS_20D_vs_SPY | 13.7447 | 89 |
| Quant_Score | 73.0000 | 88 |
| MA20 | 387.1400 | 91 |
| MA50 | 388.1900 | 91 |
| ATR_Pct | 2.7300 | 47 |
| KDJ_J | 103.9000 | 90 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 23. `XOM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-23 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- N/A（无成交记录）

---

## 24. `COST`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-23（该日共 290 只；全表 13 个日期 / 3659 行）
- Sector：Consumer Staples　Price：1018.21

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.1104 | 70 |
| Momentum_20D_Pct | 13.5787 | 90 |
| Momentum_60D_Pct | 4.5358 | 69 |
| Realized_Volatility_20D_Pct | 17.1848 | 4 |
| Volume_Ratio_20D | 1.2595 | 57 |
| ZScore_20D | 2.1965 | 63 |
| Beta_60D_SPY | -0.2208 | 17 |
| Stock_RS_20D_vs_SPY | 13.9984 | 90 |
| Quant_Score | 75.0000 | 91 |
| MA20 | 954.1200 | 98 |
| MA50 | 938.0400 | 98 |
| ATR_Pct | 1.5700 | 1 |
| KDJ_J | 94.9000 | 67 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Staples）
- N/A（无成交记录）

---

说明：只读简报；缺失项统一 N/A。宏观环境在头部统一展示，不重复。
