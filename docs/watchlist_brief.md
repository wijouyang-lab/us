# Watchlist Brief — 24 只

> 生成：`scripts/ticker_brief.py --watchlist ... --md`　仓库：us　日期：latest

- 共 **24** 只票（COP, HAS, OXY, AAPL, AMT, CVX, DVN, NXPI, ADBE, LLY, MSFT, NVDA, GOOGL, AMZN, META, TSLA, AVGO, TSM, BRK-B, JPM, V, UNH, XOM, COST）：**6** 只有 AI 快照记录，**5** 只有交易记录

## 宏观环境（结论化，仅打印一次）

- 恐惧贪婪指数：**22.00（极度恐惧）**　时间戳：2026-10-26T12:45:20+00:00
- FedWatch（会议 2026-10-28，目标区间 3.75%-4.00%）：维持不变 **90.0%** / 加息 25bp **10.0%**
- 宏观指标：
  - 10Y国债：**4.99%**（前值 4.99%，2026-10-26，中性）
  - 5Y国债：**4.82%**（前值 4.80%，2026-10-26，偏空）
  - 13周国债：**4.04%**（前值 4.03%，2026-10-26，偏空）
  - CPI：**4.00%**（前值 N/A，2026-09-01，偏空）
  - 核心CPI：**2.79%**（前值 N/A，2026-09-01，偏空）
  - 失业率：**4.20%**（前值 4.10%，2026-09-01，偏空）
- 美联储讲话：最近一次 **N/A**（10-24 12:56，Breaking News, Latest News and Videos）：美联储维持利率不变，但通胀创3年新高　立场：**偏空**

---

## 1. `COP`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Energy　Price：150.80

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.9281 | 70 |
| Momentum_20D_Pct | 18.4603 | 97 |
| Momentum_60D_Pct | 26.6908 | 95 |
| Realized_Volatility_20D_Pct | 23.3845 | 29 |
| Volume_Ratio_20D | 1.2389 | 80 |
| ZScore_20D | 1.8892 | 78 |
| Beta_60D_SPY | -1.0484 | 1 |
| Stock_RS_20D_vs_SPY | 19.9357 | 97 |
| Quant_Score | 82.0000 | 99 |
| MA20 | 136.4300 | 64 |
| MA50 | 134.0700 | 63 |
| ATR_Pct | 2.4000 | 33 |
| KDJ_J | 84.9200 | 65 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Energy）
- N/A（无成交记录）

---

## 2. `HAS`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Other　Price：117.44

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 18.9145 | 100 |
| Momentum_20D_Pct | 33.3182 | 99 |
| Momentum_60D_Pct | 24.2357 | 94 |
| Realized_Volatility_20D_Pct | 44.3965 | 81 |
| Volume_Ratio_20D | 1.1532 | 76 |
| ZScore_20D | 2.5462 | 94 |
| Beta_60D_SPY | 0.1529 | 36 |
| Stock_RS_20D_vs_SPY | 34.7935 | 99 |
| Quant_Score | 82.0000 | 99 |
| MA20 | 97.2400 | 52 |
| MA50 | 93.9600 | 49 |
| ATR_Pct | 2.7600 | 47 |
| KDJ_J | 103.5600 | 94 |

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

## 3. `OXY`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Energy　Price：64.17

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.8695 | 68 |
| Momentum_20D_Pct | 12.8561 | 91 |
| Momentum_60D_Pct | 14.6917 | 87 |
| Realized_Volatility_20D_Pct | 26.6678 | 42 |
| Volume_Ratio_20D | 1.3111 | 85 |
| ZScore_20D | 1.7478 | 71 |
| Beta_60D_SPY | -0.8173 | 2 |
| Stock_RS_20D_vs_SPY | 14.3315 | 91 |
| Quant_Score | 82.0000 | 99 |
| MA20 | 59.9900 | 27 |
| MA50 | 59.8200 | 27 |
| ATR_Pct | 2.5400 | 38 |
| KDJ_J | 75.4100 | 53 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Energy）
- N/A（无成交记录）

---

## 4. `AAPL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Technology　Price：347.73

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.2432 | 51 |
| Momentum_20D_Pct | 1.9527 | 46 |
| Momentum_60D_Pct | 4.2888 | 70 |
| Realized_Volatility_20D_Pct | 16.3979 | 2 |
| Volume_Ratio_20D | 1.0384 | 65 |
| ZScore_20D | 1.8014 | 74 |
| Beta_60D_SPY | -0.0207 | 28 |
| Stock_RS_20D_vs_SPY | 3.4280 | 46 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 338.9100 | 89 |
| MA50 | 329.4700 | 89 |
| ATR_Pct | 1.8400 | 8 |
| KDJ_J | 80.8400 | 57 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 5. `AMT`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-26 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Real Estate　Price：188.97

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.9971 | 60 |
| Momentum_20D_Pct | 11.7967 | 88 |
| Momentum_60D_Pct | 8.3171 | 77 |
| Realized_Volatility_20D_Pct | 42.0690 | 79 |
| Volume_Ratio_20D | 2.7592 | 99 |
| ZScore_20D | 1.7732 | 72 |
| Beta_60D_SPY | 0.4013 | 45 |
| Stock_RS_20D_vs_SPY | 13.2721 | 88 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 174.3600 | 72 |
| MA50 | 174.6900 | 72 |
| ATR_Pct | 3.1100 | 60 |
| KDJ_J | 38.3500 | 30 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Real Estate）
- N/A（无成交记录）

