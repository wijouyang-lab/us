# Watchlist Brief — 24 只

> 生成：`scripts/ticker_brief.py --watchlist ... --md`　仓库：us　日期：latest

- 共 **24** 只票（APA, OXY, AMZN, CVX, ISRG, NXPI, AMGN, ABNB, LLY, ROST, COP, AAPL, MSFT, NVDA, GOOGL, META, TSLA, AVGO, TSM, BRK-B, JPM, V, UNH, XOM）：**4** 只有 AI 快照记录，**6** 只有交易记录

## 宏观环境（结论化，仅打印一次）

- 恐惧贪婪指数：**22.09（极度恐惧）**　时间戳：2026-10-20T12:44:21+00:00
- FedWatch（会议 2026-10-28，目标区间 3.75%-4.00%）：维持不变 **81.2%** / 加息 25bp **18.8%**
- 宏观指标：
  - 10Y国债：**5.10%**（前值 5.14%，2026-10-20，偏多）
  - 5Y国债：**4.91%**（前值 4.93%，2026-10-20，偏多）
  - 13周国债：**4.09%**（前值 4.07%，2026-10-20，偏空）
  - CPI：**4.00%**（前值 N/A，2026-09-01，偏空）
  - 核心CPI：**2.79%**（前值 N/A，2026-09-01，偏空）
  - 失业率：**4.20%**（前值 4.10%，2026-09-01，偏空）
- 美联储讲话：最近一次 **N/A**（10-20 06:15，MarketWatch）：策略师Tom Lee表示正在买入AI股票的回调，思科是关键　立场：**偏多**

---

## 1. `APA`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：4

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-20 | Core_Dragon | scan | N/A | N/A |
| 2026-10-19 | Core_Dragon | scan | N/A | N/A |
| 2026-10-02 | Observation | scan | N/A | N/A |
| 2026-09-29 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-20 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 样本数：1（按日期倒序展示最近 1 笔）

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-19（仅日期） | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |

---

## 2. `OXY`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Energy　Price：62.72

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.6010 | 71 |
| Momentum_20D_Pct | 9.5546 | 93 |
| Momentum_60D_Pct | 9.4590 | 78 |
| Realized_Volatility_20D_Pct | 28.4894 | 59 |
| Volume_Ratio_20D | 0.9387 | 60 |
| ZScore_20D | 1.9183 | 82 |
| Beta_60D_SPY | -0.9304 | 2 |
| Stock_RS_20D_vs_SPY | 10.4622 | 93 |
| Quant_Score | 82.0000 | 100 |
| MA20 | 58.8000 | 26 |
| MA50 | 59.4600 | 25 |
| ATR_Pct | 2.3800 | 32 |
| KDJ_J | 95.9200 | 86 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Energy）
- N/A（无成交记录）

---

## 3. `AMZN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Consumer Discretionary　Price：262.45

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.1251 | 58 |
| Momentum_20D_Pct | 1.5477 | 59 |
| Momentum_60D_Pct | 13.0714 | 85 |
| Realized_Volatility_20D_Pct | 29.6025 | 63 |
| Volume_Ratio_20D | 1.5659 | 95 |
| ZScore_20D | 1.9259 | 83 |
| Beta_60D_SPY | 1.7775 | 81 |
| Stock_RS_20D_vs_SPY | 2.4553 | 59 |
| Quant_Score | 80.0000 | 98 |
| MA20 | 253.4300 | 81 |
| MA50 | 256.8400 | 83 |
| ATR_Pct | 2.4800 | 37 |
| KDJ_J | 58.2100 | 44 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 4. `CVX`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Energy　Price：224.37

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.3581 | 84 |
| Momentum_20D_Pct | 10.1635 | 94 |
| Momentum_60D_Pct | 15.1856 | 88 |
| Realized_Volatility_20D_Pct | 19.7299 | 20 |
| Volume_Ratio_20D | 1.2708 | 88 |
| ZScore_20D | 2.2042 | 91 |
| Beta_60D_SPY | -0.9104 | 2 |
| Stock_RS_20D_vs_SPY | 11.0711 | 94 |
| Quant_Score | 80.0000 | 98 |
| MA20 | 210.6500 | 76 |
| MA50 | 207.8900 | 76 |
| ATR_Pct | 1.9600 | 15 |
| KDJ_J | 100.4300 | 92 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Energy）
- N/A（无成交记录）

---

