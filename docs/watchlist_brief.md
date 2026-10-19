# Watchlist Brief — 24 只

> 生成：`scripts/ticker_brief.py --watchlist ... --md`　仓库：us　日期：latest

- 共 **24** 只票（APA, LLY, AMZN, CVX, FAST, ISRG, NXPI, SYK, OXY, ABNB, AAPL, MSFT, NVDA, GOOGL, META, TSLA, AVGO, TSM, BRK-B, JPM, V, UNH, XOM, COST）：**4** 只有 AI 快照记录，**7** 只有交易记录

## 宏观环境（结论化，仅打印一次）

- 恐惧贪婪指数：**23.11（极度恐惧）**　时间戳：2026-10-19T23:27:50+00:00
- FedWatch（会议 2026-10-28，目标区间 3.75%-4.00%）：维持不变 **84.5%** / 加息 25bp **15.5%**
- 宏观指标：
  - 10Y国债：**5.14%**（前值 5.10%，2026-10-19，偏空）
  - 5Y国债：**4.94%**（前值 4.90%，2026-10-19，偏空）
  - 13周国债：**4.08%**（前值 4.07%，2026-10-19，中性）
  - CPI：**4.00%**（前值 N/A，2026-09-01，偏空）
  - 核心CPI：**2.79%**（前值 N/A，2026-09-01，中性）
  - 失业率：**4.20%**（前值 4.10%，2026-09-01，偏空）
- 美联储讲话：最近一次 **Warsh**（10-18 19:47，Yahoo Finance）：黄金小幅走高，因交易员根据Warsh讲话放松加息押注 - 雅虎财经　立场：**中性**

---

## 1. `APA`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：3

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-19 | Core_Dragon | scan | N/A | N/A |
| 2026-10-02 | Observation | scan | N/A | N/A |
| 2026-09-29 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Other　Price：49.44

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 5.5508 | 90 |
| Momentum_20D_Pct | 12.8509 | 97 |
| Momentum_60D_Pct | 36.7635 | 96 |
| Realized_Volatility_20D_Pct | 34.1263 | 71 |
| Volume_Ratio_20D | 0.3150 | 40 |
| ZScore_20D | 2.2525 | 90 |
| Beta_60D_SPY | -1.0557 | 1 |
| Stock_RS_20D_vs_SPY | 13.6486 | 97 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 44.8300 | 17 |
| MA50 | 43.8500 | 15 |
| ATR_Pct | 3.0000 | 62 |
| KDJ_J | 102.6000 | 93 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 样本数：1（按日期倒序展示最近 1 笔）

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-19（仅日期） | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |

---