---

## 6. `CVX`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Energy　Price：233.21

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.6535 | 77 |
| Momentum_20D_Pct | 14.0670 | 93 |
| Momentum_60D_Pct | 21.2677 | 94 |
| Realized_Volatility_20D_Pct | 20.3047 | 15 |
| Volume_Ratio_20D | 1.1107 | 72 |
| ZScore_20D | 2.2285 | 88 |
| Beta_60D_SPY | -0.9194 | 2 |
| Stock_RS_20D_vs_SPY | 15.5424 | 93 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 215.3700 | 78 |
| MA50 | 210.4200 | 78 |
| ATR_Pct | 2.0500 | 17 |
| KDJ_J | 94.8900 | 84 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Energy）
- N/A（无成交记录）

---

## 7. `DVN`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-26 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Other　Price：51.39

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.3010 | 51 |
| Momentum_20D_Pct | 9.2242 | 78 |
| Momentum_60D_Pct | 16.3459 | 90 |
| Realized_Volatility_20D_Pct | 27.3254 | 44 |
| Volume_Ratio_20D | 1.5252 | 92 |
| ZScore_20D | 1.9143 | 79 |
| Beta_60D_SPY | -0.8359 | 2 |
| Stock_RS_20D_vs_SPY | 10.6996 | 78 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 48.8000 | 21 |
| MA50 | 48.5300 | 20 |
| ATR_Pct | 2.9300 | 53 |
| KDJ_J | 62.7700 | 40 |

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

## 8. `NXPI`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：2

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-23 | Core_Dragon | scan | N/A | N/A |
| 2026-10-20 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Other　Price：234.92

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.4375 | 64 |
| Momentum_20D_Pct | -1.3273 | 34 |
| Momentum_60D_Pct | -4.1769 | 44 |
| Realized_Volatility_20D_Pct | 31.4415 | 57 |
| Volume_Ratio_20D | 0.9946 | 59 |
| ZScore_20D | 0.0475 | 36 |
| Beta_60D_SPY | 1.5646 | 79 |
| Stock_RS_20D_vs_SPY | 0.1480 | 34 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 234.4500 | 81 |
| MA50 | 230.3400 | 79 |
| ATR_Pct | 3.4500 | 68 |
| KDJ_J | 87.7600 | 68 |

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

## 9. `ADBE`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-08 | Observation | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Other　Price：263.82

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 7.5938 | 94 |
| Momentum_20D_Pct | 12.0398 | 89 |
| Momentum_60D_Pct | 6.4219 | 73 |
| Realized_Volatility_20D_Pct | 39.9326 | 78 |
| Volume_Ratio_20D | 0.7226 | 17 |
| ZScore_20D | 2.2064 | 88 |
| Beta_60D_SPY | 0.8483 | 64 |
| Stock_RS_20D_vs_SPY | 13.5151 | 89 |
| Quant_Score | 79.0000 | 97 |
| MA20 | 244.0700 | 82 |
| MA50 | 255.7800 | 84 |
| ATR_Pct | 3.4500 | 68 |
| KDJ_J | 91.5700 | 77 |

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