## 5. `ISRG`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：2

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-14 | Core_Dragon | scan | N/A | N/A |
| 2026-10-07 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Other　Price：433.18

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.2955 | 60 |
| Momentum_20D_Pct | 7.8501 | 88 |
| Momentum_60D_Pct | 28.3496 | 95 |
| Realized_Volatility_20D_Pct | 25.0296 | 44 |
| Volume_Ratio_20D | 1.2818 | 89 |
| ZScore_20D | 2.0188 | 86 |
| Beta_60D_SPY | 0.8044 | 61 |
| Stock_RS_20D_vs_SPY | 8.7577 | 88 |
| Quant_Score | 80.0000 | 98 |
| MA20 | 412.7300 | 92 |
| MA50 | 392.7600 | 93 |
| ATR_Pct | 2.5200 | 39 |
| KDJ_J | 92.0800 | 81 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 样本数：2（按日期倒序展示最近 2 笔）
- **历史同类交易汇总**：共 1 笔，胜率 100.0%，平均盈利 +$233.76，平均亏损 -$0.00，盈亏比 N/A

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-14（仅日期） | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-07（仅日期） | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |

---

## 6. `NXPI`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-20 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Other　Price：230.19

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.2113 | 68 |
| Momentum_20D_Pct | -0.9552 | 48 |
| Momentum_60D_Pct | -14.5038 | 16 |
| Realized_Volatility_20D_Pct | 32.1187 | 69 |
| Volume_Ratio_20D | 0.9409 | 61 |
| ZScore_20D | -0.6021 | 33 |
| Beta_60D_SPY | 1.7058 | 79 |
| Stock_RS_20D_vs_SPY | -0.0476 | 48 |
| Quant_Score | 80.0000 | 98 |
| MA20 | 233.8800 | 80 |
| MA50 | 229.9900 | 78 |
| ATR_Pct | 3.4700 | 73 |
| KDJ_J | 50.8200 | 37 |

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

## 7. `AMGN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Healthcare　Price：424.94

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.7650 | 65 |
| Momentum_20D_Pct | 8.0832 | 88 |
| Momentum_60D_Pct | 13.0039 | 85 |
| Realized_Volatility_20D_Pct | 29.7870 | 63 |
| Volume_Ratio_20D | 0.9482 | 62 |
| ZScore_20D | 1.0992 | 63 |
| Beta_60D_SPY | 0.5137 | 52 |
| Stock_RS_20D_vs_SPY | 8.9908 | 88 |
| Quant_Score | 79.0000 | 98 |
| MA20 | 414.9800 | 93 |
| MA50 | 415.2900 | 93 |
| ATR_Pct | 2.4900 | 37 |
| KDJ_J | 74.2400 | 59 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 8. `ABNB`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Other　Price：175.46

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 7.3150 | 97 |
| Momentum_20D_Pct | 5.1666 | 74 |
| Momentum_60D_Pct | 24.3515 | 94 |
| Realized_Volatility_20D_Pct | 40.8643 | 81 |
| Volume_Ratio_20D | 0.6277 | 6 |
| ZScore_20D | 2.1569 | 90 |
| Beta_60D_SPY | 0.9067 | 64 |
| Stock_RS_20D_vs_SPY | 6.0742 | 74 |
| Quant_Score | 78.0000 | 97 |
| MA20 | 162.5300 | 69 |
| MA50 | 172.7400 | 70 |
| ATR_Pct | 2.7800 | 55 |
| KDJ_J | 95.2500 | 84 |

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

## 9. `LLY`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Healthcare　Price：1240.34

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.8807 | 85 |
| Momentum_20D_Pct | 6.4770 | 81 |
| Momentum_60D_Pct | 3.7048 | 66 |
| Realized_Volatility_20D_Pct | 27.2137 | 51 |
| Volume_Ratio_20D | 0.8519 | 46 |
| ZScore_20D | 1.9929 | 85 |
| Beta_60D_SPY | -0.3693 | 7 |
| Stock_RS_20D_vs_SPY | 7.3846 | 81 |
| Quant_Score | 78.0000 | 97 |
| MA20 | 1182.5400 | 99 |
| MA50 | 1181.4400 | 99 |
| ATR_Pct | 2.8000 | 56 |
| KDJ_J | 91.0600 | 80 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 10. `ROST`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Other　Price：238.66

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 5.6766 | 91 |
| Momentum_20D_Pct | 3.2043 | 67 |
| Momentum_60D_Pct | -0.0963 | 58 |
| Realized_Volatility_20D_Pct | 17.6644 | 10 |
| Volume_Ratio_20D | 1.1078 | 79 |
| ZScore_20D | 1.6610 | 76 |
| Beta_60D_SPY | 0.2090 | 40 |
| Stock_RS_20D_vs_SPY | 4.1119 | 67 |
| Quant_Score | 78.0000 | 97 |
| MA20 | 231.0900 | 79 |
| MA50 | 232.9800 | 79 |
| ATR_Pct | 2.2400 | 27 |
| KDJ_J | 102.5800 | 94 |

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

