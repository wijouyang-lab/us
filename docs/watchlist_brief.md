# Watchlist Brief — 24 只

> 生成：`scripts/ticker_brief.py --watchlist ... --md`　仓库：us　日期：latest

- 共 **24** 只票（APA, FAST, LLY, NXPI, AMGN, AMZN, MNST, BX, ABNB, GS, WDAY, AAPL, MSFT, NVDA, GOOGL, META, TSLA, AVGO, TSM, BRK-B, JPM, V, UNH, XOM）：**6** 只有 AI 快照记录，**8** 只有交易记录

## 宏观环境（结论化，仅打印一次）

- 恐惧贪婪指数：**31.37（恐惧）**　时间戳：2026-10-21T22:55:37+00:00
- FedWatch（会议 N/A，目标区间 N/A）：N/A
- 宏观指标：
  - 10Y国债：**5.10%**（前值 5.12%，2026-10-21，偏多）
  - 5Y国债：**4.92%**（前值 4.93%，2026-10-21，偏多）
  - 13周国债：**4.07%**（前值 4.08%，2026-10-21，偏多）
  - CPI：**4.00%**（前值 N/A，2026-09-01，偏空）
  - 核心CPI：**2.79%**（前值 N/A，2026-09-01，中性）
  - 失业率：**4.20%**（前值 4.10%，2026-09-01，偏空）
- 美联储讲话：最近一次 **Warsh**（10-18 19:47，Yahoo Finance）：黄金小幅上涨，交易员因Warsh讲话放松加息预期　立场：**偏多**

---

## 1. `APA`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：5

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-21 | Core_Dragon | scan | N/A | N/A |
| 2026-10-20 | Core_Dragon | scan | N/A | N/A |
| 2026-10-19 | Core_Dragon | scan | N/A | N/A |
| 2026-10-02 | Observation | scan | N/A | N/A |
| 2026-09-29 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-21 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 样本数：1（按日期倒序展示最近 1 笔）

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-19（仅日期） | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |

---

## 2. `FAST`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Other　Price：51.65

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.4278 | 37 |
| Momentum_20D_Pct | 3.1350 | 60 |
| Momentum_60D_Pct | 8.4173 | 77 |
| Realized_Volatility_20D_Pct | 20.0580 | 19 |
| Volume_Ratio_20D | 1.0167 | 65 |
| ZScore_20D | 1.6811 | 64 |
| Beta_60D_SPY | 0.3552 | 45 |
| Stock_RS_20D_vs_SPY | 3.6949 | 60 |
| Quant_Score | 83.0000 | 99 |
| MA20 | 50.7300 | 22 |
| MA50 | 50.3700 | 22 |
| ATR_Pct | 2.5500 | 43 |
| KDJ_J | 75.1400 | 51 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：9（按日期倒序展示最近 9 笔）
- **历史同类交易汇总**：共 4 笔，胜率 75.0%，平均盈利 +$248.47，平均亏损 -$297.04，盈亏比 0.84

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
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

## 3. `LLY`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-21 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Healthcare　Price：1283.66

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 10.0428 | 96 |
| Momentum_20D_Pct | 9.7014 | 89 |
| Momentum_60D_Pct | 7.1923 | 75 |
| Realized_Volatility_20D_Pct | 29.4460 | 62 |
| Volume_Ratio_20D | 1.3044 | 85 |
| ZScore_20D | 3.0094 | 95 |
| Beta_60D_SPY | -0.3365 | 9 |
| Stock_RS_20D_vs_SPY | 10.2613 | 89 |
| Quant_Score | 83.0000 | 99 |
| MA20 | 1188.2100 | 99 |
| MA50 | 1182.4700 | 99 |
| ATR_Pct | 2.9100 | 61 |
| KDJ_J | 92.7700 | 76 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 4. `NXPI`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-20 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Other　Price：237.60

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.9841 | 78 |
| Momentum_20D_Pct | 0.0126 | 47 |
| Momentum_60D_Pct | -11.2340 | 22 |
| Realized_Volatility_20D_Pct | 33.2230 | 70 |
| Volume_Ratio_20D | 0.9255 | 47 |
| ZScore_20D | 0.5855 | 42 |
| Beta_60D_SPY | 1.7332 | 82 |
| Stock_RS_20D_vs_SPY | 0.5725 | 47 |
| Quant_Score | 82.0000 | 99 |
| MA20 | 233.8800 | 80 |
| MA50 | 230.0700 | 79 |
| ATR_Pct | 3.5300 | 76 |
| KDJ_J | 85.2500 | 64 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：9（按日期倒序展示最近 9 笔）
- **历史同类交易汇总**：共 4 笔，胜率 75.0%，平均盈利 +$248.47，平均亏损 -$297.04，盈亏比 0.84

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
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

