# Watchlist Brief — 24 只

> 生成：`scripts/ticker_brief.py --watchlist ... --md`　仓库：us　日期：latest

- 共 **24** 只票（NXPI, AMGN, TXN, AMZN, EFX, FAST, ADI, HAS, MA, AAPL, MSFT, NVDA, GOOGL, META, TSLA, AVGO, TSM, BRK-B, JPM, V, UNH, XOM, COST, WMT）：**2** 只有 AI 快照记录，**6** 只有交易记录

## 宏观环境（结论化，仅打印一次）

- 恐惧贪婪指数：**19.81（极度恐惧）**　时间戳：2026-10-22T22:57:26+00:00
- FedWatch（会议 2026-10-28，目标区间 3.75%-4.00%）：维持不变 **84.5%** / 加息 25bp **15.5%**
- 宏观指标：
  - 10Y国债：**5.04%**（前值 5.15%，2026-10-22，偏多）
  - 5Y国债：**4.86%**（前值 4.97%，2026-10-22，偏多）
  - 13周国债：**4.05%**（前值 4.06%，2026-10-22，中性）
  - CPI：**4.00%**（前值 N/A，2026-09-01，偏空）
  - 核心CPI：**2.79%**（前值 N/A，2026-09-01，中性）
  - 失业率：**4.20%**（前值 4.10%，2026-09-01，偏空）
- 美联储讲话：最近一次 **N/A**（10-22 05:55，www.equiti.com）：黄金价格预测：通胀、国债收益率和美元　立场：**偏空**

---

## 1. `NXPI`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-20 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Other　Price：242.36

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 9.7496 | 97 |
| Momentum_20D_Pct | 2.9392 | 53 |
| Momentum_60D_Pct | -6.4680 | 39 |
| Realized_Volatility_20D_Pct | 33.7509 | 71 |
| Volume_Ratio_20D | 0.9974 | 56 |
| ZScore_20D | 1.3338 | 58 |
| Beta_60D_SPY | 1.7740 | 82 |
| Stock_RS_20D_vs_SPY | 2.2515 | 53 |
| Quant_Score | 84.0000 | 100 |
| MA20 | 234.2300 | 79 |
| MA50 | 230.1900 | 78 |
| ATR_Pct | 3.4100 | 73 |
| KDJ_J | 107.8000 | 97 |

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

## 2. `AMGN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Healthcare　Price：438.34

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.8702 | 62 |
| Momentum_20D_Pct | 7.9416 | 81 |
| Momentum_60D_Pct | 11.5085 | 83 |
| Realized_Volatility_20D_Pct | 27.7390 | 56 |
| Volume_Ratio_20D | 0.9515 | 49 |
| ZScore_20D | 2.0003 | 83 |
| Beta_60D_SPY | 0.5068 | 50 |
| Stock_RS_20D_vs_SPY | 7.2539 | 81 |
| Quant_Score | 83.0000 | 99 |
| MA20 | 418.0200 | 93 |
| MA50 | 416.2100 | 93 |
| ATR_Pct | 2.4000 | 35 |
| KDJ_J | 96.3800 | 82 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 3. `TXN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Technology　Price：284.65

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.4253 | 44 |
| Momentum_20D_Pct | 4.4127 | 61 |
| Momentum_60D_Pct | 2.7358 | 64 |
| Realized_Volatility_20D_Pct | 27.9133 | 56 |
| Volume_Ratio_20D | 1.9693 | 94 |
| ZScore_20D | 0.3007 | 37 |
| Beta_60D_SPY | 1.2479 | 73 |
| Stock_RS_20D_vs_SPY | 3.7251 | 61 |
| Quant_Score | 83.0000 | 99 |
| MA20 | 283.0700 | 84 |
| MA50 | 272.1200 | 83 |
| ATR_Pct | 3.1800 | 66 |
| KDJ_J | 49.9300 | 34 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 4. `AMZN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Consumer Discretionary　Price：262.37

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.2627 | 69 |
| Momentum_20D_Pct | 5.2553 | 65 |
| Momentum_60D_Pct | 13.6490 | 86 |
| Realized_Volatility_20D_Pct | 27.7298 | 56 |
| Volume_Ratio_20D | 0.8623 | 37 |
| ZScore_20D | 1.5601 | 67 |
| Beta_60D_SPY | 1.7570 | 82 |
| Stock_RS_20D_vs_SPY | 4.5677 | 65 |
| Quant_Score | 82.0000 | 98 |
| MA20 | 254.4600 | 80 |
| MA50 | 256.3300 | 82 |
| ATR_Pct | 2.4000 | 35 |
| KDJ_J | 87.4100 | 69 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 5. `EFX`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Other　Price：175.57

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 16.7664 | 99 |
| Momentum_20D_Pct | 13.0376 | 94 |
| Momentum_60D_Pct | -6.1223 | 40 |
| Realized_Volatility_20D_Pct | 55.0245 | 91 |
| Volume_Ratio_20D | 1.1747 | 76 |
| ZScore_20D | 2.7919 | 94 |
| Beta_60D_SPY | 0.5129 | 50 |
| Stock_RS_20D_vs_SPY | 12.3499 | 94 |
| Quant_Score | 82.0000 | 98 |
| MA20 | 149.9600 | 65 |
| MA50 | 166.8900 | 68 |
| ATR_Pct | 3.4200 | 73 |
| KDJ_J | 98.5800 | 87 |

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