## 11. `COP`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Energy　Price：145.24

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 5.5830 | 90 |
| Momentum_20D_Pct | 13.8869 | 98 |
| Momentum_60D_Pct | 20.7717 | 92 |
| Realized_Volatility_20D_Pct | 24.7024 | 42 |
| Volume_Ratio_20D | 0.7165 | 19 |
| ZScore_20D | 2.0438 | 87 |
| Beta_60D_SPY | -1.0343 | 1 |
| Stock_RS_20D_vs_SPY | 14.7945 | 98 |
| Quant_Score | 77.0000 | 95 |
| MA20 | 132.5300 | 61 |
| MA50 | 132.3200 | 60 |
| ATR_Pct | 2.1900 | 26 |
| KDJ_J | 100.8800 | 93 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Energy）
- N/A（无成交记录）

---

## 12. `AAPL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Technology　Price：342.94

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.5778 | 50 |
| Momentum_20D_Pct | 1.1682 | 57 |
| Momentum_60D_Pct | 2.9788 | 66 |
| Realized_Volatility_20D_Pct | 15.9864 | 3 |
| Volume_Ratio_20D | 0.9339 | 59 |
| ZScore_20D | 1.3172 | 67 |
| Beta_60D_SPY | -0.0274 | 21 |
| Stock_RS_20D_vs_SPY | 2.0758 | 57 |
| Quant_Score | 23.0000 | 5 |
| MA20 | 337.6200 | 88 |
| MA50 | 326.2900 | 87 |
| ATR_Pct | 1.9400 | 13 |
| KDJ_J | 73.2000 | 58 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 13. `MSFT`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Technology　Price：533.52

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -1.4100 | 30 |
| Momentum_20D_Pct | 6.3615 | 80 |
| Momentum_60D_Pct | 39.7747 | 97 |
| Realized_Volatility_20D_Pct | 21.9512 | 30 |
| Volume_Ratio_20D | 0.8058 | 36 |
| ZScore_20D | 0.9017 | 58 |
| Beta_60D_SPY | 2.1582 | 88 |
| Stock_RS_20D_vs_SPY | 7.2691 | 80 |
| Quant_Score | 25.0000 | 9 |
| MA20 | 521.8200 | 95 |
| MA50 | 506.2000 | 95 |
| ATR_Pct | 2.1900 | 26 |
| KDJ_J | 31.7700 | 28 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 14. `NVDA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Technology　Price：217.09

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -4.0783 | 22 |
| Momentum_20D_Pct | -4.5255 | 32 |
| Momentum_60D_Pct | 4.9555 | 69 |
| Realized_Volatility_20D_Pct | 23.6926 | 38 |
| Volume_Ratio_20D | 0.9382 | 60 |
| ZScore_20D | -1.7404 | 16 |
| Beta_60D_SPY | 1.9474 | 85 |
| Stock_RS_20D_vs_SPY | -3.6179 | 32 |
| Quant_Score | 30.0000 | 30 |
| MA20 | 227.6600 | 78 |
| MA50 | 222.9400 | 78 |
| ATR_Pct | 2.7300 | 51 |
| KDJ_J | 0.8200 | 12 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 15. `GOOGL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Communication　Price：344.18

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -2.4212 | 27 |
| Momentum_20D_Pct | -3.0397 | 40 |
| Momentum_60D_Pct | 7.6437 | 75 |
| Realized_Volatility_20D_Pct | 22.2082 | 31 |
| Volume_Ratio_20D | 0.7877 | 33 |
| ZScore_20D | -0.4341 | 36 |
| Beta_60D_SPY | 1.2013 | 69 |
| Stock_RS_20D_vs_SPY | -2.1321 | 40 |
| Quant_Score | 25.0000 | 9 |
| MA20 | 345.8700 | 89 |
| MA50 | 344.3800 | 88 |
| ATR_Pct | 2.5300 | 40 |
| KDJ_J | 9.6400 | 19 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 16. `META`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Communication　Price：705.44

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -5.0501 | 20 |
| Momentum_20D_Pct | -4.8310 | 30 |
| Momentum_60D_Pct | 18.5235 | 91 |
| Realized_Volatility_20D_Pct | 40.1504 | 80 |
| Volume_Ratio_20D | 0.7456 | 23 |
| ZScore_20D | -1.8655 | 13 |
| Beta_60D_SPY | 1.1224 | 67 |
| Stock_RS_20D_vs_SPY | -3.9235 | 30 |
| Quant_Score | 17.0000 | 0 |
| MA20 | 733.9800 | 97 |
| MA50 | 657.5100 | 97 |
| ATR_Pct | 3.4900 | 73 |
| KDJ_J | 8.9800 | 19 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 17. `TSLA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Consumer Discretionary　Price：368.06

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -2.6374 | 26 |
| Momentum_20D_Pct | -1.9291 | 43 |
| Momentum_60D_Pct | 17.5798 | 90 |
| Realized_Volatility_20D_Pct | 32.6205 | 70 |
| Volume_Ratio_20D | 1.1238 | 80 |
| ZScore_20D | -0.2195 | 40 |
| Beta_60D_SPY | 2.1679 | 88 |
| Stock_RS_20D_vs_SPY | -1.0216 | 43 |
| Quant_Score | 69.0000 | 86 |
| MA20 | 369.9700 | 90 |
| MA50 | 360.2500 | 89 |
| ATR_Pct | 3.2800 | 70 |
| KDJ_J | 23.3900 | 24 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 18. `AVGO`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Technology　Price：334.59

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -5.6776 | 19 |
| Momentum_20D_Pct | -7.7400 | 21 |
| Momentum_60D_Pct | -12.3927 | 21 |
| Realized_Volatility_20D_Pct | 36.6576 | 74 |
| Volume_Ratio_20D | 0.7792 | 30 |
| ZScore_20D | -1.9108 | 12 |
| Beta_60D_SPY | 2.0699 | 87 |
| Stock_RS_20D_vs_SPY | -6.8325 | 21 |
| Quant_Score | 23.0000 | 5 |
| MA20 | 353.9900 | 89 |
| MA50 | 363.8600 | 90 |
| ATR_Pct | 3.4600 | 73 |
| KDJ_J | -4.6400 | 8 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 19. `TSM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-20 无因子快照

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

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Other　Price：532.23

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.8265 | 73 |
| Momentum_20D_Pct | 6.0198 | 78 |
| Momentum_60D_Pct | 7.5364 | 75 |
| Realized_Volatility_20D_Pct | 8.5959 | 0 |
| Volume_Ratio_20D | 1.1347 | 81 |
| ZScore_20D | 2.2978 | 93 |
| Beta_60D_SPY | -0.1005 | 16 |
| Stock_RS_20D_vs_SPY | 6.9274 | 78 |
| Quant_Score | 76.0000 | 95 |
| MA20 | 511.2500 | 95 |
| MA50 | 508.7100 | 95 |
| ATR_Pct | 1.1100 | 0 |
| KDJ_J | 100.4900 | 93 |

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

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Financials　Price：333.53

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.2303 | 42 |
| Momentum_20D_Pct | -5.2579 | 28 |
| Momentum_60D_Pct | -5.5718 | 44 |
| Realized_Volatility_20D_Pct | 18.7897 | 15 |
| Volume_Ratio_20D | 0.8469 | 44 |
| ZScore_20D | -0.4043 | 37 |
| Beta_60D_SPY | 0.6139 | 55 |
| Stock_RS_20D_vs_SPY | -4.3504 | 28 |
| Quant_Score | 18.0000 | 1 |
| MA20 | 334.7300 | 88 |
| MA50 | 347.6400 | 89 |
| ATR_Pct | 1.9800 | 15 |
| KDJ_J | 58.8100 | 45 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 22. `V`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Financials　Price：402.92

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.5066 | 77 |
| Momentum_20D_Pct | 8.9120 | 91 |
| Momentum_60D_Pct | 13.2625 | 86 |
| Realized_Volatility_20D_Pct | 20.8443 | 26 |
| Volume_Ratio_20D | 0.9819 | 67 |
| ZScore_20D | 2.0060 | 86 |
| Beta_60D_SPY | 0.2360 | 41 |
| Stock_RS_20D_vs_SPY | 9.8196 | 91 |
| Quant_Score | 70.0000 | 88 |
| MA20 | 376.3700 | 90 |
| MA50 | 373.3100 | 91 |
| ATR_Pct | 1.7000 | 4 |
| KDJ_J | 100.0600 | 92 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 23. `UNH`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：Healthcare　Price：406.88

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 7.4923 | 98 |
| Momentum_20D_Pct | 7.7657 | 87 |
| Momentum_60D_Pct | -3.2942 | 49 |
| Realized_Volatility_20D_Pct | 26.4552 | 48 |
| Volume_Ratio_20D | 0.8424 | 43 |
| ZScore_20D | 2.6640 | 97 |
| Beta_60D_SPY | 0.1036 | 31 |
| Stock_RS_20D_vs_SPY | 8.6732 | 87 |
| Quant_Score | 70.0000 | 88 |
| MA20 | 380.0400 | 91 |
| MA50 | 387.2900 | 92 |
| ATR_Pct | 2.9200 | 62 |
| KDJ_J | 89.0000 | 77 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 24. `XOM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-20（该日共 286 只；全表 10 个日期 / 2792 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-20 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- **数据源缺少精确时间，仅有日期**（无 portfolio_50000_txn_time.csv 侧车）
- N/A（无成交记录）

---

说明：只读简报；缺失项统一 N/A。宏观环境在头部统一展示，不重复。