## 5. `AMGN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Healthcare　Price：438.94

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 6.3221 | 85 |
| Momentum_20D_Pct | 6.9959 | 77 |
| Momentum_60D_Pct | 16.6587 | 89 |
| Realized_Volatility_20D_Pct | 28.1334 | 57 |
| Volume_Ratio_20D | 0.7861 | 27 |
| ZScore_20D | 2.4809 | 87 |
| Beta_60D_SPY | 0.5407 | 52 |
| Stock_RS_20D_vs_SPY | 7.5558 | 77 |
| Quant_Score | 81.0000 | 99 |
| MA20 | 416.4100 | 93 |
| MA50 | 415.7300 | 93 |
| ATR_Pct | 2.4700 | 38 |
| KDJ_J | 90.6100 | 72 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 6. `AMZN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Consumer Discretionary　Price：262.63

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.5663 | 46 |
| Momentum_20D_Pct | 3.0002 | 59 |
| Momentum_60D_Pct | 13.5010 | 86 |
| Realized_Volatility_20D_Pct | 29.1145 | 60 |
| Volume_Ratio_20D | 0.9534 | 53 |
| ZScore_20D | 1.8072 | 68 |
| Beta_60D_SPY | 1.7707 | 82 |
| Stock_RS_20D_vs_SPY | 3.5601 | 59 |
| Quant_Score | 80.0000 | 98 |
| MA20 | 253.8100 | 81 |
| MA50 | 256.5300 | 83 |
| ATR_Pct | 2.4300 | 36 |
| KDJ_J | 78.8800 | 56 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 7. `MNST`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-02 | Observation | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Other　Price：47.04

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 8.6123 | 94 |
| Momentum_20D_Pct | 6.2571 | 73 |
| Momentum_60D_Pct | -1.3112 | 55 |
| Realized_Volatility_20D_Pct | 24.6905 | 41 |
| Volume_Ratio_20D | 0.8051 | 29 |
| ZScore_20D | 2.6552 | 91 |
| Beta_60D_SPY | -0.1473 | 15 |
| Stock_RS_20D_vs_SPY | 6.8169 | 73 |
| Quant_Score | 80.0000 | 98 |
| MA20 | 43.6600 | 18 |
| MA50 | 44.7900 | 17 |
| ATR_Pct | 2.2500 | 28 |
| KDJ_J | 92.6800 | 75 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：9（按日期倒序展示最近 9 笔）
- **历史同类交易汇总**：共 4 笔，胜率 75.0%，平均盈利 +$248.47，平均亏损 -$297.04，盈亏比 0.84

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
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

## 8. `BX`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：2

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-21 | Core_Dragon | scan | N/A | N/A |
| 2026-09-29 | Observation | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Other　Price：110.34

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.3273 | 36 |
| Momentum_20D_Pct | -11.0233 | 11 |
| Momentum_60D_Pct | -16.7873 | 11 |
| Realized_Volatility_20D_Pct | 33.6611 | 72 |
| Volume_Ratio_20D | 1.1456 | 79 |
| ZScore_20D | -0.6187 | 26 |
| Beta_60D_SPY | 1.9627 | 86 |
| Stock_RS_20D_vs_SPY | -10.4634 | 11 |
| Quant_Score | 79.0000 | 98 |
| MA20 | 112.3800 | 57 |
| MA50 | 126.9700 | 60 |
| ATR_Pct | 3.3800 | 72 |
| KDJ_J | 33.3100 | 25 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：9（按日期倒序展示最近 9 笔）
- **历史同类交易汇总**：共 4 笔，胜率 75.0%，平均盈利 +$248.47，平均亏损 -$297.04，盈亏比 0.84

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
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

## 9. `ABNB`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Other　Price：176.94

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 6.8607 | 88 |
| Momentum_20D_Pct | 9.3505 | 88 |
| Momentum_60D_Pct | 20.4821 | 92 |
| Realized_Volatility_20D_Pct | 38.9846 | 79 |
| Volume_Ratio_20D | 0.5797 | 5 |
| ZScore_20D | 2.1157 | 80 |
| Beta_60D_SPY | 0.9152 | 63 |
| Stock_RS_20D_vs_SPY | 9.9104 | 88 |
| Quant_Score | 78.0000 | 97 |
| MA20 | 163.2900 | 69 |
| MA50 | 172.5900 | 70 |
| ATR_Pct | 2.7100 | 51 |
| KDJ_J | 93.5700 | 77 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：9（按日期倒序展示最近 9 笔）
- **历史同类交易汇总**：共 4 笔，胜率 75.0%，平均盈利 +$248.47，平均亏损 -$297.04，盈亏比 0.84

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
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

## 10. `GS`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Financials　Price：884.81

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.7960 | 28 |
| Momentum_20D_Pct | -6.8121 | 20 |
| Momentum_60D_Pct | -15.5901 | 13 |
| Realized_Volatility_20D_Pct | 17.3871 | 7 |
| Volume_Ratio_20D | 1.0004 | 61 |
| ZScore_20D | -0.8444 | 23 |
| Beta_60D_SPY | 1.7910 | 83 |
| Stock_RS_20D_vs_SPY | -6.2522 | 20 |
| Quant_Score | 78.0000 | 97 |
| MA20 | 899.0300 | 98 |
| MA50 | 968.5700 | 99 |
| ATR_Pct | 2.8100 | 57 |
| KDJ_J | 31.7500 | 25 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 11. `WDAY`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Other　Price：203.98

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 9.6549 | 95 |
| Momentum_20D_Pct | 8.3674 | 84 |
| Momentum_60D_Pct | 38.2540 | 97 |
| Realized_Volatility_20D_Pct | 31.0563 | 65 |
| Volume_Ratio_20D | 1.1620 | 80 |
| ZScore_20D | 4.8795 | 100 |
| Beta_60D_SPY | 1.0358 | 66 |
| Stock_RS_20D_vs_SPY | 8.9273 | 84 |
| Quant_Score | 78.0000 | 97 |
| MA20 | 189.8900 | 74 |
| MA50 | 192.1600 | 74 |
| ATR_Pct | 3.6500 | 77 |
| KDJ_J | 99.2200 | 86 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：9（按日期倒序展示最近 9 笔）
- **历史同类交易汇总**：共 4 笔，胜率 75.0%，平均盈利 +$248.47，平均亏损 -$297.04，盈亏比 0.84

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
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

## 12. `AAPL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Technology　Price：339.50

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.5186 | 30 |
| Momentum_20D_Pct | -0.0736 | 46 |
| Momentum_60D_Pct | 0.7688 | 61 |
| Realized_Volatility_20D_Pct | 16.4096 | 4 |
| Volume_Ratio_20D | 0.9674 | 55 |
| ZScore_20D | 0.4312 | 40 |
| Beta_60D_SPY | -0.0352 | 21 |
| Stock_RS_20D_vs_SPY | 0.4863 | 46 |
| Quant_Score | 23.0000 | 5 |
| MA20 | 337.6100 | 88 |
| MA50 | 326.9200 | 88 |
| ATR_Pct | 1.9100 | 14 |
| KDJ_J | 56.7900 | 37 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 13. `MSFT`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Technology　Price：531.87

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -2.1308 | 25 |
| Momentum_20D_Pct | 6.8012 | 76 |
| Momentum_60D_Pct | 36.6924 | 96 |
| Realized_Volatility_20D_Pct | 21.7412 | 28 |
| Volume_Ratio_20D | 0.6647 | 12 |
| ZScore_20D | 0.7006 | 44 |
| Beta_60D_SPY | 2.1470 | 88 |
| Stock_RS_20D_vs_SPY | 7.3611 | 76 |
| Quant_Score | 22.0000 | 2 |
| MA20 | 523.5100 | 95 |
| MA50 | 506.7200 | 94 |
| ATR_Pct | 2.1500 | 24 |
| KDJ_J | 28.8300 | 24 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 14. `NVDA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Technology　Price：216.47

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -5.2731 | 17 |
| Momentum_20D_Pct | -5.4179 | 25 |
| Momentum_60D_Pct | 10.1572 | 81 |
| Realized_Volatility_20D_Pct | 23.4656 | 35 |
| Volume_Ratio_20D | 0.7569 | 24 |
| ZScore_20D | -1.6371 | 13 |
| Beta_60D_SPY | 1.9298 | 85 |
| Stock_RS_20D_vs_SPY | -4.8580 | 25 |
| Quant_Score | 30.0000 | 20 |
| MA20 | 227.0400 | 79 |
| MA50 | 222.9200 | 78 |
| ATR_Pct | 2.7300 | 52 |
| KDJ_J | 5.6800 | 12 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 15. `GOOGL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Communication　Price：340.28

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -3.8159 | 20 |
| Momentum_20D_Pct | -3.0983 | 34 |
| Momentum_60D_Pct | 4.2014 | 68 |
| Realized_Volatility_20D_Pct | 22.2423 | 30 |
| Volume_Ratio_20D | 0.7405 | 20 |
| ZScore_20D | -1.1773 | 18 |
| Beta_60D_SPY | 1.1902 | 70 |
| Stock_RS_20D_vs_SPY | -2.5384 | 34 |
| Quant_Score | 22.0000 | 2 |
| MA20 | 345.3300 | 89 |
| MA50 | 344.0300 | 89 |
| ATR_Pct | 2.5100 | 41 |
| KDJ_J | -1.9400 | 7 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 16. `META`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Communication　Price：694.25

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -8.9508 | 10 |
| Momentum_20D_Pct | -5.7494 | 24 |
| Momentum_60D_Pct | 16.9027 | 90 |
| Realized_Volatility_20D_Pct | 40.4238 | 81 |
| Volume_Ratio_20D | 0.8414 | 33 |
| ZScore_20D | -2.2644 | 3 |
| Beta_60D_SPY | 1.1009 | 68 |
| Stock_RS_20D_vs_SPY | -5.1895 | 24 |
| Quant_Score | 17.0000 | 0 |
| MA20 | 731.8700 | 97 |
| MA50 | 659.4900 | 97 |
| ATR_Pct | 3.5400 | 76 |
| KDJ_J | 4.4800 | 11 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 17. `TSLA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Consumer Discretionary　Price：373.71

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.4051 | 32 |
| Momentum_20D_Pct | -1.3698 | 39 |
| Momentum_60D_Pct | 20.8557 | 93 |
| Realized_Volatility_20D_Pct | 32.9258 | 69 |
| Volume_Ratio_20D | 0.9155 | 44 |
| ZScore_20D | 0.3629 | 38 |
| Beta_60D_SPY | 2.1714 | 89 |
| Stock_RS_20D_vs_SPY | -0.8099 | 39 |
| Quant_Score | 61.0000 | 66 |
| MA20 | 369.7100 | 90 |
| MA50 | 361.1100 | 90 |
| ATR_Pct | 3.2700 | 69 |
| KDJ_J | 46.6600 | 30 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 18. `AVGO`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Technology　Price：334.37

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -6.4202 | 14 |
| Momentum_20D_Pct | -8.2762 | 17 |
| Momentum_60D_Pct | -12.7472 | 18 |
| Realized_Volatility_20D_Pct | 36.5269 | 74 |
| Volume_Ratio_20D | 0.7241 | 18 |
| ZScore_20D | -1.6796 | 12 |
| Beta_60D_SPY | 2.0670 | 87 |
| Stock_RS_20D_vs_SPY | -7.7163 | 17 |
| Quant_Score | 22.0000 | 2 |
| MA20 | 352.4800 | 90 |
| MA50 | 362.1000 | 90 |
| ATR_Pct | 3.4300 | 73 |
| KDJ_J | -0.6600 | 8 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 19. `TSM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-21 无因子快照

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

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Other　Price：539.82

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.6939 | 70 |
| Momentum_20D_Pct | 7.2156 | 78 |
| Momentum_60D_Pct | 8.5764 | 78 |
| Realized_Volatility_20D_Pct | 9.4887 | 0 |
| Volume_Ratio_20D | 1.2600 | 83 |
| ZScore_20D | 2.6428 | 90 |
| Beta_60D_SPY | -0.0876 | 19 |
| Stock_RS_20D_vs_SPY | 7.7755 | 78 |
| Quant_Score | 76.0000 | 94 |
| MA20 | 513.0700 | 94 |
| MA50 | 508.9200 | 94 |
| ATR_Pct | 1.1400 | 0 |
| KDJ_J | 102.0000 | 91 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：9（按日期倒序展示最近 9 笔）
- **历史同类交易汇总**：共 4 笔，胜率 75.0%，平均盈利 +$248.47，平均亏损 -$297.04，盈亏比 0.84

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
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

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Financials　Price：335.26

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.1556 | 43 |
| Momentum_20D_Pct | -1.3941 | 39 |
| Momentum_60D_Pct | -5.8787 | 42 |
| Realized_Volatility_20D_Pct | 14.7876 | 3 |
| Volume_Ratio_20D | 0.7506 | 23 |
| ZScore_20D | 0.1490 | 35 |
| Beta_60D_SPY | 0.6198 | 55 |
| Stock_RS_20D_vs_SPY | -0.8342 | 39 |
| Quant_Score | 32.0000 | 34 |
| MA20 | 334.4900 | 88 |
| MA50 | 347.1500 | 89 |
| ATR_Pct | 1.9900 | 17 |
| KDJ_J | 55.1600 | 35 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 22. `V`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Financials　Price：406.57

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.6536 | 59 |
| Momentum_20D_Pct | 12.2997 | 94 |
| Momentum_60D_Pct | 12.1480 | 83 |
| Realized_Volatility_20D_Pct | 18.5308 | 12 |
| Volume_Ratio_20D | 1.1395 | 78 |
| ZScore_20D | 1.9684 | 75 |
| Beta_60D_SPY | 0.2449 | 41 |
| Stock_RS_20D_vs_SPY | 12.8596 | 94 |
| Quant_Score | 72.0000 | 89 |
| MA20 | 378.6000 | 90 |
| MA50 | 374.2200 | 91 |
| ATR_Pct | 1.6600 | 4 |
| KDJ_J | 99.3300 | 86 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 23. `UNH`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：Healthcare　Price：419.26

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 10.9858 | 98 |
| Momentum_20D_Pct | 12.4172 | 95 |
| Momentum_60D_Pct | 0.3879 | 60 |
| Realized_Volatility_20D_Pct | 27.3311 | 51 |
| Volume_Ratio_20D | 1.1552 | 79 |
| ZScore_20D | 3.1733 | 96 |
| Beta_60D_SPY | 0.1308 | 34 |
| Stock_RS_20D_vs_SPY | 12.9771 | 95 |
| Quant_Score | 73.0000 | 90 |
| MA20 | 382.3600 | 91 |
| MA50 | 387.5000 | 92 |
| ATR_Pct | 2.8900 | 61 |
| KDJ_J | 98.8800 | 85 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 24. `XOM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-21（该日共 288 只；全表 11 个日期 / 3080 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-21 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- N/A（无成交记录）

---

说明：只读简报；缺失项统一 N/A。宏观环境在头部统一展示，不重复。