## 2. `LLY`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Healthcare　Price：1247.86

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 5.5166 | 89 |
| Momentum_20D_Pct | 7.1226 | 83 |
| Momentum_60D_Pct | 4.3335 | 66 |
| Realized_Volatility_20D_Pct | 26.8108 | 49 |
| Volume_Ratio_20D | 0.3296 | 43 |
| ZScore_20D | 2.2363 | 90 |
| Beta_60D_SPY | -0.3638 | 9 |
| Stock_RS_20D_vs_SPY | 7.9202 | 83 |
| Quant_Score | 83.0000 | 100 |
| MA20 | 1182.9100 | 99 |
| MA50 | 1181.5900 | 99 |
| ATR_Pct | 2.7800 | 55 |
| KDJ_J | 95.1100 | 84 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 3. `AMZN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Consumer Discretionary　Price：262.25

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.0480 | 55 |
| Momentum_20D_Pct | 1.4703 | 58 |
| Momentum_60D_Pct | 12.9852 | 84 |
| Realized_Volatility_20D_Pct | 29.4282 | 61 |
| Volume_Ratio_20D | 0.8284 | 92 |
| ZScore_20D | 1.8842 | 82 |
| Beta_60D_SPY | 1.7892 | 83 |
| Stock_RS_20D_vs_SPY | 2.2680 | 58 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 253.4200 | 81 |
| MA50 | 256.8300 | 83 |
| ATR_Pct | 2.4700 | 38 |
| KDJ_J | 57.2700 | 41 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 4. `CVX`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Energy　Price：224.52

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.4302 | 83 |
| Momentum_20D_Pct | 10.2396 | 93 |
| Momentum_60D_Pct | 15.2652 | 87 |
| Realized_Volatility_20D_Pct | 19.6958 | 20 |
| Volume_Ratio_20D | 0.5738 | 84 |
| ZScore_20D | 2.2274 | 89 |
| Beta_60D_SPY | -0.9083 | 3 |
| Stock_RS_20D_vs_SPY | 11.0373 | 93 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 210.6600 | 75 |
| MA50 | 207.8900 | 75 |
| ATR_Pct | 1.9600 | 16 |
| KDJ_J | 101.0100 | 92 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Energy）
- N/A（无成交记录）

---

## 5. `FAST`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Other　Price：51.25

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.4756 | 38 |
| Momentum_20D_Pct | 3.2127 | 66 |
| Momentum_60D_Pct | 8.9857 | 77 |
| Realized_Volatility_20D_Pct | 19.8573 | 22 |
| Volume_Ratio_20D | 0.2485 | 15 |
| ZScore_20D | 1.0526 | 61 |
| Beta_60D_SPY | 0.3494 | 46 |
| Stock_RS_20D_vs_SPY | 4.0104 | 67 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 50.6700 | 20 |
| MA50 | 50.3800 | 20 |
| ATR_Pct | 2.6300 | 46 |
| KDJ_J | 70.1600 | 52 |

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

## 6. `ISRG`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：2

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-14 | Core_Dragon | scan | N/A | N/A |
| 2026-10-07 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Other　Price：432.11

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.0453 | 55 |
| Momentum_20D_Pct | 7.5837 | 86 |
| Momentum_60D_Pct | 28.0326 | 95 |
| Realized_Volatility_20D_Pct | 24.8951 | 42 |
| Volume_Ratio_20D | 0.6285 | 88 |
| ZScore_20D | 1.9208 | 82 |
| Beta_60D_SPY | 0.8020 | 61 |
| Stock_RS_20D_vs_SPY | 8.3814 | 86 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 412.6800 | 92 |
| MA50 | 392.7300 | 93 |
| ATR_Pct | 2.5000 | 39 |
| KDJ_J | 89.3700 | 76 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 样本数：2（按日期倒序展示最近 2 笔）
- **历史同类交易汇总**：共 1 笔，胜率 100.0%，平均盈利 +$233.76，平均亏损 -$0.00，盈亏比 N/A

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-14（仅日期） | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-07（仅日期） | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |

---

## 7. `NXPI`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Other　Price：230.70

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.4377 | 67 |
| Momentum_20D_Pct | -0.7358 | 47 |
| Momentum_60D_Pct | -14.3144 | 17 |
| Realized_Volatility_20D_Pct | 32.1654 | 69 |
| Volume_Ratio_20D | 0.3016 | 35 |
| ZScore_20D | -0.5213 | 32 |
| Beta_60D_SPY | 1.7063 | 81 |
| Stock_RS_20D_vs_SPY | 0.0619 | 48 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 233.9000 | 79 |
| MA50 | 230.0000 | 78 |
| ATR_Pct | 3.4600 | 73 |
| KDJ_J | 52.6900 | 39 |

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

## 8. `SYK`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-09-29 | Observation | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Other　Price：298.77

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 5.7219 | 91 |
| Momentum_20D_Pct | 8.9646 | 91 |
| Momentum_60D_Pct | -9.5322 | 31 |
| Realized_Volatility_20D_Pct | 25.2475 | 44 |
| Volume_Ratio_20D | 0.5035 | 78 |
| ZScore_20D | 3.1009 | 99 |
| Beta_60D_SPY | 0.2137 | 41 |
| Stock_RS_20D_vs_SPY | 9.7623 | 91 |
| Quant_Score | 80.0000 | 97 |
| MA20 | 279.7500 | 84 |
| MA50 | 299.1400 | 86 |
| ATR_Pct | 2.7200 | 52 |
| KDJ_J | 104.5800 | 95 |

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

## 9. `OXY`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Energy　Price：62.99

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.0345 | 72 |
| Momentum_20D_Pct | 10.0175 | 92 |
| Momentum_60D_Pct | 9.9215 | 79 |
| Realized_Volatility_20D_Pct | 28.5436 | 57 |
| Volume_Ratio_20D | 0.4141 | 65 |
| ZScore_20D | 2.0396 | 85 |
| Beta_60D_SPY | -0.9189 | 3 |
| Stock_RS_20D_vs_SPY | 10.8151 | 93 |
| Quant_Score | 79.0000 | 97 |
| MA20 | 58.8200 | 25 |
| MA50 | 59.4600 | 24 |
| ATR_Pct | 2.3500 | 31 |
| KDJ_J | 100.3600 | 91 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Energy）
- N/A（无成交记录）

---

## 10. `ABNB`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Other　Price：174.36

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 6.6422 | 96 |
| Momentum_20D_Pct | 4.5073 | 72 |
| Momentum_60D_Pct | 23.5719 | 92 |
| Realized_Volatility_20D_Pct | 40.7762 | 81 |
| Volume_Ratio_20D | 0.2061 | 7 |
| ZScore_20D | 1.9793 | 83 |
| Beta_60D_SPY | 0.8957 | 63 |
| Stock_RS_20D_vs_SPY | 5.3050 | 73 |
| Quant_Score | 78.0000 | 96 |
| MA20 | 162.4800 | 67 |
| MA50 | 172.7200 | 68 |
| ATR_Pct | 2.7500 | 54 |
| KDJ_J | 90.5800 | 78 |

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

## 11. `AAPL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Technology　Price：341.69

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.2112 | 44 |
| Momentum_20D_Pct | 0.7995 | 54 |
| Momentum_60D_Pct | 2.6035 | 64 |
| Realized_Volatility_20D_Pct | 16.1029 | 4 |
| Volume_Ratio_20D | 0.4647 | 72 |
| ZScore_20D | 1.0187 | 59 |
| Beta_60D_SPY | -0.0341 | 21 |
| Stock_RS_20D_vs_SPY | 1.5971 | 54 |
| Quant_Score | 30.0000 | 29 |
| MA20 | 337.5600 | 88 |
| MA50 | 326.2700 | 88 |
| ATR_Pct | 1.9400 | 14 |
| KDJ_J | 67.6300 | 50 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 12. `MSFT`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-19 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- N/A（无成交记录）