## 10. `LLY`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：2

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-26 | Core_Dragon | scan | N/A | N/A |
| 2026-10-21 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Healthcare　Price：1273.46

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.3070 | 52 |
| Momentum_20D_Pct | 7.6048 | 71 |
| Momentum_60D_Pct | 10.2591 | 81 |
| Realized_Volatility_20D_Pct | 31.0294 | 56 |
| Volume_Ratio_20D | 0.9904 | 58 |
| ZScore_20D | 1.4633 | 60 |
| Beta_60D_SPY | -0.2441 | 14 |
| Stock_RS_20D_vs_SPY | 9.0802 | 71 |
| Quant_Score | 78.0000 | 96 |
| MA20 | 1204.9400 | 99 |
| MA50 | 1186.6000 | 99 |
| ATR_Pct | 3.0000 | 56 |
| KDJ_J | 80.6500 | 56 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 11. `MSFT`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Technology　Price：524.51

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.8581 | 30 |
| Momentum_20D_Pct | 1.6158 | 45 |
| Momentum_60D_Pct | 16.2736 | 89 |
| Realized_Volatility_20D_Pct | 19.6927 | 12 |
| Volume_Ratio_20D | 0.6382 | 7 |
| ZScore_20D | -0.1668 | 33 |
| Beta_60D_SPY | 1.4838 | 76 |
| Stock_RS_20D_vs_SPY | 3.0911 | 45 |
| Quant_Score | 22.0000 | 5 |
| MA20 | 526.7000 | 95 |
| MA50 | 508.4300 | 95 |
| ATR_Pct | 2.1500 | 24 |
| KDJ_J | 4.4100 | 11 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 12. `NVDA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Technology　Price：210.96

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -1.4804 | 25 |
| Momentum_20D_Pct | -6.2692 | 23 |
| Momentum_60D_Pct | 8.1624 | 77 |
| Realized_Volatility_20D_Pct | 29.3230 | 51 |
| Volume_Ratio_20D | 0.7561 | 24 |
| ZScore_20D | -1.9009 | 13 |
| Beta_60D_SPY | 2.0589 | 86 |
| Stock_RS_20D_vs_SPY | -4.7938 | 23 |
| Quant_Score | 22.0000 | 5 |
| MA20 | 225.5400 | 79 |
| MA50 | 222.4800 | 79 |
| ATR_Pct | 2.8700 | 51 |
| KDJ_J | 4.4400 | 12 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 13. `GOOGL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Communication　Price：320.21

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -5.9837 | 11 |
| Momentum_20D_Pct | -6.8941 | 22 |
| Momentum_60D_Pct | -4.0311 | 45 |
| Realized_Volatility_20D_Pct | 20.9118 | 17 |
| Volume_Ratio_20D | 0.7336 | 20 |
| ZScore_20D | -3.5030 | 1 |
| Beta_60D_SPY | 1.5930 | 79 |
| Stock_RS_20D_vs_SPY | -5.4187 | 22 |
| Quant_Score | 22.0000 | 5 |
| MA20 | 343.0800 | 90 |
| MA50 | 342.9400 | 90 |
| ATR_Pct | 2.6900 | 42 |
| KDJ_J | -11.6300 | 0 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 14. `AMZN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Consumer Discretionary　Price：248.00

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.8000 | 30 |
| Momentum_20D_Pct | -0.6689 | 36 |
| Momentum_60D_Pct | 5.3079 | 71 |
| Realized_Volatility_20D_Pct | 32.8192 | 61 |
| Volume_Ratio_20D | 0.7039 | 15 |
| ZScore_20D | -1.1523 | 26 |
| Beta_60D_SPY | 1.8813 | 83 |
| Stock_RS_20D_vs_SPY | 0.8065 | 36 |
| Quant_Score | 27.0000 | 21 |
| MA20 | 254.4300 | 82 |
| MA50 | 255.6500 | 84 |
| ATR_Pct | 2.6900 | 42 |
| KDJ_J | 8.1500 | 16 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 15. `META`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Communication　Price：642.62

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -9.4047 | 4 |
| Momentum_20D_Pct | -14.5066 | 10 |
| Momentum_60D_Pct | 19.2178 | 92 |
| Realized_Volatility_20D_Pct | 41.6597 | 79 |
| Volume_Ratio_20D | 0.7453 | 22 |
| ZScore_20D | -3.2534 | 2 |
| Beta_60D_SPY | 2.0629 | 86 |
| Stock_RS_20D_vs_SPY | -13.0312 | 10 |
| Quant_Score | 22.0000 | 5 |
| MA20 | 717.6500 | 97 |
| MA50 | 663.8100 | 97 |
| ATR_Pct | 4.0600 | 82 |
| KDJ_J | -2.4600 | 4 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 16. `TSLA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Consumer Discretionary　Price：372.22

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.9335 | 86 |
| Momentum_20D_Pct | 0.0296 | 39 |
| Momentum_60D_Pct | 20.5180 | 93 |
| Realized_Volatility_20D_Pct | 36.5059 | 71 |
| Volume_Ratio_20D | 0.9422 | 53 |
| ZScore_20D | 0.2256 | 38 |
| Beta_60D_SPY | 2.2794 | 88 |
| Stock_RS_20D_vs_SPY | 1.5049 | 39 |
| Quant_Score | 56.0000 | 63 |
| MA20 | 369.8700 | 91 |
| MA50 | 363.7700 | 91 |
| ATR_Pct | 3.3800 | 67 |
| KDJ_J | 68.8200 | 45 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 17. `AVGO`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Technology　Price：321.68

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -2.1506 | 22 |
| Momentum_20D_Pct | -8.8234 | 18 |
| Momentum_60D_Pct | -17.0586 | 12 |
| Realized_Volatility_20D_Pct | 38.3609 | 75 |
| Volume_Ratio_20D | 0.7314 | 20 |
| ZScore_20D | -2.0260 | 10 |
| Beta_60D_SPY | 2.0737 | 87 |
| Stock_RS_20D_vs_SPY | -7.3481 | 18 |
| Quant_Score | 22.0000 | 5 |
| MA20 | 348.7100 | 90 |
| MA50 | 356.7600 | 90 |
| ATR_Pct | 3.5000 | 70 |
| KDJ_J | -0.9800 | 6 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 18. `TSM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-26 无因子快照

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

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Other　Price：542.19

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.9116 | 59 |
| Momentum_20D_Pct | 7.2624 | 67 |
| Momentum_60D_Pct | 6.3785 | 73 |
| Realized_Volatility_20D_Pct | 10.9482 | 0 |
| Volume_Ratio_20D | 0.9834 | 56 |
| ZScore_20D | 1.6788 | 67 |
| Beta_60D_SPY | -0.2150 | 15 |
| Stock_RS_20D_vs_SPY | 8.7377 | 67 |
| Quant_Score | 71.0000 | 90 |
| MA20 | 518.5800 | 95 |
| MA50 | 510.8200 | 95 |
| ATR_Pct | 1.1900 | 0 |
| KDJ_J | 81.4000 | 59 |

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

## 20. `JPM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Financials　Price：331.58

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -2.3961 | 21 |
| Momentum_20D_Pct | -3.3464 | 30 |
| Momentum_60D_Pct | -5.4924 | 38 |
| Realized_Volatility_20D_Pct | 14.5540 | 0 |
| Volume_Ratio_20D | 0.6100 | 6 |
| ZScore_20D | -0.8472 | 28 |
| Beta_60D_SPY | 0.3629 | 43 |
| Stock_RS_20D_vs_SPY | -1.8710 | 30 |
| Quant_Score | 22.0000 | 5 |
| MA20 | 333.7000 | 88 |
| MA50 | 345.4100 | 90 |
| ATR_Pct | 1.9100 | 10 |
| KDJ_J | 35.3900 | 29 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 21. `V`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Financials　Price：407.92

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.3189 | 52 |
| Momentum_20D_Pct | 11.0349 | 86 |
| Momentum_60D_Pct | 11.3714 | 84 |
| Realized_Volatility_20D_Pct | 19.5920 | 11 |
| Volume_Ratio_20D | 0.8555 | 43 |
| ZScore_20D | 1.3474 | 57 |
| Beta_60D_SPY | 0.3225 | 42 |
| Stock_RS_20D_vs_SPY | 12.5102 | 86 |
| Quant_Score | 72.0000 | 92 |
| MA20 | 385.2600 | 92 |
| MA50 | 377.0700 | 92 |
| ATR_Pct | 1.6600 | 2 |
| KDJ_J | 82.0700 | 60 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 22. `UNH`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Healthcare　Price：418.09

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.1502 | 81 |
| Momentum_20D_Pct | 11.0199 | 85 |
| Momentum_60D_Pct | -0.8020 | 54 |
| Realized_Volatility_20D_Pct | 28.8878 | 49 |
| Volume_Ratio_20D | 0.6419 | 8 |
| ZScore_20D | 1.6524 | 66 |
| Beta_60D_SPY | -0.0747 | 23 |
| Stock_RS_20D_vs_SPY | 12.4953 | 85 |
| Quant_Score | 35.0000 | 53 |
| MA20 | 389.2100 | 92 |
| MA50 | 388.5700 | 92 |
| ATR_Pct | 2.7300 | 45 |
| KDJ_J | 95.4400 | 86 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 23. `XOM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-26 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- N/A（无成交记录）

---

## 24. `COST`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-26（该日共 286 只；全表 14 个日期 / 3945 行）
- Sector：Consumer Staples　Price：1003.32

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.4366 | 54 |
| Momentum_20D_Pct | 8.7292 | 76 |
| Momentum_60D_Pct | 5.1511 | 71 |
| Realized_Volatility_20D_Pct | 16.4895 | 3 |
| Volume_Ratio_20D | 1.0692 | 68 |
| ZScore_20D | 1.4827 | 62 |
| Beta_60D_SPY | -0.0679 | 24 |
| Stock_RS_20D_vs_SPY | 10.2045 | 76 |
| Quant_Score | 70.0000 | 89 |
| MA20 | 958.1500 | 99 |
| MA50 | 938.8600 | 98 |
| ATR_Pct | 1.6100 | 1 |
| KDJ_J | 81.1200 | 57 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Staples）
- N/A（无成交记录）

---

说明：只读简报；缺失项统一 N/A。宏观环境在头部统一展示，不重复。