## 6. `FAST`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Other　Price：52.49

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.9423 | 37 |
| Momentum_20D_Pct | 2.9418 | 54 |
| Momentum_60D_Pct | 9.1268 | 79 |
| Realized_Volatility_20D_Pct | 19.8597 | 23 |
| Volume_Ratio_20D | 0.7280 | 18 |
| ZScore_20D | 2.8550 | 96 |
| Beta_60D_SPY | 0.3717 | 45 |
| Stock_RS_20D_vs_SPY | 2.2541 | 54 |
| Quant_Score | 82.0000 | 98 |
| MA20 | 50.8100 | 21 |
| MA50 | 50.3700 | 21 |
| ATR_Pct | 2.5100 | 40 |
| KDJ_J | 90.3500 | 73 |

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

## 7. `ADI`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Other　Price：405.96

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.5922 | 34 |
| Momentum_20D_Pct | 5.3812 | 66 |
| Momentum_60D_Pct | 10.9696 | 82 |
| Realized_Volatility_20D_Pct | 25.9459 | 49 |
| Volume_Ratio_20D | 1.0063 | 58 |
| ZScore_20D | 0.3265 | 38 |
| Beta_60D_SPY | 1.6790 | 80 |
| Stock_RS_20D_vs_SPY | 4.6935 | 66 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 403.5700 | 92 |
| MA50 | 384.0700 | 91 |
| ATR_Pct | 3.1000 | 64 |
| KDJ_J | 47.4700 | 33 |

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

## 8. `HAS`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Other　Price：114.00

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 19.4217 | 100 |
| Momentum_20D_Pct | 31.7614 | 99 |
| Momentum_60D_Pct | 18.3309 | 90 |
| Realized_Volatility_20D_Pct | 44.0551 | 84 |
| Volume_Ratio_20D | 2.4052 | 97 |
| ZScore_20D | 3.8176 | 99 |
| Beta_60D_SPY | 0.2712 | 41 |
| Stock_RS_20D_vs_SPY | 31.0738 | 99 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 94.2500 | 48 |
| MA50 | 93.1000 | 47 |
| ATR_Pct | 2.8100 | 55 |
| KDJ_J | 101.7000 | 93 |

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