---

## 13. `NVDA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Technology　Price：218.14

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -3.6144 | 24 |
| Momentum_20D_Pct | -4.0637 | 33 |
| Momentum_60D_Pct | 5.4631 | 68 |
| Realized_Volatility_20D_Pct | 24.1913 | 39 |
| Volume_Ratio_20D | 0.5370 | 81 |
| ZScore_20D | -1.5756 | 16 |
| Beta_60D_SPY | 1.9542 | 86 |
| Stock_RS_20D_vs_SPY | -3.2661 | 34 |
| Quant_Score | 71.0000 | 88 |
| MA20 | 227.7100 | 78 |
| MA50 | 222.9600 | 77 |
| ATR_Pct | 2.7200 | 52 |
| KDJ_J | 3.9300 | 12 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 14. `GOOGL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Communication　Price：344.51

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -2.3276 | 28 |
| Momentum_20D_Pct | -2.9467 | 39 |
| Momentum_60D_Pct | 7.7469 | 75 |
| Realized_Volatility_20D_Pct | 22.2801 | 32 |
| Volume_Ratio_20D | 0.3768 | 54 |
| ZScore_20D | -0.3700 | 36 |
| Beta_60D_SPY | 1.2026 | 71 |
| Stock_RS_20D_vs_SPY | -2.1491 | 39 |
| Quant_Score | 28.0000 | 26 |
| MA20 | 345.8900 | 89 |
| MA50 | 344.3800 | 89 |
| ATR_Pct | 2.5200 | 40 |
| KDJ_J | 10.9000 | 18 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 15. `META`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Communication　Price：701.30

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -5.6066 | 17 |
| Momentum_20D_Pct | -5.3889 | 25 |
| Momentum_60D_Pct | 17.8288 | 89 |
| Realized_Volatility_20D_Pct | 40.2674 | 80 |
| Volume_Ratio_20D | 0.3952 | 60 |
| ZScore_20D | -2.1197 | 7 |
| Beta_60D_SPY | 1.1057 | 68 |
| Stock_RS_20D_vs_SPY | -4.5912 | 25 |
| Quant_Score | 17.0000 | 1 |
| MA20 | 733.7800 | 97 |
| MA50 | 657.4200 | 97 |
| ATR_Pct | 3.5100 | 74 |
| KDJ_J | 4.8200 | 14 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 16. `TSLA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Consumer Discretionary　Price：369.13

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -2.3543 | 27 |
| Momentum_20D_Pct | -1.6440 | 43 |
| Momentum_60D_Pct | 17.9216 | 89 |
| Realized_Volatility_20D_Pct | 33.1052 | 70 |
| Volume_Ratio_20D | 0.6840 | 89 |
| ZScore_20D | -0.1162 | 40 |
| Beta_60D_SPY | 2.1795 | 88 |
| Stock_RS_20D_vs_SPY | -0.8464 | 44 |
| Quant_Score | 66.0000 | 79 |
| MA20 | 370.0200 | 90 |
| MA50 | 360.2700 | 89 |
| ATR_Pct | 3.2700 | 69 |
| KDJ_J | 25.5100 | 25 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 17. `AVGO`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Technology　Price：336.88

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -5.0334 | 21 |
| Momentum_20D_Pct | -7.1100 | 21 |
| Momentum_60D_Pct | -11.7944 | 23 |
| Realized_Volatility_20D_Pct | 37.2769 | 76 |
| Volume_Ratio_20D | 0.3340 | 45 |
| ZScore_20D | -1.7009 | 15 |
| Beta_60D_SPY | 2.0824 | 87 |
| Stock_RS_20D_vs_SPY | -6.3123 | 22 |
| Quant_Score | 30.0000 | 29 |
| MA20 | 354.1000 | 89 |
| MA50 | 363.9100 | 90 |
| ATR_Pct | 3.4300 | 72 |
| KDJ_J | -0.9600 | 9 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 18. `TSM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
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

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Other　Price：531.15

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.6179 | 68 |
| Momentum_20D_Pct | 5.8047 | 77 |
| Momentum_60D_Pct | 7.3182 | 73 |
| Realized_Volatility_20D_Pct | 8.7051 | 0 |
| Volume_Ratio_20D | 0.3704 | 53 |
| ZScore_20D | 2.1875 | 89 |
| Beta_60D_SPY | -0.1039 | 18 |
| Stock_RS_20D_vs_SPY | 6.6023 | 77 |
| Quant_Score | 71.0000 | 88 |
| MA20 | 511.2000 | 95 |
| MA50 | 508.6900 | 95 |
| ATR_Pct | 1.1100 | 0 |
| KDJ_J | 97.6200 | 87 |

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

## 20. `JPM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Financials　Price：336.62

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.6940 | 51 |
| Momentum_20D_Pct | -4.3802 | 31 |
| Momentum_60D_Pct | -4.6969 | 46 |
| Realized_Volatility_20D_Pct | 18.0516 | 13 |
| Volume_Ratio_20D | 0.2914 | 32 |
| ZScore_20D | 0.1842 | 46 |
| Beta_60D_SPY | 0.6201 | 55 |
| Stock_RS_20D_vs_SPY | -3.5825 | 32 |
| Quant_Score | 27.0000 | 22 |
| MA20 | 334.8800 | 88 |
| MA50 | 347.7000 | 89 |
| ATR_Pct | 1.9200 | 14 |
| KDJ_J | 71.2500 | 54 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 21. `V`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Financials　Price：402.78

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.4706 | 76 |
| Momentum_20D_Pct | 8.8742 | 90 |
| Momentum_60D_Pct | 13.2231 | 85 |
| Realized_Volatility_20D_Pct | 20.8526 | 28 |
| Volume_Ratio_20D | 0.3239 | 41 |
| ZScore_20D | 1.9960 | 84 |
| Beta_60D_SPY | 0.2341 | 42 |
| Stock_RS_20D_vs_SPY | 9.6718 | 90 |
| Quant_Score | 70.0000 | 86 |
| MA20 | 376.3600 | 90 |
| MA50 | 373.3100 | 91 |
| ATR_Pct | 1.6900 | 5 |
| KDJ_J | 99.7500 | 89 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 22. `UNH`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Healthcare　Price：402.77

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 6.4065 | 94 |
| Momentum_20D_Pct | 6.6771 | 81 |
| Momentum_60D_Pct | -4.2710 | 47 |
| Realized_Volatility_20D_Pct | 26.2057 | 46 |
| Volume_Ratio_20D | 0.3489 | 50 |
| ZScore_20D | 2.2772 | 91 |
| Beta_60D_SPY | 0.0919 | 31 |
| Stock_RS_20D_vs_SPY | 7.4748 | 81 |
| Quant_Score | 70.0000 | 86 |
| MA20 | 379.8300 | 91 |
| MA50 | 387.2100 | 92 |
| ATR_Pct | 2.9500 | 61 |
| KDJ_J | 81.9900 | 68 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 23. `XOM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
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

- 快照日期：2026-10-19（该日共 312 只；全表 9 个日期 / 2506 行）
- Sector：Consumer Staples　Price：992.42

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.4374 | 76 |
| Momentum_20D_Pct | 10.4554 | 94 |
| Momentum_60D_Pct | 6.1378 | 70 |
| Realized_Volatility_20D_Pct | 17.1740 | 8 |
| Volume_Ratio_20D | 0.2812 | 27 |
| ZScore_20D | 2.0848 | 86 |
| Beta_60D_SPY | -0.1684 | 14 |
| Stock_RS_20D_vs_SPY | 11.2531 | 94 |
| Quant_Score | 70.0000 | 86 |
| MA20 | 938.4400 | 98 |
| MA50 | 934.6800 | 98 |
| ATR_Pct | 1.6100 | 2 |
| KDJ_J | 74.4500 | 57 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Staples）
- N/A（无成交记录）

---

说明：只读简报；缺失项统一 N/A。宏观环境在头部统一展示，不重复。