## 9. `MA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Financials　Price：622.62

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.2127 | 68 |
| Momentum_20D_Pct | 11.1980 | 91 |
| Momentum_60D_Pct | 10.6388 | 81 |
| Realized_Volatility_20D_Pct | 17.2891 | 10 |
| Volume_Ratio_20D | 0.9215 | 45 |
| ZScore_20D | 1.7097 | 73 |
| Beta_60D_SPY | 0.2552 | 40 |
| Stock_RS_20D_vs_SPY | 10.5104 | 91 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 584.0400 | 96 |
| MA50 | 579.0500 | 97 |
| ATR_Pct | 1.5800 | 2 |
| KDJ_J | 97.5300 | 85 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 10. `AAPL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Technology　Price：343.99

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.3003 | 31 |
| Momentum_20D_Pct | 2.0681 | 48 |
| Momentum_60D_Pct | 1.1497 | 61 |
| Realized_Volatility_20D_Pct | 16.7581 | 8 |
| Volume_Ratio_20D | 0.9687 | 53 |
| ZScore_20D | 1.4670 | 62 |
| Beta_60D_SPY | -0.0197 | 21 |
| Stock_RS_20D_vs_SPY | 1.3805 | 48 |
| Quant_Score | 79.0000 | 96 |
| MA20 | 337.9600 | 88 |
| MA50 | 327.7000 | 88 |
| ATR_Pct | 1.8800 | 15 |
| KDJ_J | 68.8000 | 46 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 11. `MSFT`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Technology　Price：532.95

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.1387 | 25 |
| Momentum_20D_Pct | 6.4644 | 74 |
| Momentum_60D_Pct | 35.4900 | 96 |
| Realized_Volatility_20D_Pct | 21.7352 | 30 |
| Volume_Ratio_20D | 0.6480 | 7 |
| ZScore_20D | 0.7068 | 44 |
| Beta_60D_SPY | 2.1252 | 88 |
| Stock_RS_20D_vs_SPY | 5.7767 | 74 |
| Quant_Score | 29.0000 | 15 |
| MA20 | 525.1300 | 96 |
| MA50 | 507.3000 | 95 |
| ATR_Pct | 2.1100 | 25 |
| KDJ_J | 22.1800 | 16 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 12. `NVDA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Technology　Price：221.97

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.3028 | 31 |
| Momentum_20D_Pct | -1.5698 | 34 |
| Momentum_60D_Pct | 12.6694 | 85 |
| Realized_Volatility_20D_Pct | 25.0095 | 45 |
| Volume_Ratio_20D | 0.8368 | 33 |
| ZScore_20D | -0.6977 | 24 |
| Beta_60D_SPY | 1.9547 | 85 |
| Stock_RS_20D_vs_SPY | -2.2574 | 34 |
| Quant_Score | 32.0000 | 24 |
| MA20 | 226.8700 | 78 |
| MA50 | 223.0100 | 77 |
| ATR_Pct | 2.6600 | 47 |
| KDJ_J | 30.8900 | 22 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 13. `GOOGL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Communication　Price：334.76

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -3.7050 | 10 |
| Momentum_20D_Pct | -0.9087 | 37 |
| Momentum_60D_Pct | 0.3146 | 59 |
| Realized_Volatility_20D_Pct | 18.5444 | 16 |
| Volume_Ratio_20D | 1.2105 | 79 |
| ZScore_20D | -2.2311 | 2 |
| Beta_60D_SPY | 1.1438 | 69 |
| Stock_RS_20D_vs_SPY | -1.5964 | 37 |
| Quant_Score | 32.0000 | 24 |
| MA20 | 345.1800 | 89 |
| MA50 | 343.8500 | 89 |
| ATR_Pct | 2.5800 | 44 |
| KDJ_J | -1.2100 | 3 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 14. `META`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Communication　Price：697.52

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -5.4261 | 5 |
| Momentum_20D_Pct | -6.2599 | 21 |
| Momentum_60D_Pct | 17.5444 | 89 |
| Realized_Volatility_20D_Pct | 40.2397 | 80 |
| Volume_Ratio_20D | 1.4611 | 88 |
| ZScore_20D | -1.7484 | 5 |
| Beta_60D_SPY | 1.0990 | 68 |
| Stock_RS_20D_vs_SPY | -6.9476 | 21 |
| Quant_Score | 29.0000 | 15 |
| MA20 | 729.5400 | 97 |
| MA50 | 661.4600 | 97 |
| ATR_Pct | 3.5100 | 76 |
| KDJ_J | 6.4300 | 9 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 15. `TSLA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Consumer Discretionary　Price：386.47

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 5.2593 | 84 |
| Momentum_20D_Pct | 1.6705 | 47 |
| Momentum_60D_Pct | 25.7058 | 92 |
| Realized_Volatility_20D_Pct | 35.1427 | 73 |
| Volume_Ratio_20D | 1.3702 | 85 |
| ZScore_20D | 1.6544 | 72 |
| Beta_60D_SPY | 2.2117 | 88 |
| Stock_RS_20D_vs_SPY | 0.9829 | 47 |
| Quant_Score | 66.0000 | 76 |
| MA20 | 370.0300 | 90 |
| MA50 | 362.1800 | 90 |
| ATR_Pct | 3.2100 | 66 |
| KDJ_J | 83.5000 | 65 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 16. `AVGO`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Technology　Price：337.80

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -2.4404 | 14 |
| Momentum_20D_Pct | -4.8424 | 25 |
| Momentum_60D_Pct | -11.3176 | 24 |
| Realized_Volatility_20D_Pct | 35.8827 | 74 |
| Volume_Ratio_20D | 0.7884 | 26 |
| ZScore_20D | -1.2049 | 14 |
| Beta_60D_SPY | 2.0759 | 87 |
| Stock_RS_20D_vs_SPY | -5.5301 | 25 |
| Quant_Score | 32.0000 | 24 |
| MA20 | 351.6200 | 89 |
| MA50 | 360.5400 | 89 |
| ATR_Pct | 3.3000 | 70 |
| KDJ_J | 11.4000 | 10 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 17. `TSM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-22 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- N/A（无成交记录）

---

## 18. `BRK-B`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-02 | Observation | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Other　Price：538.99

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.4014 | 56 |
| Momentum_20D_Pct | 6.2740 | 73 |
| Momentum_60D_Pct | 5.1955 | 70 |
| Realized_Volatility_20D_Pct | 9.5380 | 0 |
| Volume_Ratio_20D | 1.2041 | 79 |
| ZScore_20D | 2.0945 | 86 |
| Beta_60D_SPY | -0.1083 | 18 |
| Stock_RS_20D_vs_SPY | 5.5864 | 73 |
| Quant_Score | 73.0000 | 88 |
| MA20 | 514.6600 | 95 |
| MA50 | 509.3700 | 96 |
| ATR_Pct | 1.1100 | 0 |
| KDJ_J | 94.5900 | 80 |

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

## 19. `JPM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Financials　Price：335.19

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.0268 | 27 |
| Momentum_20D_Pct | -0.6933 | 37 |
| Momentum_60D_Pct | -6.1907 | 40 |
| Realized_Volatility_20D_Pct | 14.5803 | 3 |
| Volume_Ratio_20D | 0.7270 | 18 |
| ZScore_20D | 0.2084 | 35 |
| Beta_60D_SPY | 0.6148 | 55 |
| Stock_RS_20D_vs_SPY | -1.3809 | 37 |
| Quant_Score | 24.0000 | 3 |
| MA20 | 334.3700 | 87 |
| MA50 | 346.6100 | 89 |
| ATR_Pct | 1.9400 | 18 |
| KDJ_J | 51.1800 | 36 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 20. `V`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Financials　Price：407.85

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.1949 | 78 |
| Momentum_20D_Pct | 12.8153 | 93 |
| Momentum_60D_Pct | 11.2551 | 82 |
| Realized_Volatility_20D_Pct | 18.3614 | 15 |
| Volume_Ratio_20D | 0.9368 | 48 |
| ZScore_20D | 1.7891 | 77 |
| Beta_60D_SPY | 0.2400 | 39 |
| Stock_RS_20D_vs_SPY | 12.1277 | 93 |
| Quant_Score | 74.0000 | 88 |
| MA20 | 380.9100 | 90 |
| MA50 | 375.1200 | 91 |
| ATR_Pct | 1.6300 | 4 |
| KDJ_J | 98.7700 | 88 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 21. `UNH`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Healthcare　Price：417.00

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 5.4042 | 85 |
| Momentum_20D_Pct | 12.3111 | 93 |
| Momentum_60D_Pct | -2.7496 | 53 |
| Realized_Volatility_20D_Pct | 27.3808 | 54 |
| Volume_Ratio_20D | 0.6631 | 9 |
| ZScore_20D | 2.3075 | 91 |
| Beta_60D_SPY | 0.1061 | 32 |
| Stock_RS_20D_vs_SPY | 11.6235 | 93 |
| Quant_Score | 71.0000 | 85 |
| MA20 | 384.6400 | 91 |
| MA50 | 387.8000 | 92 |
| ATR_Pct | 2.8200 | 55 |
| KDJ_J | 98.8200 | 88 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 22. `XOM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-22 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- N/A（无成交记录）

---

## 23. `COST`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-22 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- N/A（无成交记录）

---

## 24. `WMT`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-22（该日共 289 只；全表 12 个日期 / 3369 行）
- Sector：Consumer Staples　Price：117.80

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.4118 | 44 |
| Momentum_20D_Pct | 6.5774 | 74 |
| Momentum_60D_Pct | 4.1556 | 67 |
| Realized_Volatility_20D_Pct | 24.4759 | 44 |
| Volume_Ratio_20D | 0.8363 | 32 |
| ZScore_20D | 1.4322 | 61 |
| Beta_60D_SPY | -0.0039 | 23 |
| Stock_RS_20D_vs_SPY | 5.8897 | 74 |
| Quant_Score | 62.0000 | 67 |
| MA20 | 110.9200 | 56 |
| MA50 | 109.2400 | 55 |
| ATR_Pct | 1.9900 | 20 |
| KDJ_J | 69.8900 | 48 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Staples）
- N/A（无成交记录）

---

说明：只读简报；缺失项统一 N/A。宏观环境在头部统一展示，不重复。
